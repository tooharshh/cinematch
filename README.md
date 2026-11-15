# CineMatch

A movie recommendation capstone for my Linux and Container Technologies course. Search a movie you like and get five alternatives using **TF-IDF + cosine similarity** over overviews and genre names. Python, FastAPI, Streamlit and DuckDB; **rootless Podman only** for containers.

Adapted from [MagnusS0/movie-rec-system](https://github.com/MagnusS0/movie-rec-system), revision `a46de1bdd4b43e78f234b066aa085e88c0397527`. See [provenance](docs/upstream.md) and the retained [Apache-2.0 licence](LICENSE). Modified Python modules carry adaptation notices. The upstream algorithm and architecture are retained; this project adds reliable preparation, search, caching, tests and Podman operations.

## Quick start

On **Linux with Git and rootless Podman installed**, set `REPOSITORY_URL` to this repository's GitHub clone URL, then run the following command in Bash. No host Python, Poetry or TMDB key is needed for this demo:

```bash
git clone "$REPOSITORY_URL" cinematch && cd cinematch && podman build --target backend -t localhost/siw-backend:0.1.0 -f Containerfile . && podman build --target frontend -t localhost/siw-frontend:0.1.0 -f Containerfile . && bash scripts/podman-start.sh fixture
```

Open **http://localhost:8501** after startup. The first build downloads dependencies and can take several minutes; internet is required. This starts the complete interface with a **small synthetic catalog**, not the developer's 10,000-movie database. Search for **Inception** to try the five-film recommendation flow. Posters and real movie coverage require a live TMDB catalog; private keys and database files are not included in GitHub.

Use a fresh checkout directory, free ports **8000/8501**, and no existing `backend`, `frontend` or `siw-init` containers or initialized `siw-data` catalog. The command deliberately stops instead of replacing existing work. For an existing initialized setup, start stopped services with `podman start backend frontend`; see [troubleshooting](docs/troubleshooting.md) for failures.

For **real movies**, follow the [live-catalog instructions](docs/demo.md) using your own TMDB `API_KEY` and a fresh data volume. Choose live initialization instead of fixture initialization; the startup script will not overwrite demo data.

## Share a demo with Cloudflare Tunnel

Current demo: [Open CineMatch](https://wellness-controlled-triumph-spectacular.trycloudflare.com)

Use Cloudflare Tunnel to share the locally running application over HTTPS.

With the app running and cloudflared installed:

```bash
bash scripts/share-demo.sh
```

Share the HTTPS link printed in the terminal. No account, card or domain needed.
The laptop must stay awake and online. The URL changes when the tunnel restarts,
so previously shared links may expire.

Setup and stop instructions: [Sharing guide](docs/sharing.md).

## Structure and architecture

- `app/`: FastAPI, configuration, cached sparse TF-IDF and cosine ranking.
- `frontend/`: separate Poetry project and Streamlit UI.
- `etl/`: TMDB extraction, atomic DuckDB preparation, optional EDA notebook.
- `tests/`: offline API, ranking, extraction and UI request tests; synthetic fixtures.
- `products/`: upstream executed notebooks kept as historical reference, not runtime data.
- `Containerfile`: separate backend/frontend targets; `scripts/`: Podman startup.

Browser → Streamlit `:8501` → `http://backend:8000` on `siw-net` → read-only DuckDB in `siw-data`. An initialization container prepares data and exits. See [architecture](docs/architecture.md).

Additional documentation: [technical docs](docs/architecture.md),
[troubleshooting](docs/troubleshooting.md), and [demo checklist](docs/demo.md).

Movie data and images: TMDB. This product uses the TMDB API but is not endorsed
or certified by TMDB.
