# Adapted from upstream container files: locked installs, no data or secrets at build time.
FROM docker.io/library/python:3.10-slim AS poetry
ENV PIP_NO_CACHE_DIR=1 POETRY_NO_INTERACTION=1 POETRY_VIRTUALENVS_CREATE=false
RUN pip install poetry==1.6.1
WORKDIR /build

FROM poetry AS backend-deps
COPY pyproject.toml poetry.lock ./
RUN poetry export --without-hashes -o requirements.txt

FROM docker.io/library/python:3.10-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/movies_data.duckdb
WORKDIR /app
COPY --from=backend-deps /build/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser:appuser /data
COPY app ./app
COPY etl ./etl
COPY tests/fixtures/catalog.json ./tests/fixtures/catalog.json
COPY LICENSE ./LICENSE
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM poetry AS frontend-deps
COPY frontend/pyproject.toml frontend/poetry.lock ./
RUN poetry export --without-hashes -o requirements.txt

FROM docker.io/library/python:3.10-slim AS frontend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BACKEND_URL=http://backend:8000 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
WORKDIR /app
COPY --from=frontend-deps /build/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --uid 10001 --create-home appuser
COPY frontend/frontend_app.py ./frontend_app.py
COPY frontend/assets ./assets
COPY frontend/.streamlit ./.streamlit
COPY LICENSE ./LICENSE
USER appuser
EXPOSE 8501
CMD ["streamlit", "run", "frontend_app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
