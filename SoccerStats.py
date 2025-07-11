from soccerdata import Understat
import pandas as pd

# Initialize the FBref data loader
us =  Understat(leagues="ENG-Premier League", seasons=1920)

# Fetch match results
matches = us.read_shot_events()
# Flatten MultiIndex columns
matches = matches.reset_index()

# Optional: print sample data
print(matches.head())

# Save to CSV
# matches.to_csv("Arsenal_2024_results.csv", index=True)
