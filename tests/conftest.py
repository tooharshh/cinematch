import json
from pathlib import Path

import pytest
from app.recommender import clear_catalog_cache
from etl.prepare import build_database


@pytest.fixture
def catalog_data():
    return json.loads(Path('tests/fixtures/catalog.json').read_text())


@pytest.fixture(autouse=True)
def isolated_catalog(tmp_path, monkeypatch, catalog_data):
    path = tmp_path / 'movies.duckdb'
    build_database(path, catalog_data['movies'], catalog_data['genres'])
    monkeypatch.setenv('DATABASE_PATH', str(path))
    clear_catalog_cache()
    yield path
    clear_catalog_cache()
