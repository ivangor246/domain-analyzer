from dataclasses import dataclass
from math import isfinite
from threading import Lock
from typing import Mapping

LabelSet = tuple[tuple[str, str], ...]


def _normalize_labels(labels: Mapping[str, object] | None) -> LabelSet:
    if not labels:
        return ()
    return tuple(sorted((str(name), str(value)) for name, value in labels.items()))


def _escape_label(value: str) -> str:
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')


def _format_labels(labels: LabelSet) -> str:
    if not labels:
        return ''
    formatted = ','.join(f'{name}="{_escape_label(value)}"' for name, value in labels)
    return f'{{{formatted}}}'


def _format_value(value: float) -> str:
    return format(value, '.12g')


@dataclass
class _Histogram:
    buckets: tuple[float, ...]
    counts: list[int]
    count: int = 0
    total: float = 0.0


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._metadata: dict[str, tuple[str, str]] = {}
        self._counters: dict[str, dict[LabelSet, float]] = {}
        self._gauges: dict[str, dict[LabelSet, float]] = {}
        self._histograms: dict[str, dict[LabelSet, _Histogram]] = {}

    def register(self, name: str, metric_type: str, help_text: str) -> None:
        with self._lock:
            existing = self._metadata.get(name)
            if existing is not None and existing != (metric_type, help_text):
                raise ValueError(f'Metric {name!r} is already registered with different metadata')
            self._metadata[name] = (metric_type, help_text)

    def increment(self, name: str, labels: Mapping[str, object] | None = None, value: float = 1.0) -> None:
        if not isfinite(value) or value < 0:
            raise ValueError('Counter increments must be finite and non-negative')
        label_set = _normalize_labels(labels)
        with self._lock:
            self._require_type(name, 'counter')
            values = self._counters.setdefault(name, {})
            values[label_set] = values.get(label_set, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Mapping[str, object] | None = None) -> None:
        if not isfinite(value):
            raise ValueError('Gauge values must be finite')
        label_set = _normalize_labels(labels)
        with self._lock:
            self._require_type(name, 'gauge')
            values = self._gauges.setdefault(name, {})
            values[label_set] = value

    def observe(
        self,
        name: str,
        value: float,
        labels: Mapping[str, object] | None = None,
        buckets: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    ) -> None:
        if not isfinite(value) or value < 0:
            raise ValueError('Histogram observations must be finite and non-negative')
        if any(left >= right for left, right in zip(buckets, buckets[1:])):
            raise ValueError('Histogram buckets must be strictly increasing')
        label_set = _normalize_labels(labels)
        with self._lock:
            self._require_type(name, 'histogram')
            values = self._histograms.setdefault(name, {})
            histogram = values.setdefault(label_set, _Histogram(buckets=buckets, counts=[0] * len(buckets)))
            if histogram.buckets != buckets:
                raise ValueError(f'Histogram {name!r} uses more than one bucket configuration')
            histogram.count += 1
            histogram.total += value
            for index, bucket in enumerate(buckets):
                if value <= bucket:
                    histogram.counts[index] += 1

    def render(self) -> str:
        with self._lock:
            lines: list[str] = []
            for name in sorted(self._metadata):
                metric_type, help_text = self._metadata[name]
                lines.append(f'# HELP {name} {help_text}')
                lines.append(f'# TYPE {name} {metric_type}')
                if metric_type == 'counter':
                    lines.extend(self._render_samples(name, self._counters.get(name, {})))
                elif metric_type == 'gauge':
                    lines.extend(self._render_samples(name, self._gauges.get(name, {})))
                else:
                    lines.extend(self._render_histogram(name, self._histograms.get(name, {})))
            lines.append('# EOF')
            return '\n'.join(lines) + '\n'

    def clear(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def _require_type(self, name: str, metric_type: str) -> None:
        registered = self._metadata.get(name)
        if registered is None:
            raise KeyError(f'Metric {name!r} is not registered')
        if registered[0] != metric_type:
            raise TypeError(f'Metric {name!r} is registered as {registered[0]}')

    @staticmethod
    def _render_samples(name: str, samples: Mapping[LabelSet, float]) -> list[str]:
        return [f'{name}{_format_labels(labels)} {_format_value(value)}' for labels, value in sorted(samples.items())]

    @staticmethod
    def _render_histogram(name: str, histograms: Mapping[LabelSet, _Histogram]) -> list[str]:
        lines: list[str] = []
        for labels, histogram in sorted(histograms.items()):
            for bucket, count in zip(histogram.buckets, histogram.counts):
                bucket_labels = labels + (('le', _format_value(bucket)),)
                lines.append(f'{name}_bucket{_format_labels(bucket_labels)} {count}')
            infinity_labels = labels + (('le', '+Inf'),)
            lines.append(f'{name}_bucket{_format_labels(infinity_labels)} {histogram.count}')
            lines.append(f'{name}_sum{_format_labels(labels)} {_format_value(histogram.total)}')
            lines.append(f'{name}_count{_format_labels(labels)} {histogram.count}')
        return lines


metrics = MetricsRegistry()
metrics.register('domain_analyzer_http_requests_total', 'counter', 'Total number of HTTP responses.')
metrics.register('domain_analyzer_http_request_duration_seconds', 'histogram', 'HTTP response duration in seconds.')
metrics.register('domain_analyzer_analysis_checks_total', 'counter', 'Total number of completed analysis checks.')
metrics.register(
    'domain_analyzer_analysis_check_duration_seconds',
    'histogram',
    'Analysis check duration in seconds.',
)
metrics.register('domain_analyzer_analyses_total', 'counter', 'Total number of domain analyses by final status.')
metrics.register('domain_analyzer_analysis_duration_seconds', 'histogram', 'Domain analysis duration in seconds.')
metrics.register('domain_analyzer_rate_limit_decisions_total', 'counter', 'Total number of rate-limit decisions.')
metrics.register('domain_analyzer_jobs_total', 'counter', 'Total number of Celery analysis jobs by outcome.')
metrics.register('domain_analyzer_job_duration_seconds', 'histogram', 'Celery analysis job duration in seconds.')
metrics.register(
    'domain_analyzer_analysis_queue_depth',
    'gauge',
    'Number of queued analysis jobs; -1 means the Redis queue tracker is unavailable.',
)
metrics.register('domain_analyzer_analysis_queue_available', 'gauge', 'Whether the Redis queue tracker is available.')


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    labels = {'method': method, 'path': path, 'status': status_code}
    metrics.increment('domain_analyzer_http_requests_total', labels=labels)
    metrics.observe('domain_analyzer_http_request_duration_seconds', duration_seconds, labels=labels)


def record_analysis_check(check: str, check_status: str, duration_seconds: float) -> None:
    labels = {'check': check, 'status': check_status}
    metrics.increment('domain_analyzer_analysis_checks_total', labels=labels)
    metrics.observe('domain_analyzer_analysis_check_duration_seconds', duration_seconds, labels=labels)


def record_analysis(status: str, duration_seconds: float) -> None:
    labels = {'status': status}
    metrics.increment('domain_analyzer_analyses_total', labels=labels)
    metrics.observe('domain_analyzer_analysis_duration_seconds', duration_seconds, labels=labels)


def record_rate_limit(decision: str) -> None:
    metrics.increment('domain_analyzer_rate_limit_decisions_total', labels={'decision': decision})


def record_job(outcome: str, duration_seconds: float) -> None:
    metrics.increment('domain_analyzer_jobs_total', labels={'outcome': outcome})
    metrics.observe('domain_analyzer_job_duration_seconds', duration_seconds, labels={'outcome': outcome})
