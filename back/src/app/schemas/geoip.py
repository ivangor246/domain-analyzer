from pydantic import Field

from .base import BaseSchema


class GeoIPRecord(BaseSchema):
    ip: str = Field(..., description='IP address')
    country: str | None = Field(None, description='Country name')
    country_code: str | None = Field(None, description='ISO 3166-1 alpha-2 country code')
    region: str | None = Field(None, description='Region / state name')
    city: str | None = Field(None, description='City name')
    zip: str | None = Field(None, description='Postal / ZIP code')
    lat: float | None = Field(None, description='Latitude')
    lon: float | None = Field(None, description='Longitude')
    timezone: str | None = Field(None, description='Timezone (e.g. Europe/Moscow)')
    isp: str | None = Field(None, description='Internet Service Provider name')
    org: str | None = Field(None, description='Organization name')
    asn: str | None = Field(None, description='Autonomous System Number (e.g. AS15169)')
    asn_name: str | None = Field(None, description='Autonomous System name (e.g. Google LLC)')
