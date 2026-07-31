from datetime import datetime

from pydantic import Field

from .base import BaseSchema


class SSLCertificate(BaseSchema):
    subject: str | None = Field(None, description='Subject Common Name (CN)')
    san: list[str] = Field(default_factory=list, description='Subject Alternative Names (DNS entries)')
    issuer: str | None = Field(None, description='Issuer Common Name (CN)')
    issuer_org: str | None = Field(None, description='Issuer organization name (O)')
    valid_from: datetime | None = Field(None, description='Certificate validity start date (notBefore)')
    valid_until: datetime | None = Field(None, description='Certificate validity end date (notAfter)')
    days_remaining: int | None = Field(None, description='Days until expiration (negative if already expired)')
    expired: bool = Field(False, description='True if the certificate has expired')
    serial_number: str | None = Field(None, description='Certificate serial number in hex')
    fingerprint_sha256: str | None = Field(None, description='SHA-256 fingerprint formatted as colon-separated hex')
    signature_algorithm: str | None = Field(None, description='Signature algorithm (e.g. sha256WithRSAEncryption)')
    version: int | None = Field(None, description='X.509 version number (typically 3)')


class SSLSchema(BaseSchema):
    valid: bool = Field(..., description='True if certificate is trusted, hostname matches, and not expired')
    error: str | None = Field(None, description='Error message when validation failed or connection was refused')
    protocol: str | None = Field(None, description='Negotiated TLS protocol version (e.g. TLSv1.3)')
    cipher: str | None = Field(None, description='Negotiated cipher suite name')
    certificate: SSLCertificate | None = Field(None, description='Parsed certificate details')
