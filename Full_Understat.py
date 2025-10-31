"""
Combined Premier League Data Extractor
Pulls data from both Football-Data.org and Understat

Data Sources:
1. Football-Data.org API: Basic match data, standings, teams, scorers
2. Understat (scraping): Advanced xG stats, shot locations, team analytics

This creates a comprehensive dataset combining both sources.
"""

import requests
import pandas as pd
import json
import os
from datetime import datetime
import time
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ============================================================================
# CONFIGURATION
# ============================================================================

# Football-Data.org API Configuration
FOOTBALL_DATA_API_KEY = "33eccf988bdf462e990d1b0f10255dc5"
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
FOOTBALL_DATA_HEADERS = {'X-Auth-Token': FOOTBALL_DATA_API_KEY}
PREMIER_LEAGUE_CODE = "PL"

# Understat Configuration
MAX_WORKERS = 3
REQUEST_DELAY = 0.5
rate_limit_lock = threading.Lock()
last_request_time = {'time': 0}

# Seasons to fetch
SEASONS = [2023, 2024, 2025]  # Football-Data uses year format
UNDERSTAT_SEASONS = ['2023', '2024', '2025']  # Understat uses string format

# Output directories
OUTPUT_DIR = "premier_league_combined_data_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "football_data"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "understat"), exist_ok=True)

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
                'season': season,
                'Match Week': match.get('matchday'),
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
                'venue': match.get('venue'),
                'referee': match['referees'][0]['name'] if match.get('referees') else None
            })
        
        df = pd.DataFrame(matches_list)
        
        # Convert date to YYYY-MM-DD format
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # Clean team names - keep only first word of team name
        df.loc[df['home_team'] == 'AFC Bournemouth', 'home_team'] = 'Bournemouth'
        df.loc[df['away_team'] == 'AFC Bournemouth', 'away_team'] = 'Bournemouth'

        df['home_team_shortened'] = df['home_team'].str.split().str[0]
        
        # Create join key
        df['join_key'] = df['date'] + '_' + df['home_team_shortened']
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
        
        return pd.DataFrame(teams_list)
    return None

# ============================================================================
# UNDERSTAT EXTRACTION
# ============================================================================

def get_understat_league_table(season):
    """Get league table from Understat with xG stats"""
    url = f"https://understat.com/league/EPL/{season}"
    response = make_understat_request(url)
    if not response:
        return None
    
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if 'teamsData' in script.text:
                match = re.search(r'var teamsData\s*=\s*JSON\.parse\(\'(.+?)\'\)', script.text)
                if match:
                    json_str = match.group(1).encode().decode('unicode_escape')
                    teams_data = json.loads(json_str)
                    
                    teams_list = []
                    for team_id, team_info in teams_data.items():
                        teams_list.append({
                            'team_id': team_id,
                            'team': team_info['title'],
                            'wins': int(team_info['history'][0]['wins']) if team_info['history'] else 0,
                            'draws': int(team_info['history'][0]['draws']) if team_info['history'] else 0,
                            'loses': int(team_info['history'][0]['loses']) if team_info['history'] else 0,
                            'scored': int(team_info['history'][0]['scored']) if team_info['history'] else 0,
                            'missed': int(team_info['history'][0]['missed']) if team_info['history'] else 0,
                            'xG': float(team_info['history'][0]['xG']) if team_info['history'] else 0,
                            'xGA': float(team_info['history'][0]['xGA']) if team_info['history'] else 0,
                            'xpts': float(team_info['history'][0]['xpts']) if team_info['history'] else 0,
                            'pts': int(team_info['history'][0]['pts']) if team_info['history'] else 0,
                            'npxG': float(team_info['history'][0]['npxG']) if team_info['history'] else 0,
                            'npxGA': float(team_info['history'][0]['npxGA']) if team_info['history'] else 0,
                            'npxGD': float(team_info['history'][0]['npxGD']) if team_info['history'] else 0,
                            'ppda_att': float(team_info['history'][0]['ppda']['att']) if team_info['history'] else 0,
                            'ppda_def': float(team_info['history'][0]['ppda']['def']) if team_info['history'] else 0,
                            'deep': int(team_info['history'][0]['deep']) if team_info['history'] else 0,
                            'deep_allowed': int(team_info['history'][0]['deep_allowed']) if team_info['history'] else 0,
                            'season': season
                        })
                    
                    return pd.DataFrame(teams_list)
        return None
    except Exception as e:
        return None

def get_understat_matches(season):
    """Get matches from Understat with xG"""
    url = f"https://understat.com/league/EPL/{season}"
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
                                    'season': season
                                })
                    
                    if matches_list:
                        df = pd.DataFrame(matches_list)
                        df['Match'] = df['home_team'] + ' v ' + df['away_team']
                        # Convert date to YYYY-MM-DD format (Understat format: "2023-08-11 19:00:00")
                        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                        
                        # Clean team names - keep only first word of team name
                        df['home_team_shortened'] = df['home_team'].str.split().str[0]
                        
                        # Create join key
                        df['join_key'] = df['date'] + '_' + df['home_team_shortened']
                        df = df[['join_key'] + [col for col in df.columns if col != 'join_key']]
                        return df
        return None
    except Exception as e:
        return None

def get_match_shots(match_id):
    """Get all shots from a specific match"""
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
                                    'player': shot['player'],
                                    'player_id': shot['player_id'],
                                    'team': shot['h_team'] if side == 'h' else shot['a_team'],
                                    'home_away': 'home' if side == 'h' else 'away',
                                    'minute': int(shot['minute']),
                                    'result': shot['result'],
                                    'xG': float(shot['xG']),
                                    'X': float(shot['X']),
                                    'Y': float(shot['Y']),
                                    'shot_type': shot['shotType'],
                                    'situation': shot['situation'],
                                    'last_action': shot['lastAction'],
                                    'player_assisted': shot.get('player_assisted')
                                })
                    
                    return pd.DataFrame(all_shots) if all_shots else None
        return None
    except Exception as e:
        return None

# ============================================================================
# MAIN EXTRACTION PROCESS
# ============================================================================

print("=" * 70)
print("COMBINED PREMIER LEAGUE DATA EXTRACTOR")
print("=" * 70)
print(f"\nSeasons: {', '.join(map(str, SEASONS))}")
print(f"Sources: Football-Data.org API + Understat (web scraping)")
print(f"Output directory: {OUTPUT_DIR}\n")

# Test API connection
print("Testing Football-Data.org API...")
test = make_football_data_request("competitions")
if test:
    print("  ✓ Football-Data.org API connected")
else:
    print("  ✗ Football-Data.org API failed")

print("\n" + "=" * 70)
print("EXTRACTING DATA")
print("=" * 70)

for idx, season in enumerate(SEASONS):
    understat_season = UNDERSTAT_SEASONS[idx]
    
    print(f"\n{'=' * 70}")
    print(f"SEASON {season}-{season+1}")
    print(f"{'=' * 70}")
    
    # ========================================================================
    # FOOTBALL-DATA.ORG EXTRACTION
    # ========================================================================
    print(f"\n[Football-Data.org] Extracting...")
    
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
    print("  • Top Scorers...", end=" ")
    scorers = get_football_data_scorers(season)
    if scorers is not None:
        save_dataframe(scorers, f"top_scorers_{season}.csv", "football_data")
    else:
        print("✗ Failed")
    time.sleep(6)

    # Teams
    print("  • Teams...", end=" ")
    teams = get_football_data_teams(season)
    if teams is not None:
        save_dataframe(teams, f"teams_{season}.csv", "football_data")
    else:
        print("✗ Failed")
    time.sleep(6)
    
    # ========================================================================
    # UNDERSTAT EXTRACTION
    # ========================================================================
    print(f"\n[Understat] Extracting...")
    
    # League table with xG
    print("  • League table with xG...", end=" ")
    understat_table = get_understat_league_table(understat_season)
    if understat_table is not None:
        save_dataframe(understat_table, f"league_xG_{understat_season}.csv", "understat")
    else:
        print("✗ Failed")
    
    # Matches with xG
    print("  • Matches with xG...", end=" ")
    understat_matches = get_understat_matches(understat_season)
    if understat_matches is not None:
        save_dataframe(understat_matches, f"matches_xG_{understat_season}.csv", "understat")
    else:
        print("✗ Failed")
        understat_matches = None
    
    # Shots
    if understat_matches is not None and not understat_matches.empty:
        print(f"  • Shots (processing {len(understat_matches)} matches with {MAX_WORKERS} threads)...")
        
        match_ids = understat_matches['match_id'].tolist()
        all_shots = []
        
        def fetch_shots(match_id):
            return match_id, get_match_shots(match_id)
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_match = {executor.submit(fetch_shots, mid): mid for mid in match_ids}
            
            completed = 0
            successful = 0
            for future in as_completed(future_to_match):
                try:
                    match_id, shots_df = future.result()
                    completed += 1
                    
                    if shots_df is not None and not shots_df.empty:
                        match_info = understat_matches[understat_matches['match_id'] == match_id].iloc[0]
                        shots_df['date'] = match_info['date']
                        shots_df['home_team'] = match_info['home_team']
                        shots_df['away_team'] = match_info['away_team']
                        shots_df['Match'] = match_info['Match']
                        shots_df['season'] = understat_season
                        all_shots.append(shots_df)
                        successful += 1
                    
                    if completed % 50 == 0:
                        print(f"    Progress: {completed}/{len(match_ids)} ({successful} with shots)")
                except:
                    pass
        
        if all_shots:
            combined_shots = pd.concat(all_shots, ignore_index=True)
            save_dataframe(combined_shots, f"shots_{understat_season}.csv", "understat")
        else:
            print("    ✗ No shots collected")
    
    print(f"\n✓ Season {season} complete")

# ============================================================================
# COMBINE AND MERGE DATA
# ============================================================================

print(f"\n{'=' * 70}")
print("COMBINING AND MERGING DATA")
print(f"{'=' * 70}\n")

# Combine Football-Data.org data
for data_type in ['standings', 'matches', 'top_scorers']:
    all_dfs = []
    for season in SEASONS:
        fpath = os.path.join(OUTPUT_DIR, "football_data", f"{data_type}_{season}.csv")
        if os.path.exists(fpath):
            all_dfs.append(pd.read_csv(fpath))
    
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        save_dataframe(combined, f"{data_type}_all_seasons.csv", "football_data")

# Combine Understat data
for data_type in ['league_xG', 'matches_xG', 'shots']:
    all_dfs = []
    for season in UNDERSTAT_SEASONS:
        fpath = os.path.join(OUTPUT_DIR, "understat", f"{data_type}_{season}.csv")
        if os.path.exists(fpath):
            all_dfs.append(pd.read_csv(fpath))
    
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        save_dataframe(combined, f"{data_type}_all_seasons.csv", "understat")

print("\nCreating merged match datasets per season (Football-Data + Understat xG)...")

for idx, season in enumerate(SEASONS):
    understat_season = UNDERSTAT_SEASONS[idx]
    
    fd_matches_file = os.path.join(OUTPUT_DIR, "football_data", f"matches_{season}.csv")
    us_matches_file = os.path.join(OUTPUT_DIR, "understat", f"matches_xG_{understat_season}.csv")
    
    if os.path.exists(fd_matches_file) and os.path.exists(us_matches_file):
        fd_df = pd.read_csv(fd_matches_file)
        us_df = pd.read_csv(us_matches_file)
        
        # Merge on home_team, away_team for this season
        # Note: Team names might differ slightly between sources
        merged = pd.merge(
            us_df,
            fd_df[['join_key', 'referee', 'Match Week']],
            on='join_key',
            how='left',
            suffixes=('', '_understat')
        )
        
        save_dataframe(merged, f"matches_merged_{season}.csv")
        # Report matching success
        matched = merged['home_xg'].notna().sum()
        total = len(merged)
        print(f"  ✓ Merged {season}: {matched}/{total} matches joined successfully")
    else:
        print(f"  ⚠️  Missing data files for {season}")


# ============================================================================
# FINAL SUMMARY
# ============================================================================

print(f"\n{'=' * 70}")
print("✓ EXTRACTION COMPLETE")
print(f"{'=' * 70}\n")

print("Data Structure:")
print("  📁 football_data/")
print("     • standings_{season}.csv - League tables")
print("     • matches_{season}.csv - Match details with scores")
print("     • top_scorers_{season}.csv - Top goal scorers")
print("     • *_all_seasons.csv - Combined data")
print("\n  📁 understat/")
print("     • league_xG_{season}.csv - Team stats with xG, PPDA")
print("     • matches_xG_{season}.csv - Match xG data")
print("     • shots_{season}.csv - All shots with coordinates")
print("     • *_all_seasons.csv - Combined data")
print("\n  📁 Root/")
print("     • matches_merged_all_seasons.csv - Combined best of both!")

print("\nWhat you have:")
print("  ✓ Basic match data (Football-Data.org)")
print("  ✓ Advanced xG stats (Understat)")
print("  ✓ Shot locations and coordinates (Understat)")
print("  ✓ Team PPDA and deep completions (Understat)")
print("  ✓ Top scorers with assists (Football-Data.org)")
print("  ✓ Referee information (Football-Data.org)")

print("\nNext steps:")
print("  1. Use matches_merged_all_seasons.csv for comprehensive match analysis")
print("  2. Use shots_all_seasons.csv for shot maps and player analysis")
print("  3. Build Streamlit dashboard with mplsoccer")
print(f"\n{'=' * 70}\n")