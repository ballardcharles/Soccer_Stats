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
import logging

warnings.filterwarnings('ignore')

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('soccer_data_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Football-Data.org API Configuration (USE ENVIRONMENT VARIABLES)
FOOTBALL_DATA_API_KEY = "33eccf988bdf462e990d1b0f10255dc5"
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
FOOTBALL_DATA_HEADERS = {'X-Auth-Token': FOOTBALL_DATA_API_KEY}
PREMIER_LEAGUE_CODE = "PL"

# Understat Web Scraping Configuration
MAX_WORKERS = 3
REQUEST_DELAY = 0.5
rate_limit_lock = threading.Lock()
last_request_time = {'time': 0}

# ============================================================================
# SEASON CONFIGURATION
# ============================================================================

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

    # Understat full year format (e.g., 2023 for 2023-24 season)
    understat_years = list(range(start_year, current_season_end))
    
    return fd_seasons, sd_seasons, understat_years

# Generate seasons from 2023 to current
FOOTBALL_DATA_SEASONS, SOCCERDATA_SEASONS, UNDERSTAT_YEARS = generate_season_list(start_year=2023)

# Output directories
OUTPUT_DIR = "premier_league_combined_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "football_data"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "understat"), exist_ok=True)

logger.info(f"Seasons to process: {FOOTBALL_DATA_SEASONS[0]}-{FOOTBALL_DATA_SEASONS[-1]+1}")
logger.info(f"Output directory: {OUTPUT_DIR}")

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
        response = requests.get(url, headers=FOOTBALL_DATA_HEADERS, params=params, timeout=10)
        if response.status_code == 429:
            logger.warning("Rate limit reached. Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(url, headers=FOOTBALL_DATA_HEADERS, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            logger.warning(f"Access forbidden - may not be available in free tier for {endpoint}")
        else:
            logger.error(f"HTTP Error: {e}")
        return None
    except Exception as e:
        logger.error(f"Request failed for {endpoint}: {e}")
        return None

def make_understat_request(url):
    """Make Understat web scraping request"""
    respect_rate_limit()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response
    except Exception as e:
        logger.error(f"Web scraping failed for {url}: {e}")
        return None

def save_dataframe(df, filename, subdir=None):
    """Save dataframe as CSV"""
    if df is not None and not df.empty:
        try:
            if subdir:
                filepath = os.path.join(OUTPUT_DIR, subdir, filename)
            else:
                filepath = os.path.join(OUTPUT_DIR, filename)
            df.to_csv(filepath, index=False)
            logger.info(f"✓ Saved: {filename} ({len(df)} rows)")
            return True
        except Exception as e:
            logger.error(f"Failed to save {filename}: {e}")
            return False
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
    """Get matches from Understat with match IDs using web scraping"""
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
                        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                        return df
        return None
    except Exception as e:
        logger.error(f"Error scraping matches from {url}: {e}")
        return None

# ============================================================================
# UNDERSTAT WEB SCRAPING - DETAILED SHOTS
# ============================================================================

def get_match_shots_detailed(match_id):
    """Get all shots from a specific match with detailed fields"""
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
        logger.error(f"Error scraping match {match_id}: {e}")
        return None

# ============================================================================
# XG CALCULATION FUNCTIONS
# ============================================================================

def calculate_match_xg_difference(df):
    """Calculate xG difference (Home xG - Away xG) for each match"""
    if 'home_xg' in df.columns and 'away_xg' in df.columns:
        df['xg_difference'] = (df['home_xg'] - df['away_xg']).round(2)
    elif 'Home xG' in df.columns and 'Away xG' in df.columns:
        df['xG Difference'] = (df['Home xG'] - df['Away xG']).round(2)
    return df

def calculate_team_season_xg_stats(team_stats_df):
    """Calculate season-level xG statistics per team"""
    if team_stats_df is None or team_stats_df.empty:
        return None

    try:
        # Standardize column names
        df = team_stats_df.copy()
        df.columns = [col.lower().replace(' ', '_') for col in df.columns]
        
        # Home games stats
        home_stats = df.groupby(['season_id', 'home_team']).agg({
            'home_xg': 'sum',
            'away_xg': 'sum',
            'home_goals': 'sum',
            'away_goals': 'sum'
        }).reset_index()
        home_stats['home_games'] = df.groupby(['season_id', 'home_team']).size().values
        
        home_stats = home_stats.rename(columns={
            'home_team': 'Team',
            'home_xg': 'xG For (Home)',
            'away_xg': 'xG Against (Home)',
            'home_goals': 'Goals For (Home)',
            'away_goals': 'Goals Against (Home)'
        })
        
        # Away games stats
        away_stats = df.groupby(['season_id', 'away_team']).agg({
            'away_xg': 'sum',
            'home_xg': 'sum',
            'away_goals': 'sum',
            'home_goals': 'sum'
        }).reset_index()
        away_stats['away_games'] = df.groupby(['season_id', 'away_team']).size().values
        
        away_stats = away_stats.rename(columns={
            'away_team': 'Team',
            'away_xg': 'xG For (Away)',
            'home_xg': 'xG Against (Away)',
            'away_goals': 'Goals For (Away)',
            'home_goals': 'Goals Against (Away)'
        })
        
        # Merge home and away
        season_stats = pd.merge(home_stats, away_stats, on=['season_id', 'Team'], how='outer')
        
        # Calculate totals
        season_stats['Total Games'] = season_stats['home_games'].fillna(0) + season_stats['away_games'].fillna(0)
        season_stats['Total xG For'] = season_stats['xG For (Home)'].fillna(0) + season_stats['xG For (Away)'].fillna(0)
        season_stats['Total xG Against'] = season_stats['xG Against (Home)'].fillna(0) + season_stats['xG Against (Away)'].fillna(0)
        season_stats['xG Difference'] = season_stats['Total xG For'] - season_stats['Total xG Against']
        
        # Calculate per-game averages
        season_stats['xG For per Game'] = (season_stats['Total xG For'] / season_stats['Total Games']).round(2)
        season_stats['xG Against per Game'] = (season_stats['Total xG Against'] / season_stats['Total Games']).round(2)
        
        # Round xG columns
        xg_cols = ['Total xG For', 'Total xG Against', 'xG Difference', 'xG For (Home)', 'xG Against (Home)', 'xG For (Away)', 'xG Against (Away)']
        for col in xg_cols:
            if col in season_stats.columns:
                season_stats[col] = season_stats[col].round(2)
        
        # Sort by xG Difference
        season_stats = season_stats.sort_values(['season_id', 'xG Difference'], ascending=[True, False])
        
        return season_stats
    except Exception as e:
        logger.error(f"Error calculating season xG stats: {e}")
        return None

# ============================================================================
# MAIN EXTRACTION PROCESS
# ============================================================================

def main():
    """Main extraction and processing function"""
    
    logger.info("="*70)
    logger.info("COMBINED PREMIER LEAGUE DATA EXTRACTOR - HYBRID VERSION")
    logger.info("="*70)
    
    # Test API connection
    logger.info("\nTesting Football-Data.org API...")
    test = make_football_data_request("competitions")
    if test:
        logger.info("✓ Football-Data.org API connected")
    else:
        logger.warning("✗ Football-Data.org API failed - check API key configuration")
    
    # PART 1: FOOTBALL-DATA.ORG EXTRACTION
    logger.info("\n" + "="*70)
    logger.info("PART 1: FOOTBALL-DATA.ORG EXTRACTION")
    logger.info("="*70)
    
    for season in FOOTBALL_DATA_SEASONS:
        logger.info(f"\nProcessing Season {season}-{season+1}")
        
        # Standings
        standings = get_football_data_standings(season)
        if standings is not None:
            save_dataframe(standings, f"standings_{season}.csv", "football_data")
        time.sleep(2)
        
        # Matches
        fd_matches = get_football_data_matches(season)
        if fd_matches is not None:
            save_dataframe(fd_matches, f"matches_{season}.csv", "football_data")
        time.sleep(2)
        
        # Teams
        teams = get_football_data_teams(season)
        if teams is not None:
            save_dataframe(teams, f"teams_{season}.csv", "football_data")
        time.sleep(2)
        
        # Scorers
        scorers = get_football_data_scorers(season)
        if scorers is not None:
            save_dataframe(scorers, f"scorers_{season}.csv", "football_data")
        time.sleep(2)
    
    # PART 2: UNDERSTAT EXTRACTION VIA SOCCERDATA
    logger.info("\n" + "="*70)
    logger.info("PART 2: UNDERSTAT EXTRACTION (via soccerdata)")
    logger.info("="*70)
    
    try:
        logger.info(f"Initializing Understat for seasons: {SOCCERDATA_SEASONS[0]}-{SOCCERDATA_SEASONS[-1]}")
        understat = sd.Understat(leagues=['ENG-Premier League'], seasons=SOCCERDATA_SEASONS)
        
        # Extract team match stats
        logger.info("\n[1/4] Extracting team match stats...")
        team_stats = understat.read_team_match_stats()
        
        if isinstance(team_stats.columns, pd.MultiIndex):
            team_stats.columns = ['_'.join(col).strip() if col[1] else col[0] for col in team_stats.columns.values]
        
        team_stats = team_stats.reset_index()
        team_stats.columns = [str(col).lower().replace(' ', '_') for col in team_stats.columns]
        
        if 'date' in team_stats.columns:
            team_stats['date'] = pd.to_datetime(team_stats['date']).dt.strftime('%Y-%m-%d')
        
        team_stats['league'] = team_stats['league'].replace('ENG-Premier League', 'Premier League')
        team_stats['game'] = team_stats['game'].str.replace(r'^\d{4}-\d{2}-\d{2} ', '', regex=True).str.replace('-', ' v ')
        
        drop_cols = ['game_id', 'league_id', 'home_team_id', 'away_team_id', 'home_expected_points', 'away_expected_points']
        team_stats = team_stats.drop(columns=[col for col in drop_cols if col in team_stats.columns])
        
        team_stats = team_stats.rename(columns={
            'game': 'Game',
            'season_id': 'Season',
            'league': 'League',
            'date': 'Date',
            'home_team': 'Home Team',
            'away_team': 'Away Team',
            'home_xg': 'Home xG',
            'away_xg': 'Away xG',
            'home_goals': 'Home Goals',
            'away_goals': 'Away Goals',
            'home_np_xg': 'Home Non-Penalty xG',
            'away_np_xg': 'Away Non-Penalty xG',
            'home_ppda': 'Home PPDA',
            'away_ppda': 'Away PPDA'
        })
        
        team_stats = calculate_match_xg_difference(team_stats)
        
        save_dataframe(team_stats, "team_stats_all_seasons.csv", "understat")
        logger.info(f"✓ Saved {len(team_stats)} team match records")
        
        # Calculate season xG statistics
        logger.info("\n[1b/4] Calculating season xG statistics per team...")
        season_xg_stats = calculate_team_season_xg_stats(team_stats)
        if season_xg_stats is not None:
            save_dataframe(season_xg_stats, "team_season_xg_stats.csv", "understat")
            logger.info(f"✓ Saved season xG stats for {len(season_xg_stats)} team-seasons")
        
        # Extract shot events
        logger.info("\n[2/4] Extracting shot events...")
        shots_basic = understat.read_shot_events()
        
        if isinstance(shots_basic.columns, pd.MultiIndex):
            shots_basic.columns = ['_'.join(col).strip() if col[1] else col[0] for col in shots_basic.columns.values]
        
        shots_basic = shots_basic.reset_index()
        shots_basic.columns = [str(col).lower().replace(' ', '_') for col in shots_basic.columns]
        
        if 'date' in shots_basic.columns:
            shots_basic['date'] = pd.to_datetime(shots_basic['date']).dt.strftime('%Y-%m-%d')
        
        save_dataframe(shots_basic, "shots_basic_all_seasons.csv", "understat")
        logger.info(f"✓ Saved {len(shots_basic)} basic shot records")
        
        # Extract player season stats
        logger.info("\n[3/4] Extracting player season stats...")
        player_season = understat.read_player_season_stats()
        
        if isinstance(player_season.columns, pd.MultiIndex):
            player_season.columns = ['_'.join(col).strip() if col[1] else col[0] for col in player_season.columns.values]
        
        player_season = player_season.reset_index()
        player_season.columns = [str(col).lower().replace(' ', '_') for col in player_season.columns]
        
        drop_cols = ['league_id', 'player_id', 'team_id']
        player_season = player_season.drop(columns=[col for col in drop_cols if col in player_season.columns])
        
        save_dataframe(player_season, "player_season_all_seasons.csv", "understat")
        logger.info(f"✓ Saved {len(player_season)} player season records")
        
        # Extract player match stats
        logger.info("\n[4/4] Extracting player match stats...")
        player_match = understat.read_player_match_stats()
        
        if isinstance(player_match.columns, pd.MultiIndex):
            player_match.columns = ['_'.join(col).strip() if col[1] else col[0] for col in player_match.columns.values]
        
        player_match = player_match.reset_index()
        player_match.columns = [str(col).lower().replace(' ', '_') for col in player_match.columns]
        
        drop_cols = ['league_id', 'player_id', 'team_id']
        player_match = player_match.drop(columns=[col for col in drop_cols if col in player_match.columns])
        
        save_dataframe(player_match, "player_match_all_seasons.csv", "understat")
        logger.info(f"✓ Saved {len(player_match)} player match records")
        
        logger.info("\n✓ Understat data extraction completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during Understat extraction: {e}", exc_info=True)
    
    # PART 3: DETAILED SHOTS VIA WEB SCRAPING
    logger.info("\n" + "="*70)
    logger.info("PART 3: DETAILED SHOTS VIA WEB SCRAPING")
    logger.info("="*70)
    
    all_detailed_shots = []
    
    for idx, season in enumerate(SOCCERDATA_SEASONS):
        full_year = UNDERSTAT_YEARS[idx]
        logger.info(f"\nProcessing detailed shots for season {season} (year {full_year})...")
        
        understat_matches = get_understat_matches_with_ids(full_year)
        if understat_matches is None or understat_matches.empty:
            logger.warning(f"No matches found for season {season}")
            continue
        
        understat_matches = calculate_match_xg_difference(understat_matches.rename(columns={
            'home_xg': 'Home xG',
            'away_xg': 'Away xG'
        }))
        
        match_ids = understat_matches['match_id'].unique().tolist()
        logger.info(f"Found {len(match_ids)} matches")
        logger.info(f"Scraping shots from {len(match_ids)} matches with {MAX_WORKERS} threads...")
        
        def fetch_detailed_shots(match_id):
            return match_id, get_match_shots_detailed(match_id)
        
        season_shots = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_detailed_shots, mid): mid for mid in match_ids}
            completed = 0
            successful = 0
            
            for future in as_completed(futures):
                try:
                    match_id, shots_df = future.result()
                    completed += 1
                    
                    if shots_df is not None and not shots_df.empty:
                        match_info = understat_matches[understat_matches['match_id'] == match_id].iloc[0]
                        shots_df['Date'] = match_info['date']
                        shots_df['Game'] = match_info['Match']
                        shots_df['Season'] = full_year
                        shots_df['season_id'] = season
                        season_shots.append(shots_df)
                        successful += 1
                    
                    if completed % 50 == 0:
                        logger.info(f"Progress: {completed}/{len(match_ids)} ({successful} with shots)")
                        
                except Exception as e:
                    logger.error(f"Error processing match: {e}")
        
        if season_shots:
            combined_season = pd.concat(season_shots, ignore_index=True)
            drop_cols = ['shot_id', 'match_id', 'player_id']
            combined_season = combined_season.drop(columns=[col for col in drop_cols if col in combined_season.columns])
            
            column_order = ['Season', 'season_id', 'Date', 'Game', 'Team', 'Player', 'Assist Player',
                          'xG', 'x', 'y', 'Minute', 'Situation', 'Result', 'Shot Type', 'Last Action', 'Home/Away']
            combined_season = combined_season[[col for col in column_order if col in combined_season.columns]]
            
            save_dataframe(combined_season, f"shots_detailed_{season}.csv", "understat")
            all_detailed_shots.append(combined_season)
            logger.info(f"✓ Saved {len(combined_season)} detailed shots for season {season}")
        else:
            logger.warning(f"No shots collected for season {season}")
    
    if all_detailed_shots:
        all_shots_combined = pd.concat(all_detailed_shots, ignore_index=True)
        save_dataframe(all_shots_combined, "shots_detailed_all_seasons.csv", "understat")
        logger.info(f"\n✓ Total detailed shots saved: {len(all_shots_combined)}")
    
    # PART 4: SUMMARY
    logger.info("\n" + "="*70)
    logger.info("✓ EXTRACTION COMPLETE")
    logger.info("="*70)
    
    logger.info("\nData Structure:")
    logger.info(" 📁 football_data/")
    logger.info("   • standings_{season}.csv - League tables")
    logger.info("   • matches_{season}.csv - Match details with scores")
    logger.info("   • teams_{season}.csv - Team information")
    logger.info("   • scorers_{season}.csv - Top scorers")
    logger.info("   • *_all_seasons.csv - Combined data")
    
    logger.info("\n 📁 understat/")
    logger.info("   • team_stats_all_seasons.csv - Team match stats with xG and xG Difference")
    logger.info("   • team_season_xg_stats.csv - Season-level xG statistics per team")
    logger.info("   • shots_detailed_all_seasons.csv - All shots with detailed attributes")
    logger.info("   • player_season_all_seasons.csv - Player season stats")
    logger.info("   • player_match_all_seasons.csv - Player match stats")
    logger.info("   • shots_basic_all_seasons.csv - Basic shot events")
    
    logger.info("\n✓ Data extraction and processing completed successfully!")
    logger.info(f"Check '{OUTPUT_DIR}' directory for all output files")
    logger.info(f"Logs saved to: soccer_data_extraction.log")

if __name__ == "__main__":
    main()