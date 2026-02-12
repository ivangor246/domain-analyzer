from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    TITLE: str = 'AI consultant'
    DEBUG: bool = Field(default=False, alias='DEV_MODE')
    DOCS: bool = Field(default=False, alias='DOCS')

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
