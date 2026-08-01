from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.metrics import metrics

metrics_router = APIRouter(prefix='/metrics', tags=['metrics'])


@metrics_router.get(
    '',
    response_class=PlainTextResponse,
    summary='Expose application metrics',
    description='Return process-local metrics in Prometheus text exposition format without domain labels.',
)
async def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(metrics.render(), media_type='text/plain; version=0.0.4; charset=utf-8')
