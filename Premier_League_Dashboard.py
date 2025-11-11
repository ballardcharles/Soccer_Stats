import streamlit as st

# This is the main configuration file for your multipage app.
# st.set_page_config() must be the first Streamlit command, and it's
# only called once in this main app.py file.
st.set_page_config(
    page_title="Premier League Hub",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define the pages in your application.
# st.Page() takes the path to the script and adds a title and icon.
pg = st.navigation(
    [
        st.Page("Soccer_Stats_Dashboard_v2.py", title="Stats Dashboard", icon="📊"),
        st.Page("pl_news_app.py", title="News Feed", icon="📰"),
        st.Page("Soccer_Podcast.py", title="Podcast Player", icon="🎙️")
    ],
    position="top"  # This creates the top menu bar
)

# Add a title that will appear on *both* pages, above the navigation
st.title("Premier League Hub")

# Run the selected page's script
pg.run()