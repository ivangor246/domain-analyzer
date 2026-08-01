import asyncio
import time
from urllib.parse import urljoin, urlparse

import httpx

from app.core.exceptions import TargetNotAllowedError
from app.schemas.http import HTTPProbeResult, HTTPSchema

from .network_guard import NetworkTargetGuard

_TIMEOUT = 10
_MAX_REDIRECTS = 5
_USER_AGENT = 'Mozilla/5.0 (compatible; DomainAnalyzer/1.0)'


def _safe_redirect_url(current_url: str, location: str) -> str:
    next_url = urljoin(current_url, location)
    parsed = urlparse(next_url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise TargetNotAllowedError('Redirect target is not allowed.')
    return next_url


async def _request(client: httpx.AsyncClient, url: str) -> httpx.Response:
    response = await client.head(url)
    if response.status_code == 405:
        response = await client.get(url)
    return response


async def _request_with_safe_redirects(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[httpx.Response, list[str]]:
    current_url = url
    redirect_chain: list[str] = []

    for _ in range(_MAX_REDIRECTS + 1):
        response = await _request(client, current_url)
        if not response.is_redirect:
            return response, redirect_chain

        location = response.headers.get('location')
        if not location:
            return response, redirect_chain

        next_url = _safe_redirect_url(current_url, location)
        await NetworkTargetGuard.validate(urlparse(next_url).hostname or '')
        redirect_chain.append(str(response.url))
        current_url = next_url

    return response, redirect_chain


class HTTPHeadersService:
    @staticmethod
    async def probe(domain: str) -> HTTPSchema:
        http_result, https_result = await asyncio.gather(
            HTTPHeadersService._probe_url(f'http://{domain}'),
            HTTPHeadersService._probe_url(f'https://{domain}'),
        )
        return HTTPSchema(http=http_result, https=https_result)

    @staticmethod
    async def _probe_url(url: str) -> HTTPProbeResult:
        start = time.perf_counter()
        try:
            parsed_url = urlparse(url)
            if not parsed_url.hostname:
                return HTTPProbeResult(reachable=False)
            await NetworkTargetGuard.validate(parsed_url.hostname)

            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=False,
                verify=False,
                headers={'User-Agent': _USER_AGENT},
            ) as client:
                response, redirect_chain = await _request_with_safe_redirects(client, url)
        except Exception:
            return HTTPProbeResult(reachable=False)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        def h(name: str) -> str | None:
            return response.headers.get(name) or None

        final_url = str(response.url)

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
