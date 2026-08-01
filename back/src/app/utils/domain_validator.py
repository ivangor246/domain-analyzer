import re
from urllib.parse import urlparse

import idna

from app.core.config import settings

DOMAIN_REGEX = re.compile(r'^(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9]{1,59})$')


def normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain if '://' in domain else f'//{domain}'
    return urlparse(domain).hostname or ''


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
