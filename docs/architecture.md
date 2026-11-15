# Architecture and design

The upstream split remains: FastAPI owns catalog access and ranking; Streamlit only calls HTTP endpoints. DuckDB remains an embedded database, not a third service.

## Recommendation flow

1. Normalize lookup text using casefold and whitespace normalization; keep original display titles.
2. Search the cached catalog and select a stable TMDB ID (title/year help distinguish remakes).
3. Combine overview with genre names repeated twice, preserving upstream weighting.
4. Fit scikit-learn TF-IDF once per process, with English stop words.
5. Compute cosine similarity between one selected sparse row and the catalog.
6. Exclude the source ID, sort descending by score and then ascending ID for ties, and return five alternatives.

Ranking and title-search ordering use NumPy arrays rather than constructing pandas rows for all candidates. Poster URLs are derived from validated TMDB paths; the browser lazy-loads displayed posters directly from the public image CDN, without credentials or database image blobs.

There is no per-request N×N matrix. A single backend worker caches one snapshot. Restart after preparation; do not refresh while serving. Exact duplicate IDs are removed, while distinct movies sharing a title remain available.

## Preparation and storage

TMDB discovery gathers bounded per-language snapshots with English metadata. Only released movies with nonempty overviews and at least ten votes are collected, avoiding descriptionless upcoming titles dominating genre-only matches. Requests have timeouts and bounded retries. Missing credentials, bad responses and empty total results fail clearly. Empty pages terminate collection; duplicate pages cannot loop indefinitely.

Preparation writes `movies`, `genres`, and `movie_genre_data` to a temporary DuckDB file in the destination directory. It validates text vectorization before atomically replacing the target. Failed preparation leaves the old catalog untouched. Stop readers first: an atomic file rename is not a cache refresh or a concurrent-write mechanism.

The catalog includes a source metadata table (`synthetic`, `tmdb`, or legacy `unknown`); the API exposes the source and the UI labels synthetic results.

The initializer and backend use the same image. A named volume holds `/data`; the initializer writes and exits, then the backend mounts it read-only. Podman's fresh named-volume ownership follows the image user. Existing incorrectly owned volumes need explicit diagnosis, not broad permission changes.

## Container boundary

Two non-root containers join `siw-net`; the UI addresses `backend:8000`. Host ports are bound to loopback for a local course demonstration. Neither the UI nor backend runtime needs the TMDB key. Only initialization gets `.env`, with `DATABASE_PATH` explicitly set for the volume. Logs go to standard output/error.

The Python/Poetry locks intentionally start from upstream. Notebook tools remain in the backend dependency set for reproducibility; reducing runtime-only dependencies is a future optimization, not required for this capstone.

## Browse-first presentation

The Streamlit client uses additive catalog endpoints for a featured movie, small poster shelves and paginated collections. A query string identifies the selected movie, search or collection, so native links and browser Back remain usable. The existing recommendation endpoint still returns five cosine-ranked alternatives by default.

Backdrop paths are optional metadata. Existing catalogs can be enriched for selected films through a stopped-backend maintenance command; fresh preparation preserves paths from TMDB responses. The frontend falls back to a poster when no backdrop is available. Fonts are licensed local assets, embedded in CSS for compatibility with the pinned Streamlit version.
