from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.metrics import metrics
from app.services.analysis_queue import queue_tracker

metrics_router = APIRouter(prefix='/metrics', tags=['metrics'])


@metrics_router.get(
    '',
    response_class=PlainTextResponse,
    summary='Expose application metrics',
    description='Return process-local metrics in Prometheus text exposition format without domain labels.',
)
async def metrics_endpoint() -> PlainTextResponse:
    try:
        queue_depth = await queue_tracker.depth()
        queue_available = 1
    except Exception:
        queue_depth = -1
        queue_available = 0
    metrics.set_gauge('domain_analyzer_analysis_queue_depth', float(queue_depth))
    metrics.set_gauge('domain_analyzer_analysis_queue_available', float(queue_available))
    return PlainTextResponse(metrics.render(), media_type='text/plain; version=0.0.4; charset=utf-8')
