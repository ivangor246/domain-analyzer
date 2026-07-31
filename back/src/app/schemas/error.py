from typing import Any

from .base import BaseSchema


class ErrorSchema(BaseSchema):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None
