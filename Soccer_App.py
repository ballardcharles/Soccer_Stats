import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
from soccerdata import Understat
import requests
import io
from mplsoccer import Pitch

# ------------------------ Patch requests to avoid Understat errors ------------------------
original_get = requests.get
def patched_get(*args, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
    kwargs["headers"] = headers
    return original_get(*args, **kwargs)
requests.get = patched_get

# ------------------------ Streamlit Page Setup ------------------------
st.set_page_config(layout="wide", page_title="Football Shot Visualizer")
st.title("Premier League Shot Visualizer (Understat)")

# ------------------------ UI Controls ------------------------
season = st.selectbox("Select season", ["2023", "2024", "2025"], index=1)
plot_type = st.selectbox("Choose plot type", ["Heat Map", "Shot Map", "Positional Map"])
pitch_theme = st.selectbox("Pitch Theme", ["Grass", "Light", "Dark"], index=0)
show_xg = st.checkbox("Show xG values on Shot Map", value=False)
show_names = st.checkbox("Show player names on Shot Map", value=False)
use_plotly = st.checkbox("Use interactive Plotly map", value=False)

# ------------------------ Load Data ------------------------
@st.cache_data(show_spinner=True)
def load_data(season):
    us = Understat(leagues="ENG-Premier League", seasons=int(season))
    return us, us.read_shot_events().reset_index(), us.read_team_match_stats().reset_index(), us.read_player_match_stats().reset_index()

us, shots, matches, player_stats = load_data(season)

teams = sorted(shots["team"].unique())
team = st.selectbox("Select team", teams)

team_shots = shots[shots["team"] == team].copy()
players = sorted(team_shots["player"].dropna().unique())
players = ["(All Players)"] + players
player = st.selectbox("Select player", players)

if player != "(All Players)":
    team_shots = team_shots[team_shots["player"] == player].copy()

# ------------------------ Shot Outcome Filter ------------------------
shot_outcomes = sorted(team_shots["result"].dropna().unique())
selected_outcomes = st.multiselect("Filter by shot result", shot_outcomes, default=shot_outcomes)

# ------------------------ Match Dropdown ------------------------
match_ids = team_shots["game_id"].unique()
team_matches = matches[(matches["home_team"] == team) | (matches["away_team"] == team)].copy()
team_matches["date"] = pd.to_datetime(team_matches["date"])

# Annotate opponent and home/away
def get_opponent(row):
    return row["away_team_code"] if row["home_team"] == team else row["home_team_code"]
def get_home_away(row):
    return "Home" if row["home_team"] == team else "Away"

team_matches["opponent"] = team_matches.apply(get_opponent, axis=1)
team_matches["home_away"] = team_matches.apply(get_home_away, axis=1)
match_titles = team_matches.set_index("game_id")[["date", "opponent", "home_away"]].to_dict("index")

match_options = {
    f"{v['date'].strftime('%d %b %Y')} – vs {v['opponent']} ({v['home_away']})": gid
    for gid, v in match_titles.items()
    if gid in match_ids
}
match_options = {"All Matches": "all"} | match_options
match_label = st.selectbox("Select match", list(match_options.keys()))
match_id = match_options[match_label]

# ------------------------ Plot: Positional Map ------------------------
def plot_player_position_usage_streamlit(position_minutes, player_name="Player"):
    pos_coords = {
        "GK": (6, 40),
        "LB": (20, 10), "LCB": (30, 25), "CCB": (30, 40), "RCB": (30, 55), "RB": (20, 70),
        "LWB": (35, 10), "RWB": (35, 70),
        "LM": (50, 10), "CM": (50, 40), "RM": (50, 70),
        "LAM": (60, 20), "AM": (60, 40), "RAM": (60, 60),
        "LW": (80, 10), "SS": (80, 30), "CF": (80, 40), "RW": (80, 70)
    }

    total_minutes = sum([p["minutes"] for p in position_minutes])
    primary_position = max(position_minutes, key=lambda x: x["minutes"])["position"]

    pitch = Pitch(pitch_type='statsbomb', line_zorder=2, pitch_color='white')
    fig, ax = pitch.draw(figsize=(10, 6))
    pitch.annotate(player_name, (60, 5), ax=ax, ha='center', fontsize=14, fontweight='bold')

    for p in position_minutes:
        pos = p["position"]
        minutes = p["minutes"]
        pct = minutes / total_minutes * 100
        if pos not in pos_coords:
            continue
        x, y = pos_coords[pos]
        if pos == primary_position:
            ax.add_patch(plt.Circle((x, y), 3.5, color='black', zorder=3))
        pitch.scatter(x, y, ax=ax, color='blue', s=150, zorder=4)
        pitch.annotate(f"{pct:.0f}%", (x, y + 3), ax=ax, ha='center', fontsize=10)

    ax.set_title(f"Positional Usage – {player_name}", fontsize=16)
    st.pyplot(fig)

# ------------------------ Show Positional Map ------------------------
if plot_type == "Positional Map":
    if player == "(All Players)":
        st.warning("Please select an individual player to view positional usage.")
    else:
        player_data = player_stats[(player_stats["player"] == player) & (player_stats["team"] == team)]
        if player_data.empty:
            st.info("No position data available for this player.")
        else:
            position_minutes = (
                player_data.groupby("position")["time"]
                .sum()
                .reset_index()
                .rename(columns={"time": "minutes"})
                .to_dict("records")
            )
            plot_player_position_usage_streamlit(position_minutes, player_name=player)
