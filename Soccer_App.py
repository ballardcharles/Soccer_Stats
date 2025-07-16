import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
import plotly.express as px
from soccerdata import Understat
import requests
import io

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

st.set_page_config(layout="wide", page_title="Football Shot Visualizer")

st.title("Premier League Shot Visualizer (Understat)")

# Controls
season = st.selectbox("Select season", ["2023", "2024", "2025"], index=1)
plot_type = st.selectbox("Choose plot type", ["Heat Map", "Shot Map"])
pitch_theme = st.selectbox("Pitch Theme", ["Grass", "Light", "Dark"], index=0)
show_xg = st.checkbox("Show xG values on Shot Map", value=False)
show_names = st.checkbox("Show player names on Shot Map", value=False)
use_plotly = st.checkbox("Use interactive Plotly map", value=False)
comparison_mode = st.checkbox("Compare Home vs Away shots", value=False)

@st.cache_data(show_spinner=True)
def load_data(season):
    us = Understat(leagues="ENG-Premier League", seasons=int(season))
    shots = us.read_shot_events().reset_index()
    matches = us.read_team_match_stats().reset_index()
    return shots, matches

shots, matches = load_data(season)
teams = sorted(shots["team"].unique())
team = st.selectbox("Select team", teams)

team_shots = shots[shots["team"] == team].copy()
players = sorted(team_shots["player"].dropna().unique())
players = ["(All Players)"] + players
player = st.selectbox("Select player", players)

if player != "(All Players)":
    team_shots = team_shots[team_shots["player"] == player].copy()

# Shot outcome filter
shot_outcomes = sorted(team_shots["result"].dropna().unique())
selected_outcomes = st.multiselect("Filter by shot result", shot_outcomes, default=shot_outcomes)

match_ids = team_shots["game_id"].unique()
team_matches = matches[(matches["home_team"] == team) | (matches["away_team"] == team)].copy()
team_matches["date"] = pd.to_datetime(team_matches["date"])

# Annotate opponent & home/away
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
match_options = {"All Matches": "all"} | match_options
match_label = st.selectbox("Select match", list(match_options.keys()))
match_id = match_options[match_label]

# Filter shot data
if match_id == "all":
    match_shots = team_shots.copy()
    title = f"All Matches – {team}"
else:
    match_shots = team_shots[team_shots["game_id"] == match_id].copy()
    info = match_titles.get(match_id, {})
    try:
        match_date = info.get("date").strftime("%d %b %Y")
    except:
        match_date = "Unknown"
    title = f"{match_date} – vs {info.get('opponent', '?')} ({info.get('home_away', '?')})"

# Filter by shot result
match_shots = match_shots[match_shots["result"].isin(selected_outcomes)].copy()

# Normalize coordinates
match_shots["x"] = match_shots["location_x"] * 120
match_shots["y"] = (1 - match_shots["location_y"]) * 80

# Comparison split
if comparison_mode and match_id != "all":
    st.subheader("Home vs Away Shot Comparison")
    col1, col2 = st.columns(2)
    home_shots = match_shots[match_shots["h_a"] == "h"]
    away_shots = match_shots[match_shots["h_a"] == "a"]
    with col1:
        st.write("Home")
        st.dataframe(home_shots[["player", "result", "xg"]])
    with col2:
        st.write("Away")
        st.dataframe(away_shots[["player", "result", "xg"]])

# Draw pitch
def draw_pitch(ax, theme="Grass"):
    bg_color = {"Grass": "green", "Light": "white", "Dark": "#2c2c2c"}[theme]
    line_color = "white" if theme == "Dark" else "black"

    ax.plot([0, 0, 120, 120, 0], [0, 80, 80, 0, 0], color=line_color)
    ax.plot([60, 60], [0, 80], color=line_color)
    ax.add_patch(patches.Circle((60, 40), 10, edgecolor=line_color, facecolor="none"))
    ax.plot(60, 40, 'o', color=line_color)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 80)
    ax.set_facecolor(bg_color)

# Plotly version
if use_plotly:
    st.subheader("Interactive Shot Map (Plotly)")
    fig = px.scatter(
        match_shots, x="x", y="y", color="result",
        hover_data=["player", "xg", "minute"],
        labels={"x": "Pitch X", "y": "Pitch Y", "xg": "xG"},
        title=title, height=600
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(plot_bgcolor="green" if pitch_theme == "Grass" else pitch_theme.lower())
    st.plotly_chart(fig, use_container_width=True)
else:
    fig, ax = plt.subplots(figsize=(12, 8))
    draw_pitch(ax, theme=pitch_theme)

    if not match_shots.empty:
        if plot_type == "Heat Map":
            sns.kdeplot(data=match_shots, x="x", y="y", fill=True, cmap="Reds", ax=ax, thresh=0.05, alpha=0.8)
        else:
            for _, row in match_shots.iterrows():
                symbol = "O" if row["result"] == "Goal" else "X"
                color = "lime" if row["result"] == "Goal" else "red"
                ax.text(row["x"], row["y"], symbol, color=color, fontsize=12, ha='center', va='center', fontweight='bold')

                if show_xg and "xg" in row:
                    try:
                        ax.text(row["x"], row["y"] + 2, f"xG: {float(row['xg']):.2f}", fontsize=8,
                                color="white", ha='center', va='center', bbox=dict(facecolor='black', alpha=0.5, pad=1))
                    except:
                        pass

                if show_names and "player" in row:
                    ax.text(row["x"], row["y"] - 2, row["player"], fontsize=8,
                            color="white", ha='center', va='center', bbox=dict(facecolor='black', alpha=0.5, pad=1))

    ax.set_title(title)
    st.pyplot(fig)

# Match stats
if match_id != "all":
    match_row = team_matches[team_matches["game_id"] == match_id]
    if not match_row.empty:
        st.subheader("Match Stats")
        numeric_cols = match_row.select_dtypes(include='number').columns
        stat_table = match_row[numeric_cols].transpose()
        stat_table.columns = ["Value"]
        st.dataframe(stat_table)

# Player summary
st.subheader("Player Shot Summary (Season Total)")
summary = team_shots.groupby("player").agg(
    Shots=("xg", "count"),
    Goals=("result", lambda x: (x == "Goal").sum()),
    xG=("xg", "sum")
).sort_values("xG", ascending=False)
st.dataframe(summary.style.format({"xG": "{:.2f}"}))

# Download buttons
csv_buffer = io.StringIO()
match_shots.to_csv(csv_buffer, index=False)
st.download_button("Download shot data as CSV", data=csv_buffer.getvalue(),
                   file_name="shot_data.csv", mime="text/csv")

if not use_plotly:
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png', bbox_inches='tight')
    st.download_button("Download plot as PNG", data=img_buffer.getvalue(),
                       file_name="shot_plot.png", mime="image/png")
