from typing import Any

from pydantic import Field

from .base import BaseSchema


class ErrorSchema(BaseSchema):
    code: str = Field(..., description='Stable machine-readable error code')
    message: str = Field(..., description='Human-readable error message')
    details: list[dict[str, Any]] | None = Field(None, description='Optional validation details')
