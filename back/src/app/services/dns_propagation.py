import asyncio

import dns.asyncresolver
import dns.exception
import dns.resolver

from app.core.config import settings
from app.schemas.dns import PropagationSchema, PropagationServerSchema


class DNSPropagation:
    @staticmethod
    async def check(domain: str) -> PropagationSchema:
        tasks = [DNSPropagation._query_server(domain, s['name'], s['ip']) for s in settings.PROPAGATION_SERVERS]
        servers = list(await asyncio.gather(*tasks))

        ok_servers = [s for s in servers if s.status == 'ok']
        consistent = (
            len({(tuple(sorted(s.A)), tuple(sorted(s.AAAA))) for s in ok_servers}) <= 1 if ok_servers else False
        )

        return PropagationSchema(consistent=consistent, servers=servers)

    @staticmethod
    async def _query_server(domain: str, name: str, server_ip: str) -> PropagationServerSchema:
        resolver = dns.asyncresolver.Resolver()
        resolver.nameservers = [server_ip]
        resolver.lifetime = 5

        try:
            a_records, aaaa_records = await asyncio.gather(
                DNSPropagation._resolve(resolver, domain, 'A'),
                DNSPropagation._resolve(resolver, domain, 'AAAA'),
            )
            return PropagationServerSchema(
                name=name,
                ip=server_ip,
                A=sorted(a_records),
                AAAA=sorted(aaaa_records),
                status='ok',
            )
        except dns.exception.Timeout:
            return PropagationServerSchema(name=name, ip=server_ip, status='timeout')
        except Exception:
            return PropagationServerSchema(name=name, ip=server_ip, status='error')

    @staticmethod
    async def _resolve(resolver: dns.asyncresolver.Resolver, domain: str, rdtype: str) -> list[str]:
        try:
            answer = await resolver.resolve(domain, rdtype)
            return [rdata.address for rdata in answer]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            return []
