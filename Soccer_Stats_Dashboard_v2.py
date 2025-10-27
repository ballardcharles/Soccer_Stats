"""
Premier League Analytics Dashboard V2
Uses data from Full_Understat_V2.py (soccerdata library)
Comprehensive analysis with shot maps using mplsoccer
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from mplsoccer import Pitch
import os
import glob
import io

# Page config
st.set_page_config(page_title="Premier League Analytics V2", layout="wide", page_icon="⚽")

# Custom CSS
st.markdown("""
<style>
    .main {background-color: #0e1117;}
    h1 {color: #37003c;}
    .stMetric {background-color: #1e1e1e; padding: 10px; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA LOADING
# ============================================================================

@st.cache_data
def load_all_data():
    """Load all available data from Full_Understat_V2.py structure"""
    data = {
        'shots': None,
        'matches_merged': None,
        'matches_xg': None,
        'standings': None,
        'teams': None,
        'scorers': None,
        'team_stats': None,
        'player_season': None,
        'player_match': None
    }
    
    base_dir = "premier_league_combined_data_v2"
    
    # Load Understat shots data (all seasons combined)
    shots_file = os.path.join(base_dir, "understat", "shots_all_seasons.csv")
    if os.path.exists(shots_file):
        data['shots'] = pd.read_csv(shots_file)
        st.sidebar.success(f"✓ Loaded {len(data['shots']):,} shots")
    
    # Load merged matches (best of both sources)
    merged_files = glob.glob(os.path.join(base_dir, "matches_merged_*.csv"))
    if merged_files:
        merged_dfs = [pd.read_csv(f) for f in merged_files]
        data['matches_merged'] = pd.concat(merged_dfs, ignore_index=True)
        st.sidebar.success(f"✓ Loaded {len(data['matches_merged']):,} merged matches")
    
    # Load Understat matches with xg
    us_matches_file = os.path.join(base_dir, "understat", "matches_xg_all_seasons.csv")
    if os.path.exists(us_matches_file):
        data['matches_xg'] = pd.read_csv(us_matches_file)
    
    # Load Football-Data.org standings
    standings_file = os.path.join(base_dir, "football_data", "standings_all_seasons.csv")
    if os.path.exists(standings_file):
        data['standings'] = pd.read_csv(standings_file)
    
    # Load teams
    teams_file = os.path.join(base_dir, "football_data", "teams_all_seasons.csv")
    if os.path.exists(teams_file):
        data['teams'] = pd.read_csv(teams_file)
    
    # Load top scorers
    scorers_file = os.path.join(base_dir, "football_data", "top_scorers_all_seasons.csv")
    if os.path.exists(scorers_file):
        data['scorers'] = pd.read_csv(scorers_file)
    
    # Load Understat team stats
    team_stats_file = os.path.join(base_dir, "understat", "team_stats_all_seasons.csv")
    if os.path.exists(team_stats_file):
        data['team_stats'] = pd.read_csv(team_stats_file)
        st.sidebar.success(f"✓ Loaded {len(data['team_stats']):,} team stat records")
    
    # Load Understat player season stats
    player_season_file = os.path.join(base_dir, "understat", "player_season_all_seasons.csv")
    if os.path.exists(player_season_file):
        data['player_season'] = pd.read_csv(player_season_file)
        st.sidebar.success(f"✓ Loaded {len(data['player_season']):,} player season records")
    
    # Load Understat player match stats
    player_match_file = os.path.join(base_dir, "understat", "player_match_all_seasons.csv")
    if os.path.exists(player_match_file):
        data['player_match'] = pd.read_csv(player_match_file)
    
    return data

# Load data
st.sidebar.title("⚽ Premier League Analytics V2")
st.sidebar.markdown("---")

with st.spinner('Loading Premier League data...'):
    data = load_all_data()

# ============================================================================
# SEASON SELECTION
# ============================================================================

# Get available seasons from shots data (format: 1415, 1516, etc.)
available_seasons = []
if data['shots'] is not None and 'season' in data['shots'].columns:
    available_seasons = sorted(data['shots']['season'].dropna().unique())
elif data['standings'] is not None and 'season' in data['standings'].columns:
    # Convert Football-Data format (2014) to display format (14-15)
    fd_seasons = sorted(data['standings']['season'].dropna().unique())
    available_seasons = [f"{int(s)-2000}-{int(s)-1999}" for s in fd_seasons]

if not available_seasons:
    st.error("No data available. Please run Full_Understat_V2.py first.")
    st.stop()

# Display season in readable format
season_display = st.sidebar.selectbox(
    "Season:", 
    available_seasons,
    format_func=lambda x: f"20{x.split('-')[0]}-20{x.split('-')[1]}" if '-' in str(x) else str(x),
    index=len(available_seasons)-1
)

# Convert display format back to data format for filtering
selected_season = season_display

st.sidebar.markdown("---")

# View selection
view = st.sidebar.selectbox(
    "Select View:",
    ["🎯 Shot Maps", "🏆 Standings", "📊 Team Analysis", "👤 Player Analysis", "📈 xg Analysis"]
)

# ============================================================================
# SHOT MAPS VIEW
# ============================================================================

if view == "🎯 Shot Maps":
    st.title("🎯 Shot Maps & Analysis")
    
    if data['shots'] is None or data['shots'].empty:
        st.warning("No shot data available. Please run Full_Understat_V2.py.")
        st.stop()
    
    # Filter shots by season
    season_shots = data['shots'][data['shots']['season'] == selected_season].copy()
    
    if season_shots.empty:
        st.warning(f"No shot data available for season {selected_season}")
        st.stop()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        teams = sorted(season_shots['team'].dropna().unique())
        selected_team = st.selectbox("Select Team:", teams)
        team_shots = season_shots[season_shots['team'] == selected_team]
        
        players_on_team = sorted(team_shots['player'].dropna().unique())
        selected_player = st.selectbox("Select Player:", ['All Players'] + players_on_team)
        
        if selected_player != 'All Players':
            filtered_shots = team_shots[team_shots['player'] == selected_player]
            title = f"{selected_team} - {selected_player} Shots"
        else:
            filtered_shots = team_shots
            title = f"{selected_team} - All Shots"
    
    with col2:
        # Get matches for selected team
        if 'match_id' in season_shots.columns:
            team_matches = season_shots[season_shots['team'] == selected_team][['match_id', 'home_team', 'away_team']].drop_duplicates()
            team_matches['Match'] = team_matches['home_team'] + ' v ' + team_matches['away_team']
            matches = ['All Matches'] + sorted(team_matches['Match'].unique())
            
            selected_match = st.selectbox("Select Match:", matches)
            
            if selected_match != 'All Matches':
                match_id = team_matches[team_matches['Match'] == selected_match]['match_id'].iloc[0]
                filtered_shots = filtered_shots[filtered_shots['match_id'] == match_id]
                title = f"{selected_match} - {selected_team}"
    
    with col3:
        shot_results = sorted(filtered_shots['result'].dropna().unique())
        selected_results = st.multiselect("Shot Results:", shot_results, default=shot_results)
        filtered_shots = filtered_shots[filtered_shots['result'].isin(selected_results)]
    
    # Visualization type
    viz_type = st.radio("Visualization Type:", ["Shot Map", "Heat Map"], horizontal=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Shots", len(filtered_shots))
    with col2:
        goals = (filtered_shots['result'] == 'Goal').sum()
        st.metric("Goals", goals)
    with col3:
        total_xg = filtered_shots['xg'].sum()
        st.metric("Total xg", f"{total_xg:.2f}")
    with col4:
        if len(filtered_shots) > 0:
            conversion = (goals / len(filtered_shots) * 100)
            st.metric("Conversion %", f"{conversion:.1f}%")
    
    # Shot Map or Heat Map
    st.subheader(title)
    
    if not filtered_shots.empty:
        if viz_type == "Shot Map":
            pitch = Pitch(pitch_type='statsbomb', pitch_color='grass', line_color='white',
                          line_zorder=2, linewidth=2)
            fig, ax = pitch.draw(figsize=(14, 10))
            
            for _, shot in filtered_shots.iterrows():
                # Convert coordinates (X and Y are normalized 0-1)
                x = shot['location_x'] * 120  # StatsBomb pitch is 120 units long
                y = shot['location_y'] * 80   # StatsBomb pitch is 80 units wide
                
                if shot['result'] == 'Goal':
                    color = 'lime'
                    size = shot['xg'] * 800 + 200
                    marker = 'o'
                    alpha = 0.9
                    edgecolor = 'white'
                elif shot['result'] == 'SavedShot':
                    color = 'yellow'
                    size = shot['xg'] * 600 + 150
                    marker = 'o'
                    alpha = 0.6
                    edgecolor = 'white'
                elif shot['result'] == 'BlockedShot':
                    color = 'orange'
                    size = shot['xg'] * 600 + 150
                    marker = 's'
                    alpha = 0.6
                    edgecolor = 'white'
                else:
                    color = 'red'
                    size = shot['xg'] * 600 + 150
                    marker = 'x'
                    alpha = 0.5
                    edgecolor = 'white'
                
                ax.scatter(x, y, s=size, c=color, marker=marker, alpha=alpha,
                          edgecolors=edgecolor, linewidths=2, zorder=3)
            
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], marker='o', color='w', markerfacecolor='lime', 
                       markersize=12, label='Goal', markeredgecolor='white'),
                Line2D([0], [0], marker='o', color='w', markerfacecolor='yellow', 
                       markersize=10, label='Saved', markeredgecolor='white'),
                Line2D([0], [0], marker='s', color='w', markerfacecolor='orange', 
                       markersize=10, label='Blocked', markeredgecolor='white'),
                Line2D([0], [0], marker='x', color='w', markerfacecolor='red', 
                       markersize=10, label='Missed', markeredgecolor='white')
            ]
            ax.legend(handles=legend_elements, loc='upper left', framealpha=0.8)
            
        else:  # Heat Map
            pitch = Pitch(pitch_type='statsbomb', pitch_color='grass', line_color='white',
                          line_zorder=2, linewidth=2)
            fig, ax = pitch.draw(figsize=(14, 10))
            
            x_coords = filtered_shots['location_x'].values * 120
            y_coords = filtered_shots['location_y'].values * 80
            
            sns.kdeplot(
                x=x_coords, 
                y=y_coords, 
                fill=True, 
                ax=ax,
                cmap='Reds', 
                alpha=0.7, 
                thresh=0.05
            )
            
            ax.text(60, 5, f'Total Shots: {len(filtered_shots)}', 
                   fontsize=14, ha='center', fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, pad=0.5))
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()
        st.pyplot(fig)
        
        # Download buttons
        col1, col2 = st.columns(2)
        
        with col1:
            csv_buffer = io.StringIO()
            filtered_shots.to_csv(csv_buffer, index=False)
            st.download_button(
                label="📥 Download Shot Data (CSV)",
                data=csv_buffer.getvalue(),
                file_name=f"shot_data_{title.replace(' ', '_')}.csv",
                mime="text/csv"
            )
        
        with col2:
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', bbox_inches='tight', dpi=300)
            st.download_button(
                label="📥 Download Visualization (PNG)",
                data=img_buffer.getvalue(),
                file_name=f"shot_viz_{title.replace(' ', '_')}.png",
                mime="image/png"
            )
        
        # Additional analysis
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Shot Type Distribution")
            if 'shot_type' in filtered_shots.columns:
                shot_type_counts = filtered_shots['shot_type'].value_counts()
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.barh(shot_type_counts.index, shot_type_counts.values, color='#37003c')
                ax.set_xlabel('Number of Shots')
                plt.tight_layout()
                st.pyplot(fig)
        
        with col2:
            st.subheader("Situation Distribution")
            if 'situation' in filtered_shots.columns:
                situation_counts = filtered_shots['situation'].value_counts()
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.barh(situation_counts.index, situation_counts.values, color='#37003c')
                ax.set_xlabel('Number of Shots')
                plt.tight_layout()
                st.pyplot(fig)
        
        st.subheader("Shot Details")
        display_cols = ['player', 'minute', 'result', 'xg', 'shot_type', 'situation']
        display_cols = [col for col in display_cols if col in filtered_shots.columns]
        st.dataframe(filtered_shots[display_cols].sort_values('xg', ascending=False),
                    use_container_width=True, height=400, hide_index=True)
    
    else:
        st.warning("No shots match the selected filters")

# ============================================================================
# STANDINGS VIEW
# ============================================================================

elif view == "🏆 Standings":
    st.title("🏆 League Standings")
    
    if data['standings'] is not None:
        # Convert selected_season (1415) to Football-Data format (2014)
        fd_season = int("20" + selected_season.split('-')[0])
        season_data = data['standings'][data['standings']['season'] == fd_season].copy()
        
        if not season_data.empty:
            if data['teams'] is not None:
                teams_season = data['teams'][data['teams']['season'] == fd_season].copy()
                if not teams_season.empty and 'crest' in teams_season.columns:
                    season_data = season_data.merge(
                        teams_season[['id', 'crest']].drop_duplicates('id'),
                        how='left',
                        left_on='team_id',
                        right_on='id'
                    )
            
            st.subheader(f"Season 20{selected_season.replace('-', '/20')}")
            
            display_cols = ['position', 'team', 'playedGames', 'won', 'draw', 'lost',
                          'goalsFor', 'goalsAgainst', 'goalDifference', 'points']
            if 'crest' in season_data.columns:
                display_cols.insert(1, 'crest')
            
            display_cols = [col for col in display_cols if col in season_data.columns]
            
            styled_df = season_data[display_cols].sort_values('position').reset_index(drop=True)
            
            column_config = {}
            if 'crest' in styled_df.columns:
                column_config["crest"] = st.column_config.ImageColumn("Crest", width="small")
            
            st.dataframe(styled_df, use_container_width=True, height=700, 
                        hide_index=True, column_config=column_config)
        else:
            st.warning(f"No standings data available for season {selected_season}")
    else:
        st.warning("No standings data available.")

# ============================================================================
# TEAM ANALYSIS VIEW
# ============================================================================

elif view == "📊 Team Analysis":
    st.title("📊 Team Analysis")
    
    # Use team_stats from Understat for detailed xg analysis
    if data['team_stats'] is not None:
        season_stats = data['team_stats'][data['team_stats']['season'] == selected_season].copy()
        
        if not season_stats.empty:
            st.subheader("Team Statistics")
            
            # Display key metrics
            display_cols = ['team', 'scored', 'missed', 'xg', 'xgA', 'npxg', 'npxgA', 
                          'ppda_att', 'ppda_def', 'deep', 'deep_allowed']
            display_cols = [col for col in display_cols if col in season_stats.columns]
            
            # Aggregate by team (sum across matches)
            team_agg = season_stats.groupby('team').agg({
                'scored': 'sum',
                'missed': 'sum',
                'xg': 'sum',
                'xgA': 'sum',
                'npxg': 'sum',
                'npxgA': 'sum',
                'ppda_att': 'mean',
                'ppda_def': 'mean',
                'deep': 'sum',
                'deep_allowed': 'sum'
            }).reset_index()
            
            team_agg['xg_diff'] = team_agg['scored'] - team_agg['xg']
            
            st.dataframe(team_agg.sort_values('xg', ascending=False),
                        use_container_width=True, hide_index=True)
            
            # Visualizations
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("xg vs Actual Goals")
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.scatter(team_agg['xg'], team_agg['scored'], s=100, alpha=0.6, color='#00ff85')
                
                max_val = max(team_agg['xg'].max(), team_agg['scored'].max())
                ax.plot([0, max_val], [0, max_val], 'r--', alpha=0.5, label='Perfect xg')
                
                ax.set_xlabel('Expected Goals (xg)')
                ax.set_ylabel('Actual Goals Scored')
                ax.legend()
                ax.grid(alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)
            
            with col2:
                st.subheader("xg Overperformance")
                top_teams = team_agg.nlargest(15, 'xg')
                
                fig, ax = plt.subplots(figsize=(8, 6))
                colors = ['green' if x > 0 else 'red' for x in top_teams['xg_diff']]
                ax.barh(top_teams['team'], top_teams['xg_diff'], color=colors, alpha=0.7)
                ax.set_xlabel('Goals - xg')
                ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
                ax.invert_yaxis()
                ax.grid(axis='x', alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)
        else:
            st.warning(f"No team stats available for season {selected_season}")
    else:
        st.warning("No team statistics available.")

# ============================================================================
# PLAYER ANALYSIS VIEW
# ============================================================================

elif view == "👤 Player Analysis":
    st.title("👤 Player Analysis")
    
    if data['player_season'] is not None:
        season_players = data['player_season'][data['player_season']['season'] == selected_season].copy()
        
        if not season_players.empty:
            st.subheader("Player Season Statistics")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                min_goals = st.slider("Minimum Goals:", 0, 30, 5)
            with col2:
                top_n = st.slider("Show Top N:", 10, 50, 20, 5)
            with col3:
                sort_by = st.selectbox("Sort By:", ["goals", "xg", "assists", "xA"])
            
            filtered_players = season_players[season_players['goals'] >= min_goals]
            filtered_players = filtered_players.nlargest(top_n, sort_by)
            
            display_cols = ['player_name', 'team_title', 'position', 'games', 'goals', 
                          'xg', 'assists', 'xA', 'shots', 'key_passes', 'npxg']
            display_cols = [col for col in display_cols if col in filtered_players.columns]
            
            st.dataframe(filtered_players[display_cols], use_container_width=True, 
                        height=400, hide_index=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"Top {min(10, len(filtered_players))} by Goals")
                top_goals = filtered_players.nlargest(10, 'goals')
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.barh(top_goals['player_name'], top_goals['goals'], color='#37003c')
                ax.set_xlabel('Goals')
                ax.invert_yaxis()
                ax.grid(axis='x', alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)
            
            with col2:
                st.subheader("Goals vs xg")
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.scatter(filtered_players['xg'], filtered_players['goals'],
                          s=150, alpha=0.6, c=filtered_players['goals'],
                          cmap='viridis')
                
                max_val = max(filtered_players['xg'].max(), filtered_players['goals'].max())
                ax.plot([0, max_val], [0, max_val], 'r--', alpha=0.5, label='Perfect xg')
                
                ax.set_xlabel('xg')
                ax.set_ylabel('Goals')
                ax.legend()
                ax.grid(alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)
        else:
            st.warning(f"No player data available for season {selected_season}")
    else:
        st.warning("No player statistics available.")

# ============================================================================
# xg ANALYSIS VIEW
# ============================================================================

elif view == "📈 xg Analysis":
    st.title("📈 Expected Goals (xg) Analysis")
    
    if data['matches_xg'] is not None:
        season_matches = data['matches_xg'][data['matches_xg']['season'] == selected_season].copy()
        
        if not season_matches.empty:
            st.subheader("Match xg Statistics")
            
            # Calculate team totals
            home_stats = season_matches.groupby('home_team').agg({
                'home_goals': 'sum',
                'away_goals': 'sum',
                'home_xg': 'sum',
                'away_xg': 'sum'
            }).reset_index()
            
            home_stats.columns = ['team', 'goals_for_home', 'goals_against_home', 'xg_for_home', 'xg_against_home']
            
            away_stats = season_matches.groupby('away_team').agg({
                'away_goals': 'sum',
                'home_goals': 'sum',
                'away_xg': 'sum',
                'home_xg': 'sum'
            }).reset_index()
            
            away_stats.columns = ['team', 'goals_for_away', 'goals_against_away', 'xg_for_away', 'xg_against_away']
            
            # Combine home and away
            team_xg = home_stats.merge(away_stats, on='team')
            team_xg['total_goals'] = team_xg['goals_for_home'] + team_xg['goals_for_away']
            team_xg['total_xg'] = team_xg['xg_for_home'] + team_xg['xg_for_away']
            team_xg['xg_diff'] = team_xg['total_goals'] - team_xg['total_xg']
            
            team_xg_sorted = team_xg.sort_values('total_xg', ascending=False)
            
            st.dataframe(team_xg_sorted[['team', 'total_goals', 'total_xg', 'xg_diff']],
                        use_container_width=True, hide_index=True)
            
            # Visualization
            st.subheader("xg Performance")
            fig, ax = plt.subplots(figsize=(12, 8))
            
            x = np.arange(len(team_xg_sorted))
            width = 0.35
            
            ax.bar(x - width/2, team_xg_sorted['total_xg'], width, label='xg', color='#00ff85', alpha=0.7)
            ax.bar(x + width/2, team_xg_sorted['total_goals'], width, label='Actual Goals', color='#37003c', alpha=0.7)
            
            ax.set_xlabel('Team')
            ax.set_ylabel('Goals')
            ax.set_xticks(x)
            ax.set_xticklabels(team_xg_sorted['team'], rotation=45, ha='right')
            ax.legend()
            ax.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.warning(f"No xg data available for season {selected_season}")
    else:
        st.warning("No xg match data available.")

# ============================================================================
# FOOTER
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("### Data Sources")
st.sidebar.markdown("- Football-Data.org API")
st.sidebar.markdown("- Understat (via soccerdata)")

st.sidebar.markdown("---")
st.sidebar.info("💡 Tip: Use filters to drill down into specific matches, players, or teams")