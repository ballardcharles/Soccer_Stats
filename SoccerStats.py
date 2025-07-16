from soccerdata import Understat
from soccerdata import ESPN
import pandas as pd

# Initialize the FBref data loader
us =  Understat(leagues="ENG-Premier League", seasons=2024)

# Fetch match results
matches = us.read_player_match_stats()
# Flatten MultiIndex columns
matches = matches.reset_index()

# Optional: print sample data
print(matches.head())

# Save to CSV
matches.to_csv("Team_2024_Stats.csv", index=True)

# # Initialize the FBref data loader
# espn =  ESPN(leagues="ENG-Premier League", seasons=2024)

# # Fetch match results
# matches = espn.read_matchsheet()
# # Flatten MultiIndex columns
# matches = matches.reset_index()

# # Optional: print sample data
# print(matches.head())

# # Save to CSV
# matches.to_csv("ESPN_2024_Match_Sheet.csv", index=True)

