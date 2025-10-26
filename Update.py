"""
Premier League Understat Data Extraction using SoccerData Library
Author: Auto-generated with dynamic season range
Date: October 26, 2025

This script uses the soccerdata library to pull Understat data only.
It automatically determines seasons from 2014-15 to current season.
Includes 5 datasets: matches, team match stats, shots, player season, player match.

Installation:
    pip install soccerdata

Requirements:
    - Python 3.9+
    - soccerdata library (automatically installs pandas, requests, etc.)
"""

import soccerdata as sd
import pandas as pd
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Function to generate season list dynamically
def generate_season_list(start_year=2014):
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    # Determine current season based on August cutoff
    if current_month < 8:
        current_season_end = current_year
    else:
        current_season_end = current_year + 1

    seasons = []
    for year in range(start_year, current_season_end):
        next_year = year + 1
        season_str = f"{str(year)[-2:]}{str(next_year)[-2:]}"
        seasons.append(season_str)
    return seasons

# Generate seasons from 2014-15 to current
SEASONS = generate_season_list(start_year=2014)

# Output directory
OUTPUT_DIR = "Soccer_Data_API"

# Create directory structure
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "understat"), exist_ok=True)

print("=" * 80)
print("PREMIER LEAGUE UNDERSTAT DATA EXTRACTION")
print("=" * 80)
print(f"Output Directory: {OUTPUT_DIR}")
print(f"Seasons included: {', '.join(SEASONS)}")
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# Extract Data
try:
    print("\n[1/5] Initializing Understat for seasons:", SEASONS)
    understat = sd.Understat(leagues=['ENG-Premier League'], seasons=SEASONS)

    # 1. Match schedule with xG
    print("\n  [1/5] Extracting match schedule with xG...")
    matches = understat.read_schedule()
    matches.to_csv(os.path.join(OUTPUT_DIR, "understat", "01_matches_xG.csv"))
    print(f"     ✓ Saved {len(matches)} matches")

    # 2. Team match stats (with xG, xGA, PPDA, etc.)
    print("\n  [2/5] Extracting team match stats...")
    team_stats = understat.read_team_match_stats()
    team_stats.to_csv(os.path.join(OUTPUT_DIR, "understat", "02_team_match_stats.csv"))
    print(f"     ✓ Saved {len(team_stats)} records")

    # 3. Shot events (with xG)
    print("\n  [3/5] Extracting shot events with xG...")
    shots = understat.read_shot_events()
    shots.to_csv(os.path.join(OUTPUT_DIR, "understat", "03_shot_events.csv"))
    print(f"     ✓ Saved {len(shots)} shots")

    # 4. Player season stats
    print("\n  [4/5] Extracting player season stats...")
    player_season = understat.read_player_season_stats()
    player_season.to_csv(os.path.join(OUTPUT_DIR, "understat", "04_player_season_stats.csv"))
    print(f"     ✓ Saved {len(player_season)} records")

    # 5. Player match stats
    print("\n  [5/5] Extracting player match stats...")
    player_match = understat.read_player_match_stats()
    player_match.to_csv(os.path.join(OUTPUT_DIR, "understat", "05_player_match_stats.csv"))
    print(f"     ✓ Saved {len(player_match)} records")

    print("\n✓ Understat data extraction completed successfully!")

except Exception as e:
    print(f"\n✗ Error during extraction: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 80)
print("EXTRACTION SUMMARY:")
csv_files = [f for f in os.listdir(os.path.join(OUTPUT_DIR, "understat")) if f.endswith('.csv')]
for f in sorted(csv_files):
    fp = os.path.join(OUTPUT_DIR, "understat", f)
    try:
        df = pd.read_csv(fp)
        size_kb = round(os.path.getsize(fp)/1024, 2)
        print(f"{f:35} | Rows: {len(df):6} | Columns: {len(df.columns):3} | Size: {size_kb:7.2f} KB")
    except:
        print(f"{f:35} | Error reading file.")

print(f"\nAll files are saved in: {OUTPUT_DIR}/understat/")
print(f"Total files: {len(csv_files)}")
print("Note: Run this script again after August each year to include new seasons.")
print("=" * 80)
