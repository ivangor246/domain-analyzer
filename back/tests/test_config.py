import unittest

from pydantic import ValidationError

from app.core.config import Settings


class SettingsTestCase(unittest.TestCase):
    def test_celery_defaults_are_safe_for_local_compose(self) -> None:
        settings = Settings(_env_file=None)

        self.assertEqual(settings.REDIS_URL, 'redis://redis:6379/0')
        self.assertEqual(settings.REDIS_TIMEOUT_SECONDS, 5)
        self.assertEqual(settings.ANALYSIS_TIMEOUT_SECONDS, 120)
        self.assertEqual(settings.CELERY_TASK_TIME_LIMIT_SECONDS, 900)
        self.assertEqual(settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS, 840)
        self.assertLess(settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS, settings.CELERY_TASK_TIME_LIMIT_SECONDS)
        self.assertEqual(settings.ANALYSIS_MAX_CONCURRENCY, 2)
        self.assertEqual(settings.ANALYSIS_CONCURRENCY_LEASE_SECONDS, 180)
        self.assertEqual(settings.ANALYSIS_CONCURRENCY_RETRY_SECONDS, 5)
        self.assertEqual(settings.ANALYSIS_CONCURRENCY_MAX_RETRIES, 30)
        self.assertEqual(settings.RETRY_JITTER_SECONDS, 0.1)
        self.assertEqual(settings.RETRY_MAX_DELAY_SECONDS, 30)
        self.assertEqual(settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD, 3)
        self.assertEqual(settings.CIRCUIT_BREAKER_RESET_SECONDS, 30)
        self.assertTrue(settings.RATE_LIMIT_REDIS_ENABLED)
        self.assertTrue(settings.RATE_LIMIT_REDIS_FALLBACK_ENABLED)

    def test_celery_soft_time_limit_must_be_shorter_than_hard_limit(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                CELERY_TASK_TIME_LIMIT_SECONDS=60,
                CELERY_TASK_SOFT_TIME_LIMIT_SECONDS=60,
            )

    def test_analysis_deadline_must_fit_inside_celery_soft_limit(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                ANALYSIS_TIMEOUT_SECONDS=900,
                CELERY_TASK_SOFT_TIME_LIMIT_SECONDS=900,
                CELERY_TASK_TIME_LIMIT_SECONDS=901,
            )

    def test_concurrency_lease_must_outlive_analysis_deadline(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                ANALYSIS_TIMEOUT_SECONDS=120,
                ANALYSIS_CONCURRENCY_LEASE_SECONDS=120,
            )
