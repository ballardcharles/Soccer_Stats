import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.patches as patches
import tkinter as tk
from tkinter import ttk, messagebox
from soccerdata import Understat
import requests

# Patch requests to use a user-agent
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

# Global variables
season_choice = None
team_choice = None
player_choice = None
match_choice = None
match_id_map = {}

# Seasons
season_range = list(range(2023, 2026))
season_strings = [f"{s}" for s in season_range]

# Get opponent and home/away
def get_opponent(row):
    return row["away_team_code"] if row["home_team"] == team_var.get() else row["home_team_code"]

def get_home_away(row):
    return "Home" if row["home_team"] == team_var.get() else "Away"

# Submit button action
def on_submit():
    global season_choice, team_choice, player_choice, match_choice
    season_choice = season_var.get()
    team_choice = team_var.get()
    player_choice = player_var.get()
    match_choice = match_var.get()
    root.destroy()

# Update teams based on season
def update_teams(event=None):
    season_selected = season_var.get()
    if not season_selected:
        return
    try:
        us_temp = Understat(leagues="ENG-Premier League", seasons=int(season_selected))
        all_shots = us_temp.read_shot_events().reset_index()
        teams = sorted(all_shots["team"].unique().tolist())
        team_combo['values'] = teams
        if teams:
            team_combo.set(teams[0])
        update_players()
    except Exception as e:
        team_combo['values'] = []
        player_combo['values'] = []
        match_combo['values'] = []
        messagebox.showerror("Data Load Error", f"Could not load data for {season_selected}.")
        return

# Update players and matches
def update_players(event=None):
    global match_id_map
    season_selected = season_var.get()
    team_selected = team_var.get()
    if not (season_selected and team_selected):
        return
    us_temp = Understat(leagues="ENG-Premier League", seasons=int(season_selected))
    all_shots = us_temp.read_shot_events().reset_index()
    team_shots = all_shots[all_shots["team"] == team_selected]
    
    players = sorted(team_shots["player"].dropna().unique().tolist())
    players = ["(All Players)"] + players
    player_combo['values'] = players
    player_combo.set("(All Players)")

    match_ids = team_shots["game_id"].unique().tolist()
    match_info = us_temp.read_team_match_stats().reset_index()
    team_matches = match_info[(match_info["home_team"] == team_selected) | (match_info["away_team"] == team_selected)].copy()
    team_matches["opponent"] = team_matches.apply(get_opponent, axis=1)
    team_matches["home_away"] = team_matches.apply(get_home_away, axis=1)
    match_titles = team_matches.set_index("game_id")[["date", "opponent", "home_away"]].to_dict("index")

    match_labels = []
    match_id_map = {}
    for mid in match_ids:
        if mid in match_titles:
            title = match_titles[mid]
            label = f"{title['date']} vs {title['opponent']} ({title['home_away']})"
            match_labels.append(label)
            match_id_map[label] = mid
    match_combo['values'] = match_labels
    if match_labels:
        match_combo.set(match_labels[0])

# Build UI
root = tk.Tk()
root.title("Select Season, Team, Player, and Match")

tk.Label(root, text="Select a season:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
season_var = tk.StringVar()
season_combo = ttk.Combobox(root, textvariable=season_var, values=season_strings, state="readonly")
season_combo.grid(row=0, column=1, padx=10, pady=10)
season_combo.set("2024")
season_combo.bind("<<ComboboxSelected>>", update_teams)

tk.Label(root, text="Select a team:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
team_var = tk.StringVar()
team_combo = ttk.Combobox(root, textvariable=team_var, state="readonly")
team_combo.grid(row=1, column=1, padx=10, pady=10)
team_combo.bind("<<ComboboxSelected>>", update_players)

tk.Label(root, text="Select a player (or all):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
player_var = tk.StringVar()
player_combo = ttk.Combobox(root, textvariable=player_var, state="readonly")
player_combo.grid(row=2, column=1, padx=10, pady=10)

tk.Label(root, text="Select a match:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
match_var = tk.StringVar()
match_combo = ttk.Combobox(root, textvariable=match_var, state="readonly")
match_combo.grid(row=3, column=1, padx=10, pady=10)

submit_btn = ttk.Button(root, text="Generate Heatmap", command=on_submit)
submit_btn.grid(row=4, column=0, columnspan=2, pady=20)

update_teams()
root.mainloop()

# Load and filter shot data
us = Understat(leagues="ENG-Premier League", seasons=int(season_choice))
shots = us.read_shot_events().reset_index()

selected_match_id = match_id_map.get(match_choice)
if not selected_match_id:
    raise ValueError("Selected match not found.")

shot_data = shots[(shots["team"] == team_choice) & (shots["game_id"] == selected_match_id)].copy()
if player_choice != "(All Players)":
    shot_data = shot_data[shot_data["player"] == player_choice].copy()

shot_data["x"] = shot_data["location_x"] * 120
shot_data["y"] = (1 - shot_data["location_y"]) * 80

match_info = us.read_team_match_stats().reset_index()
team_matches = match_info[(match_info["home_team"] == team_choice) | (match_info["away_team"] == team_choice)].copy()
team_matches["opponent"] = team_matches.apply(get_opponent, axis=1)
team_matches["home_away"] = team_matches.apply(get_home_away, axis=1)
match_titles = team_matches.set_index("game_id")[["date", "opponent", "home_away"]].to_dict("index")
info = match_titles.get(selected_match_id, {})

# Draw pitch and plot
def draw_pitch(ax):
    ax.plot([0, 0], [0, 80], color="black")
    ax.plot([120, 120], [0, 80], color="black")
    ax.plot([0, 120], [0, 0], color="black")
    ax.plot([0, 120], [80, 80], color="black")
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

fig, ax = plt.subplots(figsize=(12, 8))
draw_pitch(ax)
ax.set_xlim(0, 120)
ax.set_ylim(0, 80)
ax.set_facecolor("green")

if not shot_data.empty:
    sns.kdeplot(data=shot_data, x="x", y="y", fill=True, cmap="Reds", alpha=0.8, ax=ax, thresh=0.05)

ax.set_title(f"{info.get('date', 'Unknown')} – vs {info.get('opponent', '?')} ({info.get('home_away', '?')})")
plt.show()
