from typing import ClassVar


class AppError(Exception):
    status_code: ClassVar[int] = 500
    code: ClassVar[str] = 'internal_error'


class DomainValidationError(AppError):
    status_code = 400
    code = 'invalid_domain'


class RDAPError(AppError):
    status_code = 502
    code = 'rdap_unavailable'


class TargetNotAllowedError(AppError):
    status_code = 400
    code = 'target_not_allowed'


class AnalysisNotFoundError(AppError):
    status_code = 404
    code = 'analysis_not_found'


class AnalysisConflictError(AppError):
    status_code = 409
    code = 'analysis_conflict'


class AnalysisQueueError(AppError):
    status_code = 503
    code = 'analysis_queue_unavailable'
