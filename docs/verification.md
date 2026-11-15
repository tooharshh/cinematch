# Verification record

Date: 2026-11-15. Upstream revision: `a46de1bdd4b43e78f234b066aa085e88c0397527`.

## Application checks completed

- Python 3.10.21, original backend locked dependencies installed into `.venv`.
- Original upstream tests: reproduced collection failure (`ModuleNotFoundError: movie_rec_system`).
- Updated suite: **37 passed** (including all four original API tests, adapted to isolated data).
- Two upstream SciPy/NumPy deprecation warnings; no test failures.
- Host rerun after formatting: **37 passed in 5.64 seconds**. Two sandboxed reruns stalled and were stopped; the host rerun passed.
- Python compilation, pyflakes for active code/tests, and shell syntax validation passed.
- CLI preparation produced a nine-movie synthetic database.
- Ploomber DAG loaded from `pipeline.yaml`, with test-only fixture/product overrides, built its database successfully. Live Ploomber extraction was not run.

## Container checks

Rootless Podman 5.8.7 is available on Fedora; network backend netavark with aardvark DNS and SELinux enabled. The following checks completed successfully:

- Built `localhost/siw-backend:0.1.0` (753 MB) and `localhost/siw-frontend:0.1.0` (490 MB); also applied local `capstone` tags.
- Started `backend` and `frontend` on `siw-net` with DNS enabled; published loopback ports 8000 and 8501.
- Initialized nine synthetic movies into `siw-data`; no API key supplied to either serving container.
- Both containers use `appuser`; backend mounts `/data` read-only. Frontend has no database mount.
- Replaced both original demo containers with new containers using the same named volume. Original demo containers remain stopped as `siw-backend-baseline` and `siw-frontend-baseline`; the pre-existing `itsharsh_site` was not modified.
- Tested frontend stop/start and backend restart. Catalog count/source remained unchanged; database SHA-256 before and after lifecycle checks: `b99633b9c9dec302ab29c12a2337f52cfd1a68be061a6ec59191672996d1c225`.
- Explicit `podman healthcheck run` passed for both services; both reported healthy.
- `scripts/verify-containers.py` passed API/ranking, unknown-title 404, frontend health, service DNS, non-root users, secret isolation, and read-only storage checks.
- Disposable missing-data container returned HTTP 503 and emitted a useful diagnostic; stopped it after inspection.
- Headless Chrome verified search, title/year selection, five rendered recommendations, synthetic-data warning, loaded local attribution logo, and unavailable-title handling that clears prior results.
- Found OCI build health-check omission during verification; moved health checks to Podman runtime options in the startup script.

Application: http://127.0.0.1:8501. API docs: http://127.0.0.1:8000/docs.

The synthetic fixture demonstrates operation, not real movie relevance. Build logs and browser screenshots were generated under `/tmp`; they are not committed artifacts.

## Pending external verification

No TMDB key was supplied. Live extraction and real-catalog recommendation relevance remain unverified; synthetic data does not establish recommendation quality.

Registry push/pull and GitHub publishing are not performed. They require explicit publishing authorization and the user's registry namespace/credentials. Git commits require user approval.

## Faculty-facing presentation update

The frontend is branded CineMatch with professional copy, a responsive warm-neutral theme, a featured closest-match card and a two-column recommendation layout. Credits and diagnostics are available in expandable panels. No joke tagline or repository name appears in the main interface.

Updated regression suite: **38 passed**. Headless Chrome verified the desktop search flow, five recommendation cards, demonstration-data notice, unavailable-title reset, and a 390px mobile layout without horizontal overflow. Provider content is HTML-escaped. The previous frontend container is retained stopped as `siw-frontend-before-polish`.
