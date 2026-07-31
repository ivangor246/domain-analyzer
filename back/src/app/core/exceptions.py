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
