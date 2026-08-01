#!/bin/sh

set -eu

cd src || exit 1

case "${1:-api}" in
    worker)
        exec celery -A app.core.celery_app:celery_app worker \
            --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
            --concurrency="${CELERY_WORKER_CONCURRENCY:-2}" \
            --queues=domain_analysis
        ;;
    api)
        if [ "$DEV_MODE" = "True" ]; then
            exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
        else
            exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:create_app --bind 0.0.0.0:8000
        fi
        ;;
    *)
        echo "Unknown service: $1. Use 'api' or 'worker'." >&2
        exit 64
        ;;
esac
