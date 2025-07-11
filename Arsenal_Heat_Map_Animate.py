from soccerdata import Understat
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.animation import FuncAnimation
import matplotlib.patches as patches
import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog

# Load shot data to get available teams
us_temp = Understat(leagues="ENG-Premier League", seasons=2024)
all_shots_temp = us_temp.read_shot_events().reset_index()
team_names = sorted(all_shots_temp["team"].unique().tolist())

# GUI for selecting team
def select_team():
    global team_choice
    team_choice = combo.get()
    root.destroy()

root = tk.Tk()
root.title("Select a Team")

tk.Label(root, text="Choose a team for the heatmap:").pack(padx=10, pady=10)

combo = ttk.Combobox(root, values=team_names, state="readonly")
combo.pack(padx=20, pady=10)
combo.set("Arsenal")  # Set default team

submit_btn = ttk.Button(root, text="Submit", command=select_team)
submit_btn.pack(pady=10)

root.mainloop()

# Initialize Understat interface
us = Understat(leagues="ENG-Premier League", seasons=2024)

# Load Arsenal shot data (team or player level)
shots = us.read_shot_events()
shots = shots.reset_index()
# print(shots["team_id"].unique())
# shots.to_csv("Arsenal_2023_shots.csv", index=True)
team_shots = shots[shots["team"] == team_choice].copy()

# Scale pitch coordinates
team_shots["x"] = team_shots["location_x"] * 120
team_shots["y"] = (1 - team_shots["location_y"]) * 80

# Group by match
matches = sorted(team_shots["game_id"].unique().tolist())
matches.sort()

match_info = us.read_team_match_stats()
match_info = match_info.reset_index()

# # Filter Arsenal matches only
arsenal_matches = match_info[(match_info["home_team"] == team_choice) | (match_info["away_team"] == team_choice)].copy()

# Determine opponent and home/away
def get_opponent(row):
    if row["home_team"] == team_choice:
        return row["away_team_code"]
    else:
        return row["home_team_code"]

def get_home_away(row):
    return "Home" if row["home_team"] == team_choice else "Away"

arsenal_matches["opponent"] = arsenal_matches.apply(get_opponent, axis=1)
arsenal_matches["home_away"] = arsenal_matches.apply(get_home_away, axis=1)

# # Create lookup dict
match_titles = arsenal_matches.set_index("game_id")[["date", "opponent", "home_away"]].to_dict("index")


# Setup figure
fig, ax = plt.subplots(figsize=(12, 8))
pitch_outline = plt.plot([0, 0, 120, 120, 0], [0, 80, 80, 0, 0], color="black")
plt.xlim(0, 120)
plt.ylim(0, 80)
ax.set_facecolor("green")
title = ax.set_title("")

def draw_pitch(ax):
    # Pitch Outline & Centre Line
    ax.plot([0, 0], [0, 80], color="black")
    ax.plot([120, 120], [0, 80], color="black")
    ax.plot([0, 120], [0, 0], color="black")
    ax.plot([0, 120], [80, 80], color="black")
    ax.plot([60, 60], [0, 80], color="black")  # Halfway line

    # Center circle
    center_circle = patches.Circle((60, 40), 10, edgecolor="black", facecolor="none")
    ax.add_patch(center_circle)
    ax.plot(60, 40, 'ko')  # Center spot

    # Left penalty area
    ax.plot([0, 18], [62, 62], color="black")
    ax.plot([0, 18], [18, 18], color="black")
    ax.plot([18, 18], [18, 62], color="black")

    # Right penalty area
    ax.plot([120, 102], [62, 62], color="black")
    ax.plot([120, 102], [18, 18], color="black")
    ax.plot([102, 102], [18, 62], color="black")

    # 6-yard boxes
    ax.plot([0, 6], [48, 48], color="black")
    ax.plot([0, 6], [32, 32], color="black")
    ax.plot([6, 6], [32, 48], color="black")

    ax.plot([120, 114], [48, 48], color="black")
    ax.plot([120, 114], [32, 32], color="black")
    ax.plot([114, 114], [32, 48], color="black")

    # Penalty spots
    ax.plot(12, 40, 'ko')
    ax.plot(108, 40, 'ko')

    # Remove axes
    ax.set_xticks([])
    ax.set_yticks([])

fade_frames = 5  # Number of fade transition frames between games
frame_pairs = []

# Build frame list: (prev_match_id, next_match_id, fade_step)
for i in range(len(matches) - 1):
    for step in range(fade_frames + 1):
        frame_pairs.append((matches[i], matches[i+1], step / fade_frames))

# player_name = 7322
# player_shots = team_shots[team_shots["player_id"] == player_name].copy()

# Function to update frame
def update(frame):
    ax.clear()
    match_id_a, match_id_b, alpha_b = frame
    alpha_a = 1.0 - alpha_b

    data_a = team_shots[team_shots["game_id"] == match_id_a]
    data_b = team_shots[team_shots["game_id"] == match_id_b]

    # data_a = player_shots[player_shots["game_id"] == match_id_a]
    # data_b = player_shots[player_shots["game_id"] == match_id_b]

    draw_pitch(ax)
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 80)
    ax.set_facecolor("green")

    # Blend KDE plots
    if not data_a.empty and alpha_a > 0:
        sns.kdeplot(data=data_a, x="x", y="y", fill=True, cmap="Reds", alpha=alpha_a, ax=ax, thresh=0.05)
    if not data_b.empty and alpha_b > 0:
        sns.kdeplot(data=data_b, x="x", y="y", fill=True, cmap="Reds", alpha=alpha_b, ax=ax, thresh=0.05)

    # Label based on the dominant game
    info = match_titles.get(match_id_b if alpha_b >= 0.5 else match_id_a, {})
    ax.set_title(f"{info.get('date', 'Unknown')} – vs {info.get('opponent', '?')} ({info.get('home_away', '?')})")
    # ax.text(60, -5, f"{player_name}", ha="center", fontsize=12, color="black")


# Animate
anim = FuncAnimation(fig, update, frames=frame_pairs, interval=1200)
plt.show()
# anim.save("arsenal_heatmap.gif", writer="pillow", fps=1)