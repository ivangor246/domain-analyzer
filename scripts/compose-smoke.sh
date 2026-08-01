#!/bin/sh

set -eu

compose_file='back/docker-compose.yml'
project_name="${COMPOSE_PROJECT_NAME:-domain-analyzer-smoke}"
app_port="${APP_PORT:-18000}"
base_url="http://127.0.0.1:${app_port}"

if [ ! -f back/.env ]; then
    echo 'back/.env is required. Copy back/.env.example before running the Compose smoke test.' >&2
    exit 1
fi

cleanup() {
    docker compose --project-name "$project_name" --file "$compose_file" down --volumes --remove-orphans
}

trap cleanup EXIT

export APP_PORT="$app_port"
docker compose --project-name "$project_name" --file "$compose_file" up --detach --build

for attempt in $(seq 1 30); do
    if curl --fail --silent "$base_url/api/health" >/dev/null \
        && curl --fail --silent "$base_url/api/health/ready" >/dev/null; then
        echo 'Compose smoke test passed.'
        exit 0
    fi
    sleep 2
done

docker compose --project-name "$project_name" --file "$compose_file" ps
echo 'Compose smoke test failed: the backend did not become ready.' >&2
exit 1
