#!/bin/sh

# Prints the APP_PORT value for Docker Compose. When the requested host port is
# busy, the next free port is used so the backend can start next to other local
# services. The requested value comes from the shell, then back/.env, then 8000.

set -eu

root_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$root_dir/back/docker-compose.yml"
env_file="$root_dir/back/.env"
max_attempts=100

read_env_file_port() {
    if [ -f "$env_file" ]; then
        grep -E '^APP_PORT=' "$env_file" | tail -n 1 | cut -d= -f2- | tr -d "\"'\r"
    fi
}

# The port already published by this project's app container counts as free,
# so restarting a running stack keeps its port.
current_app_port() {
    published=$(docker compose -f "$compose_file" port app 8000 2>/dev/null || true)
    printf '%s' "${published##*:}"
}

port_is_free() {
    python3 - "$1" "$2" <<'EOF'
import socket
import sys

host, port = sys.argv[1] or "0.0.0.0", int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    try:
        sock.bind((host, port))
    except OSError:
        sys.exit(1)
EOF
}

requested="${APP_PORT:-$(read_env_file_port)}"
requested="${requested:-8000}"

case "$requested" in
    *:*) host="${requested%:*}" port="${requested##*:}" ;;
    *) host='' port="$requested" ;;
esac

# Leave values this script does not understand, such as port ranges, to Compose.
case "$port" in
    '' | *[!0-9]*)
        printf '%s\n' "$requested"
        exit 0
        ;;
esac

current_port=$(current_app_port)
candidate="$port"
last_candidate=$((port + max_attempts - 1))

while [ "$candidate" -le "$last_candidate" ] && [ "$candidate" -le 65535 ]; do
    if [ "$candidate" = "$current_port" ] || port_is_free "$host" "$candidate"; then
        if [ "$candidate" != "$port" ]; then
            echo "Port $port is busy, starting the backend on port $candidate." >&2
        fi
        printf '%s\n' "${host:+$host:}$candidate"
        exit 0
    fi
    candidate=$((candidate + 1))
done

echo "No free port found in range $port-$last_candidate." >&2
exit 1
