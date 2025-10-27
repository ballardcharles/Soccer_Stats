"""
Combined Premier League Data Extractor
Pulls data from Understat and FBref (via soccerdata library)

Data Sources:
1. Understat (via soccerdata): Advanced xG stats, shot locations, team analytics, matches
2. FBref (via soccerdata): League standings

Installation Required:
    pip install soccerdata

This creates a comprehensive dataset using only the soccerdata library.
"""

import pandas as pd
import os
from datetime import datetime
import warnings
import soccerdata as sd

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

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

    # Soccerdata format (YXYY - e.g., 1415 for 2014-15)
    sd_seasons = []
    for year in range(start_year, current_season_end):
        next_year = year + 1
        season_str = f"{str(year)[-2:]}{str(next_year)[-2:]}"
        sd_seasons.append(season_str)
    
    # Also keep track of full years for display
    full_seasons = list(range(start_year, current_season_end))
    
    return sd_seasons, full_seasons

# Generate seasons from 2014 to current
SOCCERDATA_SEASONS, DISPLAY_SEASONS = generate_season_list(start_year=2014)

# Output directories
OUTPUT_DIR = "premier_league_combined_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "understat"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "fbref"), exist_ok=True)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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
# MAIN EXTRACTION PROCESS
# ============================================================================

print("=" * 70)
print("PREMIER LEAGUE DATA EXTRACTOR")
print("=" * 70)
print(f"\nSeasons: {DISPLAY_SEASONS[0]}-{DISPLAY_SEASONS[-1]+1}")
print(f"Total seasons: {len(DISPLAY_SEASONS)}")
print(f"Sources: Understat + FBref (via soccerdata library)")
print(f"Output directory: {OUTPUT_DIR}\n")

# ============================================================================
# FBREF EXTRACTION VIA SOCCERDATA
# ============================================================================

print("\n" + "=" * 70)
print("PART 1: FBREF STANDINGS EXTRACTION (via soccerdata)")
print("=" * 70)

try:
    print(f"\nInitializing FBref for seasons: {SOCCERDATA_SEASONS[0]}-{SOCCERDATA_SEASONS[-1]}")
    fbref = sd.FBref(leagues=['ENG-Premier League'], seasons=SOCCERDATA_SEASONS)
    
    print("\nExtracting league standings from FBref...")
    standings = fbref.read_team_season_stats(stat_type="league_table")
    
    # Flatten multi-index columns and reset index
    if isinstance(standings.columns, pd.MultiIndex):
        standings.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in standings.columns.values]
    standings = standings.reset_index()
    
    # Clean column names
    standings.columns = [str(col).lower().replace(' ', '_') for col in standings.columns]
    
    # Save by season
    for season in SOCCERDATA_SEASONS:
        season_data = standings[standings['season'] == season]
        if not season_data.empty:
            save_dataframe(season_data, f"standings_{season}.csv", "fbref")
    
    # Save all seasons
    save_dataframe(standings, "standings_all_seasons.csv", "fbref")
    print(f"  ✓ Saved {len(standings)} standings records")
    
    print("\n✓ FBref data extraction completed successfully!")

except Exception as e:
    print(f"\n✗ Error during FBref extraction: {e}")
    import traceback
    traceback.print_exc()

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
        matches_xg.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in matches_xg.columns.values]
    matches_xg = matches_xg.reset_index()
    
    # Clean column names
    matches_xg.columns = [str(col).lower().replace(' ', '_') for col in matches_xg.columns]
    
    # Standardize date format and create join key
    if 'date' in matches_xg.columns:
        matches_xg['date'] = pd.to_datetime(matches_xg['date']).dt.strftime('%Y-%m-%d')
        
        # Check which column name exists for home team
        home_col = None
        for col in ['home_team', 'hometeam', 'home']:
            if col in matches_xg.columns:
                home_col = col
                break
        
        if home_col:
            matches_xg['home_team_shortened'] = matches_xg[home_col].str.split().str[0]
            matches_xg['join_key'] = matches_xg['date'] + '_' + matches_xg['home_team_shortened']
            matches_xg = matches_xg[['join_key'] + [col for col in matches_xg.columns if col != 'join_key']]
            
            # Rename to standard names if needed
            if home_col != 'home_team':
                matches_xg = matches_xg.rename(columns={home_col: 'home_team'})
        
        # Check away team column
        away_col = None
        for col in ['away_team', 'awayteam', 'away']:
            if col in matches_xg.columns:
                away_col = col
                break
        
        if away_col and away_col != 'away_team':
            matches_xg = matches_xg.rename(columns={away_col: 'away_team'})
    
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
        team_stats.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in team_stats.columns.values]
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
        shots.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in shots.columns.values]
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
        player_season.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in player_season.columns.values]
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
        player_match.columns = ['_'.join(col).strip('_') if col[1] else col[0] for col in player_match.columns.values]
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
# FINAL SUMMARY
# ============================================================================

print("\n" + "=" * 70)
print("✓ EXTRACTION COMPLETE")
print("=" * 70)

print("\nData Structure:")
print("  📁 fbref/")
print("     • standings_{season}.csv - League tables from FBref")
print("     • standings_all_seasons.csv - Combined standings")
print("\n  📁 understat/")
print("     • matches_xG_{season}.csv - Match xG data")
print("     • shots_{season}.csv - All shots with coordinates")
print("     • team_stats_{season}.csv - Team match stats")
print("     • player_season_{season}.csv - Player season stats")
print("     • player_match_{season}.csv - Player match stats")
print("     • *_all_seasons.csv - Combined data")

print("\nWhat you have:")
print("  ✓ League standings (FBref via soccerdata)")
print("  ✓ Match data with xG stats (Understat)")
print("  ✓ Shot locations and coordinates (Understat)")
print("  ✓ Team PPDA and advanced metrics (Understat)")
print("  ✓ Player season and match stats (Understat)")

print("\nNext steps:")
print("  1. Use matches_xG_{season}.csv for comprehensive match analysis")
print("  2. Use shots_all_seasons.csv for shot maps and player analysis")
print("  3. Use standings files for league table tracking")
print("  4. Use player stats for detailed player performance tracking")
print("  5. Build Streamlit dashboard with mplsoccer")
print(f"\n{'=' * 70}\n")