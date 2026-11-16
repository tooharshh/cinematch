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

Initial verification used synthetic data. Live TMDB verification was subsequently completed as recorded below. Recommendation relevance has not been systematically graded; operational checks do not establish recommendation quality.

Registry push/pull and GitHub publishing are not performed. They require explicit publishing authorization and the user's registry namespace/credentials. Git commits require user approval.

## Faculty-facing presentation update

The frontend is branded CineMatch with professional copy, a responsive warm-neutral theme, a featured closest-match card and a two-column recommendation layout. Credits and diagnostics are available in expandable panels. No joke tagline or repository name appears in the main interface.

Updated regression suite: **38 passed**. Headless Chrome verified the desktop search flow, five recommendation cards, demonstration-data notice, unavailable-title reset, and a 390px mobile layout without horizontal overflow. Provider content is HTML-escaped. The previous frontend container is retained stopped as `siw-frontend-before-polish`.

## Live TMDB catalog verification

A user-supplied key in the ignored `.env` was used only by the temporary initializer. The demo catalog was backed up inside the data volume before replacement.

The first live import exposed sparse upcoming-film records dominating genre-only matches. The importer now requires released movies with nonempty overviews and at least ten votes, applies provider discovery filters, and continues bounded pagination to fill each language quota. A regression test covers unreleased, unrated and descriptionless records.

- Final catalog: **1,000 real movies**; **200 each** for `en`, `hi`, `ta`, `te` and `ml`, with English metadata.
- Zero duplicate IDs; zero empty overviews, missing/future release dates, or records with fewer than ten votes.
- `/health` reports `catalog_source: tmdb`; both serving containers remain free of the API key.
- Searches verified for Inception, Interstellar, Dangal, RRR, Vikram and Drishyam.
- Inception returned five distinct alternatives with overviews and metadata; source ID excluded.
- Browser verified real search and five result cards with no demonstration-data notice.
- Container smoke checks passed. Updated offline test suite: **39 passed**.

The live catalog is stored in the persistent volume, not committed to Git. These checks confirm data integrity and operation, not a formal recommendation-quality benchmark.

## 10,000-movie catalog, posters and performance

The live catalog was expanded to **10,000 distinct eligible movies**. Counts: English 6,215; Hindi 1,820; Tamil 735; Malayalam 706; Telugu 524. Regional quotas were attempted first; English filled the shortfall. The new snapshot was prepared alongside the live file, validated, then published with a backup and brief backend restart. The supervising process exited unexpectedly while the initializer kept running; the completed staged database was independently validated before publication.

All records satisfy the release-date, overview and vote-count rules. **9,996 movies have poster paths**; absent paths display a placeholder. The API exposes only validated public CDN URLs, with no key. Browser checks loaded all five result posters successfully and verified mobile layout. Images are lazy-loaded for displayed results, not stored in DuckDB.

Actual measurements on this machine, single-user/local execution:

| Measurement | Result |
|---|---:|
| Database file | 12.51 MiB |
| Cold database load + TF-IDF | 0.35 s |
| Recommendation function median, 25 varied IDs | 5.91 ms |
| Search function median, five queries | 2.85 ms |
| Local HTTP recommendation median, 25 Inception requests | 7.99 ms |
| Local HTTP recommendation maximum in that sample | 11.15 ms |
| Peak RSS of fresh benchmark Python process | 169.2 MiB |

These numbers exclude poster-download time and are not a concurrent-user load test. The peak memory figure describes the benchmark process, not total host or stack memory. Reproduce the engine checks with `podman exec -i backend python - < scripts/benchmark_engine.py`.

An earlier scaling experiment repeated the 1,000-row dataset in memory with distinct IDs. At 25,000 rows, optimized recommendation median was 16.44 ms and search median 12.64 ms. Repeated text understates vocabulary diversity: this is a scaling estimate, not verification of 25,000 distinct movies. Before optimization, that experiment took 777.91 ms per recommendation; numeric NumPy sorting replaced pandas row construction per candidate without changing ranking/tie behavior.

Updated test suite: **47 passed**. No new Git commit or registry publishing was performed.

A repeat using the checked-in engine benchmark measured 0.911 s cold load/TF-IDF, 11.5 ms recommendation median, 7.18 ms search median and 173.8 MiB peak process RSS. Run-to-run variation reflects machine load; the figures are samples, not latency guarantees.

## Focused web UI skills review

`npm`/`npx` were not on PATH. An official portable Node.js LTS archive was downloaded under `/tmp`, checked against Node's published SHA-256 list, and used to run `npx ui-skills list` (CLI 0.2.4; 804 catalog entries). The application remains Python/Streamlit.

Only three skills were installed into the user's Codex skill directory and applied: `baseline-ui`, `fixing-accessibility`, and `ui-ux-pro-max`. UI UX Pro Max was installed from upstream revision `1f50119f717e935f135d605ce537223d1d7a0dac`; its UX searches returned specific keyboard-focus, readable-text, and contrast guidance. No native-mobile, 3D, or framework migration guidance was applied.

Targeted changes: readable synopsis/metadata sizes, darker genre and placeholder text, visible 3px keyboard focus, clearer input/select boundaries, tabular numeric labels, balanced wrapping, a header landmark instead of a navigation landmark with no links, a contextual recommendation status, and a local SVG favicon.

Before correction, genre text on the featured card measured **4.05:1**, and placeholder text **3.80:1**. Browser measurements after correction: featured genres **4.72:1**, overview **5.63:1**, metadata **4.72:1**.

Verification: **47 tests passed**; keyboard-only search and discovery worked; input/button focus was visible; poster alternatives and result status were present. Layout checks passed at 375, 768, 1024 and 1440 pixels, 844×390 landscape, and 200% text enlargement at 375px without horizontal overflow. Reduced-motion preference was emulated; no custom motion was added. This is a scoped review, not a WCAG conformance certification or testing with every screen reader.

## Streaming-style interface and font pairing

The entire faculty-facing interface was revamped while retaining the original service architecture and recommendation method. The homepage has a real Interstellar backdrop, six bounded poster shelves, filtered collections, pagination and title search. Movie posters link to focused movie pages with five recommendations and further poster-to-poster discovery.

Added `/discover`, `/browse`, `/movies/{movie_id}`, and optional detailed search responses. Backdrop enrichment for three featured films completed after a database backup; future imports preserve backdrop metadata. The catalog remains 10,000 movies in the existing volume.

**62 tests passed**. Browser checks passed for hero keyboard activation, recommendation chaining, Indian-cinema filtering, non-overlapping pagination, browser Back, keyboard search, selected poster results, empty searches and invalid links. Testing found a Streamlit rerun issue that rendered results but dropped the URL update; it was fixed and regression-tested.

Funnel Display and DM Sans were downloaded from the official Google Fonts repository, their OFL licences retained, and their loaded font faces and intended roles verified in Chrome. Responsive checks passed at 375, 768, 1024 and 1440px, 844×390 landscape, 200% text enlargement and reduced-motion preference.

The [attention-priority sketch](ui-attention-map.png) is generated from DOM geometry and manually assigned weights. It is explicitly not eye tracking, click data, gaze probability or evidence of engagement uplift. Method and sources are in [UI design notes](ui-design.md). No behavioral tracking was introduced.


## Public container registry publication

Date: 2026-11-16. This completes the registry step that was pending in the earlier records above.

Built both Containerfile targets from application revision `e6d35ae77d0d881e14ec20d9ee33543d134b1626`
using rootless Podman. Published both images to GitHub Container Registry with
`0.1.0` and `latest` tags. GitHub reports both packages as **public**.

| Component | Public package | Registry manifest digest (both tags) |
|---|---|---|
| Backend | [cinematch-backend](https://github.com/users/tooharshh/packages/container/package/cinematch-backend) | `sha256:3d0cfdfe8d5dfe554a107ebe0011bb0b8efa50790e364c9eb10b4b2a8f12e42f` |
| Frontend | [cinematch-frontend](https://github.com/users/tooharshh/packages/container/package/cinematch-frontend) | `sha256:4f62c336ee83e049554fb98b6537f3def1b6247929ea548e2fe8b3133fe7eaea` |

Verification completed:

- Offline regression suite: **62 passed**, with two existing SciPy/NumPy deprecation warnings.
- Pulled all four registry tags with an explicitly empty registry credentials file;
  no registry login was used. All pulled manifest digests matched the pushed digests.
- Ran the pulled versioned images in an isolated Podman network with a temporary
  nine-movie synthetic catalog. Verified backend readiness, CineMatch API metadata,
  five recommendations, frontend-to-backend DNS, and Streamlit health.
- Stopped and started the frontend, then repeated the application checks successfully.
- Inspected both running containers and confirmed they use `appuser`; inspected logs.
- Removed the temporary test containers and network. Existing application containers
  and persistent catalogs were not changed.

The images include source, dependencies, licences and the synthetic catalog fixture.
Private configuration, TMDB credentials and the live database are excluded.
The README provides public image links and the Podman pull/start commands.
