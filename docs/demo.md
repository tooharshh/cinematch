# Capstone demonstration

1. Show Linux CLI, source tree, licence and upstream revision. Explain your additions separately from inherited code.
2. Show `Containerfile`: base images, locked dependencies, non-root user, ports, startup and health checks.
3. Build both targets with the README commands; show `podman images` and image inspection.
4. Initialize live data with your key, or explicitly announce that the fixture is synthetic test data.
5. Run `bash scripts/podman-start.sh live` (first live initialization), `fixture` (first synthetic initialization), or `existing` (already populated volume).
6. Open the UI and show the cinematic homepage, poster shelves and Indian-cinema collection. Search `Inception` if available and choose its poster to reveal five recommendations. Select a recommendation to continue discovery. Explain overview/genres/cosine similarity; try an unavailable title and show year/language distinctions for duplicate titles.
7. Show `podman ps`, network inspection, volume inspection and loopback port mappings. Prove service DNS with an HTTP request from the frontend container:

   ```bash
   podman exec frontend python -c "import requests; print(requests.get('http://backend:8000/health', timeout=5).json())"
   ```

8. Show stop/start/restart, logs and a disposable missing-data failure (troubleshooting guide).
9. Demonstrate persistence without deleting resources: stop application containers, rename them to unused backup names with `podman rename`, and run the startup script in `existing` mode. Compare `/health` counts and a known recommendation. The volume is unchanged. Check backup names are free before renaming.
10. With explicit publishing authorization, tag/push/pull both images to your own registry namespace. Compare digests and run pulled images under distinct test names.
11. Show `poetry run pytest -q`, GitHub-ready documentation and actual verification evidence. Do not claim unexecuted registry/live-data operations succeeded.

A good viva explanation: “TF-IDF gives important words more weight. Cosine similarity compares the direction of movie text vectors. Genres are repeated twice to give them extra influence. DuckDB stores the catalog; Podman isolates the UI and API while a volume keeps the catalog across container replacement.”
