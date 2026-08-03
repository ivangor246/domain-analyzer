#!/bin/sh

set -eu

backend_pid=''
frontend_pid=''

cleanup() {
    exit_code=$?
    trap - INT TERM EXIT

    if [ -n "$backend_pid" ]; then
        kill "$backend_pid" 2>/dev/null || true
    fi
    if [ -n "$frontend_pid" ]; then
        kill "$frontend_pid" 2>/dev/null || true
    fi

    wait 2>/dev/null || true
    exit "$exit_code"
}

trap cleanup INT TERM EXIT

make dev &
backend_pid=$!

make front-dev &
frontend_pid=$!

wait
