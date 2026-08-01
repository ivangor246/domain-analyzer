from __future__ import annotations

from typing import ClassVar

import httpx

from app.core.config import settings
from app.utils.http import is_retryable_http_error, parse_json, read_limited_response, run_with_retries


class RDAPBootstrap:
    """
    Use a get_instance method to obtain a class instance:
        RDAPBootstrap.get_instance()
    """

    _instance: ClassVar[RDAPBootstrap] | None = None

    def __init__(self):
        self.data: dict[str, list[str]] = {}

    @classmethod
    async def get_instance(cls) -> RDAPBootstrap:
        if cls._instance is None:
            instance = cls()
            await instance.load()
            cls._instance = instance
        return cls._instance

    async def load(self):
        async with httpx.AsyncClient(timeout=settings.BOOTSTRAP_TIMEOUT_SECONDS) as client:

            async def fetch() -> object:
                async with client.stream('GET', settings.BOOTSTRAP_URL) as response:
                    response.raise_for_status()
                    content = await read_limited_response(response, settings.HTTP_MAX_RESPONSE_BYTES)
                return parse_json(content)

            json_data = await run_with_retries(
                fetch,
                retries=settings.RDAP_MAX_RETRIES,
                should_retry=is_retryable_http_error,
                backoff_seconds=settings.RETRY_BACKOFF_SECONDS,
            )

        mapping = {}
        for entry in json_data['services']:
            tlds, urls = entry
            for tld in tlds:
                mapping[tld.lower()] = urls

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
                return self.data[tld], rdap_domain
        raise ValueError(f'No RDAP server for domain: {domain}')
