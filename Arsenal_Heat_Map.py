from soccerdata import Understat
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Initialize Understat interface
us = Understat(leagues="ENG-Premier League", seasons=2024)

# Load Arsenal shot data (team or player level)
shots = us.read_shot_events()
# print(shots["team_id"].unique())
# shots.to_csv("Arsenal_2023_shots.csv", index=True)
arsenal_shots = shots[shots["team_id"] == 83].copy()

# Normalize column names
arsenal_shots.columns = arsenal_shots.columns.str.lower()

# Check columns
print(arsenal_shots.columns.tolist())

# Plot heatmap if x and y exist
# if "x" in arsenal_shots.columns and "y" in arsenal_shots.columns:
arsenal_shots["x"] = arsenal_shots["location_x"] * 120
arsenal_shots["y"] = (1 - arsenal_shots["location_y"]) * 80

plt.figure(figsize=(12, 8))
sns.kdeplot(
    data=arsenal_shots,
    x="x", y="y",
    shade=True,
    cmap="Reds",
    alpha=0.6,
    thresh=0.05
)

# Draw pitch outline
plt.plot([0, 0, 120, 120, 0], [0, 80, 80, 0, 0], color="black")
plt.title("Arsenal Shot Heatmap – 2023")
plt.xlim(0, 120)
plt.ylim(0, 80)
plt.gca().set_facecolor("green")
plt.show()
# else:
#     print("Shot coordinate columns ('x' and 'y') not found.")