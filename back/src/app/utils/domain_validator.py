import re
from urllib.parse import urlparse

import idna

from app.core.config import settings

DOMAIN_REGEX = re.compile(r'^(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9]{1,59})$')


def normalize_domain(domain: str) -> str:
    value = domain.strip()
    if not value:
        return ''

    has_scheme = '://' in value
    candidate = value if has_scheme or value.startswith('//') else f'//{value}'

    try:
        parsed = urlparse(candidate)
        port = parsed.port
    except ValueError:
        return ''

    if has_scheme and parsed.scheme.lower() not in {'http', 'https'}:
        return ''
    if parsed.username or parsed.password or port is not None:
        return ''
    if parsed.path not in {'', '/'} or parsed.params or parsed.query or parsed.fragment:
        return ''

    hostname = parsed.hostname
    if not hostname:
        return ''
    if hostname.endswith('.'):
        hostname = hostname[:-1]
    return hostname.lower()


def domain_to_punycode(domain: str) -> str:
    try:
        return idna.encode(domain).decode()
    except idna.IDNAError:
        raise ValueError('Invalid IDN domain')


def validate_domain(domain: str) -> str:
    domain = normalize_domain(domain)
    domain = domain_to_punycode(domain)

    if len(domain) > settings.MAX_DOMAIN_LENGTH or not DOMAIN_REGEX.fullmatch(domain):
        raise ValueError('Invalid domain format')

    return domain
