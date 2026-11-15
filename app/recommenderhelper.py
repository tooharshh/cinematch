"""Adapted upstream helpers: read-only catalog validation and original RMSE helpers."""
import duckdb
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def get_data(path=None) -> pd.DataFrame:
    from .config import database_path
    with duckdb.connect(str(path or database_path()), read_only=True) as con:
        df = con.execute("SELECT * FROM movie_genre_data ORDER BY id").fetchdf()
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        df.attrs["source"] = con.execute("SELECT source FROM catalog_metadata LIMIT 1").fetchone()[0] if "catalog_metadata" in tables else "unknown"
        return df


def create_combined(df: pd.DataFrame, weight=2):
    df["combined"] = df["overview"] + " " + (df["genre_names"] + ", ") * weight
    return df


def retrieve_and_transform_data(path=None) -> pd.DataFrame:
    df = get_data(path)
    required = {"id", "title", "overview", "genre_names",
                "release_date", "popularity", "vote_average", "vote_count"}
    if df.empty or not required.issubset(df.columns):
        raise ValueError("Empty or incomplete catalog")
    df = df.drop_duplicates("id").copy()
    df["id"] = pd.to_numeric(df["id"], errors="raise").astype("int64")
    df = df.drop_duplicates("id").reset_index(drop=True)
    for col in ["title", "overview", "genre_names", "release_date"]:
        df[col] = df[col].fillna("").astype(str)
    df = df[df.title.str.strip().ne("")].reset_index(drop=True)
    if df.empty:
        raise ValueError("Catalog has no titled movies")
    for col in ["popularity", "vote_average", "vote_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").replace(
            [np.inf, -np.inf], np.nan).fillna(0)
    return create_combined(df)


def compute_tfidf_vectorization(df, stop_words="english"):
    return TfidfVectorizer(stop_words=stop_words).fit_transform(df["combined"])


def content_movie_recommender(
    input_movie: str,
    similarity_database: pd.DataFrame,
    movie_database_list: list,
    top_n=10,
) -> list:
    """
    Function that uses a similarity matrix to find similar movies

    Parameters
    ----------
    input_movie : str
        reference movie to find similarities
    similarity_database : pandas.DataFrame
        similarity matrix of movies
    movie_database_list : numpy.ndarray
        movies in our similarity matrix
    top_n : int
        number of similar movies to output
    """
    try:
        # Get movie similarity
        movie_sim = similarity_database[similarity_database.index ==
                                        input_movie].values[0]
        # Get movies sorted by similarity
        # [::-1] to sort in descending order
        sorted_movies_ids = np.argsort(movie_sim)[::-1]
        # Get top n movies
        # [1:top_n+1] to exclude the input movie
        recommended_movies = movie_database_list[sorted_movies_ids][1:top_n+1]
        return list(recommended_movies)
    except IndexError:
        return []


def get_popularity_rmse(
    df: pd.DataFrame, sample_movie: str, recommendations: list
) -> float:
    """
    Compute RMSE for popularity, vote average, and vote count
    for the provided movie and recommendations.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame which must contain
        a "title" column.

    sample_movie : str
        The title of the movie for which
        recommendations are to be generated.

    recommendations : list
        A list of recommended movies.

    Returns
    -------
    popularity_rmse : float
        The RMSE for popularity.
        """
    # Convert titles in dataframe and sample_movie to lowercase
    df["title"] = df["title"].str.lower()
    sample_movie = sample_movie.lower()

    filtered_df = df[df["title"] == sample_movie]

    if not filtered_df.empty:
        sample_movie_popularity = filtered_df.popularity.iloc[0]
        recommendations_popularity = df[
            df["title"].isin(recommendations)
        ].popularity.values

        squared_diffs = (
            sample_movie_popularity - recommendations_popularity
        ) ** 2  # noqa E501
        rmse = np.sqrt(squared_diffs.mean())

        return round(float(rmse), 3)
    else:
        return float("nan")


def get_vote_avg_rmse(
    df: pd.DataFrame, sample_movie: str, recommendations: list
) -> float:
    """
    Compute RMSE for popularity, vote average, and vote count
    for the provided movie and recommendations.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame which must contain
        a "title" column.

    sample_movie : str
        The title of the movie for which
        recommendations are to be generated.

    recommendations : list
        A list of recommended movies.

    Returns
    -------
    popularity_rmse : float
        The RMSE for popularity."""
    sample_movie_vote_average = df[
        df["title"] == sample_movie
    ].vote_average.iloc[  # noqa E501
        0
    ]
    recommendations_vote_average = df[
        df["title"].isin(recommendations)
    ].vote_average.values

    squared_diffs = (
        sample_movie_vote_average - recommendations_vote_average
    ) ** 2  # noqa E501
    rmse = np.sqrt(squared_diffs.mean())

    return round(float(rmse), 3)


def get_vote_count_rmse(
    df: pd.DataFrame, sample_movie: str, recommendations: list
) -> float:
    """

    Compute RMSE for popularity, vote average, and vote count
    for the provided movie and recommendations.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame which must contain
        a "title" column.

    sample_movie : str
        The title of the movie for which
        recommendations are to be generated.

    recommendations : list
        A list of recommended movies.

    Returns
    -------
        popularity_rmse : float
        The RMSE for popularity.
    """
    sample_movie_popularity = df[df["title"] == sample_movie].vote_count.iloc[
        0
    ]  # noqa E501
    recommendations_popularity = df[
        df["title"].isin(recommendations)
    ].vote_count.values  # noqa E501

    squared_diffs = (recommendations_popularity - sample_movie_popularity) ** 2
    rmse = np.sqrt(squared_diffs.mean())

    return round(float(rmse), 3)


def compute_metrics(df, movie, recommendations):
    """
    Compute RMSE for popularity, vote average, and vote count
    for the provided movie and recommendations.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame which must contain
        a "combined" column.

    movie : str
        The title of the movie for which
        recommendations are to be generated.

    recommendations : list
        A list of recommended movies.

    Returns
    -------
    popularity_rmse : float
        The RMSE for popularity.

    vote_avg_rmse : float
        The RMSE for vote average.

        ote_count_rmse : float
        The RMSE for vote count.
    """
    popularity_rmse = get_popularity_rmse(df, movie, recommendations)
    vote_avg_rmse = get_vote_avg_rmse(df, movie, recommendations)
    vote_count_rmse = get_vote_count_rmse(df, movie, recommendations)
    return popularity_rmse, vote_avg_rmse, vote_count_rmse
