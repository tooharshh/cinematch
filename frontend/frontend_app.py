"""Adapted upstream Streamlit UI: CineMatch faculty-facing presentation."""
import os
from html import escape
from pathlib import Path

import requests
import streamlit as st

SERVER_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
ASSETS = Path(__file__).parent / "assets"


def api_request(method, endpoint, **kwargs):
    try:
        response = requests.request(method, SERVER_URL + endpoint, timeout=(3, 20), **kwargs)
        if response.status_code != 200:
            messages = {
                404: "This movie is not available in the current catalog. Try another title.",
                409: "Several movies share this title. Please select a title and year.",
                503: "The movie catalog is temporarily unavailable. Please try again later.",
                422: "Please enter a valid movie title.",
            }
            st.warning(messages.get(response.status_code,
                       "We couldn't complete this request. Please try again."))
            return None
        return response.json()
    except requests.Timeout:
        st.error("The movie service took too long to respond. Please try again.")
    except (requests.RequestException, ValueError):
        st.error("The movie service is temporarily unavailable. Please try again shortly.")
    return None


def choice_label(movie, matches):
    label = f"{movie['title']} ({movie['year'] or 'year unknown'})"
    duplicates = sum(m['title'] == movie['title'] and m['year'] == movie['year'] for m in matches)
    return f"{label} · Catalog #{movie['id']}" if duplicates > 1 else label


def movie_card(movie, rank):
    """Escape provider text before placing it in a styled HTML card."""
    title = escape(str(movie["title"]))
    year = escape(str(movie.get("year") or "Year unavailable"))
    genres = escape(str(movie.get("genres") or "Genres unavailable"))
    overview = escape(str(movie.get("overview") or "No overview available."))
    rating = float(movie.get("rating") or 0)
    rating_label = f"{rating:.1f}/10" if rating else "Not rated"
    similarity = max(0.0, min(1.0, float(movie.get("similarity") or 0)))
    featured = " cm-featured" if rank == 1 else ""
    label = "Closest match" if rank == 1 else "Similar pick"
    return f"""<article class="cm-card{featured}">
<div class="cm-card-top"><span class="cm-rank">{rank:02d} / {label}</span><span class="cm-year">{year}</span></div>
<h3>{title}</h3><div class="cm-genres">{genres}</div>
<p class="cm-overview">{overview}</p>
<div class="cm-card-meta"><span>Movie rating <strong>{rating_label}</strong></span><span>Content similarity <strong>{similarity:.0%}</strong></span></div>
</article>"""


def render_results(result, source_title):
    details = result.get("recommendation_details", [])
    st.markdown(
        f'<section class="cm-section"><div class="cm-eyebrow">YOUR NEXT WATCH</div>'
        f'<h2>If you liked {escape(source_title)}</h2>'
        '<p>Explore movies with similar stories, themes and genres.</p></section>',
        unsafe_allow_html=True,
    )
    if len(details) < 5:
        st.info(f"This catalog has {len(details)} available alternatives.")
    if details:
        st.markdown(movie_card(details[0], 1), unsafe_allow_html=True)
    for offset in range(1, len(details), 2):
        columns = st.columns(2)
        for column, index in zip(columns, range(offset, min(offset + 2, len(details)))):
            with column:
                st.markdown(movie_card(details[index], index + 1), unsafe_allow_html=True)
    with st.expander("About these recommendations"):
        st.write("Each movie is represented by its English overview and genres. TF-IDF identifies informative words, and cosine similarity compares the resulting vectors. Genre names receive twice the weight.")
        st.write("Content similarity measures shared text and themes, not predicted enjoyment. Movie ratings come from the catalog. The catalog is a limited snapshot and may not include every title.")
    with st.expander("Evaluation diagnostics"):
        st.caption("These RMSE values compare popularity, ratings and vote counts with the selected movie. They are differences, not recommendation quality scores.")
        st.json(result["metrics"])


def main():
    st.set_page_config(page_title="CineMatch · Movie Discovery", page_icon="🎬", layout="wide")
    st.markdown(f"<style>{(ASSETS / 'style.css').read_text()}</style>", unsafe_allow_html=True)
    st.markdown(
        '<nav class="cm-nav"><div class="cm-brand">Cine<span>Match</span></div>'
        '<div class="cm-nav-note">Movie discovery, thoughtfully matched</div></nav>'
        '<section class="cm-hero"><div class="cm-eyebrow">A LITTLE INSPIRATION FOR MOVIE NIGHT</div>'
        '<h1>Great films lead to<br><em>great discoveries.</em></h1>'
        '<p>Start with a movie you love. Discover five more connected by their stories, themes and genres.</p></section>'
        '<div class="cm-steps"><span><b>01</b> Search a title</span>'
        '<span><b>02</b> Choose your movie</span><span><b>03</b> Discover your next five</span></div>',
        unsafe_allow_html=True,
    )
    with st.form("search"):
        query = st.text_input("Search the movie catalog", max_chars=300,
                              placeholder="Enter a movie title…")
        submitted = st.form_submit_button("Search catalog", type="primary")
    if submitted:
        st.session_state.pop("result", None)
        st.session_state["matches"] = []
        if not query.strip():
            st.info("Enter a movie title to start exploring.")
        else:
            with st.spinner("Searching the catalog…"):
                data = api_request("GET", "/movies", params={"query": query.strip()})
            if data is not None:
                st.session_state["matches"] = data["movies"]
                st.session_state["catalog_source"] = data.get("catalog_source", "unknown")
                if not data["movies"]:
                    st.info("No matching movies in this catalog. Try part of a title or another movie.")
    if st.session_state.get("catalog_source") == "synthetic":
        st.info("Demonstration catalog · Titles, dates and ratings are illustrative example data.")
    matches = st.session_state.get("matches", [])
    if matches:
        st.markdown('<section class="cm-section"><div class="cm-eyebrow">START WITH A FAVORITE</div></section>', unsafe_allow_html=True)
        selected = st.selectbox(
            "Choose a movie", matches,
            format_func=lambda m: choice_label(m, matches),
            on_change=lambda: st.session_state.pop("result", None),
        )
        if st.button("Discover five similar movies", type="primary"):
            with st.spinner("Finding similar stories…"):
                result = api_request(
                    "POST", "/recommendations/",
                    json={"movie": selected["title"], "movie_id": selected["id"], "num_rec": 5},
                )
            st.session_state["result"] = result
            st.session_state["source_title"] = selected["title"]
        result = st.session_state.get("result")
        if result:
            render_results(result, st.session_state.get("source_title", result["movie"]))
    else:
        st.markdown(
            '<section class="cm-empty"><h2>A familiar favorite. A fresh perspective.</h2>'
            '<p>Search the available catalog, choose a title and year, and explore five related films. '
            'Every recommendation starts with the content of the movie you choose.</p></section>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="cm-footer"><span>CineMatch · Content-based movie discovery</span>'
        '<span>Linux &amp; Container Technologies · SRM</span></div>', unsafe_allow_html=True,
    )
    with st.expander("Credits & data attribution"):
        st.caption("Adapted from MagnusS0/movie-rec-system · Apache-2.0")
        st.image(str(ASSETS / "tmdb.svg"), width=110)
        st.caption("This product uses the TMDB API but is not endorsed or certified by TMDB.")


if __name__ == "__main__":
    main()
