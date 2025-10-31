"""
Premier League Analytics Dashboard
Uses combined data from Full_Understat_V2.py
"""

import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
from mplsoccer import Pitch, VerticalPitch
import os
import glob
import io

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

def get_column_name(df, possible_names):
    """Helper function to get the actual column name from a list of possibilities"""
    if df is None:
        return None
    for name in possible_names:
        if name in df.columns:
            return name
    return None

@st.cache_data
def load_all_data():
    """Load all available data sources"""
    data = {
        'shots': None,
        'matches_merged': None,
        'team_stats': None,
        'standings': None,
        'teams': None,
        'scorers': None,
        'player_season': None,
        'player_match': None
    }
    
    base_dir = "premier_league_combined_data"
    
    # Load combined shots data (all seasons)
    shots_file = os.path.join(base_dir, "understat", "shots_detailed_all_seasons.csv")
    if os.path.exists(shots_file):
        data['shots'] = pd.read_csv(shots_file)
    
    # Load merged matches (best of both sources)
    merged_files = glob.glob(os.path.join(base_dir, "matches_merged_*.csv"))
    if merged_files:
        merged_dfs = [pd.read_csv(f) for f in merged_files]
        data['matches_merged'] = pd.concat(merged_dfs, ignore_index=True)
    
    # Load team stats from Understat
    team_stats_file = os.path.join(base_dir, "understat", "team_stats_all_seasons.csv")
    if os.path.exists(team_stats_file):
        data['team_stats'] = pd.read_csv(team_stats_file)
    
    # Load standings (combined)
    standings_file = os.path.join(base_dir, "football_data", "standings_all_seasons.csv")
    if os.path.exists(standings_file):
        data['standings'] = pd.read_csv(standings_file)
    
    # Load teams
    teams_files = glob.glob(os.path.join(base_dir, "football_data", "teams_*.csv"))
    if teams_files:
        teams_dfs = [pd.read_csv(f) for f in teams_files]
        data['teams'] = pd.concat(teams_dfs, ignore_index=True)
    
    # Load top scorers (combined)
    scorers_file = os.path.join(base_dir, "football_data", "top_scorers_all_seasons.csv")
    if os.path.exists(scorers_file):
        data['scorers'] = pd.read_csv(scorers_file)
    
    # Load player season stats
    player_season_file = os.path.join(base_dir, "understat", "player_season_all_seasons.csv")
    if os.path.exists(player_season_file):
        data['player_season'] = pd.read_csv(player_season_file)
    
    # Load player match stats
    player_match_file = os.path.join(base_dir, "understat", "player_match_all_seasons.csv")
    if os.path.exists(player_match_file):
        data['player_match'] = pd.read_csv(player_match_file)
    
    return data

# Load data
with st.spinner('Loading Premier League data...'):
    data = load_all_data()

# ============================================================================
# SIDEBAR
# ============================================================================

st.sidebar.title("⚽ Premier League Analytics")
st.sidebar.markdown("---")

# Season filter - use consistent format
available_seasons = []
season_col = None

# Check different possible season column names
if data['shots'] is not None:
    season_col = get_column_name(data['shots'], ['Season', 'season'])
    if season_col:
        available_seasons = sorted(data['shots'][season_col].astype(str).unique())
elif data['standings'] is not None:
    season_col = get_column_name(data['standings'], ['Season', 'season'])
    if season_col:
        available_seasons = sorted(data['standings'][season_col].astype(str).unique())

if available_seasons:
    selected_season = st.sidebar.selectbox("Season:", available_seasons, index=len(available_seasons)-1)
else:
    st.error("No data available. Please run Full_Understat_V2.py first.")
    st.stop()

st.sidebar.markdown("---")

# View selection
view = st.sidebar.selectbox(
    "Select View:",
    ["🏆 Standings", "🎯 Shot Maps", "📊 Team Analysis", "👤 Player Analysis", "📈 Match Analysis"]
)


# ============================================================================
# SHOT MAPS VIEW
# ============================================================================

if view == "🎯 Shot Maps":
    st.title("🎯 Shot Maps & Analysis")
    
    if data['shots'] is None or data['shots'].empty:
        st.warning("No shot data available. Please run Full_Understat_V2.py.")
        st.stop()
    
    # Get correct column names
    season_col = get_column_name(data['shots'], ['Season', 'season'])
    team_col = get_column_name(data['shots'], ['Team', 'team'])
    player_col = get_column_name(data['shots'], ['Player', 'player'])
    game_col = get_column_name(data['shots'], ['Game', 'game', 'Match'])
    result_col = get_column_name(data['shots'], ['Result', 'result'])
    xg_col = get_column_name(data['shots'], ['xG', 'xg'])
    x_col = get_column_name(data['shots'], ['x', 'X', 'location_x'])
    y_col = get_column_name(data['shots'], ['y', 'Y', 'location_y'])
    minute_col = get_column_name(data['shots'], ['Minute', 'minute'])
    situation_col = get_column_name(data['shots'], ['Situation', 'situation'])
    shot_type_col = get_column_name(data['shots'], ['Shot Type', 'shot_type'])
    assist_col = get_column_name(data['shots'], ['Assist Player', 'assist_player'])
    
    # Filter shots by season
    season_shots = data['shots'][data['shots'][season_col].astype(str) == selected_season].copy()
    
    if season_shots.empty:
        st.warning(f"No shot data available for season {selected_season}")
        st.stop()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:        
        teams = sorted(season_shots[team_col].dropna().unique())
        selected_team = st.selectbox("Select Team:", teams)
        team_shots = season_shots[season_shots[team_col] == selected_team]
        
        players_on_team = sorted(team_shots[player_col].dropna().unique())
        selected_player = st.selectbox("Select Player:", ['All Players'] + players_on_team)
        
        if selected_player != 'All Players':
            filtered_shots = team_shots[team_shots[player_col] == selected_player]
            title = f"{selected_team} - {selected_player} Shots"
        else:
            filtered_shots = team_shots
            title = f"{selected_team} - All Shots"
                
    with col2:    
        if game_col:
            # Filter matches to only those played by the selected team
            matches = sorted(
                season_shots.loc[season_shots[team_col] == selected_team, game_col].dropna().unique()
            )
            
            if len(matches) == 0:
                st.warning(f"No matches found for {selected_team}.")
            else:
                selected_match = st.selectbox("Select Match:", ['All Matches'] + matches)
                if selected_match != 'All Matches':
                    match_shots = season_shots[
                        (season_shots[game_col] == selected_match) & 
                        (season_shots[team_col] == selected_team)
                    ]
                    filtered_shots = match_shots
                    title = f"{selected_match} - {selected_team}"
        else:
            st.warning("Match information not available in shot data")
    
    with col3:
        if result_col:
            shot_results = sorted(filtered_shots[result_col].dropna().unique())
            selected_results = st.multiselect("Shot Results:", shot_results, default=shot_results)
            filtered_shots = filtered_shots[filtered_shots[result_col].isin(selected_results)]
    
    # Visualization type toggle
    viz_type = st.radio("Visualization Type:", ["Shot Map", "Heat Map"], horizontal=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Shots", len(filtered_shots))
    with col2:
        goals = (filtered_shots[result_col] == 'Goal').sum() if result_col else 0
        st.metric("Goals", goals)
    with col3:
        total_xg = filtered_shots[xg_col].sum() if xg_col else 0
        st.metric("Total xG", f"{total_xg:.2f}")
    with col4:
        if len(filtered_shots) > 0:
            conversion = (goals / len(filtered_shots) * 100)
            st.metric("Conversion %", f"{conversion:.1f}%")
    
    # Shot Map or Heat Map
    st.subheader(title)
    
    if not filtered_shots.empty and x_col and y_col:
        if viz_type == "Shot Map":
            # Shot map visualization
            pitch = Pitch(pitch_type='statsbomb', pitch_color='grass', line_color='white',
                        line_zorder=2, linewidth=2)
            fig, ax = pitch.draw(figsize=(14, 10))
            
            for _, shot in filtered_shots.iterrows():
                x = shot[x_col] * 120
                y = (1 - shot[y_col]) * 80
                
                shot_result = shot[result_col] if result_col else 'Unknown'
                shot_xg = shot[xg_col] if xg_col else 0.1
                
                if shot_result == 'Goal':
                    color = 'lime'
                    size = shot_xg * 800 + 200
                    marker = 'o'
                    alpha = 0.9
                    edgecolor = 'white'
                elif shot_result == 'SavedShot':
                    color = 'yellow'
                    size = shot_xg * 600 + 150
                    marker = 'o'
                    alpha = 0.6
                    edgecolor = 'white'
                elif shot_result == 'BlockedShot':
                    color = 'orange'
                    size = shot_xg * 600 + 150
                    marker = 's'
                    alpha = 0.6
                    edgecolor = 'white'
                else:
                    color = 'red'
                    size = shot_xg * 600 + 150
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
            
            # Prepare data for heatmap
            x_coords = filtered_shots[x_col].values * 120
            y_coords = (1 - filtered_shots[y_col].values) * 80
            
            # Create KDE heatmap
            sns.kdeplot(
                data=filtered_shots, 
                x=x_coords, 
                y=y_coords, 
                fill=True, 
                ax=ax,
                cmap='Reds', 
                alpha=0.7, 
                thresh=0.05
            )
            
            # Add annotation for total shots
            ax.text(60, 5, f'Total Shots: {len(filtered_shots)}', 
                fontsize=14, ha='center', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, pad=0.5))
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()
        st.pyplot(fig)
        
        # Download buttons
        col1, col2 = st.columns(2)
        
        with col1:
            # Download shot data as CSV
            csv_buffer = io.StringIO()
            filtered_shots.to_csv(csv_buffer, index=False)
            st.download_button(
                label="📥 Download Shot Data (CSV)",
                data=csv_buffer.getvalue(),
                file_name=f"shot_data_{title.replace(' ', '_').replace('-', '_')}.csv",
                mime="text/csv"
            )
        
        with col2:
            # Download visualization as PNG
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', bbox_inches='tight', dpi=300)
            st.download_button(
                label="📥 Download Visualization (PNG)",
                data=img_buffer.getvalue(),
                file_name=f"shot_viz_{title.replace(' ', '_').replace('-', '_')}.png",
                mime="image/png"
            )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if shot_type_col:
                st.subheader("Shot Type Distribution")
                shot_type_counts = filtered_shots[shot_type_col].value_counts().reset_index()
                shot_type_counts.columns = ['body_part', 'count']
                st.bar_chart(shot_type_counts.set_index('body_part'), color="#37003c", horizontal=True, height=400)
        
        with col2:
            if situation_col:
                st.subheader("Situation Distribution")
                situation_counts = filtered_shots[situation_col].value_counts().reset_index()
                situation_counts.columns = ['situation', 'count']
                st.bar_chart(situation_counts.set_index('situation'), color="#37003c", horizontal=True, height=400)
        
        st.subheader("Shot Details")
        display_cols = [player_col, minute_col, result_col, xg_col, shot_type_col, situation_col, assist_col]
        display_cols = [col for col in display_cols if col and col in filtered_shots.columns]
        if display_cols:
            sort_col = xg_col if xg_col else display_cols[0]
            st.dataframe(filtered_shots[display_cols].sort_values(sort_col, ascending=False),
                        use_container_width=True, height=400, hide_index=True)
    
    else:
        st.warning("No shots match the selected filters or coordinate data is missing")

# ============================================================================
# TEAM ANALYSIS VIEW
# ============================================================================

elif view == "📊 Team Analysis":
    st.title("📊 Team Analysis")
    
    if data['standings'] is not None:
        # Get column names
        season_col = get_column_name(data['standings'], ['Season', 'season'])
        season_data = data['standings'][data['standings'][season_col].astype(str) == selected_season].copy()
        
        if not season_data.empty:
            st.subheader("League Table")
            
            # Map column names
            col_map = {
                'Position': get_column_name(data['standings'], ['Position', 'position']),
                'Team': get_column_name(data['standings'], ['Team', 'team']),
                'Games Played': get_column_name(data['standings'], ['Games Played', 'playedGames', 'played_games']),
                'Won': get_column_name(data['standings'], ['Won', 'won']),
                'Draw': get_column_name(data['standings'], ['Draw', 'draw']),
                'Lost': get_column_name(data['standings'], ['Lost', 'lost']),
                'Goals For': get_column_name(data['standings'], ['Goals For', 'goalsFor', 'goals_for']),
                'Goals Against': get_column_name(data['standings'], ['Goals Against', 'goalsAgainst', 'goals_against']),
                'Goal Difference': get_column_name(data['standings'], ['Goal Difference', 'goalDifference', 'goal_difference']),
                'Points': get_column_name(data['standings'], ['Points', 'points'])
            }
            
            display_cols = [col_map[k] for k in col_map if col_map[k]]
            position_col = col_map['Position']
            
            st.dataframe(season_data[display_cols].sort_values(position_col),
                        use_container_width=True, height=600, hide_index=True)
            
            col1, col2 = st.columns(2)
            
            points_col = col_map['Points']
            team_col = col_map['Team']

            # Select top 10 and sort ascending by points_col
            top_10 = season_data.nlargest(10, points_col)[[team_col, points_col]].sort_values(points_col, ascending=True)

            # Reset index for Altair
            top_10 = top_10.reset_index(drop=True)

            top_10_chart = alt.Chart(top_10).mark_bar().encode(
                x=alt.X(points_col, title='Points'),
                y=alt.Y(team_col, sort=alt.SortField(points_col, order='descending'), title='Team'),
                color=alt.value("#37003c"),
                tooltip=[team_col, points_col]
            ).properties(height=400)

            with col1:
                st.subheader("Top 10 by Points")
                st.altair_chart(top_10_chart, use_container_width=True)

            gf_col = col_map['Goals For']
            ga_col = col_map['Goals Against']

            goals_data = season_data[[team_col, gf_col, ga_col]].copy()

            goals_scatter = alt.Chart(goals_data).mark_circle().encode(
                x=gf_col,
                y=ga_col,
                size=gf_col,
                color=alt.value("#37003c"),
                tooltip=[team_col, gf_col, ga_col]
            ).properties(height=400)

            with col2:
                st.subheader("Goals For vs Against")
                st.altair_chart(goals_scatter, use_container_width=True)
    
    if data['team_stats'] is not None:
        st.markdown("---")
        st.subheader("Advanced Team Metrics")
        
        season_col = get_column_name(data['team_stats'], ['Season', 'season', 'season_id'])
        season_team_stats = data['team_stats'][data['team_stats'][season_col].astype(str) == selected_season].copy()
        
        if not season_team_stats.empty:
            # Get column names
            home_team_col = get_column_name(data['team_stats'], ['Home Team', 'home_team'])
            home_xg_col = get_column_name(data['team_stats'], ['Home xG', 'home_xg'])
            home_goals_col = get_column_name(data['team_stats'], ['Home Goals', 'home_goals'])
            home_ppda_col = get_column_name(data['team_stats'], ['Home PPDA', 'home_ppda'])
            home_deep_col = get_column_name(data['team_stats'], ['Home Deep Completions', 'home_deep_completions'])
            
            # Aggregate by team
            agg_dict = {}
            if home_xg_col:
                agg_dict[home_xg_col] = 'sum'
            if home_goals_col:
                agg_dict[home_goals_col] = 'sum'
            if home_ppda_col:
                agg_dict[home_ppda_col] = 'mean'
            if home_deep_col:
                agg_dict[home_deep_col] = 'sum'
            
            if home_team_col and agg_dict:
                team_agg = season_team_stats.groupby(home_team_col).agg(agg_dict).reset_index()
                
                # Rename columns
                new_cols = {'Team': home_team_col}
                if home_xg_col:
                    new_cols['Total xG'] = home_xg_col
                if home_goals_col:
                    new_cols['Total Goals'] = home_goals_col
                if home_ppda_col:
                    new_cols['Avg PPDA'] = home_ppda_col
                if home_deep_col:
                    new_cols['Total Deep Completions'] = home_deep_col
                
                team_agg.columns = [new_cols.get(col, col) for col in [home_team_col] + list(agg_dict.keys())]
                
                if 'Total xG' in team_agg.columns and 'Total Goals' in team_agg.columns:
                    team_agg['xG Difference'] = team_agg['Total Goals'] - team_agg['Total xG']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'Total xG' in team_agg.columns and 'Total Goals' in team_agg.columns:
                        st.subheader("xG vs Actual Goals")
                        xg_scatter = team_agg[['Team', 'Total xG', 'Total Goals']].copy()
                        st.scatter_chart(
                            xg_scatter,
                            x='Total xG',
                            y='Total Goals',
                            color='#00ff85',
                            size=50
                        )
                
                with col2:
                    if 'xG Difference' in team_agg.columns:
                        st.subheader("xG Overperformance")
                        top_over = team_agg.nlargest(10, 'xG Difference')[['Team', 'xG Difference']].sort_values('xG Difference', ascending=True)
                        st.bar_chart(top_over.set_index('Team'), color=["#00ff85"], horizontal=True)
                
                st.subheader("Team Statistics")
                st.dataframe(team_agg.sort_values('Total xG', ascending=False) if 'Total xG' in team_agg.columns else team_agg,
                            use_container_width=True, hide_index=True)

# ============================================================================
# PLAYER ANALYSIS VIEW
# ============================================================================

elif view == "👤 Player Analysis":
    st.title("👤 Player Analysis")
    
    if data['player_season'] is not None:
        # Get column names
        season_col = get_column_name(data['player_season'], ['Season', 'season', 'season_id'])
        season_players = data['player_season'][data['player_season'][season_col].astype(str) == selected_season].copy()
        
        if not season_players.empty:
            st.subheader("Player Season Statistics")
            
            # Get column mappings
            minutes_col = get_column_name(season_players, ['Minutes', 'minutes'])
            goals_col = get_column_name(season_players, ['Goals', 'goals'])
            xg_col = get_column_name(season_players, ['xG', 'xg'])
            assists_col = get_column_name(season_players, ['Assists', 'assists'])
            xa_col = get_column_name(season_players, ['xA', 'xa'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                min_minutes = st.slider("Minimum Minutes:", 0, 3000, 500, 100)
            with col2:
                top_n = st.slider("Show Top N:", 10, 50, 20, 5)
            with col3:
                sort_options = [c for c in [goals_col, xg_col, assists_col, xa_col, minutes_col] if c]
                sort_by = st.selectbox("Sort By:", sort_options, index=0 if sort_options else None)
            
            if minutes_col and sort_by:
                filtered_players = season_players[season_players[minutes_col] >= min_minutes]
                filtered_players = filtered_players.nlargest(top_n, sort_by)
                
                st.dataframe(filtered_players, use_container_width=True, height=400, hide_index=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if goals_col:
                        player_col = get_column_name(filtered_players, ['Player', 'player'])
                        st.subheader(f"Top {min(10, len(filtered_players))} by Goals")
                        top_goals = filtered_players.nlargest(10, goals_col)[[player_col, goals_col]].sort_values(goals_col, ascending=True)
                        st.bar_chart(top_goals.set_index(player_col), color="#37003c", horizontal=True)
                
                with col2:
                    if goals_col and xg_col:
                        st.subheader("Goals vs xG")
                        goals_xg = filtered_players[[player_col, goals_col, xg_col]].copy()
                        st.scatter_chart(
                            goals_xg,
                            x=xg_col,
                            y=goals_col,
                            color='#37003c',
                            size=goals_col
                        )
    
    # Add top scorers from Football-Data if available
    if data['scorers'] is not None:
        st.markdown("---")
        st.subheader("Top Scorers (Official)")
        
        # Check which season column name exists
        season_col = 'Season' if 'Season' in data['scorers'].columns else 'season'
        season_scorers = data['scorers'][data['scorers'][season_col].astype(str) == selected_season].copy()
        
        if not season_scorers.empty:
            goals_col = 'Goals' if 'Goals' in season_scorers.columns else 'goals'
            top_scorers = season_scorers.nlargest(20, goals_col)
            
            # Map column names flexibly
            col_mapping = {
                'Player': 'Player' if 'Player' in season_scorers.columns else 'player_name',
                'Team': 'Team' if 'Team' in season_scorers.columns else 'team',
                'Goals': 'Goals' if 'Goals' in season_scorers.columns else 'goals',
                'Assists': 'Assists' if 'Assists' in season_scorers.columns else 'assists',
                'Penalties': 'Penalties' if 'Penalties' in season_scorers.columns else 'penalties'
            }
            
            display_cols = [col_mapping[col] for col in col_mapping if col_mapping[col] in top_scorers.columns]
            st.dataframe(top_scorers[display_cols], use_container_width=True, hide_index=True)

# ============================================================================
# MATCH ANALYSIS VIEW
# ============================================================================

elif view == "📈 Match Analysis":
    st.title("📈 Match Analysis")
    
    if data['matches_merged'] is not None:
        season_col = get_column_name(data['matches_merged'], ['Season', 'season'])
        season_matches = data['matches_merged'][data['matches_merged'][season_col].astype(str) == selected_season].copy()
        
        if not season_matches.empty:
            st.subheader(f"Season {selected_season} Matches")
            
            # Get column names
            game_col = get_column_name(season_matches, ['Game', 'game'])
            date_col = get_column_name(season_matches, ['Date', 'date'])
            home_team_col = get_column_name(season_matches, ['Home Team', 'home_team'])
            away_team_col = get_column_name(season_matches, ['Away Team', 'away_team'])
            home_goals_col = get_column_name(season_matches, ['Home Goals', 'home_goals'])
            away_goals_col = get_column_name(season_matches, ['Away Goals', 'away_goals'])
            home_xg_col = get_column_name(season_matches, ['Home xG', 'home_xg'])
            away_xg_col = get_column_name(season_matches, ['Away xG', 'away_xg'])
            referee_col = get_column_name(season_matches, ['Referee', 'referee'])
            status_col = get_column_name(season_matches, ['Status', 'status'])
            matchweek_col = get_column_name(season_matches, ['Match Week', 'matchday'])
            home_ppda_col = get_column_name(season_matches, ['Home PPDA', 'home_ppda'])
            away_ppda_col = get_column_name(season_matches, ['Away PPDA', 'away_ppda'])
            home_deep_col = get_column_name(season_matches, ['Home Deep Completions', 'home_deep_completions'])
            away_deep_col = get_column_name(season_matches, ['Away Deep Completions', 'away_deep_completions'])
            home_npxg_col = get_column_name(season_matches, ['Home Non-Penalty xG', 'home_np_xg'])
            away_npxg_col = get_column_name(season_matches, ['Away Non-Penalty xG', 'away_np_xg'])
            
            # Match selector
            if game_col:
                matches = sorted(season_matches[game_col].dropna().unique())
                selected_match = st.selectbox("Select Match:", matches)
                
                match_data = season_matches[season_matches[game_col] == selected_match].iloc[0]
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.subheader("Match Details")
                    if date_col and date_col in match_data.index:
                        st.write(f"**Date:** {match_data[date_col]}")
                    if referee_col and referee_col in match_data.index:
                        st.write(f"**Referee:** {match_data[referee_col]}")
                    if status_col and status_col in match_data.index:
                        st.write(f"**Status:** {match_data[status_col]}")
                
                with col2:
                    st.subheader("Score")
                    home_goals = match_data[home_goals_col] if home_goals_col and home_goals_col in match_data.index else 'N/A'
                    away_goals = match_data[away_goals_col] if away_goals_col and away_goals_col in match_data.index else 'N/A'
                    st.metric("Home", home_goals)
                    st.metric("Away", away_goals)
                
                with col3:
                    st.subheader("Expected Goals (xG)")
                    home_xg = match_data[home_xg_col] if home_xg_col and home_xg_col in match_data.index else 0
                    away_xg = match_data[away_xg_col] if away_xg_col and away_xg_col in match_data.index else 0
                    st.metric("Home xG", f"{home_xg:.2f}")
                    st.metric("Away xG", f"{away_xg:.2f}")
                
                st.markdown("---")
                
                # Advanced stats
                col1, col2 = st.columns(2)
                
                with col1:
                    home_team = match_data[home_team_col] if home_team_col and home_team_col in match_data.index else 'Home'
                    st.subheader(f"{home_team} Stats")
                    if home_ppda_col and home_ppda_col in match_data.index:
                        st.metric("PPDA", f"{match_data[home_ppda_col]:.2f}")
                    if home_deep_col and home_deep_col in match_data.index:
                        st.metric("Deep Completions", match_data[home_deep_col])
                    if home_npxg_col and home_npxg_col in match_data.index:
                        st.metric("Non-Penalty xG", f"{match_data[home_npxg_col]:.2f}")
                
                with col2:
                    away_team = match_data[away_team_col] if away_team_col and away_team_col in match_data.index else 'Away'
                    st.subheader(f"{away_team} Stats")
                    if away_ppda_col and away_ppda_col in match_data.index:
                        st.metric("PPDA", f"{match_data[away_ppda_col]:.2f}")
                    if away_deep_col and away_deep_col in match_data.index:
                        st.metric("Deep Completions", match_data[away_deep_col])
                    if away_npxg_col and away_npxg_col in match_data.index:
                        st.metric("Non-Penalty xG", f"{match_data[away_npxg_col]:.2f}")
            
            st.markdown("---")
            st.subheader("All Matches")
            
            # Display all matches
            display_cols = [date_col, game_col, home_goals_col, away_goals_col, home_xg_col, away_xg_col, 
                        referee_col, matchweek_col]
            display_cols = [col for col in display_cols if col and col in season_matches.columns]
            if display_cols and date_col:
                st.dataframe(season_matches[display_cols].sort_values(date_col, ascending=False),
                            use_container_width=True, height=500, hide_index=True)
            else:
                st.dataframe(season_matches,
                            use_container_width=True, height=500, hide_index=True)

# ============================================================================
# STANDINGS VIEW
# ============================================================================

elif view == "🏆 Standings":
    st.title("🏆 League Standings")
    
    if data['standings'] is not None:
        season_col = get_column_name(data['standings'], ['Season', 'season'])
        season_data = data['standings'][data['standings'][season_col].astype(str) == selected_season].copy()
        
        if not season_data.empty:
            # Try to merge with teams data for crests
            if data['teams'] is not None:
                teams_season_col = get_column_name(data['teams'], ['Season', 'season'])
                teams_season_data = data['teams'][data['teams'][teams_season_col].astype(str) == selected_season].copy()
                
                if not teams_season_data.empty:
                    # Get column names from teams table
                    teams_name_col = get_column_name(teams_season_data, ['Name', 'name', 'Team', 'team'])
                    teams_crest_col = get_column_name(teams_season_data, ['Crest', 'crest'])
                    standings_team_col = get_column_name(season_data, ['Team', 'team'])
                    
                    if teams_name_col and teams_crest_col and standings_team_col:
                        # Create a mapping of team names to crests
                        crest_mapping = teams_season_data[[teams_name_col, teams_crest_col]].drop_duplicates()
                        crest_mapping.columns = ['team_name', 'crest_url']
                        
                        # Merge crests into standings
                        season_data = season_data.merge(
                            crest_mapping,
                            left_on=standings_team_col,
                            right_on='team_name',
                            how='left'
                        )
            
            st.subheader(f"Season {selected_season}-{int(selected_season)+1}")
            
            # Get column names
            position_col = get_column_name(season_data, ['Position', 'position'])
            team_col = get_column_name(season_data, ['Team', 'team'])
            played_col = get_column_name(season_data, ['Games Played', 'playedGames', 'played_games'])
            won_col = get_column_name(season_data, ['Won', 'won'])
            draw_col = get_column_name(season_data, ['Draw', 'draw'])
            lost_col = get_column_name(season_data, ['Lost', 'lost'])
            gf_col = get_column_name(season_data, ['Goals For', 'goalsFor', 'goals_for'])
            ga_col = get_column_name(season_data, ['Goals Against', 'goalsAgainst', 'goals_against'])
            gd_col = get_column_name(season_data, ['Goal Difference', 'goalDifference', 'goal_difference'])
            points_col = get_column_name(season_data, ['Points', 'points'])
            form_col = get_column_name(season_data, ['Form', 'form'])
            
            # Build display columns list, including crest if available
            display_cols = [position_col]
            
            # Add crest column if it exists
            if 'crest_url' in season_data.columns:
                display_cols.append('crest_url')
            
            # Add remaining columns
            display_cols.extend([team_col, played_col, won_col, draw_col, lost_col,
                            gf_col, ga_col, gd_col, points_col, form_col])
            display_cols = [col for col in display_cols if col]
            
            styled_df = season_data[display_cols].sort_values(position_col).reset_index(drop=True)
            
            # Configure column display with image column for crests
            column_config = {}
            if 'crest_url' in styled_df.columns:
                column_config['crest_url'] = st.column_config.ImageColumn(
                    "Crest",
                    width="small",
                    help="Team crest"
                )
            
            st.dataframe(
                styled_df, 
                use_container_width=True, 
                height=700, 
                hide_index=True,
                column_config=column_config
            )
            
            if form_col:
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
st.sidebar.markdown("- Understat (via soccerdata)")

st.sidebar.markdown("---")
st.sidebar.info("💡 Tip: Use filters to drill down into specific matches, players, or teams")
st.sidebar.markdown("---")
st.sidebar.caption("Powered by Full_Understat_V2.py")