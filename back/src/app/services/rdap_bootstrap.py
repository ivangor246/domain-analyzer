from __future__ import annotations

import asyncio
from typing import ClassVar

import httpx

from app.core.config import settings
from app.utils.http import (
    is_retryable_http_error,
    parse_json,
    read_limited_response,
    retry_after_seconds,
    run_with_retries,
)
from app.utils.circuit_breaker import CircuitBreaker


class RDAPBootstrap:
    """
    Use a get_instance method to obtain a class instance:
        RDAPBootstrap.get_instance()
    """

    _instance: ClassVar[RDAPBootstrap] | None = None
    _load_lock: ClassVar[asyncio.Lock | None] = None
    _breaker: ClassVar[CircuitBreaker] = CircuitBreaker()

    def __init__(self) -> None:
        self.data: dict[str, list[str]] = {}

    @classmethod
    async def get_instance(cls) -> RDAPBootstrap:
        if cls._instance is not None:
            return cls._instance

        if cls._load_lock is None:
            cls._load_lock = asyncio.Lock()

        async with cls._load_lock:
            if cls._instance is None:
                instance = cls()
                await instance.load()
                cls._instance = instance
        return cls._instance

    async def load(self) -> None:
        async with httpx.AsyncClient(timeout=settings.BOOTSTRAP_TIMEOUT_SECONDS, trust_env=False) as client:

            async def fetch() -> object:
                async with client.stream('GET', settings.BOOTSTRAP_URL) as response:
                    response.raise_for_status()
                    content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
                return parse_json(content)

            json_data = await self._breaker.call(
                f'rdap-bootstrap:{settings.BOOTSTRAP_URL}',
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

        if not isinstance(json_data, dict) or not isinstance(json_data.get('services'), list):
            raise ValueError('Invalid RDAP bootstrap response.')

        mapping: dict[str, list[str]] = {}
        for entry in json_data['services']:
            if not isinstance(entry, list) or len(entry) != 2:
                continue
            tlds, urls = entry
            if not isinstance(tlds, list) or not isinstance(urls, list):
                continue

            valid_urls = [url.strip() for url in urls if isinstance(url, str) and url.strip()]
            if not valid_urls:
                continue

            for tld in tlds:
                if isinstance(tld, str) and tld.strip():
                    mapping[tld.strip().lower().rstrip('.')] = valid_urls

        if not mapping:
            raise ValueError('RDAP bootstrap response contains no services.')

        self.data = mapping

    def get_servers(self, domain: str) -> tuple[list[str], str]:
        """Return (rdap_servers, registrable_domain).

        Tries suffixes from longest to shortest to correctly handle
        multi-label TLDs such as co.uk or com.br.
        """
        labels = domain.split('.')
        for n in range(1, len(labels)):
            tld = '.'.join(labels[n:]).lower()
            if tld in self.data:
                rdap_domain = '.'.join(labels[n - 1 :])
                return list(self.data[tld]), rdap_domain
        raise ValueError(f'No RDAP server for domain: {domain}')
