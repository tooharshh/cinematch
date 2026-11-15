#!/usr/bin/env python3
"""Read-only engine benchmark. Run in the backend via stdin; see README."""
import argparse
import json
import resource
import statistics
import sys
import time
from pathlib import Path

# Also allow running directly from a local checkout with DATABASE_PATH configured.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import database_path  # noqa: E402
from app.recommender import get_catalog  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations', type=int, default=25)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 1000:
        parser.error('iterations must be between 1 and 1000')
    start = time.perf_counter()
    catalog = get_catalog()
    cold = time.perf_counter() - start
    timings = []
    for i in range(args.iterations):
        index = (i * 397) % len(catalog.df)
        movie_id = int(catalog.df.iloc[index].id)
        start = time.perf_counter()
        catalog.recommend('', movie_id=movie_id)
        timings.append((time.perf_counter() - start) * 1000)
    searches = []
    for query in ['a', 'Inception', 'star', 'love', 'the']:
        start = time.perf_counter()
        catalog.search(query)
        searches.append((time.perf_counter() - start) * 1000)
    print(json.dumps({
        'movies': len(catalog.df),
        'database_mb': round(database_path().stat().st_size / 1024**2, 2),
        'cold_load_and_tfidf_seconds': round(cold, 3),
        'recommendation_median_ms': round(statistics.median(timings), 2),
        'recommendation_max_ms': round(max(timings), 2),
        'search_median_ms': round(statistics.median(searches), 2),
        'peak_process_rss_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        'iterations': args.iterations,
    }, indent=2))


if __name__ == '__main__':
    main()
