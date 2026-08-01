from datetime import datetime
from urllib.parse import ParseResult, urlparse, urlunparse

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import RDAPError
from app.utils.http import (
    is_retryable_http_error,
    parse_json,
    read_limited_response,
    retry_after_seconds,
    run_with_retries,
)
from app.utils.circuit_breaker import CircuitOpenError, CircuitBreaker
from app.utils.ttl_cache import AsyncTTLCache

from .network_guard import NetworkTargetGuard


class RDAPResponse(BaseModel):
    server: str
    status: list[str] = Field(default_factory=list)
    nameservers: list[str] = Field(default_factory=list)
    registrar: str | None = None
    registration_date: datetime | None = None
    expiration_date: datetime | None = None
    updated_date: datetime | None = None
    whois_server: str | None = None


rdap_breaker = CircuitBreaker()
rdap_cache = AsyncTTLCache[tuple[str, tuple[str, ...]], RDAPResponse](max_entries=settings.PROVIDER_CACHE_MAX_ENTRIES)


class RDAPClient:
    @staticmethod
    async def query(domain: str, servers: list[str]) -> RDAPResponse:
        cache_key = (domain.lower().rstrip('.'), tuple(server.strip() for server in servers))
        if settings.PROVIDER_CACHE_ENABLED and settings.RDAP_CACHE_TTL_SECONDS > 0:
            cached = await rdap_cache.get(cache_key)
            if cached is not None:
                return cached.model_copy(deep=True)

        async with httpx.AsyncClient(
            timeout=settings.RDAP_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for server in servers:
                result = await RDAPClient._query_server(client, domain, server)
                if result is None:
                    continue
                if settings.PROVIDER_CACHE_ENABLED and settings.RDAP_CACHE_TTL_SECONDS > 0:
                    await rdap_cache.set(cache_key, result.model_copy(deep=True), settings.RDAP_CACHE_TTL_SECONDS)
                return result

        raise RDAPError(f'All RDAP servers failed for domain: {domain}')

    @staticmethod
    def _fixed_server_url(
        parsed_server: ParseResult,
        domain: str,
        target_ip: str,
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        hostname = parsed_server.hostname
        if not hostname:
            raise ValueError('RDAP server hostname is missing.')

        target_host = f'[{target_ip}]' if ':' in target_ip else target_ip
        port = f':{parsed_server.port}' if parsed_server.port is not None else ''
        request_url = urlunparse(
            (
                parsed_server.scheme,
                f'{target_host}{port}',
                f'{parsed_server.path.rstrip("/")}/domain/{domain}',
                '',
                '',
                '',
            )
        )
        host = f'[{hostname}]' if ':' in hostname else hostname
        return request_url, {'Host': f'{host}{port}'}, {'sni_hostname': hostname}

    @staticmethod
    async def _query_server(client: httpx.AsyncClient, domain: str, server: str) -> RDAPResponse | None:
        try:
            parsed_server = urlparse(server.strip())
            parsed_server.port
        except ValueError:
            return None
        if (
            parsed_server.scheme not in {'http', 'https'}
            or not parsed_server.hostname
            or parsed_server.username
            or parsed_server.password
            or parsed_server.params
            or parsed_server.query
            or parsed_server.fragment
        ):
            return None
        try:
            target_ip = (await NetworkTargetGuard.resolve_public_ips(parsed_server.hostname))[0]
        except Exception:
            return None

        try:
            url, headers, extensions = RDAPClient._fixed_server_url(parsed_server, domain, target_ip)
        except ValueError:
            return None
        provider_key = f'rdap:{parsed_server.geturl().rstrip("/")}'
        try:

            async def fetch() -> object:
                async with client.stream('GET', url, headers=headers, extensions=extensions) as response:
                    response.raise_for_status()
                    content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
                return parse_json(content)

            data = await rdap_breaker.call(
                provider_key,
                lambda: run_with_retries(
                    fetch,
                    retries=settings.RDAP_MAX_RETRIES,
                    should_retry=is_retryable_http_error,
                    backoff_seconds=settings.RETRY_BACKOFF_SECONDS,
                    jitter_seconds=settings.RETRY_JITTER_SECONDS,
                    retry_after=retry_after_seconds,
                    max_delay_seconds=settings.RETRY_MAX_DELAY_SECONDS,
                ),
                should_trip=is_retryable_http_error,
            )
            if not isinstance(data, dict):
                return None
            return RDAPClient._parse(server=server, data=data)
        except (CircuitOpenError, httpx.HTTPError, ValueError):
            return None

    @staticmethod
    def _parse(server: str, data: dict) -> RDAPResponse:
        events: dict[str, datetime] = {}
        events_data = data.get('events', [])
        if not isinstance(events_data, list):
            events_data = []
        for event in events_data:
            if not isinstance(event, dict):
                continue
            action = event.get('eventAction')
            event_date = RDAPClient._parse_datetime(event.get('eventDate'))
            if isinstance(action, str) and event_date is not None:
                events[action] = event_date

        nameservers_data = data.get('nameservers', [])
        if not isinstance(nameservers_data, list):
            nameservers_data = []
        nameservers = [
            ns['ldhName'].lower()
            for ns in nameservers_data
            if isinstance(ns, dict) and isinstance(ns.get('ldhName'), str)
        ][: settings.MAX_RDAP_NAMESERVERS]

        entities_data = data.get('entities', [])
        if not isinstance(entities_data, list):
            entities_data = []
        registrar = None
        for entity in entities_data:
            roles = entity.get('roles', []) if isinstance(entity, dict) else []
            if isinstance(entity, dict) and isinstance(roles, list) and 'registrar' in roles:
                registrar = RDAPClient._extract_entity_name(entity)
                break

        status_data = data.get('status', [])
        if not isinstance(status_data, list):
            status_data = []
        status = [value for value in status_data if isinstance(value, str)]
        whois_server = data.get('port43')

        return RDAPResponse(
            server=server,
            status=status,
            nameservers=nameservers,
            registrar=registrar,
            registration_date=events.get('registration'),
            expiration_date=events.get('expiration'),
            updated_date=events.get('last changed'),
            whois_server=whois_server if isinstance(whois_server, str) else None,
        )

    @staticmethod
    def _extract_entity_name(entity: dict) -> str | None:
        vcard = entity.get('vcardArray')
        if not isinstance(vcard, list) or len(vcard) < 2 or not isinstance(vcard[1], list):
            return None
        for field in vcard[1]:
            if isinstance(field, list) and len(field) >= 4 and field[0] == 'fn' and isinstance(field[3], str):
                return field[3]
        return None

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
