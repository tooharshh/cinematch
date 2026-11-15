"""Add featured-film backdrop metadata to an existing catalog; stop serving before use."""
import argparse
import logging
import os

import duckdb
import requests
from dotenv import load_dotenv

from app.config import database_path
from app.recommender import poster_url
from .prepare import request_json

logger = logging.getLogger(__name__)


def enrich_backdrops(path, movie_ids, api_key):
    if not api_key:
        raise ValueError("Set API_KEY before fetching backdrop metadata")
    if not path.is_file():
        raise ValueError("Initialize the catalog before enriching it")
    if not movie_ids or len(movie_ids) > 10 or any(mid <= 0 for mid in movie_ids):
        raise ValueError("Choose between one and ten positive movie IDs")
    with duckdb.connect(str(path), read_only=True) as con:
        existing = {row[0] for row in con.execute("SELECT id FROM movies").fetchall()}
    updates = []
    with requests.Session() as session:
        for movie_id in dict.fromkeys(movie_ids):
            if movie_id not in existing:
                continue
            data = request_json(session, f"movie/{movie_id}", api_key, language="en-US")
            backdrop = data.get("backdrop_path")
            if poster_url(backdrop):
                updates.append((backdrop, movie_id))
    with duckdb.connect(str(path)) as con:
        con.execute("BEGIN TRANSACTION")
        try:
            for table in ("movies", "movie_genre_data"):
                columns = {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}
                if "backdrop_path" not in columns:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN backdrop_path VARCHAR")
                if updates:
                    con.executemany(f"UPDATE {table} SET backdrop_path=? WHERE id=?", updates)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    logger.info("Updated backdrop metadata for %s featured films", len(updates))
    return len(updates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--movie-id", type=int, nargs="+", default=[157336, 27205, 438631])
    args = parser.parse_args()
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    try:
        enrich_backdrops(database_path(), args.movie_id, os.getenv("API_KEY"))
    except Exception as exc:
        logger.error("Backdrop enrichment failed: %s", exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
