#!/usr/bin/env bash
# Start existing images without replacing any containers or data.
set -euo pipefail
cd "$(dirname "$0")/.."
mode=${1:-live}
case "$mode" in live|fixture|existing) ;; *) echo "Usage: $0 [live|fixture|existing]" >&2; exit 2 ;; esac
for name in backend frontend siw-init; do
  if podman container exists "$name"; then
    echo "Container $name already exists. Inspect it; this script will not replace it." >&2
    exit 1
  fi
done
podman image exists localhost/siw-backend:0.1.0
podman image exists localhost/siw-frontend:0.1.0
podman network exists siw-net || podman network create siw-net
podman volume exists siw-data || podman volume create siw-data
if [ "$mode" != existing ]; then
  if podman run --rm -v siw-data:/data:ro localhost/siw-backend:0.1.0 python -c 'from pathlib import Path; raise SystemExit(not Path("/data/movies_data.duckdb").exists())'; then
    echo "Catalog already exists; use 'existing' or refresh explicitly with backend stopped." >&2
    exit 1
  fi
  args=()
  command=(python -m etl.prepare)
  if [ "$mode" = fixture ]; then
    command+=(--fixture tests/fixtures/catalog.json)
    echo "Initializing SYNTHETIC demo data, not a live TMDB catalog."
  else
    if [ ! -f .env ]; then echo 'Create .env with API_KEY first.' >&2; exit 1; fi
    args+=(--env-file .env)
  fi
  podman run --rm --name siw-init "${args[@]}" -e DATABASE_PATH=/data/movies_data.duckdb -v siw-data:/data localhost/siw-backend:0.1.0 "${command[@]}"
fi
podman run -d --name backend --network siw-net \
  --health-cmd='python -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8000/health\", timeout=3)"' \
  --health-interval=15s --health-timeout=5s --health-start-period=20s -p 127.0.0.1:8000:8000 -v siw-data:/data:ro localhost/siw-backend:0.1.0
ready=false
for attempt in {1..30}; do
  if podman exec backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" >/dev/null 2>&1; then
    ready=true; break
  fi
  sleep 1
done
if [ "$ready" != true ]; then
  echo 'Backend not ready. Inspect with: podman logs backend' >&2
  exit 1
fi
podman run -d --name frontend --network siw-net \
  --health-cmd='python -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8501/_stcore/health\", timeout=3)"' \
  --health-interval=15s --health-timeout=5s -p 127.0.0.1:8501:8501 -e BACKEND_URL=http://backend:8000 localhost/siw-frontend:0.1.0
printf 'UI: http://127.0.0.1:8501\nAPI: http://127.0.0.1:8000/docs\n'
