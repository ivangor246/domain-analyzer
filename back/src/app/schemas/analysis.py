from datetime import datetime
from enum import Enum

from pydantic import Field

from app.core.config import settings

from .base import BaseSchema
from .domain import DomainSchema
from .error import ErrorSchema


class AnalysisStatus(str, Enum):
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class AnalysisCreateSchema(BaseSchema):
    domain: str = Field(..., min_length=1, max_length=settings.MAX_DOMAIN_LENGTH)


class AnalysisJobSchema(BaseSchema):
    id: str = Field(..., description='Analysis identifier')
    domain: str = Field(..., description='Normalized domain in punycode')
    status: AnalysisStatus = Field(..., description='Current analysis state')
    created_at: datetime = Field(..., description='Time when the analysis was queued')
    result: DomainSchema | None = Field(None, description='Completed domain analysis result')
    error: ErrorSchema | None = Field(None, description='Terminal analysis error')
