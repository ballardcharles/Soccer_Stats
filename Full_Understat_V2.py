"""
Combined Premier League Data Extractor
Pulls data from both Football-Data.org and Understat

Data Sources:
1. Football-Data.org API: Basic match data, standings, teams, scorers
2. Understat (via soccerdata library): Advanced xG stats, shot locations, team analytics

Installation Required:
    pip install soccerdata

This creates a comprehensive dataset combining both sources.
"""

import requests
import pandas as pd
import os
from datetime import datetime
import time
import warnings
import soccerdata as sd

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Football-Data.org API Configuration
FOOTBALL_DATA_API_KEY = "33eccf988bdf462e990d1b0f10255dc5"
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
FOOTBALL_DATA_HEADERS = {'X-Auth-Token': FOOTBALL_DATA_API_KEY}
PREMIER_LEAGUE_CODE = "PL"

# Function to generate season list dynamically
def generate_season_list(start_year=2014):
    """Generate season list from start_year to current season"""
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    # Determine current season based on August cutoff
    if current_month < 8:
        current_season_end = current_year
    else:
        current_season_end = current_year + 1

    # Football-Data.org format (year)
    fd_seasons = list(range(start_year, current_season_end))
    
    # Soccerdata format (YXYY - e.g., 1415 for 2014-15)
    sd_seasons = []
    for year in range(start_year, current_season_end):
        next_year = year + 1
        season_str = f"{str(year)[-2:]}{str(next_year)[-2:]}"
        sd_seasons.append(season_str)
    
    return fd_seasons, sd_seasons

# Generate seasons from 2014 to current
FOOTBALL_DATA_SEASONS, SOCCERDATA_SEASONS = generate_season_list(start_year=2023)


# Output directories
OUTPUT_DIR = "premier_league_combined_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "football_data"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "understat"), exist_ok=True)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def make_football_data_request(endpoint, params=None):
    """Make Football-Data.org API request"""
    url = f"{FOOTBALL_DATA_BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=FOOTBALL_DATA_HEADERS, params=params)
        
        if response.status_code == 429:
            print(f"  ⚠️  Rate limit reached. Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(url, headers=FOOTBALL_DATA_HEADERS, params=params)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"  ✗ Access forbidden - may not be available in free tier")
        return None
    except Exception as e:
        return None

def save_dataframe(df, filename, subdir=None):
    """Save dataframe as CSV"""
    if df is not None and not df.empty:
        if subdir:
            filepath = os.path.join(OUTPUT_DIR, subdir, filename)
        else:
            filepath = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(filepath, index=False)
        print(f"  ✓ Saved: {filename} ({len(df)} rows)")
        return True
    return False

# ============================================================================
# FOOTBALL-DATA.ORG EXTRACTION
# ============================================================================

def get_football_data_standings(season):
    """Get standings from Football-Data.org"""
    standings_data = make_football_data_request(
        f"competitions/{PREMIER_LEAGUE_CODE}/standings",
        {"season": season}
    )
    
    if standings_data and 'standings' in standings_data:
        table = standings_data['standings'][0]['table']
        standings_list = []
        
        for position in table:
            standings_list.append({
                'Position': position.get('position'),
                'Team': position['team']['name'],
                # 'team_id': position['team']['id'],
                'Games Played': position.get('playedGames'),
                'Won': position.get('won'),
                'Draw': position.get('draw'),
                'Lost': position.get('lost'),
                'Points': position.get('points'),
                'Goals For': position.get('goalsFor'),
                'Goals Against': position.get('goalsAgainst'),
                'Goal Difference': position.get('goalDifference'),
                'Form': position.get('form'),
                'Season': season
            })
        
        return pd.DataFrame(standings_list)
    return None

def get_football_data_matches(season):
    """Get matches from Football-Data.org"""
    matches_data = make_football_data_request(
        f"competitions/{PREMIER_LEAGUE_CODE}/matches",
        {"season": season}
    )
    
    if matches_data and 'matches' in matches_data:
        matches_list = []
        
        for match in matches_data['matches']:
            matches_list.append({
                'id': match.get('id'),
                'Season': season,
                'Match Week': match.get('matchday'),
                'Date': match.get('utcDate'),
                'Status': match.get('status'),
                'Home Team': match['homeTeam']['name'],
                # 'home_team_id': match['homeTeam']['id'],
                'Away Team': match['awayTeam']['name'],
                # 'away_team_id': match['awayTeam']['id'],
                'Home Score': match['score']['fullTime']['home'],
                'Away Score': match['score']['fullTime']['away'],
                'Home HT Score': match['score']['halfTime']['home'],
                'Away HT Score': match['score']['halfTime']['away'],
                'Winner': match['score'].get('winner'),
                'Venue': match.get('venue'),
                'Referee': match['referees'][0]['name'] if match.get('referees') else None
            })
        
        df = pd.DataFrame(matches_list)
        
        # Convert date to YYYY-MM-DD format
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        
        # Clean team names
        df.loc[df['Home Team'] == 'AFC Bournemouth', 'Home Team'] = 'Bournemouth'
        df.loc[df['Away Team'] == 'AFC Bournemouth', 'Away Team'] = 'Bournemouth'
        
        df['home_team_shortened'] = df['Home Team'].str.split().str[0]
        
        # Create join key
        df['join_key'] = df['Date'] + '_' + df['home_team_shortened']
        df = df[['join_key'] + [col for col in df.columns if col != 'join_key']]
        
        return df
    return None

def get_football_data_scorers(season):
    """Get top scorers from Football-Data.org"""
    scorers_data = make_football_data_request(
        f"competitions/{PREMIER_LEAGUE_CODE}/scorers",
        {"season": season}
    )
    
    if scorers_data and 'scorers' in scorers_data:
        scorers_list = []
        
        for scorer in scorers_data['scorers']:
            scorers_list.append({
                'Player': scorer['player']['name'],
                # 'player_id': scorer['player']['id'],
                'Team': scorer['team']['name'],
                # 'team_id': scorer['team']['id'],
                'Goals': scorer['goals'],
                'Assists': scorer.get('assists'),
                'Penalties': scorer.get('penalties'),
                'Nationality': scorer['player'].get('nationality'),
                'Position': scorer['player'].get('position'),
                'Season': season
            })
        
        return pd.DataFrame(scorers_list)
    return None

def get_football_data_teams(season):
    """Get teams from Football-Data.org"""
    teams_data = make_football_data_request(
        f"competitions/{PREMIER_LEAGUE_CODE}/teams",
        {"season": season}
    )
    
    if teams_data and 'teams' in teams_data:
        teams_list = []
        
        for team in teams_data['teams']:
            teams_list.append({
                # 'id': team.get('id'),
                'Name': team.get('name'),
                'Short Name': team.get('shortName'),
                'tla': team.get('tla'),
                'Crest': team.get('crest'),
                'Address': team.get('address'),
                'Website': team.get('website'),
                'Founded': team.get('founded'),
                'Club Colors': team.get('clubColors'),
                'Venue': team.get('venue'),
                'Season': season
            })
        
        return pd.DataFrame(teams_list)
    return None

# ============================================================================
# MAIN EXTRACTION PROCESS
# ============================================================================

print("=" * 70)
print("COMBINED PREMIER LEAGUE DATA EXTRACTOR")
print("=" * 70)
print(f"\nSeasons: {FOOTBALL_DATA_SEASONS[0]}-{FOOTBALL_DATA_SEASONS[-1]+1}")
print(f"Total seasons: {len(FOOTBALL_DATA_SEASONS)}")
print(f"Sources: Football-Data.org API + Understat (soccerdata library)")
print(f"Output directory: {OUTPUT_DIR}\n")

# Test API connection
print("Testing Football-Data.org API...")
test = make_football_data_request("competitions")
if test:
    print("  ✓ Football-Data.org API connected")
else:
    print("  ✗ Football-Data.org API failed")

print("\n" + "=" * 70)
print("PART 1: FOOTBALL-DATA.ORG EXTRACTION")
print("=" * 70)

for season in FOOTBALL_DATA_SEASONS:
    print(f"\n{'=' * 70}")
    print(f"SEASON {season}-{season+1}")
    print(f"{'=' * 70}")
    
    # Standings
    print("  • Standings...", end=" ")
    standings = get_football_data_standings(season)
    if standings is not None:
        save_dataframe(standings, f"standings_{season}.csv", "football_data")
    else:
        print("✗ Failed")
    time.sleep(6)
    
    # Matches
    print("  • Matches...", end=" ")
    fd_matches = get_football_data_matches(season)
    if fd_matches is not None:
        save_dataframe(fd_matches, f"matches_{season}.csv", "football_data")
    else:
        print("✗ Failed")
    time.sleep(6)
    
    # Top Scorers
    # print("  • Top Scorers...", end=" ")
    # scorers = get_football_data_scorers(season)
    # if scorers is not None:
    #     save_dataframe(scorers, f"top_scorers_{season}.csv", "football_data")
    # else:
    #     print("✗ Failed")
    # time.sleep(6)
    
    # Teams
    print("  • Teams...", end=" ")
    teams = get_football_data_teams(season)
    if teams is not None:
        save_dataframe(teams, f"teams_{season}.csv", "football_data")
    else:
        print("✗ Failed")
    time.sleep(6)
    
    print(f"✓ Season {season} complete")

# ============================================================================
# UNDERSTAT EXTRACTION VIA SOCCERDATA
# ============================================================================

print("\n" + "=" * 70)
print("PART 2: UNDERSTAT EXTRACTION (via soccerdata)")
print("=" * 70)

try:
    print(f"\nInitializing Understat for seasons: {SOCCERDATA_SEASONS[0]}-{SOCCERDATA_SEASONS[-1]}")
    understat = sd.Understat(leagues=['ENG-Premier League'], seasons=SOCCERDATA_SEASONS)
    
    # 1. Match schedule with xG
    print("\n[1/5] Extracting match schedule with xG...")
    matches_xg = understat.read_schedule()
    
    # Flatten multi-index columns and reset index
    if isinstance(matches_xg.columns, pd.MultiIndex):
        matches_xg.columns = ['_'.join(col).strip() if col[1] else col[0] for col in matches_xg.columns.values]
    matches_xg = matches_xg.reset_index()
    
    # Clean column names - remove any remaining multi-index artifacts
    matches_xg.columns = [str(col).replace('_', '').lower() if '_' not in str(col) else str(col).lower() for col in matches_xg.columns]
    
    # Standardize date format and create join key
    if 'date' in matches_xg.columns:
        matches_xg['date'] = pd.to_datetime(matches_xg['date']).dt.strftime('%Y-%m-%d')
        matches_xg['home_team_shortened'] = matches_xg['home_team'].str.split().str[0]
        matches_xg['join_key'] = matches_xg['date'] + '_' + matches_xg['home_team_shortened']
        matches_xg = matches_xg[['join_key'] + [col for col in matches_xg.columns if col != 'join_key']]
    
    # Rename key columns to standard names
    # matches_xg = matches_xg.rename(columns={
    #     'hometeam': 'home_team',
    #     'awayteam': 'away_team'
    # })
    
    # Save by season
    for season in SOCCERDATA_SEASONS:
        season_data = matches_xg[matches_xg['season'] == season]
        if not season_data.empty:
            save_dataframe(season_data, f"matches_xG_{season}.csv", "understat")
    
    # Save all seasons
    save_dataframe(matches_xg, "matches_xG_all_seasons.csv", "understat")
    print(f"  ✓ Saved {len(matches_xg)} matches")
    
    # 2. Team match stats
    print("\n[2/5] Extracting team match stats...")
    team_stats = understat.read_team_match_stats()
    
    # Flatten multi-index columns and reset index
    if isinstance(team_stats.columns, pd.MultiIndex):
        team_stats.columns = ['_'.join(col).strip() if col[1] else col[0] for col in team_stats.columns.values]
    team_stats = team_stats.reset_index()
    
    # Clean column names
    team_stats.columns = [str(col).lower().replace(' ', '_') for col in team_stats.columns]
    
    # Save by season
    for season in SOCCERDATA_SEASONS:
        season_data = team_stats[team_stats['season'] == season]
        if not season_data.empty:
            save_dataframe(season_data, f"team_stats_{season}.csv", "understat")
    
    save_dataframe(team_stats, "team_stats_all_seasons.csv", "understat")
    print(f"  ✓ Saved {len(team_stats)} records")
    
    # 3. Shot events
    print("\n[3/5] Extracting shot events with xG...")
    shots = understat.read_shot_events()
    
    # Flatten multi-index columns and reset index
    if isinstance(shots.columns, pd.MultiIndex):
        shots.columns = ['_'.join(col).strip() if col[1] else col[0] for col in shots.columns.values]
    shots = shots.reset_index()
    
    # Clean column names
    shots.columns = [str(col).lower().replace(' ', '_') for col in shots.columns]
    
    # Save by season
    for season in SOCCERDATA_SEASONS:
        season_data = shots[shots['season'] == season]
        if not season_data.empty:
            save_dataframe(season_data, f"shots_{season}.csv", "understat")
    
    save_dataframe(shots, "shots_all_seasons.csv", "understat")
    print(f"  ✓ Saved {len(shots)} shots")
    
    # 4. Player season stats
    print("\n[4/5] Extracting player season stats...")
    player_season = understat.read_player_season_stats()
    
    # Flatten multi-index columns and reset index
    if isinstance(player_season.columns, pd.MultiIndex):
        player_season.columns = ['_'.join(col).strip() if col[1] else col[0] for col in player_season.columns.values]
    player_season = player_season.reset_index()
    
    # Clean column names
    player_season.columns = [str(col).lower().replace(' ', '_') for col in player_season.columns]
    
    # Save by season
    for season in SOCCERDATA_SEASONS:
        season_data = player_season[player_season['season'] == season]
        if not season_data.empty:
            save_dataframe(season_data, f"player_season_{season}.csv", "understat")
    
    save_dataframe(player_season, "player_season_all_seasons.csv", "understat")
    print(f"  ✓ Saved {len(player_season)} records")
    
    # 5. Player match stats
    print("\n[5/5] Extracting player match stats...")
    player_match = understat.read_player_match_stats()
    
    # Flatten multi-index columns and reset index
    if isinstance(player_match.columns, pd.MultiIndex):
        player_match.columns = ['_'.join(col).strip() if col[1] else col[0] for col in player_match.columns.values]
    player_match = player_match.reset_index()
    
    # Clean column names
    player_match.columns = [str(col).lower().replace(' ', '_') for col in player_match.columns]
    
    # Save by season
    for season in SOCCERDATA_SEASONS:
        season_data = player_match[player_match['season'] == season]
        if not season_data.empty:
            save_dataframe(season_data, f"player_match_{season}.csv", "understat")
    
    save_dataframe(player_match, "player_match_all_seasons.csv", "understat")
    print(f"  ✓ Saved {len(player_match)} records")
    
    print("\n✓ Understat data extraction completed successfully!")

except Exception as e:
    print(f"\n✗ Error during Understat extraction: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# COMBINE AND MERGE DATA
# ============================================================================

print("\n" + "=" * 70)
print("PART 3: COMBINING FOOTBALL-DATA.ORG DATA")
print("=" * 70)

# Combine Football-Data.org data
for data_type in ['standings', 'matches', 'top_scorers', 'teams']:
    all_dfs = []
    for season in FOOTBALL_DATA_SEASONS:
        fpath = os.path.join(OUTPUT_DIR, "football_data", f"{data_type}_{season}.csv")
        if os.path.exists(fpath):
            all_dfs.append(pd.read_csv(fpath))
    
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        save_dataframe(combined, f"{data_type}_all_seasons.csv", "football_data")

# ============================================================================
# MERGE DATASETS
# ============================================================================

print("\n" + "=" * 70)
print("PART 4: MERGING DATASETS")
print("=" * 70)

print("\nCreating merged match datasets per season (Football-Data + Understat xG)...")

# Convert soccerdata season format to Football-Data format for matching
for idx, fd_season in enumerate(FOOTBALL_DATA_SEASONS):
    sd_season = SOCCERDATA_SEASONS[idx]
    
    fd_matches_file = os.path.join(OUTPUT_DIR, "football_data", f"matches_{fd_season}.csv")
    us_matches_file = os.path.join(OUTPUT_DIR, "understat", f"matches_xG_{sd_season}.csv")
    
    if os.path.exists(fd_matches_file) and os.path.exists(us_matches_file):
        fd_df = pd.read_csv(fd_matches_file)
        us_df = pd.read_csv(us_matches_file)
        
        # Merge on join_key
        merged = pd.merge(
            us_df,
            fd_df[['join_key', 'Referee', 'Match Week', 'Status']],
            on='join_key',
            how='left',
            suffixes=('', '_fd')
        )
        
        save_dataframe(merged, f"matches_merged_{fd_season}.csv")
        
        # Report matching success
        matched = merged['Referee'].notna().sum()
        total = len(merged)
        print(f"  ✓ Merged {fd_season}: {matched}/{total} matches joined successfully")
    else:
        if not os.path.exists(fd_matches_file):
            print(f"  ⚠️  Missing Football-Data file for {fd_season}")
        if not os.path.exists(us_matches_file):
            print(f"  ⚠️  Missing Understat file for {sd_season}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "=" * 70)
print("✓ EXTRACTION COMPLETE")
print("=" * 70)

print("\nData Structure:")
print("  📁 football_data/")
print("     • standings_{season}.csv - League tables")
print("     • matches_{season}.csv - Match details with scores")
print("     • top_scorers_{season}.csv - Top goal scorers")
print("     • teams_{season}.csv - Team information")
print("     • *_all_seasons.csv - Combined data")
print("\n  📁 understat/")
print("     • matches_xG_{season}.csv - Match xG data")
print("     • shots_{season}.csv - All shots with coordinates")
print("     • team_stats_{season}.csv - Team match stats")
print("     • player_season_{season}.csv - Player season stats")
print("     • player_match_{season}.csv - Player match stats")
print("     • *_all_seasons.csv - Combined data")
print("\n  📁 Root/")
print("     • matches_merged_{season}.csv - Combined best of both per season!")

print("\nWhat you have:")
print("  ✓ Basic match data (Football-Data.org)")
print("  ✓ Advanced xG stats (Understat via soccerdata)")
print("  ✓ Shot locations and coordinates (Understat)")
print("  ✓ Team PPDA and advanced metrics (Understat)")
print("  ✓ Player season and match stats (Understat)")
print("  ✓ Top scorers with assists (Football-Data.org)")
print("  ✓ Referee information (Football-Data.org)")

print("\nNext steps:")
print("  1. Use matches_merged_{season}.csv for comprehensive match analysis")
print("  2. Use shots_all_seasons.csv for shot maps and player analysis")
print("  3. Use player stats for detailed player performance tracking")
print("  4. Build Streamlit dashboard with mplsoccer")
print(f"\n{'=' * 70}\n")