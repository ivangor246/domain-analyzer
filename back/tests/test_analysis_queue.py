import unittest

from app.services.analysis_queue import RedisAnalysisQueueTracker


class FakeRedis:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def eval(self, *args):
        self.calls.append(args)
        return next(self.responses)


class AnalysisQueueTrackerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_tracks_queued_started_and_depth_operations(self) -> None:
        client = FakeRedis([1, 1, 3])
        tracker = RedisAnalysisQueueTracker(ttl_seconds=3600)
        tracker._client = client

        await tracker.mark_queued('task-1')
        await tracker.mark_started('task-1')
        self.assertEqual(await tracker.depth(), 3)

        self.assertEqual(len(client.calls), 3)
        self.assertEqual(client.calls[0][1], 1)
        self.assertEqual(client.calls[0][2], 'domain_analyzer:analysis_queue')
        self.assertEqual(client.calls[0][3], 3600)
        self.assertEqual(client.calls[0][4], 'task-1')
        self.assertEqual(client.calls[2][1], 1)
        self.assertEqual(client.calls[2][2], 'domain_analyzer:analysis_queue')


if __name__ == '__main__':
    unittest.main()
