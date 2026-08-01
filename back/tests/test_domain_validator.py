import unittest

from app.utils.domain_validator import validate_domain


class DomainValidatorTestCase(unittest.TestCase):
    def test_normalizes_ascii_domain(self) -> None:
        self.assertEqual(validate_domain('  Example.COM  '), 'example.com')
        self.assertEqual(validate_domain('https://Example.COM/'), 'example.com')
        self.assertEqual(validate_domain('example.com.'), 'example.com')

    def test_converts_unicode_domain_to_punycode(self) -> None:
        self.assertEqual(validate_domain('münich.com'), 'xn--mnich-kva.com')

    def test_rejects_invalid_domains(self) -> None:
        for domain in (
            'localhost',
            '-example.com',
            'example_.com',
            'example',
            'https://example.com/path',
            'example.com:443',
            'https://user:password@example.com',
            'ftp://example.com',
            'example.com?query=ignored',
        ):
            with self.subTest(domain=domain):
                with self.assertRaises(ValueError):
                    validate_domain(domain)

    def test_domain_length_is_limited(self) -> None:
        domain = f'{"a" * 63}.{"b" * 63}.{"c" * 63}.{"d" * 63}.com'

        with self.assertRaises(ValueError):
            validate_domain(domain)
