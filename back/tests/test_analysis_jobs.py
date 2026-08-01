from datetime import datetime, timezone
import unittest

from app.core.exceptions import AnalysisConflictError, DomainValidationError
from app.schemas.analysis import AnalysisStatus
from app.services.analysis_jobs import AnalysisJobService, AnalysisRecord, TaskSnapshot


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

    async def enqueue(self, analysis_id: str, domain: str) -> None:
        self.enqueued.append((analysis_id, domain))
        self.snapshots[analysis_id] = TaskSnapshot(state='PENDING')

    async def snapshot(self, analysis_id: str) -> TaskSnapshot:
        return self.snapshots[analysis_id]

    async def revoke(self, analysis_id: str) -> None:
        self.snapshots[analysis_id] = TaskSnapshot(state='REVOKED')


class AnalysisJobServiceTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = FakeStore()
        self.broker = FakeBroker()
        self.service = AnalysisJobService(store=self.store, broker=self.broker)

    async def test_create_normalizes_domain_and_supports_idempotency(self) -> None:
        first = await self.service.create('https://Example.com/', idempotency_key='request-1')
        second = await self.service.create('example.com', idempotency_key='request-1')

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.domain, 'example.com')
        self.assertEqual(first.status, AnalysisStatus.QUEUED)
        self.assertEqual(len(self.broker.enqueued), 1)

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
