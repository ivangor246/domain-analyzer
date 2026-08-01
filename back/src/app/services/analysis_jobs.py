import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.core.config import settings
from app.core.exceptions import (
    AnalysisConflictError,
    AnalysisNotFoundError,
    AnalysisQueueError,
    DomainValidationError,
)
from app.schemas.analysis import AnalysisJobSchema, AnalysisStatus
from app.schemas.domain import DomainSchema
from app.schemas.error import ErrorSchema
from app.utils.domain_validator import validate_domain

_TASK_NAME = 'app.tasks.domain.analyze_domain_task'
_JOB_KEY_PREFIX = 'domain_analyzer:analysis:'
_IDEMPOTENCY_KEY_PREFIX = 'domain_analyzer:idempotency:'
_TERMINAL_STATES = {'SUCCESS', 'FAILURE', 'REVOKED'}


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    domain: str
    created_at: datetime
    cancelled: bool = False

    def to_payload(self) -> str:
        return json.dumps(
            {
                'id': self.analysis_id,
                'domain': self.domain,
                'created_at': self.created_at.isoformat(),
                'cancelled': self.cancelled,
            },
            separators=(',', ':'),
        )

    @classmethod
    def from_payload(cls, payload: str) -> 'AnalysisRecord':
        data = json.loads(payload)
        return cls(
            analysis_id=str(data['id']),
            domain=str(data['domain']),
            created_at=datetime.fromisoformat(str(data['created_at'])),
            cancelled=bool(data.get('cancelled', False)),
        )


@dataclass(frozen=True)
class TaskSnapshot:
    state: str
    result: object | None = None


class AnalysisJobStore(Protocol):
    async def reserve(self, record: AnalysisRecord, idempotency_key: str | None) -> tuple[str, bool]: ...

    async def get(self, analysis_id: str) -> AnalysisRecord | None: ...

    async def set_cancelled(self, analysis_id: str, cancelled: bool) -> None: ...

    async def delete(self, record: AnalysisRecord, idempotency_key: str | None) -> None: ...


class TaskBroker(Protocol):
    async def enqueue(self, analysis_id: str, domain: str) -> None: ...

    async def snapshot(self, analysis_id: str) -> TaskSnapshot: ...

    async def revoke(self, analysis_id: str) -> None: ...


class RedisAnalysisJobStore:
    def __init__(self) -> None:
        self._client: object | None = None
        self._client_lock = Lock()

    @staticmethod
    def _job_key(analysis_id: str) -> str:
        return f'{_JOB_KEY_PREFIX}{analysis_id}'

    @staticmethod
    def _idempotency_key(value: str) -> str:
        digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
        return f'{_IDEMPOTENCY_KEY_PREFIX}{digest}'

    def _get_client(self):
        with self._client_lock:
            if self._client is None:
                from redis import Redis

                self._client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            return self._client

    def _reserve_sync(self, record: AnalysisRecord, idempotency_key: str | None) -> tuple[str, bool]:
        client = self._get_client()
        client.set(self._job_key(record.analysis_id), record.to_payload(), ex=settings.ANALYSIS_JOB_TTL_SECONDS)

        if idempotency_key is None:
            return record.analysis_id, True

        key = self._idempotency_key(idempotency_key)
        try:
            created = client.set(
                key,
                record.analysis_id,
                ex=settings.ANALYSIS_JOB_TTL_SECONDS,
                nx=True,
            )
            if created:
                return record.analysis_id, True

            existing_id = client.get(key)
            if existing_id is None:
                raise RuntimeError('Idempotency key disappeared before it could be read')
            client.delete(self._job_key(record.analysis_id))
            return str(existing_id), False
        except Exception:
            client.delete(self._job_key(record.analysis_id))
            raise

    def _get_sync(self, analysis_id: str) -> AnalysisRecord | None:
        payload = self._get_client().get(self._job_key(analysis_id))
        if payload is None:
            return None
        try:
            return AnalysisRecord.from_payload(str(payload))
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def _set_cancelled_sync(self, analysis_id: str, cancelled: bool) -> None:
        client = self._get_client()
        payload = client.get(self._job_key(analysis_id))
        if payload is None:
            return
        try:
            record = AnalysisRecord.from_payload(str(payload))
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return
        updated = AnalysisRecord(
            analysis_id=record.analysis_id,
            domain=record.domain,
            created_at=record.created_at,
            cancelled=cancelled,
        )
        client.set(self._job_key(analysis_id), updated.to_payload(), ex=settings.ANALYSIS_JOB_TTL_SECONDS)

    def _delete_sync(self, record: AnalysisRecord, idempotency_key: str | None) -> None:
        client = self._get_client()
        client.delete(self._job_key(record.analysis_id))
        if idempotency_key is not None:
            key = self._idempotency_key(idempotency_key)
            if client.get(key) == record.analysis_id:
                client.delete(key)

    async def reserve(self, record: AnalysisRecord, idempotency_key: str | None) -> tuple[str, bool]:
        return await asyncio.to_thread(self._reserve_sync, record, idempotency_key)

    async def get(self, analysis_id: str) -> AnalysisRecord | None:
        return await asyncio.to_thread(self._get_sync, analysis_id)

    async def set_cancelled(self, analysis_id: str, cancelled: bool) -> None:
        await asyncio.to_thread(self._set_cancelled_sync, analysis_id, cancelled)

    async def delete(self, record: AnalysisRecord, idempotency_key: str | None) -> None:
        await asyncio.to_thread(self._delete_sync, record, idempotency_key)


class CeleryTaskBroker:
    @staticmethod
    def _get_app():
        from app.core.celery_app import celery_app

        return celery_app

    def _enqueue_sync(self, analysis_id: str, domain: str) -> None:
        self._get_app().send_task(_TASK_NAME, args=[domain], task_id=analysis_id)

    def _snapshot_sync(self, analysis_id: str) -> TaskSnapshot:
        result = self._get_app().AsyncResult(analysis_id)
        state = result.state
        value = result.result if state == 'SUCCESS' else None
        return TaskSnapshot(state=state, result=value)

    def _revoke_sync(self, analysis_id: str) -> None:
        self._get_app().control.revoke(analysis_id, terminate=True, signal='SIGTERM')

    async def enqueue(self, analysis_id: str, domain: str) -> None:
        await asyncio.to_thread(self._enqueue_sync, analysis_id, domain)

    async def snapshot(self, analysis_id: str) -> TaskSnapshot:
        return await asyncio.to_thread(self._snapshot_sync, analysis_id)

    async def revoke(self, analysis_id: str) -> None:
        await asyncio.to_thread(self._revoke_sync, analysis_id)


class AnalysisJobService:
    def __init__(
        self,
        store: AnalysisJobStore | None = None,
        broker: TaskBroker | None = None,
    ) -> None:
        self.store = store or RedisAnalysisJobStore()
        self.broker = broker or CeleryTaskBroker()

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        try:
            return validate_domain(domain)
        except ValueError as exc:
            raise DomainValidationError(str(exc)) from exc

    @staticmethod
    def _job_from_snapshot(record: AnalysisRecord, snapshot: TaskSnapshot) -> AnalysisJobSchema:
        if record.cancelled or snapshot.state == 'REVOKED':
            return AnalysisJobSchema(
                id=record.analysis_id,
                domain=record.domain,
                status=AnalysisStatus.CANCELLED,
                created_at=record.created_at,
            )

        if snapshot.state == 'SUCCESS':
            try:
                result = DomainSchema.model_validate(snapshot.result)
            except (TypeError, ValidationError):
                return AnalysisJobSchema(
                    id=record.analysis_id,
                    domain=record.domain,
                    status=AnalysisStatus.FAILED,
                    created_at=record.created_at,
                    error=ErrorSchema(code='invalid_analysis_result', message='The analysis result is invalid.'),
                )
            return AnalysisJobSchema(
                id=record.analysis_id,
                domain=record.domain,
                status=AnalysisStatus.COMPLETED,
                created_at=record.created_at,
                result=result,
            )

        if snapshot.state == 'FAILURE':
            return AnalysisJobSchema(
                id=record.analysis_id,
                domain=record.domain,
                status=AnalysisStatus.FAILED,
                created_at=record.created_at,
                error=ErrorSchema(code='analysis_failed', message='Domain analysis failed.'),
            )

        status = AnalysisStatus.RUNNING if snapshot.state in {'STARTED', 'RETRY', 'PROGRESS'} else AnalysisStatus.QUEUED
        return AnalysisJobSchema(
            id=record.analysis_id,
            domain=record.domain,
            status=status,
            created_at=record.created_at,
        )

    async def create(self, domain: str, idempotency_key: str | None = None) -> AnalysisJobSchema:
        normalized_domain = self._normalize_domain(domain)
        record = AnalysisRecord(
            analysis_id=uuid4().hex,
            domain=normalized_domain,
            created_at=datetime.now(timezone.utc),
        )
        key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None

        try:
            analysis_id, is_new = await self.store.reserve(record, key)
        except Exception as exc:
            raise AnalysisQueueError('Unable to reserve an analysis job.') from exc

        if not is_new:
            existing = await self.store.get(analysis_id)
            if existing is None:
                raise AnalysisNotFoundError('Analysis job not found.')
            if existing.domain != normalized_domain:
                raise AnalysisConflictError('The idempotency key was already used for another domain.')
            return await self.get(analysis_id)

        try:
            await self.broker.enqueue(record.analysis_id, normalized_domain)
        except Exception as exc:
            await self.store.delete(record, key)
            raise AnalysisQueueError('Unable to enqueue the analysis job.') from exc

        return AnalysisJobSchema(
            id=record.analysis_id,
            domain=record.domain,
            status=AnalysisStatus.QUEUED,
            created_at=record.created_at,
        )

    async def get(self, analysis_id: str) -> AnalysisJobSchema:
        record = await self.store.get(analysis_id)
        if record is None:
            raise AnalysisNotFoundError('Analysis job not found.')
        if record.cancelled:
            return self._job_from_snapshot(record, TaskSnapshot(state='REVOKED'))

        try:
            snapshot = await self.broker.snapshot(analysis_id)
        except Exception as exc:
            raise AnalysisQueueError('Unable to read the analysis job.') from exc
        return self._job_from_snapshot(record, snapshot)

    async def cancel(self, analysis_id: str) -> AnalysisJobSchema:
        record = await self.store.get(analysis_id)
        if record is None:
            raise AnalysisNotFoundError('Analysis job not found.')
        if record.cancelled:
            return self._job_from_snapshot(record, TaskSnapshot(state='REVOKED'))

        try:
            snapshot = await self.broker.snapshot(analysis_id)
        except Exception as exc:
            raise AnalysisQueueError('Unable to read the analysis job.') from exc
        if snapshot.state in _TERMINAL_STATES:
            return self._job_from_snapshot(record, snapshot)

        await self.store.set_cancelled(analysis_id, True)
        try:
            await self.broker.revoke(analysis_id)
        except Exception as exc:
            await self.store.set_cancelled(analysis_id, False)
            raise AnalysisQueueError('Unable to cancel the analysis job.') from exc

        return AnalysisJobSchema(
            id=record.analysis_id,
            domain=record.domain,
            status=AnalysisStatus.CANCELLED,
            created_at=record.created_at,
        )
