import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.exceptions import TargetNotAllowedError
from app.services import dns_resolver, geoip, http_headers
from app.services.rdap_bootstrap import RDAPBootstrap
from app.services.rdap_client import RDAPClient
from app.services.ssl_cert import SSLCertService


class FakeAnswer(list):
    pass


class ServiceParserTests(unittest.IsolatedAsyncioTestCase):
    def test_rdap_parser_extracts_domain_fields(self):
        data = {
            'status': ['active'],
            'events': [
                {'eventAction': 'registration', 'eventDate': '2020-01-02T03:04:05Z'},
                {'eventAction': 'expiration', 'eventDate': '2030-01-02T03:04:05Z'},
                {'eventAction': 'last changed', 'eventDate': '2024-01-02T03:04:05Z'},
            ],
            'nameservers': [{'ldhName': 'NS1.Example.COM.'}, {'ldhName': 'NS2.Example.COM.'}],
            'entities': [
                {
                    'roles': ['technical'],
                    'vcardArray': ['vcard', [['fn', {}, 'text', 'Technical Contact']]],
                },
                {
                    'roles': ['registrar'],
                    'vcardArray': ['vcard', [['version', {}, 'text', '4.0'], ['fn', {}, 'text', 'Example Registrar']]],
                },
            ],
            'port43': 'whois.example.com',
        }

        result = RDAPClient._parse('https://rdap.example.com', data)

        self.assertEqual(result.server, 'https://rdap.example.com')
        self.assertEqual(result.status, ['active'])
        self.assertEqual(result.nameservers, ['ns1.example.com.', 'ns2.example.com.'])
        self.assertEqual(result.registrar, 'Example Registrar')
        self.assertEqual(result.registration_date, datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        self.assertEqual(result.expiration_date, datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        self.assertEqual(result.updated_date, datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        self.assertEqual(result.whois_server, 'whois.example.com')

    def test_rdap_parser_ignores_malformed_optional_fields(self):
        result = RDAPClient._parse(
            'https://rdap.example.com',
            {
                'status': None,
                'events': [None, {}, {'eventAction': 'registration', 'eventDate': 'not-a-date'}],
                'nameservers': [None, {}, {'ldhName': 123}],
                'entities': [None, {'roles': None}, {'roles': ['registrar'], 'vcardArray': ['vcard', [['fn']]]}],
                'port43': 123,
            },
        )

        self.assertEqual(result.status, [])
        self.assertEqual(result.nameservers, [])
        self.assertIsNone(result.registrar)
        self.assertIsNone(result.registration_date)
        self.assertIsNone(result.whois_server)

    def test_rdap_bootstrap_prefers_longest_matching_suffix(self):
        bootstrap = RDAPBootstrap()
        bootstrap.data = {
            'uk': ['https://rdap.uk/'],
            'co.uk': ['https://rdap.co.uk/'],
        }

        servers, registrable_domain = bootstrap.get_servers('www.Example.co.uk')

        self.assertEqual(servers, ['https://rdap.co.uk/'])
        self.assertEqual(registrable_domain, 'Example.co.uk')

    def test_dns_parsers_normalize_records(self):
        with patch.object(dns_resolver.dns.resolver, 'Answer', FakeAnswer):
            self.assertEqual(
                dns_resolver.DNSResolver._parse_a(FakeAnswer([SimpleNamespace(address='192.0.2.1')])),
                ['192.0.2.1'],
            )
            self.assertEqual(
                dns_resolver.DNSResolver._parse_mx(
                    FakeAnswer(
                        [
                            SimpleNamespace(preference=20, exchange='mail2.example.com.'),
                            SimpleNamespace(preference=10, exchange='mail1.example.com.'),
                        ]
                    )
                ),
                [
                    {'priority': 10, 'exchange': 'mail1.example.com'},
                    {'priority': 20, 'exchange': 'mail2.example.com'},
                ],
            )
            self.assertEqual(
                dns_resolver.DNSResolver._parse_txt(FakeAnswer([SimpleNamespace(strings=(b'first ', b'second'))])),
                ['first second'],
            )
            self.assertEqual(
                dns_resolver.DNSResolver._parse_cname(FakeAnswer([SimpleNamespace(target='Alias.Example.COM.')])),
                ['Alias.Example.COM'],
            )
            self.assertEqual(
                dns_resolver.DNSResolver._parse_ns(
                    FakeAnswer([SimpleNamespace(target='NS2.Example.COM.'), SimpleNamespace(target='ns1.example.com.')])
                ),
                ['ns1.example.com', 'ns2.example.com'],
            )
            self.assertEqual(dns_resolver.DNSResolver._parse_a(None), [])

    def test_dns_parsers_extract_soa_and_caa_records(self):
        soa = SimpleNamespace(
            mname='ns1.example.com.',
            rname='hostmaster.example.com.',
            serial=2026010101,
            refresh=3600,
            retry=600,
            expire=86400,
            minimum=300,
        )
        caa = SimpleNamespace(flags=0, tag='issue', value='letsencrypt.org')

        with patch.object(dns_resolver.dns.resolver, 'Answer', FakeAnswer):
            self.assertEqual(
                dns_resolver.DNSResolver._parse_soa(FakeAnswer([soa])),
                {
                    'mname': 'ns1.example.com',
                    'rname': 'hostmaster.example.com',
                    'serial': 2026010101,
                    'refresh': 3600,
                    'retry': 600,
                    'expire': 86400,
                    'minimum': 300,
                },
            )
            self.assertEqual(
                dns_resolver.DNSResolver._parse_caa(FakeAnswer([caa])),
                [{'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'}],
            )
            self.assertIsNone(dns_resolver.DNSResolver._parse_soa(FakeAnswer()))

    def test_ssl_parser_extracts_certificate_metadata(self):
        certificate_bytes = self._build_certificate()

        result = SSLCertService._parse_cert(certificate_bytes)

        self.assertEqual(result.subject, 'example.com')
        self.assertEqual(result.san, ['example.com', '*.example.com'])
        self.assertEqual(result.issuer, 'Example CA')
        self.assertEqual(result.issuer_org, 'Example Org')
        self.assertFalse(result.expired)
        self.assertGreaterEqual(result.days_remaining, 29)
        self.assertEqual(result.serial_number, '1234')
        self.assertEqual(len(result.fingerprint_sha256.split(':')), 32)
        self.assertTrue(result.signature_algorithm)
        self.assertEqual(result.version, 3)
        self.assertIsNotNone(result.valid_from)
        self.assertIsNotNone(result.valid_until)

    async def test_http_probe_parses_redirect_and_security_headers(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(301, headers={'location': '/final'}, request=request)
            return httpx.Response(
                200,
                headers={
                    'server': 'test-server',
                    'content-type': 'text/html',
                    'strict-transport-security': 'max-age=31536000',
                    'x-frame-options': 'DENY',
                },
                request=request,
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            patch.object(http_headers.httpx, 'AsyncClient', return_value=client),
            patch.object(http_headers.NetworkTargetGuard, 'validate', new=AsyncMock()),
        ):
            result = await http_headers.HTTPHeadersService._probe_url('http://example.com/start')

        self.assertTrue(result.reachable)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.final_url, 'http://example.com/final')
        self.assertEqual(result.redirect_chain, ['http://example.com/start'])
        self.assertEqual(result.server, 'test-server')
        self.assertEqual(result.content_type, 'text/html')
        self.assertEqual(result.strict_transport_security, 'max-age=31536000')
        self.assertEqual(result.x_frame_options, 'DENY')
        self.assertEqual(len(requests), 2)

    async def test_http_request_falls_back_to_get_after_head_rejection(self):
        methods = []

        def handler(request: httpx.Request) -> httpx.Response:
            methods.append(request.method)
            if request.method == 'HEAD':
                return httpx.Response(405, request=request)
            return httpx.Response(200, content=b'ok', request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        response = await http_headers._request(client, 'http://example.com')
        await client.aclose()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
        self.assertEqual(methods, ['HEAD', 'GET'])

    async def test_http_request_uses_fixed_ip_host_header_and_sni(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        response, redirect_chain = await http_headers._request_with_safe_redirects(
            client,
            'https://example.com/path',
            target_ip='93.184.216.34',
        )
        await client.aclose()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(redirect_chain, [])
        self.assertEqual(requests[0].url.host, '93.184.216.34')
        self.assertEqual(requests[0].headers['host'], 'example.com')
        self.assertEqual(requests[0].extensions['sni_hostname'], 'example.com')
        self.assertEqual(response.extensions['domain_analyzer_original_url'], 'https://example.com/path')

    async def test_http_redirect_resolves_destination_to_fixed_ip(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(302, headers={'location': 'https://redirect.example/final'}, request=request)
            return httpx.Response(200, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(
            http_headers.NetworkTargetGuard,
            'resolve_public_ips',
            new=AsyncMock(return_value=['198.51.100.22']),
        ) as resolve_public_ips:
            response, redirect_chain = await http_headers._request_with_safe_redirects(
                client,
                'https://example.com/start',
                target_ip='93.184.216.34',
            )
        await client.aclose()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(redirect_chain, ['https://example.com/start'])
        self.assertEqual(requests[0].url.host, '93.184.216.34')
        self.assertEqual(requests[0].headers['host'], 'example.com')
        self.assertEqual(requests[1].url.host, '198.51.100.22')
        self.assertEqual(requests[1].headers['host'], 'redirect.example')
        resolve_public_ips.assert_awaited_once_with('redirect.example')

    async def test_http_redirect_limit_does_not_follow_extra_redirects(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(302, headers={'location': '/next'}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            patch.object(http_headers.settings, 'HTTP_MAX_REDIRECTS', 1),
            patch.object(http_headers.NetworkTargetGuard, 'validate', new=AsyncMock()),
        ):
            response, redirect_chain = await http_headers._request_with_safe_redirects(client, 'http://example.com')
        await client.aclose()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(requests), 2)
        self.assertEqual(redirect_chain, ['http://example.com'])

    async def test_http_redirect_limit_zero_does_not_follow(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(302, headers={'location': '/next'}, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(http_headers.settings, 'HTTP_MAX_REDIRECTS', 0):
            response, redirect_chain = await http_headers._request_with_safe_redirects(client, 'http://example.com')
        await client.aclose()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(requests), 1)
        self.assertEqual(redirect_chain, [])

    def test_safe_redirect_url_resolves_relative_locations(self):
        self.assertEqual(
            http_headers._safe_redirect_url('https://example.com/path/start', '../final'),
            'https://example.com/final',
        )
        with self.assertRaises(TargetNotAllowedError):
            http_headers._safe_redirect_url('https://example.com', 'ftp://example.com/file')

    async def test_geoip_parser_ignores_failed_records(self):
        received_payload = []

        def handler(request: httpx.Request) -> httpx.Response:
            received_payload.append(request.content)
            return httpx.Response(
                200,
                json=[
                    {
                        'status': 'success',
                        'query': '192.0.2.1',
                        'country': 'Exampleland',
                        'countryCode': 'EX',
                        'regionName': 'Example Region',
                        'city': 'Example City',
                        'zip': '12345',
                        'lat': 1.5,
                        'lon': 2.5,
                        'timezone': 'UTC',
                        'isp': 'Example ISP',
                        'org': 'Example Org',
                        'as': 'AS64500 Example Network',
                        'asname': 'Example Network',
                    },
                    {'status': 'fail', 'query': '192.0.2.2'},
                    {'status': 'success', 'query': ''},
                    {'status': 'success', 'query': '198.51.100.10'},
                    {'status': 'success', 'query': '192.0.2.2', 'as': 123, 'lat': {'invalid': True}},
                ],
                request=request,
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(geoip.httpx, 'AsyncClient', return_value=client):
            result = await geoip.GeoIPService.lookup(['192.0.2.1', '192.0.2.2'])

        self.assertEqual(result['192.0.2.1'].country, 'Exampleland')
        self.assertEqual(result['192.0.2.1'].asn, 'AS64500')
        self.assertEqual(result['192.0.2.1'].asn_name, 'Example Network')
        self.assertNotIn('192.0.2.2', result)
        self.assertNotIn('198.51.100.10', result)
        self.assertEqual(len(received_payload), 1)

    async def test_geoip_lookup_skips_empty_input(self):
        with patch.object(geoip.httpx, 'AsyncClient') as client:
            self.assertEqual(await geoip.GeoIPService.lookup([]), {})
        client.assert_not_called()

    @staticmethod
    def _build_certificate() -> bytes:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'example.com')])
        issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, 'Example CA'),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Example Org'),
            ]
        )
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(0x1234)
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=30))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName('example.com'), x509.DNSName('*.example.com')]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        return certificate.public_bytes(serialization.Encoding.DER)


if __name__ == '__main__':
    unittest.main()
