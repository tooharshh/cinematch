# CineMatch

A movie recommendation capstone for SRM Linux and Container Technologies. Search a movie you like and get five alternatives using **TF-IDF + cosine similarity** over overviews and genre names. Python, FastAPI, Streamlit and DuckDB; **rootless Podman only** for containers.

Adapted from [MagnusS0/movie-rec-system](https://github.com/MagnusS0/movie-rec-system), revision `a46de1bdd4b43e78f234b066aa085e88c0397527`. See [provenance](docs/upstream.md) and the retained [Apache-2.0 licence](LICENSE). Modified Python modules carry adaptation notices. The upstream algorithm and architecture are retained; this project adds reliable preparation, search, caching, tests and Podman operations.

## Quick start

On **Linux with Git and rootless Podman installed**, set `REPOSITORY_URL` to this repository's GitHub clone URL, then run the following command in Bash. No host Python, Poetry or TMDB key is needed for this demo:

```bash
git clone "$REPOSITORY_URL" cinematch && cd cinematch && podman build --target backend -t localhost/siw-backend:0.1.0 -f Containerfile . && podman build --target frontend -t localhost/siw-frontend:0.1.0 -f Containerfile . && bash scripts/podman-start.sh fixture
```

Open **http://localhost:8501** after startup. The first build downloads dependencies and can take several minutes; internet is required. This starts the complete interface with a **small synthetic catalog**, not the developer's 10,000-movie database. Search for **Inception** to try the five-film recommendation flow. Posters and real movie coverage require a live TMDB catalog; private keys and database files are not included in GitHub.

Use a fresh checkout directory, free ports **8000/8501**, and no existing `backend`, `frontend` or `siw-init` containers or initialized `siw-data` catalog. The command deliberately stops instead of replacing existing work. For an existing initialized setup, start stopped services with `podman start backend frontend`; see [troubleshooting](docs/troubleshooting.md) for failures.

For **real movies**, follow the live-catalog instructions below using your own TMDB `API_KEY` and a fresh data volume. Choose live initialization instead of fixture initialization; the startup script will not overwrite demo data.

## Structure and architecture

- `app/`: FastAPI, configuration, cached sparse TF-IDF and cosine ranking.
- `frontend/`: separate Poetry project and Streamlit UI.
- `etl/`: TMDB extraction, atomic DuckDB preparation, optional EDA notebook.
- `tests/`: offline API, ranking, extraction and UI request tests; synthetic fixtures.
- `products/`: upstream executed notebooks kept as historical reference, not runtime data.
- `Containerfile`: separate backend/frontend targets; `scripts/`: Podman startup.

Browser → Streamlit `:8501` → `http://backend:8000` on `siw-net` → read-only DuckDB in `siw-data`. An initialization container prepares data and exits. See [architecture](docs/architecture.md).

## Browse-first interface

CineMatch now has a dark streaming-style homepage with real cinematic artwork, poster shelves, Indian-cinema and genre collections, catalog pagination, searchable poster results, and movie pages with five related films. Selecting a recommendation continues discovery. Funnel Display headings are paired with locally bundled DM Sans reading/control text.

The [UI design notes](docs/ui-design.md) explain color, typography and the [attention-priority map](docs/ui-attention-map.png). That map is a labelled design hypothesis; it does not represent measured user behavior or proven engagement uplift.

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

The initial live catalog requests up to 200 movies each for English, Hindi, Tamil, Telugu and Malayalam with English metadata. Live imports require released movies, nonempty overviews and at least ten votes to avoid sparse upcoming-film records. Coverage is bounded; absent titles are not fetched during recommendation. Refresh only while the backend is stopped, then restart it to refresh the vector cache.

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

## Larger catalogs and posters

For a larger real catalog, stop the backend before refreshing the active database and run the initializer with `python -m etl.prepare --total-movies 10000`. This aims for equal regional quotas first; English movies fill any shortfall. The per-language import option remains available. Pagination stops at provider limits, so the requested total is a target, not a guarantee of available data.

For minimal downtime, initialize a different database filename in the same volume, validate it, then stop the backend, back up and replace the active file, and start it again. Do not rename a database while an initializer is still writing it.

Poster paths remain in DuckDB; the API adds public `poster_url` values and the UI lazy-loads only displayed images from TMDB's CDN. Images are not stored as database blobs. Missing poster paths show a placeholder. Poster loading needs an internet connection even after catalog initialization.

Recommendations use NumPy sorting with deterministic movie-ID ties, avoiding one pandas row construction per candidate. TF-IDF is still cached once per process. Benchmarks and their limitations are recorded in `docs/verification.md`. Run a read-only engine benchmark with:

```bash
podman exec -i backend python - < scripts/benchmark_engine.py
```

The current live catalog has 10,000 movies. On the development machine, the database is about 12.5 MiB and warm localhost recommendations measured about 8 ms median; poster loading and concurrent-user traffic are separate costs.

## Configuration and API

| Variable | Default | Use |
|---|---|---|
| `API_KEY` | unset | Initialization only; never an image build argument |
| `DATABASE_PATH` | `movies_data.duckdb` locally, `/data/movies_data.duckdb` in backend image | Catalog location |
| `BACKEND_URL` | `http://127.0.0.1:8000` locally | Streamlit API base URL; container uses `http://backend:8000` |

- `GET /health`: 200 with movie count/catalog source or 503 when catalog unavailable.
- `GET /movies?query=echo&limit=20`: bounded case-insensitive substring search with catalog source.
- `GET /discover`: featured movie and six bounded catalog shelves.
- `GET /browse?collection=indian&offset=0&limit=24`: filtered, paginated collections.
- `GET /movies/{movie_id}`: movie metadata and image URLs.
- `GET /movies?query=...&include_details=true`: optional full poster-result metadata.
- `POST /recommendations/`: `{"movie":"Inception","num_rec":5}`; optional `movie_id` disambiguates titles. Counts are bounded to 1–20.
- Responses retain upstream `movie`, title-list `recommendations`, and `metrics`; add `recommendation_details` with metadata, public poster URLs and cosine scores.
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
