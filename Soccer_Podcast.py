import streamlit as st
import feedparser

# --- App Configuration ---
st.set_page_config(page_title="Streamlit Podcast Player", layout="wide")

# 1. UPDATED PODCAST DICTIONARY
# Now a nested dictionary to hold more info (RSS feed and website)
PODCAST_FEEDS = {
    "Arsenal Vision Podcast": {
        "rss": "https://feeds.simplecast.com/sjbSL_pM",
        "web": "https://www.arsenalvisionpodcast.com/"
    },
    "Arseblog (Arsecast)": {
        "rss": "http://rss.acast.com/arseblog",
        "web": "https://arseblog.com/"
    }
}

# --- Caching the Feed Parsing ---
@st.cache_data(ttl=3600)  # Cache for 1 hour
def parse_feed(feed_url):
    """
    Parses the RSS feed.
    Returns a dict: {"image_url": url, "episodes": [list_of_episodes]}
    """
    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            st.error(f"Error parsing feed: {feed.bozo_exception}")
            return {"image_url": None, "episodes": []}
            
        # Get the show's main cover image
        show_image_url = None
        if "image" in feed.feed and "href" in feed.feed.image:
            show_image_url = feed.feed.image.href
        elif "itunes_image" in feed.feed and "href" in feed.feed.itunes_image:
            show_image_url = feed.feed.itunes_image.href
            
        episodes = []
        for entry in feed.entries:
            # Find the audio file URL
            audio_url = None
            for enclosure in entry.get("enclosures", []):
                if enclosure.type.startswith("audio"):
                    audio_url = enclosure.href
                    break
            
            if audio_url:
                episodes.append({
                    "title": entry.title,
                    "published": entry.published,
                    "summary": entry.summary,
                    "url": audio_url
                })
        
        return {"image_url": show_image_url, "episodes": episodes}
        
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return {"image_url": None, "episodes": []}

# --- Sidebar ---
st.sidebar.title("Podcast Selector")

# 1. Select the Podcast Feed
selected_podcast_name = st.sidebar.selectbox(
    "Choose a podcast:",
    PODCAST_FEEDS.keys()
)

# 2. Get the info for the selected podcast
selected_podcast_info = PODCAST_FEEDS[selected_podcast_name]
RSS_FEED_URL = selected_podcast_info["rss"]

# 3. Parse the feed
feed_data = parse_feed(RSS_FEED_URL)
episodes = feed_data["episodes"]
show_image_url = feed_data.get("image_url")

# 4. Display the cover art and website link
if show_image_url:
    st.sidebar.image(show_image_url, use_container_width=True, caption=selected_podcast_name)

# 2. DISPLAY WEBSITE LINK
st.sidebar.markdown(f"**Show Website:** [{selected_podcast_name}]({selected_podcast_info['web']})", 
                    unsafe_allow_html=True)


# --- Main Player ---
if not episodes:
    st.warning("No episodes found or feed could not be loaded.")
else:
    # 5. Select an episode
    episode_titles = [e["title"] for e in episodes]
    
    st.sidebar.header("Select Episode")
    selected_title = st.sidebar.selectbox(
        "Choose an episode to play:",
        episode_titles
    )
    
    # Find the full episode details
    selected_episode = next(e for e in episodes if e["title"] == selected_title)
    
    # --- Display the player ---
    st.title(f"🎙️ {selected_podcast_name}")
    st.header(selected_episode["title"])
    st.write(f"**Published:** {selected_episode['published']}")
    
    # Display the audio player
    st.audio(selected_episode["url"])
    
    # Show the episode summary/notes
    with st.expander("Show Notes"):
        st.markdown(selected_episode["summary"], unsafe_allow_html=True)