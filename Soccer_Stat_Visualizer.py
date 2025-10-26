import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from soccerdata import Understat
import requests
import io
from mplsoccer import Pitch

# --- Dependency Versions for Reproducibility ---
# Specify in requirements.txt:
# streamlit==1.26.0
# pandas==1.5.3
# matplotlib==3.7.1
# seaborn==0.12.2
# soccerdata==0.3.0
# mplsoccer==1.2.9

# --- PATCH REQUESTS HEADER ---
original_get = requests.get
def patched_get(*args, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    kwargs["headers"] = headers
    return original_get(*args, **kwargs)
requests.get = patched_get

# --- STREAMLIT LAYOUT ---
st.set_page_config(layout="wide", page_title="Football Shot Visualizer")
st.title("Premier League Shot Visualizer (Understat)")

# --- SIDEBAR CONTROLS ---
season = st.selectbox("Select season", ["2023", "2024", "2025"], index=1)
plot_type = st.selectbox("Choose plot type", ["Heat Map", "Shot Map", "Positional Map"])
pitch_theme = st.selectbox("Pitch Theme", ["grass", "white", "black"], index=0)
show_xg = st.checkbox("Show xG values", value=False)
show_names = st.checkbox("Show player names", value=False)

# --- DATA LOADING WITH ERROR HANDLING ---
@st.cache_data(show_spinner=True)
def load_data(season):
    try:
        us = Understat(leagues="ENG-Premier League", seasons=int(season))
        shots = us.read_shot_events().reset_index()
        matches = us.read_team_match_stats().reset_index()
        players = us.read_player_match_stats().reset_index()
        return shots, matches, players
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

shots, matches, player_match_stats = load_data(season)

if shots.empty or matches.empty:
    st.warning("No shot or match data loaded. Please try another season or check your connection.")
    st.stop()

# --- TEAM / PLAYER CONTROLS ---
teams = sorted(shots["team"].dropna().unique())
team = st.selectbox("Select team", teams)
team_shots = shots[shots["team"] == team].copy()
team_players = sorted(team_shots["player"].dropna().unique())
player = st.selectbox("Select player", ["(All Players)"] + team_players)

if player != "(All Players)":
    team_shots = team_shots[team_shots["player"] == player]

# --- SHOT OUTCOME FILTER ---
shot_outcomes = sorted(team_shots["result"].dropna().unique())
selected_outcomes = st.multiselect("Filter by shot result", shot_outcomes, default=shot_outcomes)
team_shots = team_shots[team_shots["result"].isin(selected_outcomes)].copy()

if team_shots.empty:
    st.warning("No shot data available for the selected filters.")
    st.stop()

# --- MATCH SELECTOR & METADATA ---
match_ids = team_shots["game_id"].unique()
team_matches = matches[
    (matches["home_team"] == team) | (matches["away_team"] == team)
].copy()
team_matches["date"] = pd.to_datetime(team_matches["date"])

def get_opponent(row):
    return row["away_team_code"] if row["home_team"] == team else row["home_team_code"]

def get_home_away(row):
    return "Home" if row["home_team"] == team else "Away"

team_matches["opponent"] = team_matches.apply(get_opponent, axis=1)
team_matches["home_away"] = team_matches.apply(get_home_away, axis=1)
match_titles = team_matches.set_index("game_id")[["date", "opponent", "home_away"]].to_dict("index")
match_options = {
    f"{v['date'].strftime('%d %b %Y')} – vs {v['opponent']} ({v['home_away']})": gid
    for gid, v in match_titles.items() if gid in match_ids
}
match_options = {"All Matches": "all", **match_options}
match_label = st.selectbox("Select match", list(match_options.keys()))
match_id = match_options[match_label]

if match_id == "all":
    match_shots = team_shots.copy()
    title = f"All Matches – {team}"
else:
    match_shots = team_shots[team_shots["game_id"] == match_id].copy()
    info = match_titles.get(match_id, {})
    title = f"{info['date'].strftime('%d %b %Y')} – vs {info['opponent']} ({info['home_away']})"

if match_shots.empty:
    st.warning("No shot data available for the selected match and filters.")
    st.stop()

# --- COORDINATE TRANSFORM ---
try:
    match_shots["x"] = match_shots["location_x"] * 120
    match_shots["y"] = (1 - match_shots["location_y"]) * 80
except Exception as e:
    st.error(f"Coordinate transformation failed: {e}")
    st.stop()

# --- PITCH & PLOTTING ---
pitch = Pitch(
    pitch_type='statsbomb',
    pitch_color=pitch_theme,
    line_color='white' if pitch_theme != 'white' else 'black'
)
fig, ax = pitch.draw(figsize=(12, 8))

try:
    if plot_type == "Heat Map":
        sns.kdeplot(
            data=match_shots, x="x", y="y", fill=True, ax=ax,
            cmap="Reds", alpha=0.7, thresh=0.05
        )
    elif plot_type == "Shot Map":
        for _, row in match_shots.iterrows():
            symbol = "O" if row["result"] == "Goal" else "X"
            color = "lime" if row["result"] == "Goal" else "red"
            ax.text(row["x"], row["y"], symbol, color=color, fontsize=12, ha='center', va='center', fontweight='bold')
            if show_xg:
                ax.text(row["x"], row["y"] + 2, f"xG: {row['xg']:.2f}", fontsize=7,
                        color="white", ha='center', bbox=dict(facecolor='black', alpha=0.5, pad=1))
            if show_names:
                ax.text(row["x"], row["y"] - 2, row["player"], fontsize=7,
                        color="white", ha='center', bbox=dict(facecolor='black', alpha=0.5, pad=1))
    elif plot_type == "Positional Map":
        pos_data = match_shots[match_shots["team"] == team]
        if match_id != "all":
            pos_data = pos_data[pos_data["game_id"] == match_id]
        if not pos_data.empty:
            avg_positions = pos_data.groupby("player").agg(
                avg_x=("x", "mean"),
                avg_y=("y", "mean"),
                total_shots=("x", "count")
            ).reset_index()
            for _, row in avg_positions.iterrows():
                ax.plot(row["avg_x"], row["avg_y"], 'o', markersize=10, color="cyan", alpha=0.8)
                ax.text(row["avg_x"], row["avg_y"], row["player"], fontsize=8,
                        ha='center', va='center', color="black",
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
        else:
            st.warning("No shot data available for this match.")
    ax.set_title(title, fontsize=14)
    st.pyplot(fig)
except Exception as e:
    st.error(f"Error creating the plot: {e}")

# --- MATCH STATS TABLE ---
if match_id != "all":
    match_row = team_matches[team_matches["game_id"] == match_id]
    if not match_row.empty:
        st.subheader("Match Stats")
        numeric_cols = match_row.select_dtypes(include='number').columns
        stat_table = match_row[numeric_cols].transpose()
        stat_table.columns = ["Value"]
        st.dataframe(stat_table)

# --- PLAYER SUMMARY ---
st.subheader("Player Shot Summary (Season Total)")
summary = team_shots.groupby("player").agg(
    Shots=("xg", "count"),
    Goals=("result", lambda x: (x == "Goal").sum()),
    xG=("xg", "sum")
).sort_values("xG", ascending=False)
st.dataframe(summary.style.format({"xG": "{:.2f}"}))

# --- DOWNLOAD BUTTONS ---
csv_buffer = io.StringIO()
match_shots.to_csv(csv_buffer, index=False)
st.download_button(
    "Download shot data as CSV", data=csv_buffer.getvalue(),
    file_name="shot_data.csv", mime="text/csv"
)

img_buffer = io.BytesIO()
fig.savefig(img_buffer, format='png', bbox_inches='tight')
st.download_button(
    "Download pitch as PNG", data=img_buffer.getvalue(),
    file_name="shot_plot.png", mime="image/png"
)
