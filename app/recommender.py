"""Adapted from MagnusS0/movie-rec-system: cached TF-IDF and ID-safe ranking."""
import json
from functools import lru_cache
from threading import RLock

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .config import database_path
from .recommenderhelper import retrieve_and_transform_data, compute_tfidf_vectorization


class CatalogUnavailable(RuntimeError):
    pass


class AmbiguousTitle(ValueError):
    def __init__(self, choices):
        self.choices = choices
        super().__init__("Several movies have that title. Choose a title and year.")


def normalize_title(title):
    return " ".join(title.casefold().split())


class Catalog:
    def __init__(self, path, stop_words="english"):
        try:
            self.df = retrieve_and_transform_data(path)
            self.matrix = compute_tfidf_vectorization(self.df, stop_words)
        except Exception as exc:
            raise CatalogUnavailable(
                "Catalog unavailable. Initialize the database, then restart the backend.") from exc
        self.source = self.df.attrs.get("source", "unknown")
        self.keys = self.df.title.map(normalize_title)

    def details(self, index):
        row = self.df.iloc[index]
        date = str(row.release_date or "")
        return {
            "id": int(row.id), "title": str(row.title),
            "year": date[:4] if len(date) >= 4 else None,
            "genres": str(row.genre_names), "overview": str(row.overview),
            "rating": float(row.vote_average),
        }

    def search(self, query, limit=20):
        key = normalize_title(query)
        if not key:
            return []
        indices = [i for i, title in enumerate(self.keys) if key in title]
        indices.sort(key=lambda i: (self.keys.iloc[i] !=
                     key, self.keys.iloc[i], int(self.df.iloc[i].id)))
        return [{k: v for k, v in self.details(i).items() if k in ("id", "title", "year")} for i in indices[:limit]]

    def recommend(self, movie, num_rec=5, movie_id=None):
        if not 1 <= num_rec <= 20:
            raise ValueError("num_rec must be between 1 and 20")
        if movie_id is not None:
            matches = np.flatnonzero(self.df.id.to_numpy() == movie_id)
        else:
            matches = np.flatnonzero(self.keys.to_numpy() == normalize_title(movie))
        if not len(matches):
            return None
        if len(matches) > 1:
            raise AmbiguousTitle([self.details(int(i)) for i in matches])
        index = int(matches[0])
        scores = cosine_similarity(self.matrix[index], self.matrix).ravel()
        candidates = [i for i in range(len(scores)) if i != index]
        candidates.sort(key=lambda i: (-float(scores[i]), int(self.df.iloc[i].id)))
        selected = candidates[:num_rec]
        details = [{**self.details(i), "similarity": round(float(scores[i]), 6)} for i in selected]
        metrics = {}
        for field, name in [("popularity", "popularity"), ("vote_average", "vote_avg"), ("vote_count", "vote_count")]:
            values = self.df.iloc[selected][field].to_numpy(dtype=float)
            metrics[name] = round(
                float(np.sqrt(np.mean((values - float(self.df.iloc[index][field])) ** 2))), 3) if selected else 0.0
        return {
            "movie": normalize_title(self.df.iloc[index].title),
            "recommendations": [normalize_title(d["title"]) for d in details],
            "recommendation_details": details, "metrics": metrics,
        }


# lru_cache alone permits simultaneous first-call computation; serialize initialization.
_catalog_lock = RLock()


@lru_cache(maxsize=4)
def _load_catalog(path, stop_words):
    return Catalog(path, stop_words)


def get_catalog(stop_words="english"):
    with _catalog_lock:
        return _load_catalog(str(database_path()), stop_words)


def clear_catalog_cache():
    with _catalog_lock:
        _load_catalog.cache_clear()


def get_recommendation(movie: str, num_rec: int = 5, stop_words="english", movie_id=None):
    """Keep the upstream JSON-string interface for Python callers."""
    result = get_catalog(stop_words).recommend(movie, num_rec, movie_id)
    return json.dumps(result, allow_nan=False) if result is not None else None
