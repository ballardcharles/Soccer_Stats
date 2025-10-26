import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import io
from mplsoccer import Pitch

# Page config
st.set_page_config(page_title="Premier League Analytics", layout="wide")

# Patch requests with User-Agent for Understat scraping
original_get = requests.get
def patched_get(*args, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    kwargs["headers"] = headers
    return original_get(*args, **kwargs)
requests.get = patched_get

@st.cache_data(show_spinner=True)
def load_understat_data(season):
    """Load Understat data using soccerdata library"""
    try:
        from soccerdata import Understat
        us = Understat(leagues="ENG-Premier League", seasons=int(season))
        shots = us.read_shot_events().reset_index()
        matches = us.read_team_match_stats().reset_index()
        players = us.read_player_match_stats().reset_index()
        return shots, matches, players
    except ImportError:
        st.error("Please install soccerdata: pip install soccerdata")
        return None, None, None
    except Exception as e:
        st.error(f"Error loading Understat data: {e}")
        return None, None, None

# Title
st.title("⚽ Premier League Analytics Dashboard")
st.subheader("Powered by Understat Data")

# Sidebar controls
st.sidebar.title("Settings")
season = st.sidebar.selectbox("Season:", ["2023", "2024", "2025"], index=1)
view = st.sidebar.radio("Select View:", ["Shot Analysis", "Team Statistics", "Player Statistics"])

# Load Understat data
with st.spinner('Loading Understat data...'):
    shots, matches, player_match_stats = load_understat_data(season)

if shots is None or shots.empty:
    st.error("Unable to load Understat data. Please ensure soccerdata is installed: pip install soccerdata")
    st.stop()

if view == "Shot Analysis":
    st.header("🎯 Shot Analysis")
    
    # Filter controls
    col1, col2 = st.columns(2)
    
    with col1:
        filter_by = st.radio("Filter by:", ["Team", "Player"])
    
    with col2:
        plot_type = st.selectbox("Visualization:", ["Heat Map", "Shot Map", "Positional Map"])
    
    # Team or Player selection
    if filter_by == "Team":
        teams = sorted(shots["team"].unique())
        selected_team = st.selectbox("Select Team:", teams)
        team_shots = shots[shots["team"] == selected_team].copy()
        
        team_players = sorted(team_shots["player"].dropna().unique())
        selected_player = st.selectbox("Select Player (optional):", ["(All Players)"] + team_players)
        
        if selected_player != "(All Players)":
            team_shots = team_shots[team_shots["player"] == selected_player]
            display_title = f"{selected_player} ({selected_team})"
        else:
            display_title = f"{selected_team} - All Players"
    
    else:  # Filter by Player
        all_players = sorted(shots["player"].dropna().unique())
        selected_player = st.selectbox("Select Player:", all_players)
        team_shots = shots[shots["player"] == selected_player].copy()
        selected_team = team_shots["team"].iloc[0] if not team_shots.empty else ""
        display_title = selected_player
    
    # Shot outcome filter
    col1, col2, col3 = st.columns(3)
    
    with col1:
        shot_outcomes = sorted(team_shots["result"].dropna().unique())
        selected_outcomes = st.multiselect("Filter by result:", shot_outcomes, default=shot_outcomes)
        team_shots = team_shots[team_shots["result"].isin(selected_outcomes)].copy()
    
    with col2:
        pitch_theme = st.selectbox("Pitch Theme:", ["grass", "white", "black"], index=0)
    
    with col3:
        show_xg = st.checkbox("Show xG values", value=False)
    
    # Match filter
    if filter_by == "Team":
        match_ids = team_shots["game_id"].unique()
        team_matches = matches[(matches["home_team"] == selected_team) | (matches["away_team"] == selected_team)].copy()
        team_matches["date"] = pd.to_datetime(team_matches["date"])
        
        def get_opponent(row):
            return row["away_team_code"] if row["home_team"] == selected_team else row["home_team_code"]
        def get_home_away(row):
            return "Home" if row["home_team"] == selected_team else "Away"
        
        team_matches["opponent"] = team_matches.apply(get_opponent, axis=1)
        team_matches["home_away"] = team_matches.apply(get_home_away, axis=1)
        match_titles = team_matches.set_index("game_id")[["date", "opponent", "home_away"]].to_dict("index")
        
        match_options = {
            f"{v['date'].strftime('%d %b %Y')} - vs {v['opponent']} ({v['home_away']})": gid
            for gid, v in match_titles.items()
            if gid in match_ids
        }
        match_options = {"All Matches": "all"} | match_options
        match_label = st.selectbox("Select Match:", list(match_options.keys()))
        match_id = match_options[match_label]
        
        if match_id != "all":
            team_shots = team_shots[team_shots["game_id"] == match_id].copy()
    
    # Convert coordinates to pitch scale
    team_shots["x"] = team_shots["location_x"] * 120
    team_shots["y"] = (1 - team_shots["location_y"]) * 80
    
    # Draw pitch
    pitch = Pitch(pitch_type='statsbomb', pitch_color=pitch_theme, 
                  line_color='white' if pitch_theme != 'white' else 'black')
    fig, ax = pitch.draw(figsize=(14, 10))
    
    if not team_shots.empty:
        if plot_type == "Heat Map":
            sns.kdeplot(
                data=team_shots, x="x", y="y", fill=True, ax=ax,
                cmap="YlOrRd", alpha=0.7, thresh=0.05, levels=10
            )
            ax.set_title(f"{display_title} - Shot Heat Map", fontsize=16, fontweight='bold', pad=20)
        
        elif plot_type == "Shot Map":
            for _, row in team_shots.iterrows():
                symbol = "o" if row["result"] == "Goal" else "x"
                color = "lime" if row["result"] == "Goal" else "red"
                size = row["xg"] * 500 + 50  # Size based on xG
                ax.scatter(row["x"], row["y"], s=size, c=color, marker=symbol, 
                          alpha=0.7, edgecolors='white', linewidths=1.5)
                
                if show_xg:
                    ax.text(row["x"], row["y"] + 2, f"{row['xg']:.2f}", fontsize=7,
                           color="white", ha='center', 
                           bbox=dict(facecolor='black', alpha=0.6, pad=1))
            
            ax.set_title(f"{display_title} - Shot Map (size = xG)", fontsize=16, fontweight='bold', pad=20)
        
        elif plot_type == "Positional Map":
            avg_positions = team_shots.groupby("player").agg(
                avg_x=("x", "mean"),
                avg_y=("y", "mean"),
                total_shots=("x", "count")
            ).reset_index()
            
            for _, row in avg_positions.iterrows():
                ax.scatter(row["avg_x"], row["avg_y"], s=200, color="cyan", 
                          alpha=0.8, edgecolors='white', linewidths=2)
                ax.text(row["avg_x"], row["avg_y"], row["player"], fontsize=8,
                       ha='center', va='center', color="black", fontweight='bold',
                       bbox=dict(facecolor='white', alpha=0.9, boxstyle='round,pad=0.3'))
            
            ax.set_title(f"{display_title} - Average Shot Positions", fontsize=16, fontweight='bold', pad=20)
    
    else:
        st.warning("No shot data available for the selected filters.")
    
    plt.tight_layout()
    st.pyplot(fig)
    
    # Statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Shots", len(team_shots))
    with col2:
        goals = (team_shots["result"] == "Goal").sum()
        st.metric("Goals", goals)
    with col3:
        total_xg = team_shots["xg"].sum()
        st.metric("Total xG", f"{total_xg:.2f}")
    with col4:
        conversion = (goals / len(team_shots) * 100) if len(team_shots) > 0 else 0
        st.metric("Conversion %", f"{conversion:.1f}%")
    
    # Player summary table
    st.subheader("Shot Summary")
    summary = team_shots.groupby("player").agg(
        Shots=("xg", "count"),
        Goals=("result", lambda x: (x == "Goal").sum()),
        xG=("xg", "sum")
    ).sort_values("xG", ascending=False)
    summary["Conversion %"] = (summary["Goals"] / summary["Shots"] * 100).round(1)
    st.dataframe(summary.style.format({"xG": "{:.2f}", "Conversion %": "{:.1f}%"}), use_container_width=True)
    
    # Download options
    col1, col2 = st.columns(2)
    
    with col1:
        csv_buffer = io.StringIO()
        team_shots.to_csv(csv_buffer, index=False)
        st.download_button("📥 Download Shot Data (CSV)", data=csv_buffer.getvalue(),
                          file_name="shot_data.csv", mime="text/csv")
    
    with col2:
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', bbox_inches='tight', dpi=300)
        st.download_button("📥 Download Visualization (PNG)", data=img_buffer.getvalue(),
                          file_name="shot_visualization.png", mime="image/png")

elif view == "Team Statistics":
    st.header("📊 Team Statistics")
    
    # Process team match stats
    team_stats = matches.groupby("home_team").agg({
        "home_goals": "sum",
        "home_xg": "sum",
        "away_goals": "sum",
        "away_xg": "sum"
    }).reset_index()
    
    # Also aggregate away stats
    away_stats = matches.groupby("away_team").agg({
        "away_goals": "sum",
        "away_xg": "sum",
        "home_goals": "sum",
        "home_xg": "sum"
    }).reset_index()
    
    # Combine for total stats
    all_teams = sorted(matches["home_team"].unique())
    team_totals = []
    
    for team in all_teams:
        home_games = matches[matches["home_team"] == team]
        away_games = matches[matches["away_team"] == team]
        
        total_gf = home_games["home_goals"].sum() + away_games["away_goals"].sum()
        total_ga = home_games["away_goals"].sum() + away_games["home_goals"].sum()
        total_xgf = home_games["home_xg"].sum() + away_games["away_xg"].sum()
        total_xga = home_games["away_xg"].sum() + away_games["home_xg"].sum()
        
        team_totals.append({
            "Team": team,
            "Goals For": int(total_gf),
            "Goals Against": int(total_ga),
            "Goal Difference": int(total_gf - total_ga),
            "xG For": round(total_xgf, 2),
            "xG Against": round(total_xga, 2),
            "xG Difference": round(total_xgf - total_xga, 2)
        })
    
    team_df = pd.DataFrame(team_totals).sort_values("xG For", ascending=False)
    
    st.dataframe(team_df, use_container_width=True, height=600)
    
    # Visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top 10 Teams by xG")
        fig, ax = plt.subplots(figsize=(8, 6))
        top_10 = team_df.nlargest(10, "xG For")
        ax.barh(top_10["Team"], top_10["xG For"], color='#37003c')
        ax.set_xlabel('Expected Goals (xG)')
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)
    
    with col2:
        st.subheader("Goals vs xG")
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(team_df["xG For"], team_df["Goals For"], s=100, alpha=0.6, color='#00ff85')
        ax.plot([0, team_df["xG For"].max()], [0, team_df["xG For"].max()], 'r--', alpha=0.5, label='Perfect xG')
        ax.set_xlabel('xG For')
        ax.set_ylabel('Goals For')
        ax.legend()
        ax.grid(alpha=0.3)
        for _, team in team_df.iterrows():
            ax.annotate(team["Team"], (team["xG For"], team["Goals For"]), 
                       fontsize=7, alpha=0.7, xytext=(3, 3), textcoords='offset points')
        plt.tight_layout()
        st.pyplot(fig)

else:  # Player Statistics
    st.header("👤 Player Statistics")
    
    # Aggregate player stats from match data
    player_stats = player_match_stats.groupby("player").agg({
        "goals": "sum",
        "assists": "sum",
        "xg": "sum",
        "xa": "sum",
        "shots": "sum",
        "key_passes": "sum"
    }).reset_index()
    
    player_stats.columns = ["Player", "Goals", "Assists", "xG", "xA", "Shots", "Key Passes"]
    player_stats = player_stats.sort_values("xG", ascending=False)
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        min_shots = st.slider("Minimum Shots:", 0, 50, 10, 5)
    with col2:
        stat_filter = st.selectbox("Sort By:", ["xG", "Goals", "Assists", "Shots"])
    with col3:
        top_n = st.slider("Show Top N Players:", 10, 50, 20, 5)
    
    filtered_players = player_stats[player_stats["Shots"] >= min_shots].copy()
    filtered_players = filtered_players.sort_values(stat_filter, ascending=False).head(top_n)
    
    st.subheader(f"Top {top_n} Players (Min {min_shots} shots)")
    st.dataframe(filtered_players.style.format({
        "xG": "{:.2f}", 
        "xA": "{:.2f}"
    }), use_container_width=True, height=400)
    
    # Visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"Top 10 by {stat_filter}")
        fig, ax = plt.subplots(figsize=(8, 6))
        top_10 = filtered_players.head(10)
        ax.barh(top_10["Player"], top_10[stat_filter], color='#37003c')
        ax.set_xlabel(stat_filter)
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)
    
    with col2:
        st.subheader("Goals vs xG")
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(filtered_players["xG"], filtered_players["Goals"], s=150, alpha=0.6, color='#e90052')
        max_val = max(filtered_players["xG"].max(), filtered_players["Goals"].max())
        ax.plot([0, max_val], [0, max_val], 'g--', alpha=0.5, label='Perfect xG')
        ax.set_xlabel('xG')
        ax.set_ylabel('Goals')
        ax.legend()
        ax.grid(alpha=0.3)
        top_5 = filtered_players.nlargest(5, "Goals")
        for _, player in top_5.iterrows():
            ax.annotate(player["Player"], (player["xG"], player["Goals"]), 
                       fontsize=8, alpha=0.8, xytext=(3, 3), textcoords='offset points')
        plt.tight_layout()
        st.pyplot(fig)
    
    # Additional analysis
    st.subheader("Performance Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        # Conversion rate
        conversion_data = filtered_players[filtered_players["Shots"] > 0].copy()
        conversion_data["Conversion %"] = (conversion_data["Goals"] / conversion_data["Shots"] * 100).round(1)
        top_conversion = conversion_data.nlargest(10, "Conversion %")
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh(top_conversion["Player"], top_conversion["Conversion %"], color='#00ff85')
        ax.set_xlabel('Conversion Rate (%)')
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)
    
    with col2:
        # xG overperformance
        overperformance = filtered_players.copy()
        overperformance["xG Diff"] = overperformance["Goals"] - overperformance["xG"]
        top_over = overperformance.nlargest(10, "xG Diff")
        
        fig, ax = plt.subplots(figsize=(8, 6))
        colors = ['green' if x > 0 else 'red' for x in top_over["xG Diff"]]
        ax.barh(top_over["Player"], top_over["xG Diff"], color=colors, alpha=0.7)
        ax.set_xlabel('Goals - xG (Overperformance)')
        ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)

# Footer
st.sidebar.markdown("---")
st.sidebar.success("✅ Using Understat Data")
st.sidebar.info("💡 Data from soccerdata library")