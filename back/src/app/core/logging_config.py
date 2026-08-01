import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar('request_id', default=None)
analysis_id_context: ContextVar[str | None] = ContextVar('analysis_id', default=None)
task_id_context: ContextVar[str | None] = ContextVar('task_id', default=None)


@contextmanager
def correlation_context(
    *,
    request_id: str | None,
    analysis_id: str | None,
    task_id: str | None,
) -> Iterator[None]:
    tokens = (
        request_id_context.set(request_id),
        analysis_id_context.set(analysis_id),
        task_id_context.set(task_id),
    )
    try:
        yield
    finally:
        task_id_context.reset(tokens[2])
        analysis_id_context.reset(tokens[1])
        request_id_context.reset(tokens[0])


class JsonFormatter(logging.Formatter):
    _FIELDS = (
        'request_id',
        'method',
        'path',
        'status_code',
        'duration_ms',
        'analysis_duration_ms',
        'analysis_id',
        'task_id',
        'job_status',
        'job_duration_ms',
        'domain',
        'check',
        'check_duration_ms',
        'check_status',
        'deadline_ms',
        'error_count',
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        for field in self._FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        return json.dumps(payload, ensure_ascii=False, default=str)


class CorrelationContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field, context in (
            ('request_id', request_id_context),
            ('analysis_id', analysis_id_context),
            ('task_id', task_id_context),
        ):
            value = context.get()
            if value is not None:
                setattr(record, field, value)
        return True


def configure_logging(debug: bool) -> None:
    logger = logging.getLogger('app')
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    if any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.addFilter(CorrelationContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
