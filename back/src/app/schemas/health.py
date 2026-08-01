from typing import Literal

from .base import BaseSchema


class HealthSchema(BaseSchema):
    status: Literal['ok'] = 'ok'


class ReadinessSchema(BaseSchema):
    status: Literal['ready', 'not_ready']
    checks: dict[str, Literal['ok', 'unavailable']]
