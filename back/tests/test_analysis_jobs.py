from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

from app.core.exceptions import AnalysisConflictError, DomainValidationError
from app.schemas.analysis import AnalysisStatus
from app.services.analysis_jobs import (
    AnalysisJobService,
    AnalysisRecord,
    CeleryTaskBroker,
    RedisAnalysisJobStore,
    TaskSnapshot,
)


class FakeStore:
    def __init__(self) -> None:
        self.records: dict[str, AnalysisRecord] = {}
        self.idempotency: dict[str, str] = {}

    async def reserve(self, record: AnalysisRecord, idempotency_key: str | None) -> tuple[str, bool]:
        if idempotency_key and idempotency_key in self.idempotency:
            return self.idempotency[idempotency_key], False
        self.records[record.analysis_id] = record
        if idempotency_key:
            self.idempotency[idempotency_key] = record.analysis_id
        return record.analysis_id, True

    async def get(self, analysis_id: str) -> AnalysisRecord | None:
        return self.records.get(analysis_id)

    async def set_cancelled(self, analysis_id: str, cancelled: bool) -> None:
        record = self.records[analysis_id]
        self.records[analysis_id] = AnalysisRecord(
            analysis_id=record.analysis_id,
            domain=record.domain,
            created_at=record.created_at,
            cancelled=cancelled,
        )

    async def delete(self, record: AnalysisRecord, idempotency_key: str | None) -> None:
        self.records.pop(record.analysis_id, None)
        if idempotency_key:
            self.idempotency.pop(idempotency_key, None)


class FakeBroker:
    def __init__(self) -> None:
        self.snapshots: dict[str, TaskSnapshot] = {}
        self.enqueued: list[tuple[str, str]] = []
        self.request_ids: list[str | None] = []

    async def enqueue(self, analysis_id: str, domain: str, request_id: str | None = None) -> None:
        self.enqueued.append((analysis_id, domain))
        self.request_ids.append(request_id)
        self.snapshots[analysis_id] = TaskSnapshot(state='PENDING')

    async def snapshot(self, analysis_id: str) -> TaskSnapshot:
        return self.snapshots[analysis_id]

    async def revoke(self, analysis_id: str) -> None:
        self.snapshots[analysis_id] = TaskSnapshot(state='REVOKED')


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int, nx: bool = False):
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def get(self, key: str):
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class AnalysisJobServiceTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = FakeStore()
        self.broker = FakeBroker()
        self.service = AnalysisJobService(store=self.store, broker=self.broker)

    async def test_create_normalizes_domain_and_supports_idempotency(self) -> None:
        first = await self.service.create('https://Example.com/', idempotency_key='request-1', request_id='http-1')
        second = await self.service.create('example.com', idempotency_key='request-1')

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.domain, 'example.com')
        self.assertEqual(first.status, AnalysisStatus.QUEUED)
        self.assertEqual(len(self.broker.enqueued), 1)
        self.assertEqual(self.broker.request_ids, ['http-1'])

    async def test_idempotency_key_cannot_be_reused_for_another_domain(self) -> None:
        await self.service.create('example.com', idempotency_key='request-1')

        with self.assertRaises(AnalysisConflictError):
            await self.service.create('example.org', idempotency_key='request-1')

    async def test_invalid_domain_is_rejected_before_queueing(self) -> None:
        with self.assertRaises(DomainValidationError):
            await self.service.create('not-a-domain')

        self.assertEqual(self.broker.enqueued, [])

    async def test_statuses_and_cancellation_are_mapped(self) -> None:
        job = await self.service.create('example.com')

        self.broker.snapshots[job.id] = TaskSnapshot(state='STARTED')
        self.assertEqual((await self.service.get(job.id)).status, AnalysisStatus.RUNNING)

        self.broker.snapshots[job.id] = TaskSnapshot(
            state='SUCCESS',
            result={'domain': 'example.com'},
        )
        completed = await self.service.get(job.id)
        self.assertEqual(completed.status, AnalysisStatus.COMPLETED)
        self.assertIsNotNone(completed.result)

        self.broker.snapshots[job.id] = TaskSnapshot(state='PENDING')
        cancelled = await self.service.cancel(job.id)
        self.assertEqual(cancelled.status, AnalysisStatus.CANCELLED)
        self.assertEqual((await self.service.get(job.id)).status, AnalysisStatus.CANCELLED)

    async def test_created_at_is_timezone_aware(self) -> None:
        job = await self.service.create('example.com')

        self.assertIsNotNone(job.created_at.tzinfo)
        self.assertEqual(job.created_at.tzinfo, timezone.utc)
        self.assertLessEqual(job.created_at, datetime.now(timezone.utc))


class RedisAnalysisJobStoreTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_persists_job_metadata_without_blocking_event_loop(self) -> None:
        client = FakeAsyncRedis()
        store = RedisAnalysisJobStore()
        store._client = client
        record = AnalysisRecord(
            analysis_id='a' * 32,
            domain='example.com',
            created_at=datetime.now(timezone.utc),
            request_id='http-1',
        )

        reserved = await store.reserve(record, 'request-1')
        stored = await store.get(record.analysis_id)
        await store.set_cancelled(record.analysis_id, True)
        cancelled = await store.get(record.analysis_id)
        await store.delete(record, 'request-1')

        self.assertEqual(reserved, (record.analysis_id, True))
        self.assertEqual(stored, record)
        self.assertIsNotNone(cancelled)
        self.assertTrue(cancelled.cancelled)
        self.assertIsNone(await store.get(record.analysis_id))


class CeleryTaskBrokerTestCase(unittest.TestCase):
    def test_enqueue_propagates_request_id_as_task_header(self) -> None:
        app = Mock()
        broker = CeleryTaskBroker()

        with patch.object(broker, '_get_app', return_value=app):
            broker._enqueue_sync('a' * 32, 'example.com', 'request-1')

        app.send_task.assert_called_once_with(
            'app.tasks.domain.analyze_domain_task',
            args=['example.com'],
            task_id='a' * 32,
            headers={'request_id': 'request-1'},
        )
