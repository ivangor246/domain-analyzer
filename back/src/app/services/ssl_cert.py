import asyncio
import ssl
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes

from app.core.config import settings
from app.schemas.ssl import SSLCertificate, SSLSchema

from .network_guard import NetworkTargetGuard

_PORT = 443


class SSLCertService:
    @staticmethod
    async def check(domain: str) -> SSLSchema:
        target_ip = (await NetworkTargetGuard.resolve_public_ips(domain))[0]

        # Verify certificate with default context (trusted CA + hostname check)
        valid, error = await SSLCertService._check_validity(domain, target_ip)

        # Get raw certificate and TLS negotiation info without verification
        try:
            cert_bin, protocol, cipher = await SSLCertService._get_raw_cert(domain, target_ip)
        except Exception as e:
            return SSLSchema(valid=valid, error=error or str(e))

        # Parse certificate fields
        try:
            certificate = SSLCertService._parse_cert(cert_bin)
        except Exception:
            certificate = None

        return SSLSchema(
            valid=valid,
            error=error if not valid else None,
            protocol=protocol,
            cipher=cipher,
            certificate=certificate,
        )

    @staticmethod
    async def _check_validity(domain: str, target_ip: str | None = None) -> tuple[bool, str | None]:
        ctx = ssl.create_default_context()
        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target_ip or domain, _PORT, ssl=ctx, server_hostname=domain),
                timeout=settings.TLS_TIMEOUT_SECONDS,
            )
            return True, None
        except ssl.SSLCertVerificationError as e:
            return False, e.verify_message
        except ssl.SSLError as e:
            return False, str(e)
        except (TimeoutError, asyncio.TimeoutError):
            return False, 'Connection timed out'
        except OSError as e:
            return False, str(e)
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

    @staticmethod
    async def _get_raw_cert(domain: str, target_ip: str | None = None) -> tuple[bytes, str | None, str | None]:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        _, writer = await asyncio.wait_for(
            asyncio.open_connection(target_ip or domain, _PORT, ssl=ctx, server_hostname=domain),
            timeout=settings.TLS_TIMEOUT_SECONDS,
        )
        try:
            ssl_obj: ssl.SSLObject = writer.get_extra_info('ssl_object')
            cert_bin: bytes = ssl_obj.getpeercert(binary_form=True)
            protocol: str | None = ssl_obj.version()
            cipher_info: tuple | None = ssl_obj.cipher()
            cipher_name: str | None = cipher_info[0] if cipher_info else None
            return cert_bin, protocol, cipher_name
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    @staticmethod
    def _parse_cert(cert_bin: bytes) -> SSLCertificate:
        cert = x509.load_der_x509_certificate(cert_bin)
        now = datetime.now(timezone.utc)

        # Subject CN
        try:
            subject = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
        except (IndexError, Exception):
            subject = None

        # Subject Alternative Names
        try:
            san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            san = san_ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            san = []

        # Issuer CN and org
        try:
            issuer = cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
        except (IndexError, Exception):
            issuer = None

        try:
            issuer_org = cert.issuer.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)[0].value
        except (IndexError, Exception):
            issuer_org = None

        # Validity dates
        valid_from = cert.not_valid_before_utc
        valid_until = cert.not_valid_after_utc
        expired = now > valid_until
        days_remaining = (valid_until - now).days

        # Serial number as uppercase hex
        serial_number = format(cert.serial_number, 'X')

        # SHA-256 fingerprint as colon-separated hex pairs
        raw_fp = cert.fingerprint(hashes.SHA256()).hex().upper()
        fingerprint_sha256 = ':'.join(raw_fp[i : i + 2] for i in range(0, len(raw_fp), 2))

        # Signature algorithm: prefer OID name, fall back to hash algo name
        try:
            sig_alg: str | None = cert.signature_algorithm_oid._name or cert.signature_algorithm_oid.dotted_string
        except Exception:
            try:
                sig_alg = cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else None
            except Exception:
                sig_alg = None

        return SSLCertificate(
            subject=subject,
            san=list(san),
            issuer=issuer,
            issuer_org=issuer_org,
            valid_from=valid_from,
            valid_until=valid_until,
            days_remaining=days_remaining,
            expired=expired,
            serial_number=serial_number,
            fingerprint_sha256=fingerprint_sha256,
            signature_algorithm=sig_alg,
            version=cert.version.value + 1,
        )
