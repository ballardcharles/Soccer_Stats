import streamlit as st
import feedparser
from datetime import datetime

# Configure page
st.set_page_config(
    page_title="Premier League News",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom styling
st.markdown("""
    <style>
    .article-container {
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 15px;
        background-color: #f9f9f9;
    }
    .article-title {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 10px;
        color: #1f77b4;
    }
    .article-meta {
        font-size: 12px;
        color: #666;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# App title
st.title("⚽ Premier League News Aggregator")
st.markdown("*Curated headlines from multiple sports news sources*")

# Multiple RSS feeds
FEEDS = {
    "BBC Sport": "http://newsrss.bbc.co.uk/rss/sportonline_uk_edition/football/rss.xml",
    "Sky Sports": "https://www.skysports.com/rss/12040",
    "Mirror Football": "https://www.mirror.co.uk/sport/football/rss.xml",
    "The Guardian Football": "https://www.theguardian.com/football/rss",    
}

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_articles(selected_feeds):
    """Fetch articles from selected RSS feeds"""
    articles = []
    
    for source_name in selected_feeds:
        feed_url = FEEDS[source_name]
        try:
            feed = feedparser.parse(feed_url)
            
            # Check if feed has entries
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                continue
            
            for entry in feed.entries:
                # Extract image URL from various possible sources
                image_url = None
                
                # Try media:content first (most common in BBC feeds)
                if hasattr(entry, 'media_content') and entry.media_content:
                    image_url = entry.media_content[0].get('url')
                
                # Try media:thumbnail as backup
                elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                    image_url = entry.media_thumbnail[0].get('url')
                
                # Try links with image type
                elif hasattr(entry, 'links'):
                    for link in entry.links:
                        if link.get('type', '').startswith('image/'):
                            image_url = link.get('href')
                            break
                
                article = {
                    'title': entry.get('title', 'No title'),
                    'summary': entry.get('summary', 'No summary available'),
                    'link': entry.get('link', '#'),
                    'published': entry.get('published', 'Unknown date'),
                    'source': source_name,
                    'image': image_url
                }
                articles.append(article)
                
        except Exception as e:
            st.sidebar.warning(f"Error fetching from {source_name}")
    
    return articles

def filter_articles_by_search(articles, search_term):
    """Filter articles by search term in title or summary"""
    if not search_term:
        return articles
    
    search_term = search_term.lower()
    filtered = []
    
    for article in articles:
        title_lower = article['title'].lower()
        summary_lower = article['summary'].lower()
        
        if search_term in title_lower or search_term in summary_lower:
            filtered.append(article)
    
    return filtered

# Sidebar controls
st.sidebar.header("📋 Settings")

# Source selection
st.sidebar.subheader("Select News Sources")
selected_sources = st.sidebar.multiselect(
    "Choose one or more sources:",
    options=list(FEEDS.keys()),
    default=list(FEEDS.keys())
)

# Search functionality
st.sidebar.subheader("Search Articles")
search_term = st.sidebar.text_input(
    "Search by team or topic:",
    placeholder="e.g., Arsenal, Liverpool, transfer..."
)

# Number of articles slider
num_articles = st.sidebar.slider(
    "Number of articles to display:",
    min_value=5,
    max_value=50,
    value=15,
    step=5
)

# Refresh button
refresh_button = st.sidebar.button("🔄 Refresh News", use_container_width=True)

# Fetch articles only if sources are selected
if not selected_sources:
    st.warning("Please select at least one news source from the sidebar.")
else:
    with st.spinner("Fetching latest news..."):
        articles = fetch_articles(selected_sources)
    
    # Apply search filter
    if search_term:
        articles = filter_articles_by_search(articles, search_term)
    
    # Display message if no articles found
    if not articles:
        st.warning("No articles found. Try adjusting your filters or search terms.")
    else:
        # Display summary stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Articles", len(articles))
        with col2:
            st.metric("Displaying", min(num_articles, len(articles)))
        with col3:
            st.metric("Sources", len(selected_sources))
        with col4:
            if search_term:
                st.metric("Search", f'"{search_term}"')
            else:
                st.metric("Search", "All")
        
        st.divider()
        
        # Display articles as tiles (3 per row)
        num_cols = 3
        article_tiles = [articles[i:i+num_cols] for i in range(0, min(num_articles, len(articles)), num_cols)]

        for row in article_tiles:
            cols = st.columns(num_cols)
            for col, article in zip(cols, row):
                with col:
                    st.markdown(
                        "<div style='border:1px solid #ddd; border-radius:8px; padding:2px; margin-bottom:10px; background:#f9f9f9;'>",
                        unsafe_allow_html=True
                    )
                    # Image on top (square aspect forced)
                    if article['image']:
                        try:
                            st.image(article['image'], use_container_width=False)
                        except Exception:
                            st.info("Image unavailable")
                    else:
                        st.info("No image available")
                    # Headline below image
                    st.markdown(f"<div style='font-size:16px; font-weight:600; margin-top:10px; color:#1f77b4'>{article['title']}</div>", unsafe_allow_html=True)
                    # Article snippet below headline
                    summary = article['summary']
                    summary = summary.replace('<p>', '').replace('</p>', '').replace('<br/>', ' ').replace('<br>', ' ').replace('&nbsp;', ' ')
                    if len(summary) > 300:
                        summary = summary[:300] + "..."
                    st.markdown(f"<div style='font-size:13px; margin-top:6px;'>{summary}</div>", unsafe_allow_html=True)
                    # Link and metadata
                    st.markdown(
                        f"<a href='{article['link']}' style='font-size:13px; color:#2277bb;' target='_blank'>Read Full Article →</a>",
                        unsafe_allow_html=True
                    )
                    st.caption(f"📰 {article['source']}")
                    st.markdown("</div>", unsafe_allow_html=True)



# Footer
st.sidebar.divider()
st.sidebar.caption("💡 Tip: Use the search box to find articles about specific teams or topics.")
st.sidebar.caption("📰 Select multiple sources to aggregate news from different outlets.")
st.sidebar.caption("🔄 Articles are cached for 5 minutes to improve performance.")