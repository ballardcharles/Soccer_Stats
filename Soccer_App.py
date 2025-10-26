"""
Premier League Analytics Dashboard
Combines all data sources for comprehensive analysis with shot maps
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from mplsoccer import Pitch, VerticalPitch
import os
import glob

# Page config
st.set_page_config(page_title="Premier League Analytics", layout="wide", page_icon="⚽")

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
    """Load all available data sources"""
    data = {
        'shots': None,
        'matches_merged': None,
        'matches_fd': None,
        'matches_us': None,
        'standings': None,
        'teams': None,
        'scorers': None,
        'team_xg': None
    }
    
    base_dir = "premier_league_combined_data"
    
    # Load combined shots data (all seasons)
    shots_file = os.path.join(base_dir, "understat", "shots_all_seasons.csv")
    if os.path.exists(shots_file):
        data['shots'] = pd.read_csv(shots_file)
        st.sidebar.success(f"✓ Loaded {len(data['shots'])} shots")
    
    # Load merged matches (best of both sources)
    merged_files = glob.glob(os.path.join(base_dir, "matches_merged_*.csv"))
    if merged_files:
        merged_dfs = [pd.read_csv(f) for f in merged_files]
        data['matches_merged'] = pd.concat(merged_dfs, ignore_index=True)
        st.sidebar.success(f"✓ Loaded {len(data['matches_merged'])} merged matches")
    
    # Load Football-Data.org matches
    fd_matches_file = os.path.join(base_dir, "football_data", "matches_all_seasons.csv")
    if os.path.exists(fd_matches_file):
        data['matches_fd'] = pd.read_csv(fd_matches_file)
    
    # Load Understat matches
    us_matches_file = os.path.join(base_dir, "understat", "matches_xG_all_seasons.csv")
    if os.path.exists(us_matches_file):
        data['matches_us'] = pd.read_csv(us_matches_file)
    
    # Load standings (combined)
    standings_file = os.path.join(base_dir, "football_data", "standings_all_seasons.csv")
    if os.path.exists(standings_file):
        data['standings'] = pd.read_csv(standings_file)
        st.sidebar.success(f"✓ Loaded standings")
    
    # Load teams
    teams_files = glob.glob(os.path.join(base_dir, "football_data", "teams_*.csv"))
    if teams_files:
        teams_dfs = [pd.read_csv(f) for f in teams_files]
        data['teams'] = pd.concat(teams_dfs, ignore_index=True)
    
    # Load top scorers (combined)
    scorers_file = os.path.join(base_dir, "football_data", "top_scorers_all_seasons.csv")
    if os.path.exists(scorers_file):
        data['scorers'] = pd.read_csv(scorers_file)
        st.sidebar.success(f"✓ Loaded {len(data['scorers'])} scorer records")
    
    # Load team xG stats (combined)
    team_xg_file = os.path.join(base_dir, "understat", "league_xG_all_seasons.csv")
    if os.path.exists(team_xg_file):
        data['team_xg'] = pd.read_csv(team_xg_file)
        st.sidebar.success(f"✓ Loaded team xG stats")
    
    return data

# Load data
with st.spinner('Loading Premier League data...'):
    data = load_all_data()

# ============================================================================
# SIDEBAR
# ============================================================================

st.sidebar.title("⚽ Premier League Analytics")
st.sidebar.markdown("---")

# View selection
view = st.sidebar.radio(
    "Select View:",
    ["🎯 Shot Maps", "📊 Team Analysis", "👤 Player Analysis", "📈 xG Analysis", "🏆 Standings"]
)

st.sidebar.markdown("---")

# Season filter - use string format for consistency
available_seasons = []
if data['shots'] is not None and 'season' in data['shots'].columns:
    available_seasons = sorted(data['shots']['season'].astype(str).unique())
elif data['standings'] is not None and 'season' in data['standings'].columns:
    available_seasons = sorted(data['standings']['season'].astype(str).unique())

if available_seasons:
    selected_season = st.sidebar.selectbox("Season:", available_seasons, index=len(available_seasons)-1)
else:
    st.error("No data available. Please run Full_Understat.py first.")
    st.stop()

# ============================================================================
# SHOT MAPS VIEW
# ============================================================================

if view == "🎯 Shot Maps":
    st.title("🎯 Shot Maps & Analysis")
    
    if data['shots'] is None or data['shots'].empty:
        st.warning("No shot data available. Please run Full_Understat.py.")
        st.stop()
    
    # Filter shots by season (convert to string for comparison)
    season_shots = data['shots'][data['shots']['season'].astype(str) == selected_season].copy()
    
    if season_shots.empty:
        st.warning(f"No shot data available for season {selected_season}")
        st.stop()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_type = st.radio("Filter by:", ["Team", "Match"])
    
    with col2:
        if filter_type == "Team":
            teams = sorted(season_shots['team'].dropna().unique())
            selected_team = st.selectbox("Select Team:", teams)
            team_shots = season_shots[season_shots['team'] == selected_team]
            
            players_on_team = sorted(team_shots['player'].dropna().unique())
            selected_player = st.selectbox("Select Player (Optional):", ['All Players'] + players_on_team)
            
            if selected_player != 'All Players':
                filtered_shots = team_shots[team_shots['player'] == selected_player]
                title = f"{selected_team} - {selected_player} Shots"
            else:
                filtered_shots = team_shots
                title = f"{selected_team} - All Shots"
            
        else:  # Match
            if 'Match' in season_shots.columns:
                matches = sorted(season_shots['Match'].dropna().unique())
                selected_match = st.selectbox("Select Match:", matches)
                filtered_shots = season_shots[season_shots['Match'] == selected_match]
                title = selected_match
            else:
                st.warning("Match information not available in shot data")
                filtered_shots = season_shots
                title = "All Shots"
    
    with col3:
        shot_results = sorted(filtered_shots['result'].dropna().unique())
        selected_results = st.multiselect("Shot Results:", shot_results, default=shot_results)
        filtered_shots = filtered_shots[filtered_shots['result'].isin(selected_results)]
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Shots", len(filtered_shots))
    with col2:
        goals = (filtered_shots['result'] == 'Goal').sum()
        st.metric("Goals", goals)
    with col3:
        total_xg = filtered_shots['xG'].sum()
        st.metric("Total xG", f"{total_xg:.2f}")
    with col4:
        if len(filtered_shots) > 0:
            conversion = (goals / len(filtered_shots) * 100)
            st.metric("Conversion %", f"{conversion:.1f}%")
    
    # Shot Map
    st.subheader(title)
    
    if not filtered_shots.empty:
        pitch = Pitch(pitch_type='statsbomb', pitch_color='#195905', line_color='white',
                      line_zorder=2, linewidth=2)
        fig, ax = pitch.draw(figsize=(14, 10))
        
        for _, shot in filtered_shots.iterrows():
            x = shot['X'] * 120
            y = (1 - shot['Y']) * 80
            
            if shot['result'] == 'Goal':
                color = 'lime'
                size = shot['xG'] * 800 + 200
                marker = 'o'
                alpha = 0.9
                edgecolor = 'white'
            elif shot['result'] == 'SavedShot':
                color = 'yellow'
                size = shot['xG'] * 600 + 150
                marker = 'o'
                alpha = 0.6
                edgecolor = 'white'
            elif shot['result'] == 'BlockedShot':
                color = 'orange'
                size = shot['xG'] * 600 + 150
                marker = 's'
                alpha = 0.6
                edgecolor = 'white'
            else:
                color = 'red'
                size = shot['xG'] * 600 + 150
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
        
        plt.tight_layout()
        st.pyplot(fig)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Shot Type Distribution")
            shot_type_counts = filtered_shots['shot_type'].value_counts()
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.barh(shot_type_counts.index, shot_type_counts.values, color='#37003c')
            ax.set_xlabel('Number of Shots')
            plt.tight_layout()
            st.pyplot(fig)
        
        with col2:
            st.subheader("Situation Distribution")
            situation_counts = filtered_shots['situation'].value_counts()
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.barh(situation_counts.index, situation_counts.values, color='#37003c')
            ax.set_xlabel('Number of Shots')
            plt.tight_layout()
            st.pyplot(fig)
        
        st.subheader("Shot Details")
        display_cols = ['player', 'minute', 'result', 'xG', 'shot_type', 'situation']
        display_cols = [col for col in display_cols if col in filtered_shots.columns]
        st.dataframe(filtered_shots[display_cols].sort_values('xG', ascending=False),
                    use_container_width=True, height=400)
    
    else:
        st.warning("No shots match the selected filters")

# ============================================================================
# TEAM ANALYSIS VIEW
# ============================================================================

elif view == "📊 Team Analysis":
    st.title("📊 Team Analysis")
    
    if data['standings'] is not None:
        season_data = data['standings'][data['standings']['season'].astype(str) == selected_season].copy()
        
        if not season_data.empty:
            st.subheader("League Table")
            
            display_cols = ['position', 'team', 'playedGames', 'won', 'draw', 'lost', 
                          'goalsFor', 'goalsAgainst', 'goalDifference', 'points']
            display_cols = [col for col in display_cols if col in season_data.columns]
            st.dataframe(season_data[display_cols].sort_values('position'),
                        use_container_width=True, height=600)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Top 10 by Points")
                top_10 = season_data.nlargest(10, 'points')
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.barh(top_10['team'], top_10['points'], color='#37003c')
                ax.set_xlabel('Points')
                ax.invert_yaxis()
                ax.grid(axis='x', alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)
            
            with col2:
                st.subheader("Goals For vs Against")
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.scatter(season_data['goalsFor'], season_data['goalsAgainst'], 
                          s=season_data['points']*3, alpha=0.6, c=season_data['points'],
                          cmap='RdYlGn')
                ax.set_xlabel('Goals For')
                ax.set_ylabel('Goals Against')
                ax.grid(alpha=0.3)
                
                top_5 = season_data.nlargest(5, 'points')
                for _, team in top_5.iterrows():
                    ax.annotate(team['team'], 
                               (team['goalsFor'], team['goalsAgainst']),
                               fontsize=8, xytext=(5, 5), textcoords='offset points')
                plt.tight_layout()
                st.pyplot(fig)
    
    if data['team_xg'] is not None:
        st.markdown("---")
        st.subheader("Expected Goals (xG) Analysis")
        
        season_xg = data['team_xg'][data['team_xg']['season'].astype(str) == selected_season].copy()
        
        if not season_xg.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("xG vs Actual Goals")
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.scatter(season_xg['xG'], season_xg['scored'], s=100, alpha=0.6, color='#00ff85')
                
                max_val = max(season_xg['xG'].max(), season_xg['scored'].max())
                ax.plot([0, max_val], [0, max_val], 'r--', alpha=0.5, label='Perfect xG')
                
                ax.set_xlabel('Expected Goals (xG)')
                ax.set_ylabel('Actual Goals Scored')
                ax.legend()
                ax.grid(alpha=0.3)
                
                for _, team in season_xg.iterrows():
                    ax.annotate(team['team'], (team['xG'], team['scored']),
                               fontsize=7, alpha=0.7, xytext=(3, 3), textcoords='offset points')
                plt.tight_layout()
                st.pyplot(fig)
            
            with col2:
                st.subheader("xG Overperformance")
                season_xg['xG_diff'] = season_xg['scored'] - season_xg['xG']
                top_over = season_xg.nlargest(10, 'xG_diff')
                
                fig, ax = plt.subplots(figsize=(8, 6))
                colors = ['green' if x > 0 else 'red' for x in top_over['xG_diff']]
                ax.barh(top_over['team'], top_over['xG_diff'], color=colors, alpha=0.7)
                ax.set_xlabel('Goals - xG')
                ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
                ax.invert_yaxis()
                ax.grid(axis='x', alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)
            
            st.subheader("Team xG Statistics")
            xg_cols = ['team', 'wins', 'draws', 'loses', 'scored', 'missed', 'xG', 'xGA', 'npxG', 'npxGA', 'xpts', 'pts']
            xg_cols = [col for col in xg_cols if col in season_xg.columns]
            st.dataframe(season_xg[xg_cols].sort_values('xG', ascending=False),
                        use_container_width=True)

# ============================================================================
# PLAYER ANALYSIS VIEW
# ============================================================================

elif view == "👤 Player Analysis":
    st.title("👤 Player Analysis")
    
    if data['scorers'] is not None:
        season_scorers = data['scorers'][data['scorers']['season'].astype(str) == selected_season].copy()
        
        if not season_scorers.empty:
            st.subheader("Top Scorers")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                min_goals = st.slider("Minimum Goals:", 0, 30, 5)
            with col2:
                top_n = st.slider("Show Top N:", 10, 50, 20, 5)
            with col3:
                sort_by = st.selectbox("Sort By:", ["goals", "assists"])
            
            filtered_scorers = season_scorers[season_scorers['goals'] >= min_goals]
            filtered_scorers = filtered_scorers.nlargest(top_n, sort_by)
            
            st.dataframe(filtered_scorers, use_container_width=True, height=400)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"Top {min(10, len(filtered_scorers))} by Goals")
                top_goals = filtered_scorers.nlargest(10, 'goals')
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.barh(top_goals['player_name'], top_goals['goals'], color='#37003c')
                ax.set_xlabel('Goals')
                ax.invert_yaxis()
                ax.grid(axis='x', alpha=0.3)
                plt.tight_layout()
                st.pyplot(fig)
            
            with col2:
                st.subheader("Goals vs Assists")
                fig, ax = plt.subplots(figsize=(8, 6))
                scatter = ax.scatter(filtered_scorers['goals'], filtered_scorers['assists'],
                                   s=150, alpha=0.6, c=filtered_scorers['goals'],
                                   cmap='viridis')
                ax.set_xlabel('Goals')
                ax.set_ylabel('Assists')
                ax.grid(alpha=0.3)
                plt.colorbar(scatter, ax=ax, label='Goals')
                
                top_5 = filtered_scorers.nlargest(5, 'goals')
                for _, player in top_5.iterrows():
                    ax.annotate(player['player_name'],
                               (player['goals'], player['assists']),
                               fontsize=8, xytext=(5, 5), textcoords='offset points')
                plt.tight_layout()
                st.pyplot(fig)

# ============================================================================
# xG ANALYSIS VIEW
# ============================================================================

elif view == "📈 xG Analysis":
    st.title("📈 Expected Goals (xG) Analysis")
    
    if data['team_xg'] is None:
        st.warning("No xG data available. Please run Full_Understat.py.")
        st.stop()
    
    season_xg = data['team_xg'][data['team_xg']['season'].astype(str) == selected_season].copy()
    
    if not season_xg.empty:
        st.subheader("xG-Based League Table")
        season_xg['xG_diff'] = season_xg['xG'] - season_xg['xGA']
        season_xg_sorted = season_xg.sort_values('xpts', ascending=False).reset_index(drop=True)
        season_xg_sorted['xG_position'] = range(1, len(season_xg_sorted) + 1)
        
        st.dataframe(season_xg_sorted[['xG_position', 'team', 'xG', 'xGA', 'xG_diff', 'xpts', 'pts']],
                    use_container_width=True)
        
        st.subheader("Expected vs Actual Points")
        fig, ax = plt.subplots(figsize=(12, 8))
        
        x = np.arange(len(season_xg_sorted))
        width = 0.35
        
        ax.bar(x - width/2, season_xg_sorted['xpts'], width, label='xPts', color='#00ff85', alpha=0.7)
        ax.bar(x + width/2, season_xg_sorted['pts'], width, label='Actual Pts', color='#37003c', alpha=0.7)
        
        ax.set_xlabel('Team')
        ax.set_ylabel('Points')
        ax.set_xticks(x)
        ax.set_xticklabels(season_xg_sorted['team'], rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)

# ============================================================================
# STANDINGS VIEW
# ============================================================================

elif view == "🏆 Standings":
    st.title("🏆 League Standings")
    
    if data['standings'] is not None:
        season_data = data['standings'][data['standings']['season'].astype(str) == selected_season].copy()
        
        if not season_data.empty:
            if data['teams'] is not None:
                teams_season = data['teams'][data['teams']['season'].astype(str) == selected_season].copy()
                if not teams_season.empty:
                    if 'team_id' in season_data.columns and 'id' in teams_season.columns:
                        season_data = season_data.merge(
                            teams_season[['id', 'crest']].drop_duplicates('id'), 
                            how='left', 
                            left_on='team_id', 
                            right_on='id'
                        )
        
            st.subheader(f"Season {selected_season}-{int(selected_season)+1}")
            
            display_cols = ['position', 'crest', 'team', 'playedGames', 'won', 'draw', 'lost',
                            'goalsFor', 'goalsAgainst', 'goalDifference', 'points', 'form']
            display_cols = [col for col in display_cols if col in season_data.columns]
            
            styled_df = season_data[display_cols].sort_values('position').reset_index(drop=True)
            
            st.dataframe(styled_df, use_container_width=True, height=700, column_config={
                "crest": st.column_config.ImageColumn("Crest", width="small")
            })
            
            if 'form' in season_data.columns:
                st.subheader("Recent Form")
                st.info("Form string: W=Win, D=Draw, L=Loss (most recent on right)")
    
    else:
        st.warning("No standings data available.")

# ============================================================================
# FOOTER
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("### Data Sources")
st.sidebar.markdown("- Football-Data.org API")
st.sidebar.markdown("- Understat")

st.sidebar.markdown("---")
st.sidebar.info("💡 Tip: Use filters to drill down into specific matches, players, or teams")