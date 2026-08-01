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
