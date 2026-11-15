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


def test_live_catalog_skips_unreleased_and_descriptionless_movies(catalog_data):
    session = Mock()
    session.get.return_value.status_code = 200
    responses = [{'genres': catalog_data['genres']}]
    for language in ['en', 'hi', 'ta', 'te', 'ml']:
        movie = next(m for m in catalog_data['movies'] if m['original_language'] == language)
        responses.append({'results': [
            {**movie, 'id': 901, 'overview': '   '},
            {**movie, 'id': 902, 'release_date': '2999-01-01'},
            {**movie, 'id': 903, 'vote_count': 0},
            {**movie, 'id': 904, 'release_date': ''},
            movie,
        ]})
    session.get.return_value.json.side_effect = responses
    result, _ = fetch_catalog('key', per_language=1, session=session)
    assert len(result) == 5
    assert not {901, 902, 903, 904}.intersection(m['id'] for m in result)
    params = session.get.call_args.kwargs['params']
    assert params['vote_count.gte'] == 10
    assert 'primary_release_date.lte' in params


def test_total_target_fills_regional_shortfall_and_stops_at_last_page(catalog_data):
    session = Mock()
    session.get.return_value.status_code = 200
    responses = [{'genres': catalog_data['genres']}]
    # Target ten = two per language. Each regional catalog only has one eligible film.
    for language in ['hi', 'ta', 'te', 'ml']:
        movie = next(m for m in catalog_data['movies'] if m['original_language'] == language)
        responses.append({'results': [movie], 'total_pages': 1})
    english = next(m for m in catalog_data['movies'] if m['original_language'] == 'en')
    responses.append({'results': [{**english, 'id': 100 + i} for i in range(6)], 'total_pages': 1})
    session.get.return_value.json.side_effect = responses
    result, _ = fetch_catalog('key', session=session, total_movies=10)
    assert len(result) == 10
    assert sum(m['original_language'] == 'en' for m in result) == 6
    assert session.get.call_count == 6


def test_backdrop_enrichment_is_idempotent(isolated_catalog, monkeypatch):
    from etl.enrich_backdrops import enrich_backdrops
    from app.recommender import Catalog
    fetch = Mock(return_value={'backdrop_path': '/scene123.jpg'})
    monkeypatch.setattr('etl.enrich_backdrops.request_json', fetch)
    assert enrich_backdrops(isolated_catalog, [1], 'test-key') == 1
    assert enrich_backdrops(isolated_catalog, [1], 'test-key') == 1
    assert Catalog(isolated_catalog).movie(1)['backdrop_url'] == 'https://image.tmdb.org/t/p/w1280/scene123.jpg'


def test_backdrop_failed_fetch_preserves_catalog(isolated_catalog, monkeypatch):
    from etl.enrich_backdrops import enrich_backdrops
    before = isolated_catalog.read_bytes()
    monkeypatch.setattr('etl.enrich_backdrops.request_json', Mock(side_effect=RuntimeError('provider failed')))
    with pytest.raises(RuntimeError):
        enrich_backdrops(isolated_catalog, [1], 'test-key')
    assert isolated_catalog.read_bytes() == before
