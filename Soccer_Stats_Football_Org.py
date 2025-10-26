"""
Premier League Data Extraction using Football-Data.org API
Free tier includes current season data!

Setup:
1. Sign up for free API key at https://www.football-data.org/client/register
2. Free tier: 10 requests/minute, includes Premier League current season
3. Set your API key in the script below
"""

import requests
import pandas as pd
import json
import os
from datetime import datetime
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get your free API key from: https://www.football-data.org/client/register
API_KEY = "33eccf988bdf462e990d1b0f10255dc5"  # Replace with your actual API key

# API Configuration
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {
    'X-Auth-Token': API_KEY
}

# Premier League Competition Code
PREMIER_LEAGUE_CODE = "PL"
PREMIER_LEAGUE_ID = 2021

# Seasons to fetch (format: YYYY for season starting that year)
# Note: Free tier includes current season and recent past seasons
CURRENT_SEASON = datetime.now().year
SEASONS = [2023, 2024, 2025]  # 2023-24, 2024-25, 2025-26

OUTPUT_DIR = "premier_league_data_footballdata"

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def make_api_request(endpoint, params=None):
    """Make API request with error handling and rate limiting"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        
        # Check rate limiting
        if response.status_code == 429:
            print(f"  ⚠ Rate limit reached. Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(url, headers=HEADERS, params=params)
        
        response.raise_for_status()
        data = response.json()
        
        # Show remaining requests
        if 'X-Requests-Available-Minute' in response.headers:
            remaining = response.headers.get('X-Requests-Available-Minute', 'Unknown')
            print(f"  📊 Requests remaining this minute: {remaining}")
        
        return data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"  ✗ Access forbidden - this data may not be available in free tier")
        elif e.response.status_code == 404:
            print(f"  ✗ Data not found for this request")
        else:
            print(f"  ✗ HTTP Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request failed: {e}")
        return None

def save_json(data, filename):
    """Save data as JSON"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ Saved: {filename}")

def save_dataframe(df, filename):
    """Save dataframe as CSV"""
    if df is not None and not df.empty:
        filepath = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(filepath, index=False)
        size_kb = os.path.getsize(filepath) / 1024
        print(f"  ✓ Saved: {filename} ({len(df)} rows, {size_kb:.1f} KB)")
        return True
    return False

def delete_json_files(directory):
    json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
    for file in json_files:
        file_path = os.path.join(directory, file)
        try:
            os.remove(file_path)
            print(f"Deleted: {file}")
        except Exception as e:
            print(f"Error deleting {file}: {e}")

# Call this function after data frames are created, for example:
# delete_json_files('premier_league_data_footballdata')


# ============================================================================
# CHECK API STATUS
# ============================================================================

print("=" * 60)
print("Football-Data.org API Extractor")
print("=" * 60)

print("\nTesting API connection...")
# Test with a simple competition list request
test = make_api_request("competitions")
if test:
    print("  ✓ API Connected Successfully!")
    print(f"  Available competitions: {len(test.get('competitions', []))}")
else:
    print("  ✗ Failed to connect to API. Check your API key!")
    print("  Get your free API key at: https://www.football-data.org/client/register")
    exit()

time.sleep(1)

# ============================================================================
# 1. COMPETITION INFORMATION
# ============================================================================

print("\n" + "=" * 60)
print("Fetching Premier League Competition Info")
print("=" * 60)

competition_data = make_api_request(f"competitions/{PREMIER_LEAGUE_CODE}")
if competition_data:
    save_json(competition_data, "competition_info.json")
    
    # Extract key info
    comp_df = pd.DataFrame([{
        'id': competition_data.get('id'),
        'name': competition_data.get('name'),
        'code': competition_data.get('code'),
        'type': competition_data.get('type'),
        'emblem': competition_data.get('emblem'),
        'current_season_start': competition_data.get('currentSeason', {}).get('startDate'),
        'current_season_end': competition_data.get('currentSeason', {}).get('endDate'),
        'current_matchday': competition_data.get('currentSeason', {}).get('currentMatchday')
    }])
    save_dataframe(comp_df, "competition_summary.csv")

time.sleep(1)

# ============================================================================
# 2. TEAMS
# ============================================================================

print("\n" + "=" * 60)
print("Fetching Teams")
print("=" * 60)

for season in SEASONS:
    print(f"\nSeason {season}-{season+1}:")
    teams_data = make_api_request(f"competitions/{PREMIER_LEAGUE_CODE}/teams", {"season": season})
    
    if teams_data and 'teams' in teams_data:
        teams_list = []
        for team in teams_data['teams']:
            teams_list.append({
                'id': team.get('id'),
                'name': team.get('name'),
                'shortName': team.get('shortName'),
                'tla': team.get('tla'),
                'crest': team.get('crest'),
                'address': team.get('address'),
                'website': team.get('website'),
                'founded': team.get('founded'),
                'clubColors': team.get('clubColors'),
                'venue': team.get('venue'),
                'season': season
            })
        
        teams_df = pd.DataFrame(teams_list)
        save_dataframe(teams_df, f"teams_{season}.csv")
    
    time.sleep(6)  # Free tier: 10 requests/minute

# ============================================================================
# 3. STANDINGS
# ============================================================================

print("\n" + "=" * 60)
print("Fetching Standings (League Table)")
print("=" * 60)

for season in SEASONS:
    print(f"\nSeason {season}-{season+1}:")
    standings_data = make_api_request(f"competitions/{PREMIER_LEAGUE_CODE}/standings", {"season": season})
    
    if standings_data and 'standings' in standings_data:
        # Get the main league table
        table = standings_data['standings'][0]['table']
        standings_list = []
        
        for position in table:
            standings_list.append({
                'position': position.get('position'),
                'team': position['team']['name'],
                'team_id': position['team']['id'],
                'playedGames': position.get('playedGames'),
                'won': position.get('won'),
                'draw': position.get('draw'),
                'lost': position.get('lost'),
                'points': position.get('points'),
                'goalsFor': position.get('goalsFor'),
                'goalsAgainst': position.get('goalsAgainst'),
                'goalDifference': position.get('goalDifference'),
                'form': position.get('form'),
                'season': season
            })
        
        standings_df = pd.DataFrame(standings_list)
        save_dataframe(standings_df, f"standings_{season}.csv")
        
        # Save full JSON with home/away splits
        save_json(standings_data, f"standings_{season}_full.json")
    
    time.sleep(6)

# ============================================================================
# 4. MATCHES (FIXTURES)
# ============================================================================

print("\n" + "=" * 60)
print("Fetching Matches")
print("=" * 60)

for season in SEASONS:
    print(f"\nSeason {season}-{season+1}:")
    matches_data = make_api_request(f"competitions/{PREMIER_LEAGUE_CODE}/matches", {"season": season})
    
    if matches_data and 'matches' in matches_data:
        matches_list = []
        
        for match in matches_data['matches']:
            matches_list.append({
                'id': match.get('id'),
                'season': season,
                'matchday': match.get('matchday'),
                'date': match.get('utcDate'),
                'status': match.get('status'),
                'home_team': match['homeTeam']['name'],
                'home_team_id': match['homeTeam']['id'],
                'away_team': match['awayTeam']['name'],
                'away_team_id': match['awayTeam']['id'],
                'home_score': match['score']['fullTime']['home'],
                'away_score': match['score']['fullTime']['away'],
                'home_ht_score': match['score']['halfTime']['home'],
                'away_ht_score': match['score']['halfTime']['away'],
                'winner': match['score'].get('winner'),
                'duration': match['score'].get('duration'),
                'venue': match.get('venue'),
                'referee': match['referees'][0]['name'] if match.get('referees') else None
            })
        
        matches_df = pd.DataFrame(matches_list)
        save_dataframe(matches_df, f"matches_{season}.csv")
        
        # Save full JSON for detailed stats
        save_json(matches_data['matches'], f"matches_{season}_full.json")
    
    time.sleep(6)

# ============================================================================
# 5. SCORERS (TOP GOAL SCORERS)
# ============================================================================

print("\n" + "=" * 60)
print("Fetching Top Scorers")
print("=" * 60)

for season in SEASONS:
    print(f"\nSeason {season}-{season+1}:")
    scorers_data = make_api_request(f"competitions/{PREMIER_LEAGUE_CODE}/scorers", {"season": season})
    
    if scorers_data and 'scorers' in scorers_data:
        scorers_list = []
        
        for scorer in scorers_data['scorers']:
            scorers_list.append({
                'player_name': scorer['player']['name'],
                'player_id': scorer['player']['id'],
                'team': scorer['team']['name'],
                'team_id': scorer['team']['id'],
                'goals': scorer['goals'],
                'assists': scorer.get('assists'),
                'penalties': scorer.get('penalties'),
                'nationality': scorer['player'].get('nationality'),
                'position': scorer['player'].get('position'),
                'season': season
            })
        
        scorers_df = pd.DataFrame(scorers_list)
        save_dataframe(scorers_df, f"top_scorers_{season}.csv")
    
    time.sleep(6)

# ============================================================================
# 6. CURRENT SEASON - DETAILED TEAM INFO
# ============================================================================

print("\n" + "=" * 60)
print("Fetching Detailed Team Information (Current Season)")
print("=" * 60)

current_season = SEASONS[-1]
teams_data = make_api_request(f"competitions/{PREMIER_LEAGUE_CODE}/teams", {"season": current_season})

if teams_data and 'teams' in teams_data:
    all_teams = teams_data['teams']
    print(f"\nGetting squad details for {len(all_teams)} teams...")
    print(f"⚠️  Note: This will use {len(all_teams)} API requests. Free tier = 10/minute.")
    
    for i, team in enumerate(all_teams, 1):  # Get ALL teams
        team_id = team['id']
        team_name = team['name']
        
        print(f"\n{i}. {team_name}:")
        team_detail = make_api_request(f"teams/{team_id}")
        
        if team_detail:
            # Save team info
            save_json(team_detail, f"team_{team_id}_{team_name.replace(' ', '_')}.json")
            
            # Extract squad
            if 'squad' in team_detail:
                squad_list = []
                for player in team_detail['squad']:
                    squad_list.append({
                        'team': team_name,
                        'team_id': team_id,
                        'player_name': player.get('name'),
                        'player_id': player.get('id'),
                        'position': player.get('position'),
                        'dateOfBirth': player.get('dateOfBirth'),
                        'nationality': player.get('nationality')
                    })
                
                squad_df = pd.DataFrame(squad_list)
                save_dataframe(squad_df, f"squad_{team_name.replace(' ', '_')}.csv")
        
        time.sleep(6)  # Rate limiting

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 60)
print("EXTRACTION COMPLETE")
print("=" * 60)

# List all generated files
csv_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.csv')]
json_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.json')]

print(f"\nTotal CSV files: {len(csv_files)}")
# print(f"Total JSON files: {len(json_files)}")
print(f"Location: {os.path.abspath(OUTPUT_DIR)}\n")

delete_json_files(OUTPUT_DIR)

if csv_files:
    print("CSV Files:")
    for file in sorted(csv_files):
        file_path = os.path.join(OUTPUT_DIR, file)
        size_kb = os.path.getsize(file_path) / 1024
        print(f"  • {file:<45} ({size_kb:>8.1f} KB)")

print("\n" + "=" * 60)
print("Data Available:")
print("=" * 60)
print("""
✓ Competition Information
✓ Teams (all seasons including current)
✓ Standings/League Table (all seasons)
✓ All Matches with scores and referees
✓ Top Scorers with goals, assists, penalties
✓ Squad information for teams

Key Advantages:
- Includes CURRENT 2024-25 season data
- Free tier is sufficient for Premier League
- Clean, well-structured API
- 10 requests/minute is manageable

Next Steps:
1. Review the CSV files
2. Build Streamlit dashboard with mplsoccer visualizations
3. Add real-time match updates
4. Consider upgrading for more detailed stats

Free Tier Limitations:
- Basic data only (no xG, shot locations, etc.)
- 10 requests per minute
- For detailed player stats, consider paid tier
""")