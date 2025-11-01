"""
Current Season Premier League Data Extractor - Comprehensive Version
Pulls only the most recent season data from Football-Data.org and Understat
Includes web scraping for detailed shot data (Shot Type, Last Action, etc.)

Data Sources:
1. Football-Data.org API: Basic match data, standings, teams, scorers
2. Understat (via soccerdata library): Advanced xG stats, team analytics, player stats
3. Understat (via web scraping): Detailed shot data with Shot Type and Last Action

Installation Required:
    pip install soccerdata beautifulsoup4
"""

import requests
import pandas as pd
import json
import os
from datetime import datetime
import time
import warnings
import soccerdata as sd
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Football-Data.org API Configuration
FOOTBALL_DATA_API_KEY = "33eccf988bdf462e990d1b0f10255dc5"
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
FOOTBALL_DATA_HEADERS = {'X-Auth-Token': FOOTBALL_DATA_API_KEY}
PREMIER_LEAGUE_CODE = "PL"

# Understat Web Scraping Configuration
MAX_WORKERS = 4
REQUEST_DELAY = 0.5
rate_limit_lock = threading.Lock()
last_request_time = {'time': 0}

def get_current_season():
    """Determine the current Premier League season"""
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    
    # Premier League season starts in August
    if current_month < 8:
        season_start = current_year - 1
    else:
        season_start = current_year
    
    # Football-Data.org format (year)
    fd_season = season_start
    
    # Soccerdata format (YXYY - e.g., 2425 for 2024-25)
    next_year = season_start + 1
    sd_season = f"{str(season_start)[-2:]}{str(next_year)[-2:]}"
    
    # Understat full year format (e.g., 2024 for 2024-25 season)
    understat_year = season_start
    
    return fd_season, sd_season, understat_year

# Get current season
FD_SEASON, SD_SEASON, UNDERSTAT_YEAR = get_current_season()

# Output directory
OUTPUT_DIR = "premier_league_combined_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def respect_rate_limit():
    """Ensure we don't make Understat requests too quickly"""
    with rate_limit_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time['time']
        if time_since_last < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - time_since_last)
        last_request_time['time'] = time.time()

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
        print(f"  ✗ Error: {e}")
        return None

def make_understat_request(url):
    """Make Understat web scraping request"""
    respect_rate_limit()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    except Exception as e:
        return None

def save_dataframe(df, filename):
    """Save dataframe as CSV"""
    if df is not None and not df.empty:
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
                'Away Team': match['awayTeam']['name'],
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
                'Team': scorer['team']['name'],
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
                'Name': team.get('name'),
                'Short Name': team.get('shortName'),
                'TLA': team.get('tla'),
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
# UNDERSTAT WEB SCRAPING - MATCH IDS
# ============================================================================

def get_understat_matches_with_ids(season_year):
    """Get matches from Understat with match IDs using web scraping
    
    Args:
        season_year: Full year format (e.g., 2024 for 2024-25 season)
    
    Returns:
        DataFrame with match_id, date, home_team, away_team, etc.
    """
    url = f"https://understat.com/league/EPL/{season_year}"
    response = make_understat_request(url)
    if not response:
        return None
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if 'datesData' in script.text:
                match = re.search(r'var datesData\s*=\s*JSON\.parse\(\'(.+?)\'\)', script.text)
                if match:
                    json_str = match.group(1).encode().decode('unicode_escape')
                    dates_data = json.loads(json_str)
                    
                    matches_list = []
                    
                    # Handle both dict and list formats
                    data_items = dates_data.items() if isinstance(dates_data, dict) else enumerate(dates_data)
                    
                    for key, matches in data_items:
                        match_list = matches if isinstance(matches, list) else [matches]
                        for match_item in match_list:
                            if match_item.get('xG') and match_item['xG'].get('h') is not None:
                                matches_list.append({
                                    'match_id': match_item['id'],
                                    'date': match_item['datetime'],
                                    'home_team': match_item['h']['title'],
                                    'away_team': match_item['a']['title'],
                                    'home_goals': match_item['goals']['h'],
                                    'away_goals': match_item['goals']['a'],
                                    'home_xg': float(match_item['xG']['h']),
                                    'away_xg': float(match_item['xG']['a']),
                                })
                    
                    if matches_list:
                        df = pd.DataFrame(matches_list)
                        df['Match'] = df['home_team'] + ' v ' + df['away_team']
                        
                        # Convert date to YYYY-MM-DD format
                        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                        
                        return df
        return None
    except Exception as e:
        print(f"  Error scraping matches: {e}")
        return None

# ============================================================================
# UNDERSTAT WEB SCRAPING - DETAILED SHOTS
# ============================================================================

def get_match_shots_detailed(match_id):
    """Get all shots from a specific match with detailed fields via web scraping
    
    Args:
        match_id: The match ID from Understat
    
    Returns:
        DataFrame with shot details including Shot Type, Last Action, etc.
    """
    url = f"https://understat.com/match/{match_id}"
    response = make_understat_request(url)
    if not response:
        return None
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if 'shotsData' in script.text:
                match = re.search(r'var shotsData\s*=\s*JSON\.parse\(\'(.+?)\'\)', script.text)
                if match:
                    json_str = match.group(1).encode().decode('unicode_escape')
                    shots_data = json.loads(json_str)
                    
                    all_shots = []
                    for side in ['h', 'a']:
                        if side in shots_data:
                            for shot in shots_data[side]:
                                all_shots.append({
                                    'shot_id': shot['id'],
                                    'match_id': match_id,
                                    'Player': shot['player'],
                                    'player_id': shot['player_id'],
                                    'Team': shot['h_team'] if side == 'h' else shot['a_team'],
                                    'Home/Away': 'Home' if side == 'h' else 'Away',
                                    'Minute': int(shot['minute']),
                                    'Result': shot['result'],
                                    'xG': float(shot['xG']),
                                    'x': float(shot['X']),
                                    'y': float(shot['Y']),
                                    'Shot Type': shot['shotType'],
                                    'Situation': shot['situation'],
                                    'Last Action': shot['lastAction'],
                                    'Assist Player': shot.get('player_assisted')
                                })
                    
                    return pd.DataFrame(all_shots) if all_shots else None
        return None
    except Exception as e:
        print(f"  Error scraping match {match_id}: {e}")
        return None

# ============================================================================
# MAIN EXTRACTION PROCESS
# ============================================================================

print("=" * 70)
print("CURRENT SEASON PREMIER LEAGUE DATA EXTRACTOR - COMPREHENSIVE")
print("=" * 70)
print(f"\nCurrent Season: {FD_SEASON}-{FD_SEASON+1}")
print(f"Sources: Football-Data.org API + Understat (soccerdata + web scraping)")
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

print(f"\nExtracting data for season {FD_SEASON}-{FD_SEASON+1}...")

# Standings
print("\n  • Standings...", end=" ")
standings = get_football_data_standings(FD_SEASON)
if standings is not None:
    save_dataframe(standings, "standings.csv")
else:
    print("✗ Failed")
time.sleep(6)

# Matches
print("  • Matches...", end=" ")
fd_matches = get_football_data_matches(FD_SEASON)
if fd_matches is not None:
    save_dataframe(fd_matches, "matches_football_data.csv")
else:
    print("✗ Failed")
time.sleep(6)

# Top Scorers
print("  • Top Scorers...", end=" ")
scorers = get_football_data_scorers(FD_SEASON)
if scorers is not None:
    save_dataframe(scorers, "top_scorers.csv")
else:
    print("✗ Failed")
time.sleep(6)

# Teams
print("  • Teams...", end=" ")
teams = get_football_data_teams(FD_SEASON)
if teams is not None:
    save_dataframe(teams, "teams.csv")
else:
    print("✗ Failed")
time.sleep(6)

print(f"\n✓ Football-Data.org extraction complete")

# ============================================================================
# UNDERSTAT EXTRACTION VIA SOCCERDATA
# ============================================================================

print("\n" + "=" * 70)
print("PART 2: UNDERSTAT EXTRACTION (via soccerdata)")
print("=" * 70)

try:
    print(f"\nInitializing Understat for season: {SD_SEASON}")
    understat = sd.Understat(leagues=['ENG-Premier League'], seasons=[SD_SEASON])
    
    # 1. Team match stats
    print("\n[1/4] Extracting team match stats...")
    team_stats = understat.read_team_match_stats()
    
    # Flatten multi-index columns and reset index
    if isinstance(team_stats.columns, pd.MultiIndex):
        team_stats.columns = ['_'.join(col).strip() if col[1] else col[0] for col in team_stats.columns.values]
    team_stats = team_stats.reset_index()
    
    # Clean column names
    team_stats.columns = [str(col).lower().replace(' ', '_') for col in team_stats.columns]

    # Standardize date format and create join key
    if 'date' in team_stats.columns:
        team_stats['date'] = pd.to_datetime(team_stats['date']).dt.strftime('%Y-%m-%d')
        team_stats['home_team_shortened'] = team_stats['home_team'].str.split().str[0]
        team_stats['join_key'] = team_stats['date'] + '_' + team_stats['home_team_shortened']
        team_stats = team_stats[['join_key'] + [col for col in team_stats.columns if col != 'join_key']]

    # Change League Name
    team_stats['league'] = team_stats['league'].replace('ENG-Premier League', 'Premier League')

    # Remove the date and space, replace '-' with ' v '
    team_stats['game'] = team_stats['game'].str.replace(r'^\d{4}-\d{2}-\d{2} ', '', regex=True).str.replace('-', ' v ')

    # Drop specific columns
    team_stats_drop = ['game_id', 'league_id','home_team_id', 'away_team_id', 'home_team_shortened', 'away_expected_points', 'home_expected_points']
    team_stats = team_stats.drop(columns=[col for col in team_stats_drop if col in team_stats.columns])

    # Rename Columns
    team_stats = team_stats.rename(columns={
        'game': 'Game',
        'season_id': 'Season',
        'season': 'season_id',
        'league': 'League',
        'date': 'Date',
        'home_team': 'Home Team',
        'away_team': 'Away Team',
        'away_team_code': 'Away Team Code',
        'home_team_code': 'Home Team Code',
        'away_points': 'Away Points',
        'home_points': 'Home Points',
        'home_xg': 'Home xG',
        'away_xg': 'Away xG',
        'home_goals': 'Home Goals',
        'away_goals': 'Away Goals',
        'away_np_xg': 'Away Non-Penalty xG',
        'home_np_xg': 'Home Non-Penalty xG',
        'away_deep_completions': 'Away Deep Completions',
        'home_deep_completions': 'Home Deep Completions',
        'away_ppda': 'Away PPDA',
        'home_ppda': 'Home PPDA',
    })
    
    # Add xG differential columns
    team_stats['Home xG Diff'] = team_stats['Home xG'] - team_stats['Away xG']
    team_stats['Away xG Diff'] = team_stats['Away xG'] - team_stats['Home xG']
    
    save_dataframe(team_stats, "team_stats.csv")
    print(f"  ✓ Saved {len(team_stats)} records")
    
    # 2. Player season stats
    print("\n[2/4] Extracting player season stats...")
    player_season = understat.read_player_season_stats()
    
    # Flatten multi-index columns and reset index
    if isinstance(player_season.columns, pd.MultiIndex):
        player_season.columns = ['_'.join(col).strip() if col[1] else col[0] for col in player_season.columns.values]
    player_season = player_season.reset_index()
    
    # Clean column names
    player_season.columns = [str(col).lower().replace(' ', '_') for col in player_season.columns]

    # Change League Name
    player_season['league'] = player_season['league'].replace('ENG-Premier League', 'Premier League')
    
    # Drop specific columns
    player_season_drop = ['league_id','player_id','team_id']
    player_season = player_season.drop(columns=[col for col in player_season_drop if col in player_season.columns])

    # Rename columns
    player_season = player_season.rename(columns={
        'season_id': 'Season',
        'season': 'season_id',
        'league': 'League',
        'player': 'Player',
        'team': 'Team',
        'minutes': 'Minutes',
        'matches': 'Matches',
        'goals': 'Goals',
        'xg': 'xG',
        'np_goals': 'Non-Penalty Goals',
        'np_xg': 'Non-Penalty xG',
        'assists': 'Assists',
        'xa': 'xA',
        'shots': 'Shots',
        'key_passes': 'Key Passes',
        'passes': 'Total Passes',
        'yellow_cards': 'Yellow Cards',
        'red_cards': 'Red Cards',        
    })

    save_dataframe(player_season, "player_season_stats.csv")
    print(f"  ✓ Saved {len(player_season)} records")
    
    # 3. Player match stats
    print("\n[3/4] Extracting player match stats...")
    player_match = understat.read_player_match_stats()
    
    # Flatten multi-index columns and reset index
    if isinstance(player_match.columns, pd.MultiIndex):
        player_match.columns = ['_'.join(col).strip() if col[1] else col[0] for col in player_match.columns.values]
    player_match = player_match.reset_index()
    
    # Clean column names
    player_match.columns = [str(col).lower().replace(' ', '_') for col in player_match.columns]

    # Remove the date and space, replace '-' with ' v '
    player_match['game'] = player_match['game'].str.replace(r'^\d{4}-\d{2}-\d{2} ', '', regex=True).str.replace('-', ' v ')

    # Drop specific columns
    player_match_drop = ['league_id','player_id','team_id']
    player_match = player_match.drop(columns=[col for col in player_match_drop if col in player_match.columns])

    # Rename columns
    player_match = player_match.rename(columns={
        'season_id': 'Season',
        'season': 'season_id',
        'league': 'League',
        'game': 'Game',
        'team': 'Team',
        'player': 'Player',
        'minutes': 'Minutes',
        'position': 'Position',
        'goals': 'Goals',
        'xg': 'xG',
        'shots': 'Shots',
        'key_passes': 'Key Passes',
        'own_goals': 'Own Goals',
        'assists': 'Assists',
        'xa': 'xA',
        'position_id': 'Position ID',
        'yellow_cards': 'Yellow Cards',
        'red_cards': 'Red Cards',        
    })
    
    save_dataframe(player_match, "player_match_stats.csv")
    print(f"  ✓ Saved {len(player_match)} records")
    
    # 4. ENHANCED: Detailed shots via web scraping
    print("\n[4/4] Extracting DETAILED shot data via web scraping...")
    print("  (This includes: Shot Type, Last Action, Home/Away)")
    
    print(f"\n  Processing season {SD_SEASON} (using year {UNDERSTAT_YEAR} for scraping)...")
    
    # Get match IDs directly from Understat scraping
    print(f"    • Fetching match list from Understat...")
    understat_matches = get_understat_matches_with_ids(UNDERSTAT_YEAR)
    
    if understat_matches is None or understat_matches.empty:
        print(f"    ⚠️  No matches found via Understat scraping")
    else:
        match_ids = understat_matches['match_id'].unique().tolist()
        print(f"    ✓ Found {len(match_ids)} matches")
        print(f"    • Scraping shots from {len(match_ids)} matches with {MAX_WORKERS} threads...")
        
        def fetch_detailed_shots(match_id):
            return match_id, get_match_shots_detailed(match_id)
        
        season_shots = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_match = {executor.submit(fetch_detailed_shots, mid): mid for mid in match_ids}
            completed = 0
            successful = 0
            
            for future in as_completed(future_to_match):
                try:
                    match_id, shots_df = future.result()
                    completed += 1
                    
                    if shots_df is not None and not shots_df.empty:
                        # Add match context from understat_matches
                        match_info = understat_matches[understat_matches['match_id'] == match_id].iloc[0]
                        shots_df['Date'] = match_info['date']
                        shots_df['Game'] = match_info['Match']
                        shots_df['Season'] = UNDERSTAT_YEAR
                        shots_df['season_id'] = SD_SEASON
                        
                        season_shots.append(shots_df)
                        successful += 1
                    
                    if completed % 50 == 0:
                        print(f"      Progress: {completed}/{len(match_ids)} ({successful} with shots)")
                except Exception as e:
                    pass
        
        if season_shots:
            combined_shots = pd.concat(season_shots, ignore_index=True)
            
            # Drop columns we don't need and reorder
            drop_cols = ['shot_id', 'match_id', 'player_id']
            combined_shots = combined_shots.drop(columns=[col for col in drop_cols if col in combined_shots.columns])
            
            # Reorder columns for consistency
            column_order = ['Season', 'season_id', 'Date', 'Game', 'Team', 'Player', 'Assist Player',
                        'xG', 'x', 'y', 'Minute', 'Situation', 'Result', 'Shot Type', 
                        'Last Action', 'Home/Away']
            combined_shots = combined_shots[[col for col in column_order if col in combined_shots.columns]]
            
            save_dataframe(combined_shots, "shots_detailed.csv")
            print(f"    ✓ Saved {len(combined_shots)} detailed shots")
        else:
            print(f"    ✗ No shots collected")
    
    print("\n✓ Understat data extraction completed successfully!")

except Exception as e:
    print(f"\n✗ Error during Understat extraction: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# MERGE DATASETS
# ============================================================================

print("\n" + "=" * 70)
print("PART 3: MERGING DATASETS")
print("=" * 70)

print("\nCreating merged match dataset (Football-Data + Understat xG)...")

fd_matches_file = os.path.join(OUTPUT_DIR, "matches_football_data.csv")
us_matches_file = os.path.join(OUTPUT_DIR, "team_stats.csv")

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
    
    save_dataframe(merged, "matches_merged.csv")
    
    # Report matching success
    matched = merged['Referee'].notna().sum()
    total = len(merged)
    print(f"  ✓ Merged matches: {matched}/{total} matches joined successfully")
else:
    print("  ⚠️  Could not merge - missing source files")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "=" * 70)
print("✓ EXTRACTION COMPLETE")
print("=" * 70)

print("\nFiles created:")
print("  • standings.csv - Current league table")
print("  • matches_football_data.csv - Match details with scores")
print("  • matches_merged.csv - Combined match data with xG")
print("  • top_scorers.csv - Current top goal scorers")
print("  • teams.csv - Team information")
print("  • team_stats.csv - Team match stats with xG, PPDA")
print("  • shots_detailed.csv - ALL shots with Shot Type, Last Action")
print("  • player_season_stats.csv - Player season statistics")
print("  • player_match_stats.csv - Player match-by-match stats")

print("\nWhat you have:")
print("  ✓ Current standings and form")
print("  ✓ All matches with scores and referees")
print("  ✓ Advanced xG stats for all matches")
print("  ✓ DETAILED shot data with Shot Type & Last Action")
print("  ✓ Shot locations and coordinates (x, y)")
print("  ✓ Team PPDA and advanced metrics")
print("  ✓ Player season and match stats")
print("  ✓ Top scorers with assists")

print("\nShot data includes:")
print("  ✓ Shot Type (LeftFoot, RightFoot, Head, OtherBodyPart)")
print("  ✓ Last Action (Pass, Dribble, Rebound, etc.)")
print("  ✓ Home/Away designation")
print("  ✓ Assist Player information")
print("  ✓ xG value for each shot")
print("  ✓ Exact x,y coordinates on pitch")

print("\nKey Features:")
print("  ✓ Automatically detects current season")
print("  ✓ No dependency on match file matching")
print("  ✓ Multi-threaded shot scraping for speed")
print("  ✓ Rate limiting to respect Understat")

print("\nNext steps:")
print("  1. Use matches_merged.csv for comprehensive match analysis")
print("  2. Use shots_detailed.csv for complete shot maps and analysis")
print("  3. Use player stats for detailed player performance tracking")
print("  4. Build Streamlit dashboard with mplsoccer for visualizations")

print(f"\nData saved to: {OUTPUT_DIR}/")
print(f"Season: {FD_SEASON}-{FD_SEASON+1}")
print(f"\n{'=' * 70}\n")