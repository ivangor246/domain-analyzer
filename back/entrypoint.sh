#!/bin/sh

cd src

if [ "$DEV_MODE" = "True" ]; then
    exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
else
    exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:create_app --bind 0.0.0.0:8000
fi
