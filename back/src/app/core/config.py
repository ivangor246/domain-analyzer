from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=('.env', 'back/.env'),
        env_file_encoding='utf-8',
        extra='ignore',
    )

    TITLE: str = 'Domain Analyzer'
    DEV_MODE: bool = False
    DOCS: bool = False

    BOOTSTRAP_URL: str = 'https://data.iana.org/rdap/dns.json'
    DNS_SERVERS: list[str] = Field(default_factory=lambda: ['8.8.8.8', '1.1.1.1'])
    PROPAGATION_SERVERS: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {'name': 'Google', 'ip': '8.8.8.8'},
            {'name': 'Google Secondary', 'ip': '8.8.4.4'},
            {'name': 'Cloudflare', 'ip': '1.1.1.1'},
            {'name': 'Cloudflare Secondary', 'ip': '1.0.0.1'},
            {'name': 'Quad9', 'ip': '9.9.9.9'},
            {'name': 'OpenDNS', 'ip': '208.67.222.222'},
        ]
    )

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
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
