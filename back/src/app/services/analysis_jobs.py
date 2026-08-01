import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from logging import getLogger
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
from app.schemas.analysis import (
    ANALYSIS_CHECKS,
    AnalysisJobSchema,
    AnalysisProgressSchema,
    AnalysisStatus,
)
from app.schemas.domain import DomainSchema
from app.schemas.error import ErrorSchema
from app.services.analysis_queue import mark_analysis_queued, remove_analysis_from_queue
from app.utils.domain_validator import validate_domain

_TASK_NAME = 'app.tasks.domain.analyze_domain_task'
_JOB_KEY_PREFIX = 'domain_analyzer:analysis:'
_IDEMPOTENCY_KEY_PREFIX = 'domain_analyzer:idempotency:'
_TERMINAL_STATES = {'SUCCESS', 'FAILURE', 'REVOKED'}

logger = getLogger(__name__)


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    domain: str
    created_at: datetime
    cancelled: bool = False
    request_id: str | None = None

    def to_payload(self) -> str:
        return json.dumps(
            {
                'id': self.analysis_id,
                'domain': self.domain,
                'created_at': self.created_at.isoformat(),
                'cancelled': self.cancelled,
                'request_id': self.request_id,
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
            request_id=str(data['request_id']) if data.get('request_id') else None,
        )


@dataclass(frozen=True)
class TaskSnapshot:
    state: str
    result: object | None = None
    meta: object | None = None


class AnalysisJobStore(Protocol):
    async def reserve(self, record: AnalysisRecord, idempotency_key: str | None) -> tuple[str, bool]: ...

    async def get(self, analysis_id: str) -> AnalysisRecord | None: ...

    async def set_cancelled(self, analysis_id: str, cancelled: bool) -> None: ...

    async def delete(self, record: AnalysisRecord, idempotency_key: str | None) -> None: ...


class TaskBroker(Protocol):
    async def enqueue(self, analysis_id: str, domain: str, request_id: str | None = None) -> None: ...

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

    async def _get_client(self):
        with self._client_lock:
            if self._client is None:
                from redis.asyncio import Redis

                self._client = Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
                    socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
                )
            return self._client

    async def _reserve_async(self, record: AnalysisRecord, idempotency_key: str | None) -> tuple[str, bool]:
        client = await self._get_client()
        await client.set(self._job_key(record.analysis_id), record.to_payload(), ex=settings.ANALYSIS_JOB_TTL_SECONDS)

        if idempotency_key is None:
            return record.analysis_id, True

        key = self._idempotency_key(idempotency_key)
        try:
            created = await client.set(
                key,
                record.analysis_id,
                ex=settings.ANALYSIS_JOB_TTL_SECONDS,
                nx=True,
            )
            if created:
                return record.analysis_id, True

            existing_id = await client.get(key)
            if existing_id is None:
                raise RuntimeError('Idempotency key disappeared before it could be read')
            await client.delete(self._job_key(record.analysis_id))
            return str(existing_id), False
        except Exception:
            await client.delete(self._job_key(record.analysis_id))
            raise

    async def _get_async(self, analysis_id: str) -> AnalysisRecord | None:
        client = await self._get_client()
        payload = await client.get(self._job_key(analysis_id))
        if payload is None:
            return None
        try:
            return AnalysisRecord.from_payload(str(payload))
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None

    async def _set_cancelled_async(self, analysis_id: str, cancelled: bool) -> None:
        client = await self._get_client()
        payload = await client.get(self._job_key(analysis_id))
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
            request_id=record.request_id,
        )
        await client.set(self._job_key(analysis_id), updated.to_payload(), ex=settings.ANALYSIS_JOB_TTL_SECONDS)

    async def _delete_async(self, record: AnalysisRecord, idempotency_key: str | None) -> None:
        client = await self._get_client()
        await client.delete(self._job_key(record.analysis_id))
        if idempotency_key is not None:
            key = self._idempotency_key(idempotency_key)
            if await client.get(key) == record.analysis_id:
                await client.delete(key)

    async def reserve(self, record: AnalysisRecord, idempotency_key: str | None) -> tuple[str, bool]:
        return await self._reserve_async(record, idempotency_key)

    async def get(self, analysis_id: str) -> AnalysisRecord | None:
        return await self._get_async(analysis_id)

    async def set_cancelled(self, analysis_id: str, cancelled: bool) -> None:
        await self._set_cancelled_async(analysis_id, cancelled)

    async def delete(self, record: AnalysisRecord, idempotency_key: str | None) -> None:
        await self._delete_async(record, idempotency_key)


class CeleryTaskBroker:
    @staticmethod
    def _get_app():
        from app.core.celery_app import celery_app

        return celery_app

    def _enqueue_sync(self, analysis_id: str, domain: str, request_id: str | None = None) -> None:
        options: dict[str, object] = {'task_id': analysis_id}
        if request_id is not None:
            options['headers'] = {'request_id': request_id}
        self._get_app().send_task(_TASK_NAME, args=[domain], **options)

    def _snapshot_sync(self, analysis_id: str) -> TaskSnapshot:
        result = self._get_app().AsyncResult(analysis_id)
        state = result.state
        value = result.result if state == 'SUCCESS' else None
        meta = result.info if state in {'STARTED', 'PROGRESS'} else None
        return TaskSnapshot(state=state, result=value, meta=meta)

    def _revoke_sync(self, analysis_id: str) -> None:
        self._get_app().control.revoke(analysis_id, terminate=True, signal='SIGTERM')

    async def enqueue(self, analysis_id: str, domain: str, request_id: str | None = None) -> None:
        await asyncio.to_thread(self._enqueue_sync, analysis_id, domain, request_id)

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
    def _initial_progress() -> list[AnalysisProgressSchema]:
        return [AnalysisProgressSchema(check=check, status='queued') for check in ANALYSIS_CHECKS]

    @staticmethod
    def _progress_from_payload(payload: object) -> list[AnalysisProgressSchema]:
        if not isinstance(payload, dict) or not isinstance(payload.get('progress'), list):
            return []

        progress: list[AnalysisProgressSchema] = []
        for item in payload['progress']:
            try:
                progress.append(AnalysisProgressSchema.model_validate(item))
            except (TypeError, ValidationError):
                continue
        return progress

    @classmethod
    def _snapshot_progress(cls, snapshot: TaskSnapshot) -> list[AnalysisProgressSchema]:
        progress = cls._progress_from_payload(snapshot.meta)
        if isinstance(snapshot.result, dict):
            progress = cls._progress_from_payload(snapshot.result) or progress
        if not progress and snapshot.state in {'PENDING', 'STARTED', 'RETRY', 'PROGRESS'}:
            return cls._initial_progress()
        return progress

    @staticmethod
    def _snapshot_result(snapshot: TaskSnapshot) -> object | None:
        if isinstance(snapshot.result, dict) and 'analysis' in snapshot.result:
            return snapshot.result['analysis']
        return snapshot.result

    @classmethod
    def _job_from_snapshot(cls, record: AnalysisRecord, snapshot: TaskSnapshot) -> AnalysisJobSchema:
        progress = cls._snapshot_progress(snapshot)
        if record.cancelled or snapshot.state == 'REVOKED':
            return AnalysisJobSchema(
                id=record.analysis_id,
                domain=record.domain,
                status=AnalysisStatus.CANCELLED,
                created_at=record.created_at,
                progress=progress,
            )

        if snapshot.state == 'SUCCESS':
            try:
                result = DomainSchema.model_validate(cls._snapshot_result(snapshot))
            except (TypeError, ValidationError):
                return AnalysisJobSchema(
                    id=record.analysis_id,
                    domain=record.domain,
                    status=AnalysisStatus.FAILED,
                    created_at=record.created_at,
                    error=ErrorSchema(code='invalid_analysis_result', message='The analysis result is invalid.'),
                    progress=progress,
                )
            return AnalysisJobSchema(
                id=record.analysis_id,
                domain=record.domain,
                status=AnalysisStatus.COMPLETED,
                created_at=record.created_at,
                result=result,
                progress=progress,
            )

        if snapshot.state == 'FAILURE':
            return AnalysisJobSchema(
                id=record.analysis_id,
                domain=record.domain,
                status=AnalysisStatus.FAILED,
                created_at=record.created_at,
                error=ErrorSchema(code='analysis_failed', message='Domain analysis failed.'),
                progress=progress,
            )

        status = AnalysisStatus.RUNNING if snapshot.state in {'STARTED', 'RETRY', 'PROGRESS'} else AnalysisStatus.QUEUED
        return AnalysisJobSchema(
            id=record.analysis_id,
            domain=record.domain,
            status=status,
            created_at=record.created_at,
            progress=progress,
        )

    async def create(
        self,
        domain: str,
        idempotency_key: str | None = None,
        request_id: str | None = None,
    ) -> AnalysisJobSchema:
        normalized_domain = self._normalize_domain(domain)
        record = AnalysisRecord(
            analysis_id=uuid4().hex,
            domain=normalized_domain,
            created_at=datetime.now(timezone.utc),
            request_id=request_id,
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

        await mark_analysis_queued(record.analysis_id)
        try:
            await self.broker.enqueue(record.analysis_id, normalized_domain, record.request_id)
        except Exception as exc:
            await remove_analysis_from_queue(record.analysis_id)
            await self.store.delete(record, key)
            raise AnalysisQueueError('Unable to enqueue the analysis job.') from exc

        logger.info(
            'analysis queued',
            extra={
                'request_id': record.request_id,
                'analysis_id': record.analysis_id,
                'task_id': record.analysis_id,
                'domain': record.domain,
            },
        )

        return AnalysisJobSchema(
            id=record.analysis_id,
            domain=record.domain,
            status=AnalysisStatus.QUEUED,
            created_at=record.created_at,
            progress=self._initial_progress(),
        )

    async def get(self, analysis_id: str) -> AnalysisJobSchema:
        record = await self.store.get(analysis_id)
        if record is None:
            raise AnalysisNotFoundError('Analysis job not found.')
        if record.cancelled:
            await remove_analysis_from_queue(analysis_id)
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
            await remove_analysis_from_queue(analysis_id)
            return self._job_from_snapshot(record, snapshot)

        await self.store.set_cancelled(analysis_id, True)
        try:
            await self.broker.revoke(analysis_id)
        except Exception as exc:
            await self.store.set_cancelled(analysis_id, False)
            raise AnalysisQueueError('Unable to cancel the analysis job.') from exc

        await remove_analysis_from_queue(analysis_id)

        return AnalysisJobSchema(
            id=record.analysis_id,
            domain=record.domain,
            status=AnalysisStatus.CANCELLED,
            created_at=record.created_at,
            progress=self._snapshot_progress(snapshot),
        )
