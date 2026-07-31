from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    TITLE: str = 'AI consultant'
    DEBUG: bool = Field(default=False, alias='DEV_MODE')
    DOCS: bool = Field(default=False, alias='DOCS')

    BOOTSTRAP_URL: str = 'https://data.iana.org/rdap/dns.json'
    DNS_SERVERS: list[str] = ['8.8.8.8', '1.1.1.1']
    PROPAGATION_SERVERS: list[dict[str, str]] = [
        {'name': 'Google', 'ip': '8.8.8.8'},
        {'name': 'Google Secondary', 'ip': '8.8.4.4'},
        {'name': 'Cloudflare', 'ip': '1.1.1.1'},
        {'name': 'Cloudflare Secondary', 'ip': '1.0.0.1'},
        {'name': 'Quad9', 'ip': '9.9.9.9'},
        {'name': 'OpenDNS', 'ip': '208.67.222.222'},
    ]

    @property
    def DOCS_URL(self) -> str | None:
        return '/api/docs' if self.DOCS else None

    @property
    def OPENAPI_URL(self) -> str | None:
        return '/api/docs.json' if self.DOCS else None

    @property
    def REDOC_URL(self) -> str | None:
        return '/api/redoc' if self.DOCS else None


@lru_cache
def get_config() -> Config:
    return Config()


config = get_config()
