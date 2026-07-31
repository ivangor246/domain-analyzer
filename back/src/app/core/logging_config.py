import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar('request_id', default=None)


class JsonFormatter(logging.Formatter):
    _FIELDS = (
        'request_id',
        'method',
        'path',
        'status_code',
        'duration_ms',
        'domain',
        'check',
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


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_context.get()
        if request_id is not None:
            record.request_id = request_id
        return True


def configure_logging(debug: bool) -> None:
    logger = logging.getLogger('app')
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    if any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
