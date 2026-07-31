from typing import Literal

from .base import BaseSchema


class HealthSchema(BaseSchema):
    status: Literal['ok'] = 'ok'
