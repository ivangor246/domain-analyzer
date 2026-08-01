import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.geoip import GeoIPRecord
from app.utils.http import (
    is_retryable_http_error,
    parse_json,
    read_limited_response,
    retry_after_seconds,
    run_with_retries,
)
from app.utils.circuit_breaker import CircuitBreaker
from app.utils.ttl_cache import AsyncTTLCache

_FIELDS = 'status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,query'
geoip_breaker = CircuitBreaker()
geoip_cache = AsyncTTLCache[tuple[str, str], GeoIPRecord](max_entries=settings.PROVIDER_CACHE_MAX_ENTRIES)


class GeoIPService:
    @staticmethod
    async def lookup(ips: list[str]) -> dict[str, GeoIPRecord]:
        if not ips:
            return {}

        requested_ips = list(dict.fromkeys(ips[: settings.MAX_GEOIP_IPS]))
        result: dict[str, GeoIPRecord] = {}
        cache_enabled = settings.PROVIDER_CACHE_ENABLED and settings.GEOIP_CACHE_TTL_SECONDS > 0
        missing_ips = await GeoIPService._load_cached(requested_ips, result, cache_enabled)

        if not missing_ips:
            return result

        data = await GeoIPService._fetch(missing_ips)
        parsed = GeoIPService._parse(data, set(requested_ips))
        result.update(parsed)
        if cache_enabled:
            for ip, record in parsed.items():
                await geoip_cache.set(
                    (settings.GEOIP_URL, ip),
                    record.model_copy(deep=True),
                    settings.GEOIP_CACHE_TTL_SECONDS,
                )

        return result

    @staticmethod
    async def _load_cached(
        ips: list[str],
        result: dict[str, GeoIPRecord],
        cache_enabled: bool,
    ) -> list[str]:
        missing_ips: list[str] = []
        for ip in ips:
            cached = await geoip_cache.get((settings.GEOIP_URL, ip)) if cache_enabled else None
            if cached is None:
                missing_ips.append(ip)
            else:
                result[ip] = cached.model_copy(deep=True)
        return missing_ips

    @staticmethod
    async def _fetch(ips: list[str]) -> object:
        payload = [{'query': ip, 'fields': _FIELDS} for ip in ips]
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS, trust_env=False) as client:

            async def fetch() -> object:
                async with client.stream('POST', settings.GEOIP_URL, json=payload) as response:
                    response.raise_for_status()
                    content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
                return parse_json(content)

            return await geoip_breaker.call(
                f'geoip:{settings.GEOIP_URL}',
                lambda: run_with_retries(
                    fetch,
                    retries=settings.GEOIP_MAX_RETRIES,
                    should_retry=is_retryable_http_error,
                    backoff_seconds=settings.RETRY_BACKOFF_SECONDS,
                    jitter_seconds=settings.RETRY_JITTER_SECONDS,
                    retry_after=retry_after_seconds,
                    max_delay_seconds=settings.RETRY_MAX_DELAY_SECONDS,
                ),
                should_trip=is_retryable_http_error,
            )

    @staticmethod
    def _parse(data: object, requested_ips: set[str]) -> dict[str, GeoIPRecord]:
        if not isinstance(data, list):
            return {}

        result: dict[str, GeoIPRecord] = {}
        for item in data:
            parsed = GeoIPService._parse_record(item, requested_ips)
            if parsed is not None:
                ip, record = parsed
                result[ip] = record
        return result

    @staticmethod
    def _parse_record(item: object, requested_ips: set[str]) -> tuple[str, GeoIPRecord] | None:
        if not isinstance(item, dict) or item.get('status') != 'success':
            return None

        ip = item.get('query')
        if not isinstance(ip, str) or ip not in requested_ips:
            return None

        # "as" field contains "AS15169 Google LLC" - split off the number
        asn_raw = item.get('as')
        parts = asn_raw.split(' ', 1) if isinstance(asn_raw, str) else []
        asn_number = parts[0] if parts and parts[0].startswith('AS') else None

        try:
            return ip, GeoIPRecord(
                ip=ip,
                country=item.get('country') or None,
                country_code=item.get('countryCode') or None,
                region=item.get('regionName') or None,
                city=item.get('city') or None,
                zip=item.get('zip') or None,
                lat=item.get('lat'),
                lon=item.get('lon'),
                timezone=item.get('timezone') or None,
                isp=item.get('isp') or None,
                org=item.get('org') or None,
                asn=asn_number,
                asn_name=item.get('asname') or None,
            )
        except ValidationError:
            return None
