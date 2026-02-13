import re
from urllib.parse import urlparse

import idna

DOMAIN_REGEX = re.compile(
    r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.'
    r'(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9]{1,59})$'
)


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

    if not DOMAIN_REGEX.match(domain):
        raise ValueError('Invalid domain format')

    return domain
