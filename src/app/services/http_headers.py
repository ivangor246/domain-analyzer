import asyncio
import time

import httpx

from app.schemas.http import HTTPProbeResult, HTTPSchema

_TIMEOUT = 10
_USER_AGENT = 'Mozilla/5.0 (compatible; DomainAnalyzer/1.0)'


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
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=True,
                verify=False,
                headers={'User-Agent': _USER_AGENT},
            ) as client:
                response = await client.head(url)

                if response.status_code == 405:
                    response = await client.get(url)
        except Exception:
            return HTTPProbeResult(reachable=False)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        def h(name: str) -> str | None:
            return response.headers.get(name) or None

        redirect_chain = [str(r.url) for r in response.history]
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
