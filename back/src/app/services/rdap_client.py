from datetime import datetime
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from app.core.exceptions import RDAPError

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
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
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
                    response = await client.get(url)
                    response.raise_for_status()
                    return RDAPClient._parse(server=server, data=response.json())
                except httpx.HTTPError:
                    continue

        raise RDAPError(f'All RDAP servers failed for domain: {domain}')

    @staticmethod
    def _parse(server: str, data: dict) -> RDAPResponse:
        events = {e['eventAction']: e['eventDate'] for e in data.get('events', [])}

        nameservers = [ns['ldhName'].lower() for ns in data.get('nameservers', []) if 'ldhName' in ns]

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
