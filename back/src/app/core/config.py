from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
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
    BOOTSTRAP_TIMEOUT_SECONDS: float = Field(default=10, gt=0)
    RDAP_TIMEOUT_SECONDS: float = Field(default=10, gt=0)
    DNS_TIMEOUT_SECONDS: float = Field(default=5, gt=0)
    NETWORK_TIMEOUT_SECONDS: float = Field(default=5, gt=0)
    HTTP_TIMEOUT_SECONDS: float = Field(default=10, gt=0)
    TLS_TIMEOUT_SECONDS: float = Field(default=10, gt=0)
    PORT_TIMEOUT_SECONDS: float = Field(default=3, gt=0)
    LATENCY_TIMEOUT_SECONDS: float = Field(default=5, gt=0)
    LATENCY_PROBES: int = Field(default=3, gt=0)
    HTTP_MAX_REDIRECTS: int = Field(default=5, ge=0)
    HTTP_MAX_RESPONSE_BYTES: int = Field(default=65536, gt=0)
    MAX_DOMAIN_LENGTH: int = Field(default=253, gt=0)
    MAX_DNS_RECORDS: int = Field(default=100, gt=0)
    MAX_GEOIP_IPS: int = Field(default=100, gt=0)
    MAX_RDAP_NAMESERVERS: int = Field(default=100, gt=0)
    RDAP_MAX_RETRIES: int = Field(default=1, ge=0)
    GEOIP_MAX_RETRIES: int = Field(default=1, ge=0)
    HTTP_MAX_RETRIES: int = Field(default=1, ge=0)
    RETRY_BACKOFF_SECONDS: float = Field(default=0.1, ge=0)
    RETRY_JITTER_SECONDS: float = Field(default=0.1, ge=0)
    RETRY_MAX_DELAY_SECONDS: float = Field(default=30, gt=0)
    GEOIP_URL: str = 'http://ip-api.com/batch'
    HTTP_USER_AGENT: str = 'Mozilla/5.0 (compatible; DomainAnalyzer/1.0)'
    REDIS_URL: str = 'redis://redis:6379/0'
    REDIS_TIMEOUT_SECONDS: float = Field(default=5, gt=0)
    ANALYSIS_TIMEOUT_SECONDS: float = Field(default=120, gt=0)
    CELERY_TASK_TIME_LIMIT_SECONDS: int = Field(default=900, gt=0)
    CELERY_TASK_SOFT_TIME_LIMIT_SECONDS: int = Field(default=840, gt=0)
    CELERY_RESULT_EXPIRES_SECONDS: int = Field(default=3600, gt=0)
    CELERY_WORKER_CONCURRENCY: int = Field(default=2, gt=0)
    ANALYSIS_JOB_TTL_SECONDS: int = Field(default=3600, gt=0)
    ANALYSIS_MAX_CONCURRENCY: int = Field(default=2, gt=0)
    ANALYSIS_CONCURRENCY_LEASE_SECONDS: float = Field(default=180, gt=0)
    ANALYSIS_CONCURRENCY_RETRY_SECONDS: int = Field(default=5, gt=0)
    ANALYSIS_CONCURRENCY_MAX_RETRIES: int = Field(default=30, ge=0)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REDIS_ENABLED: bool = True
    RATE_LIMIT_REDIS_FALLBACK_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = Field(default=30, gt=0)
    RATE_LIMIT_WINDOW_SECONDS: float = Field(default=60, gt=0)
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ['http://localhost:5173'])
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

    @model_validator(mode='after')
    def validate_celery_time_limits(self) -> Self:
        if self.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS >= self.CELERY_TASK_TIME_LIMIT_SECONDS:
            raise ValueError('CELERY_TASK_SOFT_TIME_LIMIT_SECONDS must be less than CELERY_TASK_TIME_LIMIT_SECONDS')
        if self.ANALYSIS_TIMEOUT_SECONDS >= self.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS:
            raise ValueError('ANALYSIS_TIMEOUT_SECONDS must be less than CELERY_TASK_SOFT_TIME_LIMIT_SECONDS')
        if self.ANALYSIS_CONCURRENCY_LEASE_SECONDS <= self.ANALYSIS_TIMEOUT_SECONDS:
            raise ValueError('ANALYSIS_CONCURRENCY_LEASE_SECONDS must be greater than ANALYSIS_TIMEOUT_SECONDS')
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
