import unittest

from app.core.metrics import MetricsRegistry


class MetricsRegistryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = MetricsRegistry()
        self.registry.register('test_requests_total', 'counter', 'Test request count.')
        self.registry.register('test_latency_seconds', 'histogram', 'Test latency.')
        self.registry.register('test_workers', 'gauge', 'Test worker count.')

    def test_render_includes_counters_histograms_and_gauges(self) -> None:
        self.registry.increment('test_requests_total', labels={'path': '/api/test', 'quote': 'a"b'}, value=2)
        self.registry.observe('test_latency_seconds', 0.2, labels={'path': '/api/test'}, buckets=(0.1, 0.5))
        self.registry.set_gauge('test_workers', 2)

        output = self.registry.render()

        self.assertIn('# TYPE test_requests_total counter', output)
        self.assertIn('test_requests_total{path="/api/test",quote="a\\"b"} 2', output)
        self.assertIn('test_latency_seconds_bucket{path="/api/test",le="0.5"} 1', output)
        self.assertIn('test_latency_seconds_bucket{path="/api/test",le="+Inf"} 1', output)
        self.assertIn('test_latency_seconds_count{path="/api/test"} 1', output)
        self.assertIn('test_workers 2', output)
        self.assertTrue(output.endswith('# EOF\n'))

    def test_rejects_invalid_metric_values(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.increment('test_requests_total', value=-1)
        with self.assertRaises(ValueError):
            self.registry.observe('test_latency_seconds', -1)
        with self.assertRaises(ValueError):
            self.registry.set_gauge('test_workers', float('inf'))


if __name__ == '__main__':
    unittest.main()
