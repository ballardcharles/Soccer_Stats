import requests
import json
import pandas as pd
import os
from time import sleep

# Create directory for saving CSVs
output_dir = "Sports_DB_EPL"
os.makedirs(output_dir, exist_ok=True)

# API configuration
API_KEY = "123"  # Free test API key (use "1" or "3" for testing, or your premium key)
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"
LEAGUE_ID = "4328"  # English Premier League ID

# Dictionary to store all data
all_data = {}

print("Starting data collection from TheSportsDB for Premier League...")

# 1. Get League Details
print("\n1. Fetching league details...")
try:
    response = requests.get(f"{BASE_URL}/lookupleague.php?id={LEAGUE_ID}")
    league_data = response.json()
    if league_data.get('leagues'):
        df_league = pd.DataFrame(league_data['leagues'])
        df_league.to_csv(f"{output_dir}/league_details.csv", index=False)
        all_data['league'] = league_data['leagues']
        print(f"✓ League details saved ({len(df_league)} records)")
except Exception as e:
    print(f"✗ Error fetching league details: {e}")

# 2. Get All Teams in the League
print("\n2. Fetching all teams...")
try:
    response = requests.get(f"{BASE_URL}/lookup_all_teams.php?id={LEAGUE_ID}")
    teams_data = response.json()
    if teams_data.get('teams'):
        df_teams = pd.DataFrame(teams_data['teams'])
        df_teams.to_csv(f"{output_dir}/teams.csv", index=False)
        all_data['teams'] = teams_data['teams']
        print(f"✓ Teams saved ({len(df_teams)} records)")
        
        # Store team IDs for later use
        team_ids = [team['idTeam'] for team in teams_data['teams']]
except Exception as e:
    print(f"✗ Error fetching teams: {e}")
    team_ids = []

# 3. Get All Players for Each Team
print("\n3. Fetching players for each team...")
all_players = []
for i, team_id in enumerate(team_ids):
    try:
        response = requests.get(f"{BASE_URL}/lookup_all_players.php?id={team_id}")
        players_data = response.json()
        if players_data.get('player'):
            all_players.extend(players_data['player'])
            print(f"✓ Fetched players for team {i+1}/{len(team_ids)}")
        sleep(0.5)  # Rate limiting
    except Exception as e:
        print(f"✗ Error fetching players for team {team_id}: {e}")

if all_players:
    df_players = pd.DataFrame(all_players)
    df_players.to_csv(f"{output_dir}/players.csv", index=False)
    all_data['players'] = all_players
    print(f"✓ Players saved ({len(df_players)} records)")

# 4. Get All Seasons
print("\n4. Fetching seasons...")
try:
    response = requests.get(f"{BASE_URL}/search_all_seasons.php?id={LEAGUE_ID}")
    seasons_data = response.json()
    if seasons_data.get('seasons'):
        df_seasons = pd.DataFrame(seasons_data['seasons'])
        df_seasons.to_csv(f"{output_dir}/seasons.csv", index=False)
        all_data['seasons'] = seasons_data['seasons']
        print(f"✓ Seasons saved ({len(df_seasons)} records)")
except Exception as e:
    print(f"✗ Error fetching seasons: {e}")

# 5. Get Last 15 Events (Recent matches)
print("\n5. Fetching last 15 events...")
try:
    response = requests.get(f"{BASE_URL}/eventspastleague.php?id={LEAGUE_ID}")
    events_data = response.json()
    if events_data.get('events'):
        df_events = pd.DataFrame(events_data['events'])
        df_events.to_csv(f"{output_dir}/past_events.csv", index=False)
        all_data['past_events'] = events_data['events']
        print(f"✓ Past events saved ({len(df_events)} records)")
except Exception as e:
    print(f"✗ Error fetching past events: {e}")

# 6. Get Next 15 Events (Upcoming matches)
print("\n6. Fetching next 15 events...")
try:
    response = requests.get(f"{BASE_URL}/eventsnextleague.php?id={LEAGUE_ID}")
    next_events_data = response.json()
    if next_events_data.get('events'):
        df_next_events = pd.DataFrame(next_events_data['events'])
        df_next_events.to_csv(f"{output_dir}/next_events.csv", index=False)
        all_data['next_events'] = next_events_data['events']
        print(f"✓ Next events saved ({len(df_next_events)} records)")
except Exception as e:
    print(f"✗ Error fetching next events: {e}")

# 7. Get League Table/Standings for current season
print("\n7. Fetching league table/standings...")
try:
    response = requests.get(f"{BASE_URL}/lookuptable.php?l={LEAGUE_ID}&s=2024-2025")
    table_data = response.json()
    if table_data.get('table'):
        df_table = pd.DataFrame(table_data['table'])
        df_table.to_csv(f"{output_dir}/league_table.csv", index=False)
        all_data['league_table'] = table_data['table']
        print(f"✓ League table saved ({len(df_table)} records)")
except Exception as e:
    print(f"✗ Error fetching league table: {e}")

# 8. Get Team Equipment/Jerseys
print("\n8. Fetching team equipment...")
all_equipment = []
for i, team_id in enumerate(team_ids):
    try:
        response = requests.get(f"{BASE_URL}/lookupequipment.php?id={team_id}")
        equipment_data = response.json()
        if equipment_data.get('equipment'):
            all_equipment.extend(equipment_data['equipment'])
            print(f"✓ Fetched equipment for team {i+1}/{len(team_ids)}")
        sleep(0.5)
    except Exception as e:
        print(f"✗ Error fetching equipment for team {team_id}: {e}")

if all_equipment:
    df_equipment = pd.DataFrame(all_equipment)
    df_equipment.to_csv(f"{output_dir}/team_equipment.csv", index=False)
    all_data['equipment'] = all_equipment
    print(f"✓ Equipment saved ({len(df_equipment)} records)")

print("\n" + "="*60)
print("Data collection complete!")
print(f"All CSV files saved to: {output_dir}/")
print("="*60)

# Summary of collected data
print("\nSummary:")
for key, value in all_data.items():
    print(f"  - {key}: {len(value)} records")
