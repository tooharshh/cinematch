#!/usr/bin/env bash
# Publish the running frontend through an account-free, temporary HTTPS tunnel.
set -euo pipefail
cd "$(dirname "$0")/.."
binary=${CLOUDFLARED_BIN:-"$PWD/.runtime/cloudflared"}
if [ ! -x "$binary" ]; then
  if command -v cloudflared >/dev/null 2>&1; then binary=$(command -v cloudflared)
  else echo 'Install cloudflared first; see docs/sharing.md.' >&2; exit 1; fi
fi
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8501/_stcore/health >/dev/null
echo 'Sharing CineMatch publicly. Keep the laptop awake. Ctrl+C stops sharing.'
# An explicit empty config avoids interfering with an existing named-tunnel config.
exec "$binary" tunnel --config /dev/null --no-autoupdate --url http://127.0.0.1:8501
