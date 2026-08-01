import json
import logging
import unittest

from app.core.logging_config import CorrelationContextFilter, JsonFormatter, correlation_context


class LoggingConfigTestCase(unittest.TestCase):
    def test_correlation_context_adds_ids_to_log_record(self) -> None:
        record = logging.LogRecord('app.test', logging.INFO, __file__, 1, 'message', (), None)

        with correlation_context(request_id='request-1', analysis_id='analysis-1', task_id='task-1'):
            self.assertTrue(CorrelationContextFilter().filter(record))

        self.assertEqual(record.request_id, 'request-1')
        self.assertEqual(record.analysis_id, 'analysis-1')
        self.assertEqual(record.task_id, 'task-1')

    def test_formatter_includes_job_lifecycle_fields(self) -> None:
        record = logging.LogRecord('app.test', logging.INFO, __file__, 1, 'task finished', (), None)
        record.request_id = 'request-1'
        record.analysis_id = 'analysis-1'
        record.task_id = 'task-1'
        record.job_status = 'completed'
        record.job_duration_ms = 12.5

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload['request_id'], 'request-1')
        self.assertEqual(payload['analysis_id'], 'analysis-1')
        self.assertEqual(payload['task_id'], 'task-1')
        self.assertEqual(payload['job_status'], 'completed')
        self.assertEqual(payload['job_duration_ms'], 12.5)


if __name__ == '__main__':
    unittest.main()
