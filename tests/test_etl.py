from unittest.mock import Mock

import duckdb
import pytest
import requests

from etl.prepare import build_database, fetch_catalog, request_json


def test_repeat_refresh_and_failed_validation_preserve_snapshot(isolated_catalog, catalog_data):
    before = isolated_catalog.read_bytes()
    with pytest.raises(Exception):
        build_database(isolated_catalog, [
                       {'id': 1, 'title': 'Empty', 'overview': 'the and', 'genre_ids': []}], [])
    assert isolated_catalog.read_bytes() == before
    build_database(isolated_catalog, catalog_data['movies'] * 2, catalog_data['genres'])
    with duckdb.connect(str(isolated_catalog), read_only=True) as con:
        assert con.execute('SELECT count(*) FROM movies').fetchone()[0] == 9
        assert con.execute('SELECT count(*) FROM movie_genre_data').fetchone()[0] == 9
    assert not list(isolated_catalog.parent.glob('.siw-*'))


@pytest.mark.parametrize('status', [401, 429, 500])
def test_http_failure(status):
    session = Mock()
    session.get.return_value.status_code = status
    with pytest.raises(RuntimeError, match=f'HTTP {status}'):
        request_json(session, 'discover/movie', 'private-key')


@pytest.mark.parametrize('error', [requests.Timeout('secret URL'), ValueError('bad json')])
def test_request_errors_do_not_leak_key(error):
    session = Mock()
    session.get.side_effect = error
    with pytest.raises(RuntimeError) as exc:
        request_json(session, 'discover/movie', 'private-key')
    assert 'secret' not in str(exc.value)
    assert 'private-key' not in str(exc.value)


def test_missing_key():
    with pytest.raises(ValueError, match='API_KEY'):
        fetch_catalog('')


def test_empty_pages_terminate():
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.json.side_effect = [
        {'genres': [{'id': 1, 'name': 'Drama'}]}] + [{'results': []}] * 5
    with pytest.raises(RuntimeError, match='no movies'):
        fetch_catalog('key', session=session)
    assert session.get.call_count == 6


def test_language_filter_and_deduplication(catalog_data):
    session = Mock()
    session.get.return_value.status_code = 200
    movies = catalog_data['movies']
    responses = [{'genres': catalog_data['genres']}]
    for language in ['en', 'hi', 'ta', 'te', 'ml']:
        chosen = next(m for m in movies if m['original_language'] == language)
        responses.append({'results': [chosen, chosen]})
    session.get.return_value.json.side_effect = responses
    result, _ = fetch_catalog('key', per_language=1, session=session)
    assert len(result) == len({m['id'] for m in result}) == 5
    assert {m['original_language'] for m in result} == {'en', 'hi', 'ta', 'te', 'ml'}


def test_partial_failure_preserves_existing(isolated_catalog, monkeypatch):
    from etl.prepare import prepare
    before = isolated_catalog.read_bytes()
    monkeypatch.setattr('etl.prepare.fetch_catalog', Mock(side_effect=RuntimeError('failed page')))
    with pytest.raises(RuntimeError):
        prepare()
    assert isolated_catalog.read_bytes() == before


def test_invalid_json_body():
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.json.side_effect = ValueError('bad body')
    with pytest.raises(RuntimeError, match='request failed'):
        request_json(session, 'discover/movie', 'private-key')


def test_duplicate_pages_are_bounded(catalog_data):
    session = Mock()
    session.get.return_value.status_code = 200
    movie = catalog_data['movies'][0]

    def body():
        return {'genres': catalog_data['genres']} if session.get.call_count == 1 else {'results': [movie]}
    session.get.return_value.json.side_effect = body
    result, _ = fetch_catalog('key', per_language=20, session=session)
    assert len(result) == 1
    assert session.get.call_count == 16  # genres + three bounded pages per language


def test_incomplete_movie_record(catalog_data):
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.json.side_effect = [
        {'genres': catalog_data['genres']}, {'results': [{'id': 1}]}]
    with pytest.raises(RuntimeError, match='record is incomplete'):
        fetch_catalog('key', session=session)


def test_fixture_source_is_reported(tmp_path):
    from etl.prepare import prepare
    from app.recommender import Catalog
    path = tmp_path / 'labelled.duckdb'
    prepare(product={'data': path}, fixture='tests/fixtures/catalog.json')
    assert Catalog(path).source == 'synthetic'
