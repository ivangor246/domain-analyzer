import asyncio
from typing import Any

import dns.asyncresolver
import dns.reversename
from pydantic import BaseModel, Field

from app.core.config import settings


class DNSRecords(BaseModel):
    A: list[str] = Field(default_factory=list)
    AAAA: list[str] = Field(default_factory=list)
    MX: list[dict[str, Any]] = Field(default_factory=list)
    TXT: list[str] = Field(default_factory=list)
    CNAME: list[str] = Field(default_factory=list)
    NS: list[str] = Field(default_factory=list)
    SOA: dict[str, Any] | None = None
    CAA: list[dict[str, Any]] = Field(default_factory=list)
    PTR: dict[str, str | None] = Field(default_factory=dict)


class DNSResolver:
    RECORD_TYPES = ('A', 'AAAA', 'MX', 'TXT', 'CNAME', 'NS', 'SOA', 'CAA')

    @staticmethod
    async def resolve(domain: str) -> DNSRecords:
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = settings.DNS_TIMEOUT_SECONDS
        resolver.nameservers = settings.DNS_SERVERS

        tasks = {rtype: DNSResolver._query(resolver, domain, rtype) for rtype in DNSResolver.RECORD_TYPES}

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        raw = dict(zip(tasks.keys(), results))

        a_records = DNSResolver._parse_a(raw['A'])
        aaaa_records = DNSResolver._parse_a(raw['AAAA'])

        ptr_records = await DNSResolver._resolve_ptr(resolver, (a_records + aaaa_records)[: settings.MAX_DNS_RECORDS])

        return DNSRecords(
            A=a_records,
            AAAA=aaaa_records,
            MX=DNSResolver._parse_mx(raw['MX']),
            TXT=DNSResolver._parse_txt(raw['TXT']),
            CNAME=DNSResolver._parse_cname(raw['CNAME']),
            NS=DNSResolver._parse_ns(raw['NS']),
            SOA=DNSResolver._parse_soa(raw['SOA']),
            CAA=DNSResolver._parse_caa(raw['CAA']),
            PTR=ptr_records,
        )

    @staticmethod
    async def _query(resolver: dns.asyncresolver.Resolver, domain: str, rdtype: str) -> dns.resolver.Answer | None:
        try:
            return await resolver.resolve(domain, rdtype)
        except dns.exception.DNSException:
            return None

    @staticmethod
    async def _resolve_ptr(resolver: dns.asyncresolver.Resolver, ips: list[str]) -> dict[str, str | None]:
        async def _query_ptr(ip: str) -> tuple[str, str | None]:
            try:
                rev_name = dns.reversename.from_address(ip)
                answer = await resolver.resolve(rev_name, 'PTR')
                for rdata in answer:
                    return ip, str(rdata.target).rstrip('.')
            except (dns.exception.DNSException, ValueError):
                pass
            return ip, None

        results = await asyncio.gather(*[_query_ptr(ip) for ip in ips])
        return dict(results)

    @staticmethod
    def _parse_a(answer: dns.resolver.Answer | None | BaseException) -> list[str]:
        if not isinstance(answer, dns.resolver.Answer):
            return []
        return [rdata.address for rdata in answer][: settings.MAX_DNS_RECORDS]

    @staticmethod
    def _parse_mx(answer: dns.resolver.Answer | None | BaseException) -> list[dict[str, Any]]:
        if not isinstance(answer, dns.resolver.Answer):
            return []
        records = sorted(
            [{'priority': rdata.preference, 'exchange': str(rdata.exchange).rstrip('.')} for rdata in answer],
            key=lambda r: r['priority'],
        )
        return records[: settings.MAX_DNS_RECORDS]

    @staticmethod
    def _parse_txt(answer: dns.resolver.Answer | None | BaseException) -> list[str]:
        if not isinstance(answer, dns.resolver.Answer):
            return []
        return [b''.join(rdata.strings).decode('utf-8', errors='replace') for rdata in answer][
            : settings.MAX_DNS_RECORDS
        ]

    @staticmethod
    def _parse_cname(answer: dns.resolver.Answer | None | BaseException) -> list[str]:
        if not isinstance(answer, dns.resolver.Answer):
            return []
        return [str(rdata.target).rstrip('.') for rdata in answer][: settings.MAX_DNS_RECORDS]

    @staticmethod
    def _parse_ns(answer: dns.resolver.Answer | None | BaseException) -> list[str]:
        if not isinstance(answer, dns.resolver.Answer):
            return []
        return sorted(str(rdata.target).rstrip('.').lower() for rdata in answer)[: settings.MAX_DNS_RECORDS]

    @staticmethod
    def _parse_soa(answer: dns.resolver.Answer | None | BaseException) -> dict[str, Any] | None:
        if not isinstance(answer, dns.resolver.Answer):
            return None
        for rdata in answer:
            return {
                'mname': str(rdata.mname).rstrip('.'),
                'rname': str(rdata.rname).rstrip('.'),
                'serial': rdata.serial,
                'refresh': rdata.refresh,
                'retry': rdata.retry,
                'expire': rdata.expire,
                'minimum': rdata.minimum,
            }
        return None

    @staticmethod
    def _parse_caa(answer: dns.resolver.Answer | None | BaseException) -> list[dict[str, Any]]:
        if not isinstance(answer, dns.resolver.Answer):
            return []
        return [{'flags': rdata.flags, 'tag': rdata.tag, 'value': rdata.value} for rdata in answer][
            : settings.MAX_DNS_RECORDS
        ]
