import unittest

from app.schemas.analysis import ANALYSIS_CHECKS
from app.tasks.domain import TaskProgressReporter


class FakeTask:
    def __init__(self) -> None:
        self.states: list[dict[str, object]] = []

    def update_state(self, **kwargs: object) -> None:
        self.states.append(kwargs)


class TaskProgressReporterTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_initial_and_changed_progress_without_duplicates(self) -> None:
        task = FakeTask()
        reporter = TaskProgressReporter(task)

        await reporter.publish_initial()
        await reporter.report('dns', 'running')
        await reporter.report('dns', 'successful', 12.5)
        await reporter.report('dns', 'successful', 12.5)

        self.assertEqual(len(task.states), 3)
        self.assertEqual(
            [item['check'] for item in task.states[0]['meta']['progress']],
            list(ANALYSIS_CHECKS),
        )
        self.assertEqual(
            task.states[-1]['meta']['progress'][1],
            {
                'check': 'dns',
                'status': 'successful',
                'duration_ms': 12.5,
            },
        )

    async def test_progress_publication_failure_does_not_fail_the_reporter(self) -> None:
        class FailingTask:
            @staticmethod
            def update_state(**_kwargs: object) -> None:
                raise ConnectionError('Redis unavailable')

        reporter = TaskProgressReporter(FailingTask())
        await reporter.publish_initial()
        await reporter.report('dns', 'running')

        self.assertEqual(reporter.snapshot()[1]['status'], 'running')


if __name__ == '__main__':
    unittest.main()
