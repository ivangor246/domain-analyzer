import unittest

from app.utils.domain_validator import validate_domain


class DomainValidatorTestCase(unittest.TestCase):
    def test_normalizes_ascii_domain(self) -> None:
        self.assertEqual(validate_domain('  Example.COM  '), 'example.com')

    def test_converts_unicode_domain_to_punycode(self) -> None:
        self.assertEqual(validate_domain('münich.com'), 'xn--mnich-kva.com')

    def test_rejects_invalid_domains(self) -> None:
        for domain in ('localhost', '-example.com', 'example_.com', 'example'):
            with self.subTest(domain=domain):
                with self.assertRaises(ValueError):
                    validate_domain(domain)
