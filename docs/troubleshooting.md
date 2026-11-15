# Troubleshooting

Start with `podman ps -a`, `podman logs --tail 100 backend`, and `podman inspect backend`. Diagnose before changing configuration. Avoid deleting volumes: they contain the catalog.

| Symptom | Inspect | Resolution |
|---|---|---|
| Podman runtime directory is read-only | `podman info` in normal host terminal | Use the host's rootless user session; a restricted agent sandbox may block runtime access. Do not change global permissions. |
| Backend 503 | `/health`, backend logs, volume mounts in inspect | Initialize the intended catalog, then restart. Missing files are never silently created by serving. |
| TMDB 401/403 | Initialization status (never print `.env`) | Confirm developer key, permissions and access. |
| TMDB timeout/429 | Initialization logs | Retry later. The prior catalog remains intact. |
| UI cannot reach API | `podman network inspect siw-net` and frontend environment | Both containers must join the network; `BACKEND_URL=http://backend:8000`. |
| Address already in use | `ss -ltnp` | Stop the intended conflicting service or explicitly choose another host port. |
| Container name exists | `podman ps -a` | Inspect/start the existing container; startup refuses replacement. |
| Database permission denied | Volume mount ownership and backend user | Use the image initializer on a fresh named volume. For existing data, back it up and correct only its ownership deliberately. |
| Ambiguous title | Search results and years | Select the movie ID; this is an expected 409 for title-only calls. |
| No matching title | `/movies` search | Catalog is bounded, not the whole TMDB library. Try another available title. |
| Stale results after refresh | Backend process lifetime | Stop backend, prepare data, then restart to rebuild cached vectors. |

## Safe failure demonstration

Use distinct names and no live data volume:

```bash
podman run -d --name siw-missing-data localhost/siw-backend:0.1.0
podman logs siw-missing-data
podman exec siw-missing-data python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
podman stop siw-missing-data
```

The last request is expected to fail with HTTP 503. Do not remove your working database to demonstrate a failure.

For a connection failure, stop `backend`, request recommendations in the UI, inspect its friendly error, and start `backend` again. For a port conflict, start a separately named frontend with the occupied host port; inspect the expected failure. Keep failed containers available until you finish diagnosing them.
