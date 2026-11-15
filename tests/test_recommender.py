import numpy as np
import pytest
from app.recommender import CatalogUnavailable, get_catalog


def test_rank_matches_full_cosine_and_excludes_source():
    from sklearn.metrics.pairwise import cosine_similarity
    catalog = get_catalog()
    result = catalog.recommend('  INCEPTION  ')
    assert len(result['recommendation_details']) == 5
    assert result['recommendation_details'][0]['title'] == 'Dream Courier'
    full = cosine_similarity(catalog.matrix)
    expected = sorted(range(1, len(catalog.df)),
                      key=lambda i: (-full[0, i], int(catalog.df.iloc[i].id)))[:5]
    assert [m['id'] for m in result['recommendation_details']] == [
        int(catalog.df.iloc[i].id) for i in expected]
    scores = [m['similarity'] for m in result['recommendation_details']]
    assert scores == sorted(scores, reverse=True)
    assert 1 not in [m['id'] for m in result['recommendation_details']]


def test_vectors_cached_and_only_one_query_row(monkeypatch):
    import app.recommender as module
    catalog = get_catalog()
    assert catalog is get_catalog()
    original = module.cosine_similarity

    def compare(a, b):
        assert a.shape[0] == 1
        return original(a, b)
    monkeypatch.setattr(module, 'cosine_similarity', compare)
    catalog.recommend('Inception')
    catalog.recommend('Inception')


def test_duplicate_titles_selected_by_id():
    result = get_catalog().recommend('Echo', movie_id=8)
    assert 8 not in [m['id'] for m in result['recommendation_details']]
    assert len({m['id'] for m in result['recommendation_details']}) == 5


def test_small_catalog_and_tied_self_exclusion(tmp_path, catalog_data):
    from etl.prepare import build_database
    from app.recommender import Catalog
    movies = catalog_data['movies'][:2]
    movies[1]['overview'] = movies[0]['overview']
    path = tmp_path / 'small.duckdb'
    build_database(path, movies, catalog_data['genres'])
    catalog = Catalog(path)
    for movie in movies:
        result = catalog.recommend(movie['title'], movie_id=movie['id'])
        assert len(result['recommendations']) == 1
        assert result['recommendation_details'][0]['id'] != movie['id']


def test_unavailable_database(monkeypatch, tmp_path):
    path = tmp_path / 'absent.duckdb'
    monkeypatch.setenv('DATABASE_PATH', str(path))
    with pytest.raises(CatalogUnavailable):
        get_catalog()
    assert not path.exists()


def test_null_text_and_nonfinite_numbers(tmp_path, catalog_data):
    from etl.prepare import build_database
    from app.recommender import Catalog
    movies = catalog_data['movies'][:2]
    movies[0]['overview'] = None
    movies[0]['popularity'] = float('inf')
    path = tmp_path / 'nulls.duckdb'
    build_database(path, movies, catalog_data['genres'])
    result = Catalog(path).recommend('Inception')
    assert np.isfinite(result['metrics']['popularity'])


def test_punctuation_search_and_original_case(tmp_path, catalog_data):
    from etl.prepare import build_database
    from app.recommender import Catalog
    catalog_data['movies'][0]['title'] = "A Hero's Journey: Part II"
    path = tmp_path / 'punctuation.duckdb'
    build_database(path, catalog_data['movies'], catalog_data['genres'])
    catalog = Catalog(path)
    assert catalog.search("hero's")[0]['title'] == "A Hero's Journey: Part II"
    assert catalog.recommend(" a HERO'S journey: part II ") is not None
    assert catalog.search('   ') == []


@pytest.mark.parametrize('path', [None, '', '/poster.jpg" onerror=alert(1)', 'https://evil.test/a.jpg', '/../a.jpg'])
def test_poster_url_rejects_missing_or_untrusted_paths(path):
    from app.recommender import poster_url
    assert poster_url(path) is None


def test_poster_url_uses_public_cdn_without_key():
    from app.recommender import poster_url
    assert poster_url('/abc123.jpg') == 'https://image.tmdb.org/t/p/w500/abc123.jpg'
