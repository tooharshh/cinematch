"""Adapted upstream API: catalog search, validated inputs and explicit readiness."""
import json
import logging

from fastapi import FastAPI, HTTPException, Query, Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from .recommender import AmbiguousTitle, CatalogUnavailable, get_catalog, get_recommendation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="CineMatch", version="0.1.0")


@app.get("/")
def root():
    return {"message": "Welcome! You can use this API to get movie recommendations based on viewers' votes. Visit /docs for more information and to try it out!"}


class RecommendationRequest(BaseModel):
    movie: str = Field(min_length=1, max_length=300)
    num_rec: int = Field(default=5, ge=1, le=20, strict=True)
    movie_id: int | None = Field(default=None, gt=0, strict=True)

    @field_validator("movie")
    @classmethod
    def format_movie_name(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter a movie title")
        return value


def unavailable(exc):
    logger.warning("Catalog not ready: %s", exc.__cause__ or exc)
    return HTTPException(status_code=503, detail=str(exc))


@app.get("/health")
def health():
    try:
        catalog = get_catalog()
    except CatalogUnavailable as exc:
        raise unavailable(exc) from exc
    return {"status": "ready", "movies": len(catalog.df), "catalog_source": catalog.source}


@app.get("/movies")
def movies(query: str = Query(min_length=1, max_length=300), limit: int = Query(default=20, ge=1, le=50), include_details: bool = False):
    try:
        catalog = get_catalog()
        return {"movies": catalog.search(query, limit, include_details=include_details), "catalog_source": catalog.source}
    except CatalogUnavailable as exc:
        raise unavailable(exc) from exc


@app.post("/recommendations/")
def get_movie_recommendations(request: RecommendationRequest):
    try:
        result = get_recommendation(request.movie, request.num_rec, movie_id=request.movie_id)
    except AmbiguousTitle as exc:
        raise HTTPException(status_code=409, detail={
                            "message": str(exc), "choices": exc.choices}) from exc
    except CatalogUnavailable as exc:
        raise unavailable(exc) from exc
    if result is None:
        raise HTTPException(
            status_code=404, detail="Movie not found in this catalog. Search available titles first.")
    return json.loads(result)


@app.get("/discover")
def discover():
    try:
        return get_catalog().discovery()
    except CatalogUnavailable as exc:
        raise unavailable(exc) from exc


@app.get("/browse")
def browse(collection: Literal["popular", "indian", "science-fiction", "thriller", "top-rated", "tamil", "malayalam", "all"] = "popular",
           offset: int = Query(default=0, ge=0, le=100000), limit: int = Query(default=24, ge=1, le=48)):
    try:
        return get_catalog().browse(collection, offset, limit)
    except CatalogUnavailable as exc:
        raise unavailable(exc) from exc


@app.get("/movies/{movie_id}")
def movie_details(movie_id: int = Path(gt=0)):
    try:
        movie = get_catalog().movie(movie_id)
    except CatalogUnavailable as exc:
        raise unavailable(exc) from exc
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found in this catalog")
    return movie
