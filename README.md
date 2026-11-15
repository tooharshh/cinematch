# CineMatch

A movie recommendation capstone for SRM Linux and Container Technologies. Search a movie you like and get five alternatives using **TF-IDF + cosine similarity** over overviews and genre names. Python, FastAPI, Streamlit and DuckDB; **rootless Podman only** for containers.

Adapted from [MagnusS0/movie-rec-system](https://github.com/MagnusS0/movie-rec-system), revision `a46de1bdd4b43e78f234b066aa085e88c0397527`. See [provenance](docs/upstream.md) and the retained [Apache-2.0 licence](LICENSE). Modified Python modules carry adaptation notices. The upstream algorithm and architecture are retained; this project adds reliable preparation, search, caching, tests and Podman operations.

## Structure and architecture

- `app/`: FastAPI, configuration, cached sparse TF-IDF and cosine ranking.
- `frontend/`: separate Poetry project and Streamlit UI.
- `etl/`: TMDB extraction, atomic DuckDB preparation, optional EDA notebook.
- `tests/`: offline API, ranking, extraction and UI request tests; synthetic fixtures.
- `products/`: upstream executed notebooks kept as historical reference, not runtime data.
- `Containerfile`: separate backend/frontend targets; `scripts/`: Podman startup.

Browser → Streamlit `:8501` → `http://backend:8000` on `siw-net` → read-only DuckDB in `siw-data`. An initialization container prepares data and exits. See [architecture](docs/architecture.md).

## Prerequisites

Linux, Git, Python **3.10**, Poetry **1.6.1**, and rootless Podman with user-defined network DNS enabled. Install Podman using your distribution's supported package instructions; verify `podman info` reports `rootless: true`. On Fedora, `sudo dnf install podman` installs the platform; application containers do not require sudo. Ports 8000 and 8501 must be free. Allow disk space for two Python images and notebook dependencies inherited from upstream.

The original locks are retained for reproducibility, not a claim of current dependency security. Do not expose this coursework deployment publicly without a separate dependency/security update.

## Run locally

```bash
poetry install --no-root
# Copy once; do not overwrite an existing .env:
cp -n .env.example .env
```

For a real catalog, put your TMDB developer `API_KEY` in `.env`, then run:

```bash
poetry run python -m etl.prepare --per-language 200
# Equivalent pipeline entrypoint: poetry run ploomber build
poetry run uvicorn app.app:app --host 127.0.0.1 --port 8000
```

The initial live catalog requests up to 200 movies each for English, Hindi, Tamil, Telugu and Malayalam with English metadata. Coverage is bounded; absent titles are not fetched during recommendation. Refresh only while the backend is stopped, then restart it to refresh the vector cache.

For a **synthetic, offline demonstration**, use this instead of live preparation:

```bash
poetry run python -m etl.prepare --fixture tests/fixtures/catalog.json
```

This fixture includes `Inception` as a query anchor and fictional example movies. It is test data, not authentic movie information or relevance evidence. Preparation replaces the target database; use `DATABASE_PATH=/tmp/siw-demo.duckdb` to avoid replacing a real catalog.

In another terminal:

```bash
cd frontend
poetry install --no-root
BACKEND_URL=http://127.0.0.1:8000 poetry run streamlit run frontend_app.py
```

Open http://127.0.0.1:8501 and http://127.0.0.1:8000/docs.

## Build custom Podman images

```bash
podman build --target backend -t localhost/siw-backend:0.1.0 -f Containerfile .
podman build --target frontend -t localhost/siw-frontend:0.1.0 -f Containerfile .
podman images
```

`FROM` selects Python 3.10 slim; `WORKDIR`, `COPY` and `RUN` install locked dependencies and application code. `USER` selects an unprivileged account. `EXPOSE` documents ports; `CMD` starts each service. The startup script configures Podman runtime health checks; this works with the default OCI image format. Build stages isolate Poetry from runtime images. Builds need package-registry access, **no TMDB credentials**. Data and private configuration are excluded by `.containerignore`.

## Network, volume and startup

```bash
# Creates siw-net and siw-data if absent; initializes live data, then starts services:
bash scripts/podman-start.sh live
# Or choose synthetic data for the first initialization:
# bash scripts/podman-start.sh fixture
# Reuse an already initialized volume:
# bash scripts/podman-start.sh existing
```

The script refuses to replace existing named containers or overwrite an existing catalog. On failure, inspect the resources it leaves for diagnosis. It does not automatically delete containers or volumes.

The core commands, also useful for a viva demonstration, are:

```bash
podman network create siw-net
podman volume create siw-data
podman run --rm --name siw-init --env-file .env \
  -e DATABASE_PATH=/data/movies_data.duckdb -v siw-data:/data \
  localhost/siw-backend:0.1.0 python -m etl.prepare
podman run -d --name backend --network siw-net \
  -p 127.0.0.1:8000:8000 -v siw-data:/data:ro localhost/siw-backend:0.1.0
# Wait for /health to return 200 before starting the UI.
podman run -d --name frontend --network siw-net \
  -p 127.0.0.1:8501:8501 -e BACKEND_URL=http://backend:8000 \
  localhost/siw-frontend:0.1.0
```

Use the script OR the manual sequence, not both. Named volumes avoid host-path SELinux labelling issues. If adapting to a private bind mount on an SELinux host, label only the intended project data directory with `:Z`; never relabel broad home/system directories. Synthetic catalogs are labelled in the UI after searching. The UI has no database mount. Serving uses a read-only database connection and volume; initialization is the only writer.

## Configuration and API

| Variable | Default | Use |
|---|---|---|
| `API_KEY` | unset | Initialization only; never an image build argument |
| `DATABASE_PATH` | `movies_data.duckdb` locally, `/data/movies_data.duckdb` in backend image | Catalog location |
| `BACKEND_URL` | `http://127.0.0.1:8000` locally | Streamlit API base URL; container uses `http://backend:8000` |

- `GET /health`: 200 with movie count/catalog source or 503 when catalog unavailable.
- `GET /movies?query=echo&limit=20`: bounded case-insensitive substring search with catalog source.
- `POST /recommendations/`: `{"movie":"Inception","num_rec":5}`; optional `movie_id` disambiguates titles. Counts are bounded to 1–20.
- Responses retain upstream `movie`, title-list `recommendations`, and `metrics`; add `recommendation_details` with metadata and cosine scores.
- Unknown titles/IDs: 404; ambiguous title: 409 with choices; invalid input: 422; unavailable catalog: 503.

```bash
curl -f http://127.0.0.1:8000/health
curl -f 'http://127.0.0.1:8000/movies?query=Inception'
curl -f http://127.0.0.1:8000/recommendations/ \
  -H 'Content-Type: application/json' -d '{"movie":"Inception","num_rec":5}'
```

Cosine similarity measures text overlap, not predicted enjoyment. Legacy RMSE diagnostics measure differences in popularity/ratings/votes, **not recommendation quality**. Fewer than five alternatives are returned for very small catalogs.

## Tests and operations

```bash
poetry run pytest -q
python3 scripts/verify-containers.py  # after starting both containers
podman ps -a
podman logs --tail 100 backend
podman inspect backend
podman network inspect siw-net
podman volume inspect siw-data
podman stop frontend
podman start frontend
podman restart backend
```

See [troubleshooting](docs/troubleshooting.md), [demo checklist](docs/demo.md) and [verification record](docs/verification.md). CI runs offline tests and does not publish images.

## Tag, push and pull

Publishing requires your own registry namespace and credentials. Replace `OWNER` before executing; no registry publishing is automatic.

```bash
podman login ghcr.io
podman tag localhost/siw-backend:0.1.0 ghcr.io/OWNER/siw-backend:0.1.0
podman push ghcr.io/OWNER/siw-backend:0.1.0
podman pull ghcr.io/OWNER/siw-backend:0.1.0
# Repeat tag/push/pull for siw-frontend.
podman image inspect ghcr.io/OWNER/siw-backend:0.1.0
```

Keep version tags and compare pushed/pulled digests. Test pulled images under distinct container names before replacing a working deployment.

## Credits

Original project: MagnusS0; guided by Ploomber's movie recommendation blueprint. Movie data: [TMDB](https://www.themoviedb.org/). This product uses the TMDB API but is not endorsed or certified by TMDB. The code licence does not grant redistribution rights to all third-party movie metadata/images; live data is not committed here.
