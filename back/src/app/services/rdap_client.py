import json
from datetime import datetime
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import RDAPError
from app.utils.http import is_retryable_http_error, parse_json, read_limited_response, run_with_retries

from .network_guard import NetworkTargetGuard


class RDAPResponse(BaseModel):
    server: str
    status: list[str] = []
    nameservers: list[str] = []
    registrar: str | None = None
    registration_date: datetime | None = None
    expiration_date: datetime | None = None
    updated_date: datetime | None = None
    whois_server: str | None = None


class RDAPClient:
    @staticmethod
    async def query(domain: str, servers: list[str]) -> RDAPResponse:
        async with httpx.AsyncClient(timeout=settings.RDAP_TIMEOUT_SECONDS, follow_redirects=False) as client:
            for server in servers:
                parsed_server = urlparse(server)
                if (
                    parsed_server.scheme not in {'http', 'https'}
                    or not parsed_server.hostname
                    or parsed_server.username
                    or parsed_server.password
                ):
                    continue
                try:
                    await NetworkTargetGuard.validate(parsed_server.hostname)
                except Exception:
                    continue

                url = f'{server.rstrip("/")}/domain/{domain}'
                try:

                    async def fetch() -> object:
                        async with client.stream('GET', url) as response:
                            response.raise_for_status()
                            content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
                        return parse_json(content)

                    data = await run_with_retries(
                        fetch,
                        retries=settings.RDAP_MAX_RETRIES,
                        should_retry=is_retryable_http_error,
                        backoff_seconds=settings.RETRY_BACKOFF_SECONDS,
                    )
                    if not isinstance(data, dict):
                        continue
                    return RDAPClient._parse(server=server, data=data)
                except httpx.HTTPError:
                    continue
                except (json.JSONDecodeError, ValueError):
                    continue

        raise RDAPError(f'All RDAP servers failed for domain: {domain}')

    @staticmethod
    def _parse(server: str, data: dict) -> RDAPResponse:
        events = {e['eventAction']: e['eventDate'] for e in data.get('events', [])}

        nameservers = [ns['ldhName'].lower() for ns in data.get('nameservers', []) if 'ldhName' in ns][
            : settings.MAX_RDAP_NAMESERVERS
        ]

        registrar = None
        for entity in data.get('entities', []):
            if 'registrar' in entity.get('roles', []):
                registrar = RDAPClient._extract_entity_name(entity)
                break

        return RDAPResponse(
            server=server,
            status=data.get('status', []),
            nameservers=nameservers,
            registrar=registrar,
            registration_date=events.get('registration'),
            expiration_date=events.get('expiration'),
            updated_date=events.get('last changed'),
            whois_server=data.get('port43'),
        )

    @staticmethod
    def _extract_entity_name(entity: dict) -> str | None:
        vcard = entity.get('vcardArray')
        if not vcard or len(vcard) < 2:
            return None
        for field in vcard[1]:
            if field[0] == 'fn':
                return field[3]
        return None
