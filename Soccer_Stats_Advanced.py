"""
Match-Level Detailed Data Extractor
Gets granular data: shots per match, xG per player per match, shot locations

Sources:
1. Understat - Match-level xG, shot locations per player per match
2. StatsBomb Open Data - Event-level data with coordinates
3. Creates per-match, per-player breakdowns
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

OUTPUT_DIR = "premier_league_match_level_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SEASONS = ['2023', '2024', '2025']

# Rate limiting settings
MAX_WORKERS = 3  # Number of concurrent threads (conservative to respect server)
REQUEST_DELAY = 0.5  # Reduced from 1-2 seconds to 0.5 seconds
rate_limit_lock = threading.Lock()
last_request_time = {'time': 0}

# ============================================================================
# UNDERSTAT MATCH-LEVEL DATA
# ============================================================================

def respect_rate_limit():
    """Ensure we don't make requests too quickly"""
    with rate_limit_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time['time']
        if time_since_last < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - time_since_last)
        last_request_time['time'] = time.time()

def get_understat_matches(season):
    """
    Get all matches from Understat for the season
    Returns list of match IDs and basic info
    """
    respect_rate_limit()
    url = f"https://understat.com/league/EPL/{season}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
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
                    if isinstance(dates_data, dict):
                        # Dict format: date -> list of matches
                        for date, matches in dates_data.items():
                            if isinstance(matches, list):
                                for match_item in matches:
                                    # Skip if xG data is missing (future matches)
                                    if match_item.get('xG') and match_item['xG'].get('h') is not None:
                                        matches_list.append({
                                            'match_id': match_item['id'],
                                            'date': match_item['datetime'],
                                            'home_team': match_item['h']['title'],
                                            'home_id': match_item['h']['id'],
                                            'away_team': match_item['a']['title'],
                                            'away_id': match_item['a']['id'],
                                            'home_goals': match_item['goals']['h'],
                                            'away_goals': match_item['goals']['a'],
                                            'home_xg': float(match_item['xG']['h']),
                                            'away_xg': float(match_item['xG']['a']),
                                            'season': season
                                        })
                    elif isinstance(dates_data, list):
                        # List format: direct list of matches
                        for match_item in dates_data:
                            # Skip if xG data is missing (future matches)
                            if match_item.get('xG') and match_item['xG'].get('h') is not None:
                                matches_list.append({
                                    'match_id': match_item['id'],
                                    'date': match_item['datetime'],
                                    'home_team': match_item['h']['title'],
                                    'home_id': match_item['h']['id'],
                                    'away_team': match_item['a']['title'],
                                    'away_id': match_item['a']['id'],
                                    'home_goals': match_item['goals']['h'],
                                    'away_goals': match_item['goals']['a'],
                                    'home_xg': float(match_item['xG']['h']),
                                    'away_xg': float(match_item['xG']['a']),
                                    'season': season
                                })
                    
                    if matches_list:
                        return pd.DataFrame(matches_list)
        
        return None
        
    except Exception as e:
        print(f"  ✗ Error getting matches: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_match_shots(match_id):
    """
    Get all shots from a specific match with locations and xG
    This is the KEY function for shot-level data
    """
    respect_rate_limit()
    url = f"https://understat.com/match/{match_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if 'shotsData' in script.text:
                match = re.search(r'var shotsData\s*=\s*JSON\.parse\(\'(.+?)\'\)', script.text)
                if match:
                    json_str = match.group(1).encode().decode('unicode_escape')
                    shots_data = json.loads(json_str)
                    
                    all_shots = []
                    
                    # Home team shots
                    if 'h' in shots_data:
                        for shot in shots_data['h']:
                            all_shots.append({
                                'match_id': match_id,
                                'player': shot['player'],
                                'player_id': shot['player_id'],
                                'team': shot['h_team'],
                                'home_away': 'home',
                                'minute': int(shot['minute']),
                                'result': shot['result'],
                                'xG': float(shot['xG']),
                                'X': float(shot['X']),
                                'Y': float(shot['Y']),
                                'shot_type': shot['shotType'],
                                'situation': shot['situation'],
                                'last_action': shot['lastAction']
                            })
                    
                    # Away team shots
                    if 'a' in shots_data:
                        for shot in shots_data['a']:
                            all_shots.append({
                                'match_id': match_id,
                                'player': shot['player'],
                                'player_id': shot['player_id'],
                                'team': shot['a_team'],
                                'home_away': 'away',
                                'minute': int(shot['minute']),
                                'result': shot['result'],
                                'xG': float(shot['xG']),
                                'X': float(shot['X']),
                                'Y': float(shot['Y']),
                                'shot_type': shot['shotType'],
                                'situation': shot['situation'],
                                'last_action': shot['lastAction']
                            })
                    
                    return pd.DataFrame(all_shots)
        
        return None
        
    except Exception as e:
        print(f"    ✗ Error getting shots for match {match_id}: {str(e)[:50]}")
        return None

def get_match_player_stats(match_id):
    """
    Get player statistics for a specific match
    xG, xA, shots, key passes per player
    """
    respect_rate_limit()
    url = f"https://understat.com/match/{match_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if 'rostersData' in script.text:
                match = re.search(r'var rostersData\s*=\s*JSON\.parse\(\'(.+?)\'\)', script.text)
                if match:
                    json_str = match.group(1).encode().decode('unicode_escape')
                    rosters_data = json.loads(json_str)
                    
                    # Check if it's a valid roster structure
                    if not isinstance(rosters_data, dict):
                        return None
                    
                    all_players = []
                    
                    # Home team players
                    if 'h' in rosters_data and isinstance(rosters_data['h'], list):
                        for player in rosters_data['h']:
                            if not isinstance(player, dict):
                                continue
                            all_players.append({
                                'match_id': match_id,
                                'player': player.get('player', 'Unknown'),
                                'player_id': player.get('player_id', ''),
                                'team': player.get('team_title', 'Unknown'),
                                'home_away': 'home',
                                'position': player.get('position', ''),
                                'minutes': int(player.get('time', 0)),
                                'goals': int(player.get('goals', 0)),
                                'assists': int(player.get('assists', 0)),
                                'shots': int(player.get('shots', 0)),
                                'key_passes': int(player.get('key_passes', 0)),
                                'xG': float(player.get('xG', 0)),
                                'xA': float(player.get('xA', 0)),
                                'xGChain': float(player.get('xGChain', 0)),
                                'xGBuildup': float(player.get('xGBuildup', 0))
                            })
                    
                    # Away team players
                    if 'a' in rosters_data and isinstance(rosters_data['a'], list):
                        for player in rosters_data['a']:
                            if not isinstance(player, dict):
                                continue
                            all_players.append({
                                'match_id': match_id,
                                'player': player.get('player', 'Unknown'),
                                'player_id': player.get('player_id', ''),
                                'team': player.get('team_title', 'Unknown'),
                                'home_away': 'away',
                                'position': player.get('position', ''),
                                'minutes': int(player.get('time', 0)),
                                'goals': int(player.get('goals', 0)),
                                'assists': int(player.get('assists', 0)),
                                'shots': int(player.get('shots', 0)),
                                'key_passes': int(player.get('key_passes', 0)),
                                'xG': float(player.get('xG', 0)),
                                'xA': float(player.get('xA', 0)),
                                'xGChain': float(player.get('xGChain', 0)),
                                'xGBuildup': float(player.get('xGBuildup', 0))
                            })
                    
                    if all_players:
                        return pd.DataFrame(all_players)
        
        return None
        
    except Exception as e:
        # Silently skip errors - player stats are bonus data
        return None

def get_understat_team_shots(team, season):
    """
    Get all shots for a team from their team page
    More reliable than match-by-match for getting shot data
    """
    respect_rate_limit()
    url = f"https://understat.com/team/{team}/{season}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if 'shotsData' in script.text:
                match = re.search(r'var shotsData\s*=\s*JSON\.parse\(\'(.+?)\'\)', script.text)
                if match:
                    json_str = match.group(1).encode().decode('unicode_escape')
                    shots_data = json.loads(json_str)
                    
                    all_shots = []
                    
                    for shot in shots_data:
                        all_shots.append({
                            'match_id': shot['match_id'],
                            'player': shot['player'],
                            'player_id': shot['player_id'],
                            'team': team.replace('_', ' '),
                            'h_team': shot['h_team'],
                            'a_team': shot['a_team'],
                            'home_away': shot['h_a'],
                            'minute': int(shot['minute']),
                            'result': shot['result'],
                            'xG': float(shot['xG']),
                            'X': float(shot['X']),
                            'Y': float(shot['Y']),
                            'shot_type': shot['shotType'],
                            'situation': shot['situation'],
                            'last_action': shot['lastAction'],
                            'date': shot['date'],
                            'season': season
                        })
                    
                    return pd.DataFrame(all_shots)
        
        return None
        
    except Exception as e:
        return None

# ============================================================================
# STATSBOMB OPEN DATA
# ============================================================================

def get_statsbomb_competitions():
    """Get available competitions from StatsBomb"""
    url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"
    try:
        response = requests.get(url)
        competitions = response.json()
        pl_comps = [c for c in competitions if c['competition_name'] == 'Premier League']
        return pl_comps
    except:
        return []

def get_statsbomb_matches(competition_id, season_id):
    """Get matches for a StatsBomb competition/season"""
    url = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/{competition_id}/{season_id}.json"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return []

def get_statsbomb_events(match_id):
    """Get all events (including shots) for a match"""
    url = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json"
    try:
        response = requests.get(url)
        events = response.json()
        
        # Filter for shots
        shots = [e for e in events if e['type']['name'] == 'Shot']
        
        shots_list = []
        for shot in shots:
            shots_list.append({
                'match_id': match_id,
                'player': shot['player']['name'],
                'team': shot['team']['name'],
                'minute': shot['minute'],
                'second': shot['second'],
                'outcome': shot['shot']['outcome']['name'],
                'body_part': shot['shot']['body_part']['name'],
                'technique': shot['shot']['technique']['name'],
                'shot_type': shot['shot']['type']['name'],
                'location_x': shot['location'][0] if 'location' in shot else None,
                'location_y': shot['location'][1] if 'location' in shot else None,
                'end_location_x': shot['shot']['end_location'][0] if 'end_location' in shot['shot'] else None,
                'end_location_y': shot['shot']['end_location'][1] if 'end_location' in shot['shot'] else None,
                'end_location_z': shot['shot']['end_location'][2] if 'end_location' in shot['shot'] else None,
                'xG': shot['shot'].get('statsbomb_xg'),
                'under_pressure': 'under_pressure' in shot
            })
        
        return pd.DataFrame(shots_list)
    except:
        return None

# ============================================================================
# MAIN EXTRACTION
# ============================================================================

print("=" * 60)
print("Match-Level Detailed Data Extractor")
print("=" * 60)

# 1. GET ALL MATCHES FROM UNDERSTAT
print("\n" + "=" * 60)
print("Step 1: Getting All Matches")
print("=" * 60)

all_seasons_matches = []

for season in SEASONS:
    print(f"\nSeason {season}:")
    matches_df = get_understat_matches(season)
    
    if matches_df is not None and not matches_df.empty:
        filepath = os.path.join(OUTPUT_DIR, f"matches_summary_{season}.csv")
        matches_df.to_csv(filepath, index=False)
        print(f"  ✓ Saved {len(matches_df)} matches")
        all_seasons_matches.append(matches_df)
    else:
        print(f"  ⚠️  No matches found for {season}")
    
    # Reduced delay between seasons
    time.sleep(1)

# Combine all matches
if all_seasons_matches:
    all_matches = pd.concat(all_seasons_matches, ignore_index=True)
    print(f"\n✓ Total matches across all seasons: {len(all_matches)}")
else:
    print("\n⚠️  Understat matches not available. Using Football-Data.org matches instead...")
    
    # Try to load from Football-Data.org export
    football_data_dir = "premier_league_data_footballdata"
    
    if os.path.exists(football_data_dir):
        print(f"Loading matches from {football_data_dir}...")
        football_matches = []
        
        for season in SEASONS:
            match_file = os.path.join(football_data_dir, f"matches_{season}.csv")
            if os.path.exists(match_file):
                df = pd.read_csv(match_file)
                
                # Filter to only completed matches (have scores)
                if 'status' in df.columns:
                    df = df[df['status'] == 'FINISHED']
                    print(f"  ℹ Filtered to {len(df)} completed matches")
                
                # Football-Data.org IDs won't work with Understat
                # We need to skip the match-by-match fetching and use team-based approach
                df['match_id'] = None  # Mark as invalid for Understat
                df['season'] = season
                
                football_matches.append(df)
                print(f"  ✓ Loaded {len(df)} matches from {season}")
        
        if football_matches:
            all_matches = pd.concat(football_matches, ignore_index=True)
            print(f"\n✓ Using {len(all_matches)} matches from Football-Data.org")
            print("  ⚠️  Note: Football-Data.org IDs don't work with Understat")
            print("  📌 RECOMMENDATION: Use team-based shot collection instead")
            print("     This will be done automatically in Step 2...\n")
        else:
            print("\n✗ No matches found from any source")
            exit()
    else:
        print(f"\n✗ No data found. Please run the Football-Data.org extractor first.")
        exit()

# 2. GET DETAILED SHOT DATA FOR EACH SEASON
print("\n" + "=" * 60)
print("Step 2: Getting Shot-Level Data for Each Season")
print("=" * 60)

# If we don't have Understat match IDs, use team-based approach
if 'match_id' not in all_matches.columns or all_matches['match_id'].isna().all() or all_matches['match_id'].iloc[0] is None:
    print("\n⚠️  Don't have valid Understat match IDs.")
    print("📌 Using team-based approach (more reliable anyway)...\n")
    
    # Use team-based approach FOR EACH SEASON
    PREMIER_LEAGUE_TEAMS = [
        'Manchester_City', 'Arsenal', 'Liverpool', 'Aston_Villa', 'Tottenham',
        'Chelsea', 'Newcastle_United', 'Manchester_United', 'West_Ham',
        'Brighton', 'Wolves', 'Fulham', 'Brentford', 'Everton',
        'Nottingham_Forest', 'Crystal_Palace', 'Bournemouth', 'Luton',
        'Burnley', 'Sheffield_United', 'Ipswich_Town', 'Southampton', 'Leicester'
    ]
    
    # Process each season
    for target_season in SEASONS:
        print(f"\n{'=' * 60}")
        print(f"Processing {target_season} Season")
        print(f"{'=' * 60}\n")
        print(f"Fetching shots from team pages for {target_season} season...")
        print(f"Processing {len(PREMIER_LEAGUE_TEAMS)} teams with {MAX_WORKERS} concurrent threads...\n")
        
        all_team_shots = []
        successful_teams = 0
        failed_teams = []
        
        # Use ThreadPoolExecutor for concurrent requests
        def fetch_team_shots(team):
            """Wrapper function for thread pool"""
            shots_df = get_understat_team_shots(team, target_season)
            return team, shots_df
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks
            future_to_team = {executor.submit(fetch_team_shots, team): team for team in PREMIER_LEAGUE_TEAMS}
            
            # Process completed tasks
            for idx, future in enumerate(as_completed(future_to_team), 1):
                team = future_to_team[future]
                try:
                    team_name, shots_df = future.result()
                    print(f"[{idx}/{len(PREMIER_LEAGUE_TEAMS)}] {team_name}...", end=" ")
                    
                    if shots_df is not None and not shots_df.empty:
                        all_team_shots.append(shots_df)
                        successful_teams += 1
                        print(f"✓ Got {len(shots_df)} shots")
                    else:
                        failed_teams.append(team_name)
                        print(f"⚠️  No data")
                except Exception as e:
                    failed_teams.append(team)
                    print(f"[{idx}/{len(PREMIER_LEAGUE_TEAMS)}] {team}... ✗ Error: {str(e)[:30]}")
        
        if all_team_shots:
            all_shots_combined = pd.concat(all_team_shots, ignore_index=True)
            
            # Remove duplicates (same shot from home and away team pages)
            all_shots_combined = all_shots_combined.drop_duplicates(
                subset=['match_id', 'player', 'minute', 'X', 'Y'], 
                keep='first'
            )
            
            filepath = os.path.join(OUTPUT_DIR, f"shots_detailed_{target_season}.csv")
            all_shots_combined.to_csv(filepath, index=False)
            print(f"\n✓ Saved {len(all_shots_combined)} unique shots from {successful_teams} teams")
            
            if failed_teams:
                print(f"⚠️  Teams with no data: {', '.join(failed_teams)}")
            
            # Also save JSON
            filepath_json = os.path.join(OUTPUT_DIR, f"shots_detailed_{target_season}.json")
            all_shots_combined.to_json(filepath_json, orient='records', indent=2)
            print(f"✓ Also saved as JSON")
            
            # Create match summary from shots
            match_summary = all_shots_combined.groupby(['match_id', 'h_team', 'a_team']).agg({
                'xG': 'sum',
                'date': 'first'
            }).reset_index()
            match_summary.to_csv(os.path.join(OUTPUT_DIR, f"matches_from_shots_{target_season}.csv"), index=False)
            print(f"✓ Also created match summary with {len(match_summary)} matches\n")
        else:
            print(f"\n✗ No shot data collected for {target_season}\n")
    
    print("\n" + "=" * 60)
    print("✓ Completed team-based data collection for all seasons")
    print("=" * 60)
    print("📌 This approach is actually MORE reliable than match-by-match!")
    print("   You now have shot-level data with coordinates for shot maps!")
    
else:
    # Original match-by-match approach - NOW LOOPS THROUGH ALL SEASONS
    print(f"Fetching detailed data for matches from all seasons...")
    print(f"Using {MAX_WORKERS} concurrent threads for faster processing...")
    print("⚠️  This will take time. Progress will be shown.\n")

    # Process each season separately
    for target_season in SEASONS:
        print(f"\n{'=' * 60}")
        print(f"Processing {target_season} Season")
        print(f"{'=' * 60}\n")
        
        season_matches = all_matches[all_matches['season'] == target_season].copy()
        season_matches = season_matches.drop_duplicates(subset=['match_id'])
        
        print(f"Processing {len(season_matches)} unique matches from {target_season} season...\n")

        all_shots = []
        all_player_stats = []
        
        total_matches = len(season_matches)
        
        # Use ThreadPoolExecutor for concurrent match processing
        def fetch_match_data(match_row):
            """Fetch shots and player stats for a single match"""
            _, match = match_row
            match_id = match['match_id']
            
            shots_df = get_match_shots(match_id)
            if shots_df is not None and not shots_df.empty:
                shots_df['date'] = match['date']
                shots_df['home_team'] = match['home_team']
                shots_df['away_team'] = match['away_team']
                shots_df['season'] = match['season']
            
            player_stats_df = get_match_player_stats(match_id)
            if player_stats_df is not None and not player_stats_df.empty:
                player_stats_df['date'] = match['date']
                player_stats_df['home_team'] = match['home_team']
                player_stats_df['away_team'] = match['away_team']
                player_stats_df['season'] = match['season']
            
            return shots_df, player_stats_df
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_match_data, row): idx for idx, row in enumerate(season_matches.iterrows(), 1)}
            
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    shots_df, player_stats_df = future.result()
                    
                    if shots_df is not None and not shots_df.empty:
                        all_shots.append(shots_df)
                    if player_stats_df is not None and not player_stats_df.empty:
                        all_player_stats.append(player_stats_df)
                    
                    if idx % 10 == 0:
                        print(f"Progress: {idx}/{total_matches} matches processed...")
                        
                except Exception as e:
                    print(f"Error processing match {idx}: {str(e)[:50]}")

        # Save shot data for this season
        if all_shots:
            shots_combined = pd.concat(all_shots, ignore_index=True)
            filepath = os.path.join(OUTPUT_DIR, f"shots_detailed_{target_season}.csv")
            shots_combined.to_csv(filepath, index=False)
            print(f"\n✓ Saved {len(shots_combined)} shots with locations and xG for {target_season}")
            
            filepath_json = os.path.join(OUTPUT_DIR, f"shots_detailed_{target_season}.json")
            shots_combined.to_json(filepath_json, orient='records', indent=2)
            print(f"✓ Also saved as JSON")

        # Save player match stats for this season
        if all_player_stats:
            player_stats_combined = pd.concat(all_player_stats, ignore_index=True)
            filepath = os.path.join(OUTPUT_DIR, f"player_match_stats_{target_season}.csv")
            player_stats_combined.to_csv(filepath, index=False)
            print(f"✓ Saved {len(player_stats_combined)} player-match records for {target_season}")

# 3. STATSBOMB DATA (if available)
print("\n" + "=" * 60)
print("Step 3: Checking StatsBomb Open Data")
print("=" * 60)

statsbomb_comps = get_statsbomb_competitions()
if statsbomb_comps:
    print(f"Found {len(statsbomb_comps)} Premier League seasons in StatsBomb")
    
    for comp in statsbomb_comps:
        season_name = comp['season_name']
        comp_id = comp['competition_id']
        season_id = comp['season_id']
        
        print(f"\nSeason: {season_name}")
        matches = get_statsbomb_matches(comp_id, season_id)
        print(f"  Matches: {len(matches)}")
        
        # Save match list
        matches_df = pd.json_normalize(matches)
        filepath = os.path.join(OUTPUT_DIR, f"statsbomb_matches_{season_name.replace('/', '_')}.csv")
        matches_df.to_csv(filepath, index=False)
        
        # Get shots for first 5 matches as sample
        print(f"  Getting shots for first 5 matches...")
        statsbomb_shots = []
        
        for match in matches[:5]:
            match_id = match['match_id']
            shots_df = get_statsbomb_events(match_id)
            if shots_df is not None and not shots_df.empty:
                statsbomb_shots.append(shots_df)
            time.sleep(1)
        
        if statsbomb_shots:
            shots_combined = pd.concat(statsbomb_shots, ignore_index=True)
            filepath = os.path.join(OUTPUT_DIR, f"statsbomb_shots_{season_name.replace('/', '_')}_sample.csv")
            shots_combined.to_csv(filepath, index=False)
            print(f"  ✓ Saved {len(shots_combined)} StatsBomb shots (sample)")
else:
    print("  ℹ No Premier League data in StatsBomb open data")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 60)
print("EXTRACTION COMPLETE")
print("=" * 60)

csv_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.csv')]
json_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.json')]

print(f"\nTotal CSV files: {len(csv_files)}")
print(f"Total JSON files: {len(json_files)}")
print(f"Location: {os.path.abspath(OUTPUT_DIR)}\n")

if csv_files:
    print("Files created:")
    for file in sorted(csv_files):
        file_path = os.path.join(OUTPUT_DIR, file)
        size_kb = os.path.getsize(file_path) / 1024
        rows = pd.read_csv(file_path).shape[0]
        print(f"  • {file:<50} ({rows:>5} rows, {size_kb:>7.1f} KB)")

print("\n" + "=" * 60)
print("Match-Level Data Available Across All Seasons:")
print("=" * 60)
print(f"""
Seasons: {', '.join(SEASONS)}

Per Match:
  ✓ Match summary with xG for both teams
  ✓ All shots with X,Y coordinates
  ✓ Shot type, situation, result
  ✓ xG per shot
  ✓ Minute of each shot

Per Player Per Match:
  ✓ Goals, assists, shots, key passes
  ✓ xG, xA, xGChain, xGBuildup
  ✓ Minutes played
  ✓ Position

This enables:
  • Shot maps per match/player/team across multiple seasons
  • xG timelines during matches
  • Player performance tracking across matches and seasons
  • Shot quality analysis (xG distribution)
  • Shooting efficiency per player over time
  • Match-by-match xG trends
  • Season-over-season comparisons
  • Multi-year trend analysis

Next: Build Streamlit dashboard with mplsoccer for visualizations!
""")