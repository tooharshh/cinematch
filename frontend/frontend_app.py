"""Adapted from MagnusS0/movie-rec-system: CineMatch streaming-style discovery UI."""
import os
import base64
import re
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import requests
import streamlit as st

SERVER_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
ASSETS = Path(__file__).parent / "assets"
COLLECTIONS = {"popular", "indian", "science-fiction", "thriller", "top-rated", "tamil", "malayalam", "all"}
LANGUAGES = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam"}
SEARCH_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>'
ARROW_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>'


def font_styles():
    """Bundle licensed fonts as data URLs; Streamlit 1.27 does not serve font MIME types."""
    rules = []
    for family, filename, weights in [
        ("Funnel Display", "FunnelDisplay.ttf", "300 800"),
        ("DM Sans", "DMSans.ttf", "100 1000"),
    ]:
        payload = base64.b64encode((ASSETS / "fonts" / filename).read_bytes()).decode("ascii")
        rules.append(f"@font-face{{font-family:'{family}';src:url(data:font/ttf;base64,{payload}) format('truetype');font-weight:{weights};font-style:normal;font-display:swap;}}")
    return "".join(rules)


def api_request(method, endpoint, **kwargs):
    try:
        response = requests.request(method, SERVER_URL + endpoint, timeout=(3, 20), **kwargs)
        if response.status_code != 200:
            messages = {
                404: "This film is not in the current collection. Try another title.",
                409: "Several films share this title. Choose a title and year.",
                503: "The collection is temporarily unavailable. Please try again shortly.",
                422: "Please enter a valid movie title.",
            }
            st.warning(messages.get(response.status_code, "We couldn't complete this request. Please try again."))
            return None
        return response.json()
    except requests.Timeout:
        st.error("The movie service took too long to respond. Please try again.")
    except (requests.RequestException, ValueError):
        st.error("The movie service is temporarily unavailable. Please try again shortly.")
    return None


def route(params):
    def value(name, default=""):
        item = params.get(name, [default])
        return item[0] if isinstance(item, list) and item else default
    movie = value("movie")
    collection = value("collection")
    page = value("page", "1")
    invalid = bool(movie and (not movie.isdigit() or not 0 < int(movie) < 2**63))
    return {"movie_id": int(movie) if movie and not invalid else None,
            "collection": collection if collection in COLLECTIONS else "",
            "view": "search" if value("view") == "search" or value("q") else "home",
            "query": value("q")[:300].strip(),
            "page": min(max(int(page), 1), 1000) if page.isdigit() else 1,
            "invalid": invalid}


def safe_image(url):
    return url if isinstance(url, str) and re.fullmatch(
        r"https://image\.tmdb\.org/t/p/(?:w500|w1280)/[A-Za-z0-9]+\.(?:jpg|jpeg|png|webp)", url) else None


def choice_label(movie, matches):
    label = f"{movie['title']} ({movie.get('year') or 'year unknown'})"
    duplicates = sum(m['title'] == movie['title'] and m.get('year') == movie.get('year') for m in matches)
    return f"{label} · Catalog #{movie['id']}" if duplicates > 1 else label


def movie_href(movie):
    return "?" + urlencode({"movie": int(movie["id"])})


def movie_card(movie, rank=None, compact=False, heading_level=3):
    """Native links/details support keyboard use; all provider text is escaped."""
    heading_tag = "h2" if heading_level == 2 else "h3"
    title = escape(str(movie["title"]))
    year = escape(str(movie.get("year") or "Year unavailable"))
    href = movie_href(movie) if movie.get("id") else "?view=search"
    poster = safe_image(movie.get("poster_url"))
    artwork = (f'<img src="{escape(poster, quote=True)}" alt="{title} poster" loading="lazy" decoding="async">'
               if poster else '<span class="cm-poster-empty">POSTER<br>UNAVAILABLE</span>')
    badge = f'<span class="cm-card-rank">{rank:02d}</span>' if rank else ""
    rating = float(movie.get("rating") or 0)
    rating_label = f"{rating:.1f}" if rating else "Not rated"
    genres = escape(str(movie.get("genres") or "Genres unavailable"))
    language = escape(LANGUAGES.get(movie.get("language"), ""))
    info = ""
    if not compact:
        overview = escape(str(movie.get("overview") or "No overview available."))
        similarity = movie.get("similarity")
        score = (f'<p class="cm-similarity">Text similarity: {max(0, min(1, float(similarity))):.0%}. Not a predicted rating.</p>'
                 if similarity is not None else "")
        info = f'<details class="cm-synopsis"><summary>Synopsis &amp; details</summary><p>{overview}</p><p>{genres}</p>{score}</details>'
    return f'''<article class="cm-card">
<a class="cm-card-link" href="{href}" target="_self" aria-label="Find films like {title} ({year})">
<div class="cm-poster">{artwork}{badge}<span class="cm-card-action">Find similar {ARROW_ICON}</span></div>
<div class="cm-card-copy"><{heading_tag}>{title}</{heading_tag}><p class="cm-card-meta"><span>{year}</span><span class="cm-rating">{rating_label}<span class="cm-sr-only"> out of ten</span></span><span>{language}</span></p></div>
</a>{info}</article>'''


def render_grid(movies, ranked=False, heading_level=3):
    cards = "".join(f'<li>{movie_card(movie, i + 1 if ranked else None, compact=not ranked, heading_level=heading_level)}</li>'
                    for i, movie in enumerate(movies))
    classes = 'cm-grid cm-ranked' if ranked else 'cm-grid'
    st.markdown(f'<ol class="{classes}">{cards}</ol>', unsafe_allow_html=True)


def render_shelf(shelf):
    sid = "shelf-" + shelf["collection"]
    cards = "".join(f'<li>{movie_card(movie, compact=True)}</li>' for movie in shelf["movies"])
    st.markdown(
        f'<section class="cm-shelf"><header class="cm-shelf-heading"><div><h2 id="{sid}">{escape(shelf["title"])}</h2>'
        f'<p>{escape(shelf["description"])}</p></div><a class="cm-see-all" href="?collection={shelf["collection"]}" target="_self">View all {ARROW_ICON}</a></header>'
        f'<div class="cm-rail" role="region" aria-labelledby="{sid}" tabindex="0"><ol>{cards}</ol></div></section>',
        unsafe_allow_html=True,
    )


def render_hero(movie, home=False):
    title = escape(str(movie["title"]))
    overview = str(movie.get("overview") or "A new starting point for your next movie night.")
    if home and len(overview) > 240:
        overview = overview[:237].rsplit(" ", 1)[0] + "…"
    image = safe_image(movie.get("backdrop_url")) or safe_image(movie.get("poster_url"))
    artwork = f'<img class="cm-hero-image" src="{escape(image, quote=True)}" alt="" fetchpriority="high" decoding="async">' if image else ""
    genre = escape(str(movie.get("genres") or "Discover a different story"))
    year = escape(str(movie.get("year") or "Year unavailable"))
    language = escape(LANGUAGES.get(movie.get("language"), ""))
    rating = float(movie.get("rating") or 0)
    label = "TONIGHT STARTS HERE" if home else "YOUR NEXT FIVE START HERE"
    destination = movie_href(movie) + "#recommendations" if home else "#recommendations"
    back = '<a class="cm-back" href="?" target="_self">← Back to browse</a>' if not home else ""
    st.markdown(
        f'<section class="cm-hero" aria-labelledby="cm-feature-title">{artwork}<div class="cm-hero-shade"></div><div class="cm-hero-content">{back}'
        f'<p class="cm-eyebrow">{label}</p><h1 id="cm-feature-title">{title}</h1>'
        f'<p class="cm-hero-meta"><span>{year}</span><span class="cm-rating">{rating:.1f}/10</span><span>{language}</span><span>Film</span></p>'
        f'<p class="cm-hero-genres">{genre}</p><p class="cm-hero-overview">{escape(overview)}</p>'
        f'<div class="cm-hero-actions"><a class="cm-button cm-button-primary" href="{destination}" target="_self">Find similar films {ARROW_ICON}</a>'
        '<a class="cm-button cm-button-secondary" href="?view=search#search" target="_self">Search a title</a></div>'
        '<p class="cm-hero-note">One film you love. Five more to discover.</p></div></section>', unsafe_allow_html=True,
    )


def render_results(result, source_title):
    movies = result.get("recommendation_details", [])
    st.markdown(
        f'<section class="cm-section" id="recommendations" aria-labelledby="cm-results-heading"><p class="cm-eyebrow">KEEP THE STORY GOING</p>'
        f'<h2 id="cm-results-heading">Because you chose {escape(source_title)}</h2>'
        f'<p role="status" aria-live="polite">{len(movies)} films with related stories, themes and genres.</p></section>', unsafe_allow_html=True,
    )
    if len(movies) < 5:
        st.info(f"This catalog has {len(movies)} available alternatives.")
    render_grid(movies, ranked=True)
    st.caption("Choose any poster to discover five more films like it.")
    with st.expander("How your five are chosen"):
        st.write("TF-IDF compares English overviews and genre names, with genres weighted twice. Cosine similarity ranks related content; the selected film is excluded. This is content similarity, not a prediction of your taste.")
        st.caption("The legacy RMSE diagnostics below compare ratings, popularity and vote counts. They do not measure recommendation quality.")
        st.json(result["metrics"])


def render_header(active, count):
    links = [("Home", "?", active == "home"), ("Indian cinema", "?collection=indian", active == "indian"),
             ("Highly rated", "?collection=top-rated", active == "top-rated"), ("Browse all", "?collection=all", active == "all")]
    nav = "".join(f'<li><a href="{href}" target="_self" {"aria-current=page" if selected else ""}>{label}</a></li>' for label, href, selected in links)
    st.markdown(
        '<header class="cm-header"><a class="cm-brand" href="?" target="_self" aria-label="CineMatch home">CINE<span>MATCH</span></a>'
        f'<nav aria-label="Main navigation"><ul>{nav}</ul></nav><a class="cm-nav-search" href="?view=search#search" target="_self">{SEARCH_ICON}<span>Search</span></a></header>'
        f'<div class="cm-catalog-line"><span>{count:,} films. Countless possibilities.</span><span>EN / HI / TA / TE / ML</span></div>', unsafe_allow_html=True,
    )


def render_footer():
    st.markdown('<footer class="cm-footer"><a class="cm-brand" href="?" target="_self">CINE<span>MATCH</span></a><p>A little less scrolling. A lot more cinema.</p><p>Movie discovery · SRM Linux &amp; Container Technologies</p></footer>', unsafe_allow_html=True)
    with st.expander("About CineMatch & data credits"):
        st.write("A content-based movie discovery project built with FastAPI, Streamlit, DuckDB, TF-IDF and cosine similarity. This app recommends films; it does not stream them.")
        st.caption("Adapted from MagnusS0/movie-rec-system · Apache-2.0")
        st.image(str(ASSETS / "tmdb.svg"), width=110)
        st.caption("This product uses the TMDB API but is not endorsed or certified by TMDB.")


def main():
    st.set_page_config(page_title="CineMatch · Find your next film", page_icon=str(ASSETS / "favicon.svg"), layout="wide")
    st.markdown(f'<style>{font_styles()}{(ASSETS / "style.css").read_text()}</style>', unsafe_allow_html=True)
    current = route(st.experimental_get_query_params())
    health = api_request("GET", "/health")
    render_header(current["collection"] or current["view"], health["movies"] if health else 0)
    if health is None:
        st.info("The collection will be back shortly. Please reload to try again.")
        render_footer()
        return
    if health.get("catalog_source") == "synthetic":
        st.info("Demonstration collection · Film information is illustrative example data.")
    if current["invalid"]:
        st.warning("That movie link isn't valid. Choose a film from the collection.")
    elif current["movie_id"]:
        movie = api_request("GET", f'/movies/{current["movie_id"]}')
        if movie:
            render_hero(movie)
            with st.spinner("Finding your next five…"):
                result = api_request("POST", "/recommendations/", json={"movie": movie["title"], "movie_id": movie["id"], "num_rec": 5})
            if result:
                render_results(result, movie["title"])
    elif current["view"] == "search":
        st.markdown('<section class="cm-search-heading" id="search"><p class="cm-eyebrow">FOLLOW YOUR CURIOSITY</p><h1>What are you in the mood for?</h1><p>Start with a title. We’ll help you find what comes next.</p></section>', unsafe_allow_html=True)
        with st.form("search"):
            query = st.text_input("Movie title", value=current["query"], max_chars=300, placeholder="Search for a film you love…")
            submitted = st.form_submit_button("Search films", type="primary")
        if submitted:
            if not query.strip():
                st.info("Enter a movie title to start exploring.")
                render_footer()
                return
            else:
                st.experimental_set_query_params(view="search", q=query.strip())
                # A form submission already reruns Streamlit. Finish this run so the
                # URL update is delivered, and render the submitted query immediately.
                current["query"] = query.strip()
        if current["query"]:
            with st.spinner("Searching the collection…"):
                data = api_request("GET", "/movies", params={"query": current["query"], "limit": 36, "include_details": True})
            if data is not None:
                movies = data["movies"]
                title = escape(current["query"])
                st.markdown(f'<section class="cm-section"><h2>Results for “{title}”</h2><p role="status">{len(movies)} matches shown. Choose a poster to discover similar films.</p></section>', unsafe_allow_html=True)
                if movies:
                    render_grid(movies)
                else:
                    st.info("No matching films in this collection. Try part of a title or a different movie.")
    elif current["collection"]:
        page = current["page"]
        data = api_request("GET", "/browse", params={"collection": current["collection"], "offset": (page - 1) * 24, "limit": 24})
        if data:
            st.markdown(f'<section class="cm-collection-heading"><p class="cm-eyebrow">YOUR NEXT DISCOVERY</p><h1>{escape(data["title"])}</h1><p>{escape(data["description"])}</p><p class="cm-muted">{data["total"]:,} films in this collection</p></section>', unsafe_allow_html=True)
            if data["movies"]:
                render_grid(data["movies"], heading_level=2)
            else:
                st.info("There are no films on this page. Choose another collection or return to the first page.")
            pages = max(1, (data["total"] + 23) // 24)
            controls = f'<span>Page {page} of {pages}</span>'
            if page > 1:
                controls = f'<a class="cm-button cm-button-secondary" href="?collection={current["collection"]}&amp;page={page-1}" target="_self">Previous page</a>' + controls
            if page < pages:
                controls += f'<a class="cm-button cm-button-secondary" href="?collection={current["collection"]}&amp;page={page+1}" target="_self">Next page {ARROW_ICON}</a>'
            st.markdown(f'<nav class="cm-pagination" aria-label="Collection pages">{controls}</nav>', unsafe_allow_html=True)
    else:
        data = api_request("GET", "/discover")
        if data:
            render_hero(data["featured"], home=True)
            st.markdown('<nav class="cm-chips" aria-label="Explore collections"><a href="?collection=science-fiction" target="_self">Other worlds</a><a href="?collection=thriller" target="_self">Edge of your seat</a><a href="?collection=tamil" target="_self">Tamil spotlight</a><a href="?collection=malayalam" target="_self">Malayalam stories</a></nav>', unsafe_allow_html=True)
            for shelf in data["shelves"]:
                render_shelf(shelf)
    render_footer()


if __name__ == "__main__":
    main()
