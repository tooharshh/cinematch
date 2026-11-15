"""Adapted from MagnusS0/movie-rec-system: cached TF-IDF and ID-safe ranking."""
import json
import re
from functools import lru_cache
from threading import RLock

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .config import database_path
from .recommenderhelper import retrieve_and_transform_data, compute_tfidf_vectorization


def poster_url(path):
    """Use a bounded TMDB CDN path; never expose credentials in image URLs."""
    if isinstance(path, str) and re.fullmatch(r"/[A-Za-z0-9]+\.(?:jpg|jpeg|png|webp)", path):
        return "https://image.tmdb.org/t/p/w500" + path
    return None


COLLECTIONS = {
    "popular": {"title": "Popular in the collection", "description": "A starting point for your next movie night."},
    "indian": {"title": "Stories from Indian cinema", "description": "Hindi, Tamil, Telugu and Malayalam. A world of stories."},
    "science-fiction": {"title": "Beyond the ordinary", "description": "New worlds. Big ideas. Science fiction.", "genre": "Science Fiction"},
    "thriller": {"title": "Keep the lights on", "description": "Thrillers for a night on the edge of your seat.", "genre": "Thriller"},
    "top-rated": {"title": "Highly rated, worth discovering", "description": "Highest catalog ratings among films with at least 500 votes."},
    "tamil": {"title": "Spotlight on Tamil cinema", "description": "Explore stories in Tamil.", "language": "ta"},
    "malayalam": {"title": "Malayalam, a little closer", "description": "Big stories, told differently.", "language": "ml"},
    "all": {"title": "Find your kind of cinema", "description": "Explore the full collection, one great film at a time."},
}


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
            "poster_url": poster_url(row.get("poster_path")),
            "backdrop_url": (poster_url(row.get("backdrop_path")) or "").replace("/w500/", "/w1280/") or None,
            "language": str(row.get("original_language") or ""),
            "vote_count": int(row.vote_count),
        }

    def search(self, query, limit=20, include_details=False):
        key = normalize_title(query)
        if not key:
            return []
        indices = np.flatnonzero(self.keys.str.contains(key, regex=False).to_numpy())
        titles = self.keys.iloc[indices].to_numpy()
        ids = self.df.id.to_numpy()[indices]
        order = np.lexsort((ids, titles, titles != key))
        results = [self.details(int(i)) for i in indices[order][:limit]]
        return results if include_details else [{k: v for k, v in m.items() if k in ("id", "title", "year")} for m in results]

    def movie(self, movie_id):
        indices = np.flatnonzero(self.df.id.to_numpy() == movie_id)
        return self.details(int(indices[0])) if len(indices) else None

    def browse(self, collection="popular", offset=0, limit=24):
        if collection not in COLLECTIONS:
            raise ValueError("Unknown collection")
        frame = self.df
        language = COLLECTIONS[collection].get("language")
        genre = COLLECTIONS[collection].get("genre")
        if language:
            frame = frame[frame.original_language.eq(language)]
        if collection == "indian":
            frame = frame[frame.original_language.isin(["hi", "ta", "te", "ml"])]
        if genre:
            frame = frame[frame.genre_names.str.split(", ").map(lambda genres: genre in genres)]
        if collection == "top-rated":
            frame = frame[frame.vote_count.ge(500)].sort_values(
                ["vote_average", "vote_count", "id"], ascending=[False, False, True])
        else:
            frame = frame.sort_values(["popularity", "vote_count", "id"], ascending=[False, False, True])
        return {"collection": collection, "title": COLLECTIONS[collection]["title"],
                "description": COLLECTIONS[collection]["description"], "total": len(frame),
                "movies": [self.details(int(i)) for i in frame.iloc[offset:offset + limit].index]}

    def discovery(self):
        favorite = self.search("Interstellar", 10, include_details=True)
        featured = next((m for m in favorite if normalize_title(m["title"]) == "interstellar"), None)
        if featured is None:
            featured = self.browse("popular", limit=1)["movies"][0]
        keys = ["popular", "indian", "science-fiction", "thriller", "top-rated", "malayalam"]
        shelves = [self.browse(key, limit=12) for key in keys]
        return {"featured": featured, "shelves": [s for s in shelves if s["movies"]],
                "total": len(self.df), "catalog_source": self.source}

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
        # Sort numeric arrays in NumPy instead of constructing a pandas row per candidate.
        # Movie ID remains the deterministic tie-breaker, including identical vectors.
        order = np.lexsort((self.df.id.to_numpy(), -scores))
        selected = order[order != index][:num_rec].tolist()
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
