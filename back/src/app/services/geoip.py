import httpx

from app.schemas.geoip import GeoIPRecord

_FIELDS = 'status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,query'


class GeoIPService:
    _API_URL = 'http://ip-api.com/batch'

    @staticmethod
    async def lookup(ips: list[str]) -> dict[str, GeoIPRecord]:
        if not ips:
            return {}

        payload = [{'query': ip, 'fields': _FIELDS} for ip in ips]

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(GeoIPService._API_URL, json=payload)
            response.raise_for_status()
            data: list[dict] = response.json()

        result: dict[str, GeoIPRecord] = {}
        for item in data:
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
