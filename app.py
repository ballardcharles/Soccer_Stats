import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from soccerdata import Understat
import requests

# Patch requests with User-Agent for Understat scraping
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

st.set_page_config(layout="wide", page_title="Football Shot Heatmap")

# UI
st.title("Premier League Shot Heatmap (Understat)")
season = st.selectbox("Select season", ["2023", "2024", "2025"], index=1)

# Load data
@st.cache_data(show_spinner=True)
def load_data(season):
    us = Understat(leagues="ENG-Premier League", seasons=int(season))
    shots = us.read_shot_events().reset_index()
    matches = us.read_team_match_stats().reset_index()
    return shots, matches

shots, matches = load_data(season)
teams = sorted(shots["team"].unique())
team = st.selectbox("Select team", teams)

# Filter shots for selected team
team_shots = shots[shots["team"] == team].copy()
players = sorted(team_shots["player"].dropna().unique())
players = ["(All Players)"] + players
player = st.selectbox("Select player", players)

# Filter by player
if player != "(All Players)":
    team_shots = team_shots[team_shots["player"] == player].copy()

# Get matches for dropdown
match_ids = team_shots["game_id"].unique()
team_matches = matches[(matches["home_team"] == team) | (matches["away_team"] == team)].copy()

def get_opponent(row):
    return row["away_team_code"] if row["home_team"] == team else row["home_team_code"]

def get_home_away(row):
    return "Home" if row["home_team"] == team else "Away"

team_matches["opponent"] = team_matches.apply(get_opponent, axis=1)
team_matches["home_away"] = team_matches.apply(get_home_away, axis=1)
match_titles = team_matches.set_index("game_id")[["date", "opponent", "home_away"]].to_dict("index")

match_options = {
    f"{v['date']} vs {v['opponent']} ({v['home_away']})": gid
    for gid, v in match_titles.items()
    if gid in match_ids
}

match_label = st.selectbox("Select match", list(match_options.keys()))
match_id = match_options[match_label]

# Final shot filtering
match_shots = team_shots[team_shots["game_id"] == match_id].copy()
match_shots["x"] = match_shots["location_x"] * 120
match_shots["y"] = (1 - match_shots["location_y"]) * 80

# Draw pitch function
def draw_pitch(ax):
    ax.plot([0, 0, 120, 120, 0], [0, 80, 80, 0, 0], color="black")
    ax.plot([60, 60], [0, 80], color="black")
    ax.add_patch(patches.Circle((60, 40), 10, edgecolor="black", facecolor="none"))
    ax.plot(60, 40, 'ko')
    ax.plot([0, 18], [62, 62], color="black")
    ax.plot([0, 18], [18, 18], color="black")
    ax.plot([18, 18], [18, 62], color="black")
    ax.plot([120, 102], [62, 62], color="black")
    ax.plot([120, 102], [18, 18], color="black")
    ax.plot([102, 102], [18, 62], color="black")
    ax.plot([0, 6], [48, 48], color="black")
    ax.plot([0, 6], [32, 32], color="black")
    ax.plot([6, 6], [32, 48], color="black")
    ax.plot([120, 114], [48, 48], color="black")
    ax.plot([120, 114], [32, 32], color="black")
    ax.plot([114, 114], [32, 48], color="black")
    ax.plot(12, 40, 'ko')
    ax.plot(108, 40, 'ko')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 80)
    ax.set_facecolor("green")

# Plot
fig, ax = plt.subplots(figsize=(12, 8))
draw_pitch(ax)

if not match_shots.empty:
    sns.kdeplot(
        data=match_shots, x="x", y="y", fill=True,
        cmap="Reds", alpha=0.8, ax=ax, thresh=0.05
    )

info = match_titles.get(match_id, {})
ax.set_title(f"{info.get('date', 'Unknown')} vs {info.get('opponent', '?')} ({info.get('home_away', '?')})")

st.pyplot(fig)
