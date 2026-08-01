import httpx

from app.core.config import settings
from app.schemas.geoip import GeoIPRecord
from app.utils.http import is_retryable_http_error, parse_json, read_limited_response, run_with_retries

_FIELDS = 'status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,query'


class GeoIPService:
    @staticmethod
    async def lookup(ips: list[str]) -> dict[str, GeoIPRecord]:
        if not ips:
            return {}

        payload = [{'query': ip, 'fields': _FIELDS} for ip in ips[: settings.MAX_GEOIP_IPS]]

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:

            async def fetch() -> object:
                async with client.stream('POST', settings.GEOIP_URL, json=payload) as response:
                    response.raise_for_status()
                    content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
                return parse_json(content)

            data = await run_with_retries(
                fetch,
                retries=settings.GEOIP_MAX_RETRIES,
                should_retry=is_retryable_http_error,
                backoff_seconds=settings.RETRY_BACKOFF_SECONDS,
            )
            if not isinstance(data, list):
                return {}

        result: dict[str, GeoIPRecord] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            if item.get('status') != 'success':
                continue

            ip: str = item.get('query', '')
            if not ip:
                continue

            # "as" field contains "AS15169 Google LLC" - split off the number
            asn_raw: str = item.get('as', '') or ''
            parts = asn_raw.split(' ', 1)
            asn_number = parts[0] if parts[0].startswith('AS') else None

            result[ip] = GeoIPRecord(
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

        return result
