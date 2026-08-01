import asyncio
import time
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.core.config import settings
from app.core.exceptions import TargetNotAllowedError
from app.schemas.http import HTTPProbeResult, HTTPSchema
from app.utils.http import read_limited_response, retry_after_seconds, run_with_retries

from .network_guard import NetworkTargetGuard


def _safe_redirect_url(current_url: str, location: str) -> str:
    next_url = urljoin(current_url, location)
    parsed = urlparse(next_url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise TargetNotAllowedError('Redirect target is not allowed.')
    return next_url


async def _request(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await _request_to_target(client, url, None)


def _fixed_target_url(url: str, target_ip: str | None) -> tuple[str, dict[str, str], dict[str, str]]:
    parsed = urlparse(url)
    if not target_ip or not parsed.hostname or target_ip == parsed.hostname:
        return url, {}, {}

    target_host = f'[{target_ip}]' if ':' in target_ip else target_ip
    port = f':{parsed.port}' if parsed.port is not None else ''
    request_url = urlunparse(
        (
            parsed.scheme,
            f'{target_host}{port}',
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    host_header = f'{parsed.hostname}{port}'
    return request_url, {'Host': host_header}, {'sni_hostname': parsed.hostname}


async def _request_to_target(
    client: httpx.AsyncClient,
    url: str,
    target_ip: str | None,
) -> httpx.Response:
    request_url, headers, extensions = _fixed_target_url(url, target_ip)

    def with_original_url(response: httpx.Response, content: bytes) -> httpx.Response:
        result = httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=content,
            request=response.request,
        )
        result.extensions['domain_analyzer_original_url'] = url
        return result

    async def request_once() -> httpx.Response:
        async with client.stream('HEAD', request_url, headers=headers, extensions=extensions) as response:
            content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
            if response.status_code != 405:
                return with_original_url(response, content)

        async with client.stream('GET', request_url, headers=headers, extensions=extensions) as response:
            content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
            return with_original_url(response, content)

    return await run_with_retries(
        request_once,
        retries=settings.HTTP_MAX_RETRIES,
        should_retry=lambda exc: isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)),
        backoff_seconds=settings.RETRY_BACKOFF_SECONDS,
        jitter_seconds=settings.RETRY_JITTER_SECONDS,
        retry_after=retry_after_seconds,
        max_delay_seconds=settings.RETRY_MAX_DELAY_SECONDS,
    )


async def _request_with_safe_redirects(
    client: httpx.AsyncClient,
    url: str,
    target_ip: str | None = None,
) -> tuple[httpx.Response, list[str]]:
    current_url = url
    current_ip = target_ip or urlparse(url).hostname
    redirect_chain: list[str] = []

    for redirect_count in range(settings.HTTP_MAX_REDIRECTS + 1):
        response = await _request_to_target(client, current_url, current_ip)
        if not response.is_redirect:
            return response, redirect_chain

        location = response.headers.get('location')
        if not location or redirect_count >= settings.HTTP_MAX_REDIRECTS:
            return response, redirect_chain

        next_url = _safe_redirect_url(current_url, location)
        next_host = urlparse(next_url).hostname or ''
        if target_ip is None:
            await NetworkTargetGuard.validate(next_host)
            current_ip = next_host
        else:
            current_ip = (await NetworkTargetGuard.resolve_public_ips(next_host))[0]
        redirect_chain.append(current_url)
        current_url = next_url

    return response, redirect_chain


class HTTPHeadersService:
    @staticmethod
    async def probe(domain: str, target_ips: list[str] | None = None) -> HTTPSchema:
        if target_ips is None:
            target_ips = await NetworkTargetGuard.resolve_public_ips(domain)
        target_ip = target_ips[0] if target_ips else None
        http_result, https_result = await asyncio.gather(
            HTTPHeadersService._probe_url(f'http://{domain}', target_ip=target_ip),
            HTTPHeadersService._probe_url(f'https://{domain}', target_ip=target_ip),
        )
        return HTTPSchema(http=http_result, https=https_result)

    @staticmethod
    async def _probe_url(url: str, target_ip: str | None = None) -> HTTPProbeResult:
        start = time.perf_counter()
        try:
            parsed_url = urlparse(url)
            if not parsed_url.hostname:
                return HTTPProbeResult(reachable=False)
            if target_ip is None:
                await NetworkTargetGuard.validate(parsed_url.hostname)

            async with httpx.AsyncClient(
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                follow_redirects=False,
                verify=False,
                trust_env=False,
                headers={'User-Agent': settings.HTTP_USER_AGENT},
            ) as client:
                response, redirect_chain = await _request_with_safe_redirects(client, url, target_ip=target_ip)
        except Exception:
            return HTTPProbeResult(reachable=False)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        def h(name: str) -> str | None:
            return response.headers.get(name) or None

        final_url = str(response.extensions.get('domain_analyzer_original_url', response.url))

        return HTTPProbeResult(
            reachable=True,
            status_code=response.status_code,
            final_url=final_url if redirect_chain else None,
            redirect_chain=redirect_chain,
            response_time_ms=elapsed_ms,
            server=h('server'),
            x_powered_by=h('x-powered-by'),
            via=h('via'),
            content_type=h('content-type'),
            cache_control=h('cache-control'),
            content_security_policy=h('content-security-policy'),
            strict_transport_security=h('strict-transport-security'),
            x_frame_options=h('x-frame-options'),
            x_content_type_options=h('x-content-type-options'),
            referrer_policy=h('referrer-policy'),
            permissions_policy=h('permissions-policy'),
        )
