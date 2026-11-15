# Adapted upstream tests: correct import and isolated catalog fixture.
from fastapi.testclient import TestClient
from app.app import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Welcome! You can use this API to get movie recommendations based on viewers' votes. Visit /docs for more information and to try it out!"  # noqa E501
    }


def test_recommendation_endpoint():
    test_data = {"movie": "Inception", "num_rec": 5}
    response = client.post("/recommendations/", json=test_data)
    assert response.status_code == 200

    response_data = response.json()
    assert response_data["movie"] == "inception"


def test_recommendation_for_nonexistent_movie():
    test_data = {"movie": "NonExistentMovie", "num_rec": 5}
    response = client.post("/recommendations/", json=test_data)
    assert response.status_code == 404


def test_recommendation_result():
    test_data = {"movie": "Inception", "num_rec": 5}
    response = client.post("/recommendations/", json=test_data)
    assert response.status_code == 200

    response_data = response.json()

    assert isinstance(response_data["movie"], str)

    assert isinstance(response_data["recommendations"], list)
    assert len(response_data["recommendations"]) == test_data["num_rec"]

    assert isinstance(response_data["metrics"], dict)
    metrics = response_data["metrics"]

    assert "popularity" in metrics
    assert "vote_avg" in metrics
    assert "vote_count" in metrics

    assert isinstance(metrics["popularity"], float)
    assert isinstance(metrics["vote_avg"], float)


def test_search_and_defaults():
    results = client.get('/movies', params={'query': 'echo'}).json()['movies']
    assert len(results) == 2
    response = client.post('/recommendations/', json={'movie': 'Inception'})
    assert len(response.json()['recommendations']) == 5
    assert client.get('/health').json()['status'] == 'ready'


def test_ambiguous_and_id_selection():
    response = client.post('/recommendations/', json={'movie': 'Echo'})
    assert response.status_code == 409
    assert len(response.json()['detail']['choices']) == 2
    assert client.post('/recommendations/',
                       json={'movie': 'Echo', 'movie_id': 8}).status_code == 200
    assert client.post('/recommendations/',
                       json={'movie': 'Echo', 'movie_id': 999}).status_code == 404


def test_invalid_inputs():
    for payload in [{'movie': '   '}, {'movie': ''}, {'movie': 'Inception', 'num_rec': 0},
                    {'movie': 'Inception', 'num_rec': 21}, {'movie': 'Inception', 'num_rec': 1.5},
                    {'movie': 'Inception', 'movie_id': -1}]:
        assert client.post('/recommendations/', json=payload).status_code == 422
    assert client.get('/movies', params={'query': 'x', 'limit': 100}).status_code == 422


def test_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'missing.duckdb'))
    assert client.get('/health').status_code == 503
    assert client.get('/movies', params={'query': 'x'}).status_code == 503
    assert client.post('/recommendations/', json={'movie': 'Inception'}).status_code == 503
