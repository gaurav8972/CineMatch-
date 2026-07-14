import streamlit as st
import pickle
import pandas as pd
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Replace this with your actual TMDB API key (v3 auth key, not the v4 bearer token)
# Get one free at: https://www.themoviedb.org/settings/api
API_KEY = "29ddc62df9d97c05b3e360af2000151e"

st.set_page_config(page_title="Movies Hub", page_icon="🎬", layout="wide")


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
def inject_css():
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(160deg, #0b0f1a 0%, #141a2e 45%, #1d1033 100%);
            color: #f5f5f7;
        }

        h1 {
            font-weight: 800 !important;
            background: linear-gradient(90deg, #ff5f6d, #ffc371);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 1px;
        }

        .subtitle {
            color: #9aa3b8;
            font-size: 1rem;
            margin-top: -10px;
            margin-bottom: 1.5rem;
        }

        div[data-testid="stSelectbox"] > div > div {
            background-color: #1b2236;
            border: 1px solid #2e3a59;
            border-radius: 10px;
        }

        div[data-testid="stButton"] button {
            background: linear-gradient(90deg, #ff5f6d, #ffc371);
            color: #1b1b1b;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1.2rem;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        div[data-testid="stButton"] button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(255, 95, 109, 0.4);
        }

        .movie-card {
            background: #161c2e;
            border-radius: 14px;
            padding: 14px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
            margin-bottom: 1rem;
        }

        .movie-title {
            font-weight: 600;
            font-size: 0.95rem;
            margin: 10px 0 8px 0;
            min-height: 48px;
            color: #f5f5f7;
        }

        img {
            border-radius: 10px;
        }

        .detail-meta {
            color: #9aa3b8;
            font-size: 0.95rem;
            margin-bottom: 0.5rem;
        }

        .rating-badge {
            display: inline-block;
            background: #1b2236;
            border: 1px solid #ffc371;
            color: #ffc371;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            margin-bottom: 1rem;
        }

        .footer-note {
            color: #5c6377;
            font-size: 0.8rem;
            margin-top: 3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()


# ---------------------------------------------------------------------------
# TMDB fetching (session reuse + retry on transient connection errors)
# ---------------------------------------------------------------------------
def _build_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _build_session()

EMPTY_DETAILS = {
    "poster": None,
    "overview": "No description available.",
    "release_date": "",
    "runtime": None,
    "vote_average": None,
    "genres": [],
}


def fetch_movie_details(movie_id, attempt=1, max_attempts=3):
    """Single TMDB call that returns poster, overview, rating, genres, etc."""
    if API_KEY == "YOUR_TMDB_API_KEY":
        st.error("⚠️ You haven't set a real TMDB API key yet — replace the placeholder in app.py")
        return dict(EMPTY_DETAILS)

    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}"

    try:
        response = SESSION.get(url, timeout=10)
        data = response.json()

        if response.status_code != 200:
            st.warning(f"TMDB error for movie_id={movie_id}: {data.get('status_message', data)}")
            return dict(EMPTY_DETAILS)

        poster = None
        if data.get("poster_path"):
            poster = "https://image.tmdb.org/t/p/w500" + data["poster_path"]

        return {
            "poster": poster,
            "overview": data.get("overview") or "No description available.",
            "release_date": data.get("release_date", ""),
            "runtime": data.get("runtime"),
            "vote_average": data.get("vote_average"),
            "genres": [g["name"] for g in data.get("genres", [])],
        }

    except requests.exceptions.RequestException as e:
        if attempt < max_attempts:
            time.sleep(0.5 * attempt)
            return fetch_movie_details(movie_id, attempt + 1, max_attempts)
        st.warning(f"Request failed for movie_id={movie_id} after {max_attempts} attempts: {e}")
        return dict(EMPTY_DETAILS)


def recommend(movie):
    movie_index = movies[movies["title"] == movie].index[0]
    distances = similarity[movie_index]

    movies_list = sorted(
        list(enumerate(distances)),
        reverse=True,
        key=lambda x: x[1],
    )[1:6]

    results = []
    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id
        title = movies.iloc[i[0]].title
        details = fetch_movie_details(movie_id)
        details["title"] = title
        results.append(details)

    return results


# ---------------------------------------------------------------------------
# Data load
# ---------------------------------------------------------------------------
movies_dict = pickle.load(open("movies_dict.pkl", "rb"))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open("similarity.pkl", "rb"))


# ---------------------------------------------------------------------------
# Navigation state
# ---------------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "rec_results" not in st.session_state:
    st.session_state.rec_results = None
if "detail_idx" not in st.session_state:
    st.session_state.detail_idx = None


def go_to_details(idx):
    st.session_state.detail_idx = idx
    st.session_state.page = "details"


def go_home():
    st.session_state.page = "home"


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------
def render_home():
    st.title("🎬 CineMatch")
    st.markdown('<div class="subtitle">Find movies similar to the ones you already love</div>', unsafe_allow_html=True)

    selected_movie_name = st.selectbox("Select a movie", movies["title"].values)

    if st.button("✨ Recommend"):
        st.session_state.rec_results = recommend(selected_movie_name)

    if st.session_state.rec_results:
        results = st.session_state.rec_results
        cols = st.columns(5)

        for i, col in enumerate(cols):
            movie = results[i]
            with col:
                st.markdown('<div class="movie-card">', unsafe_allow_html=True)

                if movie["poster"]:
                    st.image(movie["poster"], use_container_width=True)
                else:
                    st.write("Poster not available")

                st.markdown(f'<div class="movie-title">{movie["title"]}</div>', unsafe_allow_html=True)

                if st.button("ℹ️ Details", key=f"details_btn_{i}"):
                    go_to_details(i)
                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="footer-note">Thanks for using.</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Details page
# ---------------------------------------------------------------------------
def render_details():
    results = st.session_state.rec_results
    movie = results[st.session_state.detail_idx]

    if st.button("← Back to recommendations"):
        go_home()
        st.rerun()

    st.title(movie["title"])

    col1, col2 = st.columns([1, 2])

    with col1:
        if movie["poster"]:
            st.image(movie["poster"], use_container_width=True)
        else:
            st.write("Poster not available")

    with col2:
        meta_bits = []
        if movie.get("release_date"):
            meta_bits.append(movie["release_date"][:4])
        if movie.get("runtime"):
            meta_bits.append(f"{movie['runtime']} min")
        if movie.get("genres"):
            meta_bits.append(", ".join(movie["genres"]))

        if meta_bits:
            st.markdown(f'<div class="detail-meta">{" • ".join(meta_bits)}</div>', unsafe_allow_html=True)

        if movie.get("vote_average") is not None:
            st.markdown(f'<div class="rating-badge">⭐ {movie["vote_average"]:.1f} / 10</div>', unsafe_allow_html=True)

        st.subheader("Overview")
        st.write(movie["overview"])


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
if st.session_state.page == "details" and st.session_state.rec_results:
    render_details()
else:
    render_home()