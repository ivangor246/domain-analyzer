from __future__ import annotations

from typing import ClassVar

import httpx

from app.core.config import config


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
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(config.BOOTSTRAP_URL)
            response.raise_for_status()
            json_data = response.json()

        mapping = {}
        for entry in json_data['services']:
            tlds, urls = entry
            for tld in tlds:
                mapping[tld.lower()] = urls

        self.data = mapping

    def get_servers(self, domain: str) -> list[str]:
        tld = domain.split('.')[-1].lower()
        if tld not in self.data:
            raise ValueError(f'No RDAP server for TLD: {tld}')
        return self.data[tld]
