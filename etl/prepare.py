"""Prepare an atomic, bounded DuckDB snapshot; replaces upstream notebook schema setup.

Stop the backend before refresh. A failed extraction leaves the existing file untouched.
"""
import argparse
import json
import logging
import math
import os
import tempfile
from datetime import date
from pathlib import Path

import duckdb
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import database_path

logger = logging.getLogger(__name__)
LANGUAGES = ("en", "hi", "ta", "te", "ml")


def request_json(session, endpoint, api_key, **params):
    # Do not log response URLs: they include the API key.
    try:
        response = session.get(f"https://api.themoviedb.org/3/{endpoint}",
                               params={"api_key": api_key, **params}, timeout=(5, 30))
        if response.status_code != 200:
            raise RuntimeError(f"TMDB returned HTTP {response.status_code}")
        data = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError("TMDB request failed; check connectivity and credentials") from None
    if not isinstance(data, dict):
        raise RuntimeError("TMDB returned an invalid response")
    return data


def usable_movie(movie):
    """Exclude unreleased/descriptionless records that inflate genre-only matches."""
    overview = movie.get("overview")
    if not isinstance(overview, str) or not overview.strip():
        return False
    votes = movie.get("vote_count")
    if not isinstance(votes, int) or votes < 10:
        return False
    try:
        return date.fromisoformat(movie.get("release_date") or "") <= date.today()
    except (TypeError, ValueError):
        return False


def fetch_catalog(api_key, per_language=200, session=None, total_movies=None):
    if not api_key or not api_key.strip():
        raise ValueError("Set API_KEY in .env before live catalog initialization")
    if not 1 <= per_language <= 10000:
        raise ValueError("per_language must be between 1 and 10000")
    if total_movies is not None and not len(LANGUAGES) <= total_movies <= 25000:
        raise ValueError("total_movies must be between 5 and 25000")
    own_session = session is None
    session = session or requests.Session()
    if own_session:
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"], raise_on_status=False)))
    try:
        genres = request_json(session, "genre/movie/list", api_key, language="en-US").get("genres")
        if not isinstance(genres, list) or not genres or any(not isinstance(g, dict) or not isinstance(g.get("id"), int) or not isinstance(g.get("name"), str) for g in genres):
            raise RuntimeError("TMDB genre response is incomplete")
        movies = {}
        # For a total target, collect regional cinema first. English fills any shortfall.
        languages = (*LANGUAGES[1:], LANGUAGES[0]) if total_movies else LANGUAGES
        for language in languages:
            quota = (total_movies - len(movies) if language == 'en' else total_movies // len(LANGUAGES)) if total_movies else per_language
            language_ids = set()
            # Bounded even when the provider returns duplicate movies on every page.
            for page in range(1, min(500, math.ceil(quota / 20) * 3) + 1):
                data = request_json(session, "discover/movie", api_key, language="en-US", with_original_language=language,
                                    include_adult="false", sort_by="popularity.desc", page=page,
                                    **{"primary_release_date.lte": date.today().isoformat(), "vote_count.gte": 10})
                results = data.get("results")
                if not isinstance(results, list):
                    raise RuntimeError("TMDB movie response is incomplete")
                if not results:
                    break
                for movie in results:
                    if not isinstance(movie, dict) or not isinstance(movie.get("id"), int) or not isinstance(movie.get("title"), str):
                        raise RuntimeError("TMDB movie record is incomplete")
                    if movie.get("original_language") != language or not usable_movie(movie):
                        continue
                    movies[movie["id"]] = movie
                    language_ids.add(movie["id"])
                    if len(language_ids) >= quota:
                        break
                if len(language_ids) >= quota:
                    break
                total_pages = data.get("total_pages")
                if isinstance(total_pages, int) and page >= total_pages:
                    break
            logger.info("Collected %s movies for language %s", len(language_ids), language)
        if not movies:
            raise RuntimeError("TMDB returned no movies; old catalog preserved")
        return list(movies.values()), genres
    finally:
        if own_session:
            session.close()


def build_database(path, movies, genres, source="unknown"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    genre_map = {int(g["id"]): str(g["name"]) for g in genres}
    unique = {}
    for movie in movies:
        if not str(movie.get("title") or "").strip():
            continue
        unique[int(movie["id"])] = movie
    if not unique:
        raise ValueError("Catalog has no titled movies")
    fd, temporary = tempfile.mkstemp(prefix=".siw-", suffix=".duckdb.tmp", dir=path.parent)
    os.close(fd)
    os.unlink(temporary)  # DuckDB requires a new file, not an empty placeholder.
    try:
        with duckdb.connect(temporary) as con:
            con.execute("CREATE TABLE catalog_metadata (source VARCHAR)")
            con.execute("INSERT INTO catalog_metadata VALUES (?)", [source])
            con.execute("CREATE TABLE genres (id BIGINT PRIMARY KEY, name VARCHAR)")
            if genre_map:
                con.executemany("INSERT INTO genres VALUES (?, ?)", list(genre_map.items()))
            con.execute("""CREATE TABLE movies (
                id BIGINT PRIMARY KEY, title VARCHAR, overview VARCHAR, original_language VARCHAR,
                release_date VARCHAR, popularity DOUBLE, vote_average DOUBLE, vote_count BIGINT,
                genre_ids BIGINT[], poster_path VARCHAR, backdrop_path VARCHAR)""")

            def number(value):
                value = float(value or 0)
                return value if math.isfinite(value) else 0.0
            rows = []
            for mid, m in unique.items():
                rows.append((mid, m["title"].strip(), m.get("overview") or "", m.get("original_language") or "",
                             m.get("release_date") or "", number(
                                 m.get("popularity")), number(m.get("vote_average")),
                             int(number(m.get("vote_count"))), m.get("genre_ids") or [], m.get("poster_path"), m.get("backdrop_path")))
            con.executemany("INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
            con.execute("""CREATE TABLE movie_genre_data AS
                SELECT m.*, coalesce((SELECT string_agg(g.name, ', ' ORDER BY g.id)
                FROM genres g WHERE list_contains(m.genre_ids, g.id)), '') AS genre_names FROM movies m""")
            from app.recommender import Catalog
            # Validate after closing the writer below, including TF-IDF vocabulary.
        Catalog(temporary)
        os.replace(temporary, path)
        logger.info("Catalog ready: %s movies", len(unique))
        return len(unique)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(product=None, upstream=None, fixture=None, per_language=200, total_movies=None):
    load_dotenv()
    path = product["data"] if product is not None else database_path()
    if fixture:
        data = json.loads(Path(fixture).read_text())
        movies, genres = data["movies"], data["genres"]
    else:
        movies, genres = fetch_catalog(os.getenv("API_KEY"), per_language, total_movies=total_movies)
    return build_database(path, movies, genres, source="synthetic" if fixture else "tmdb")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture", help="Use a synthetic JSON fixture instead of TMDB (demo/testing only)")
    size = parser.add_mutually_exclusive_group()
    size.add_argument("--per-language", type=int, default=200)
    size.add_argument("--total-movies", type=int, help="Target total across five languages; English fills regional shortfalls")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        prepare(fixture=args.fixture, per_language=args.per_language, total_movies=args.total_movies)
    except Exception as exc:
        logger.error("Catalog preparation failed: %s", exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
