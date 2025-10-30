import streamlit as st
import feedparser
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dateutil import parser as date_parser
import html
import re
import json
import logging
import pandas as pd
from pathlib import Path

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    filename='app.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="Premier League News",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================
if 'preferences' not in st.session_state:
    st.session_state.preferences = {
        'sources': [],
        'num_articles': 15,
        'dark_mode': False
    }

if 'bookmarks' not in st.session_state:
    st.session_state.bookmarks = []

if 'read_articles' not in st.session_state:
    st.session_state.read_articles = set()

# =============================================================================
# THEME CONFIGURATION
# =============================================================================
def get_theme_colors():
    """Return color scheme based on dark mode preference"""
    if st.session_state.preferences['dark_mode']:
        return {
            'bg_primary': '#1e1e1e',
            'bg_secondary': '#2d2d2d',
            'text_primary': '#ffffff',
            'text_secondary': '#b0b0b0',
            'border': '#404040',
            'link': '#58a6ff'
        }
    else:
        return {
            'bg_primary': '#ffffff',
            'bg_secondary': '#f9f9f9',
            'text_primary': '#000000',
            'text_secondary': '#666666',
            'border': '#dddddd',
            'link': '#1f77b4'
        }

theme = get_theme_colors()

# =============================================================================
# CUSTOM CSS STYLING
# =============================================================================
st.markdown(f"""
    <style>
    .article-container {{
        padding: 15px;
        border-radius: 10px;
        border: 1px solid {theme['border']};
        margin-bottom: 15px;
        background-color: {theme['bg_secondary']};
    }}
    .article-title {{
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 10px;
        color: {theme['link']};
    }}
    .article-meta {{
        font-size: 12px;
        color: {theme['text_secondary']};
        margin-top: 10px;
    }}
    .read-article {{
        opacity: 0.6;
    }}
    .source-badge {{
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        background-color: {theme['link']};
        color: white;
        font-size: 11px;
        margin-right: 8px;
    }}
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# APP HEADER
# =============================================================================
st.title("⚽ Premier League News Aggregator")
st.markdown("*Curated headlines from multiple sports news sources with advanced filtering*")

# =============================================================================
# FEED CONFIGURATION
# =============================================================================
def load_feeds():
    """Load feeds from configuration file or use defaults"""
    config_file = Path('feeds_config.json')
    
    default_feeds = {
        "BBC Sport": "http://newsrss.bbc.co.uk/rss/sportonline_uk_edition/football/rss.xml",
        "Sky Sports": "https://www.skysports.com/rss/12040",
        "Mirror Football": "https://www.mirror.co.uk/sport/football/rss.xml",
        "The Guardian Football": "https://www.theguardian.com/football/rss",
    }
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config file: {e}")
            return default_feeds
    else:
        # Create default config file
        try:
            with open(config_file, 'w') as f:
                json.dump(default_feeds, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to create config file: {e}")
        return default_feeds

FEEDS = load_feeds()

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def clean_html(text):
    """Remove HTML tags and decode entities"""
    if not text:
        return ""
    # Decode HTML entities
    text = html.unescape(text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def humanize_time(date_str):
    """Convert date string to human-readable format"""
    try:
        pub_date = date_parser.parse(date_str)
        now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()
        diff = now - pub_date
        
        if diff.days > 7:
            return pub_date.strftime("%B %d, %Y")
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    except:
        return date_str

def validate_image_url(url):
    """Validate image URL (simplified without requests library)"""
    if not url:
        return None
    # Basic URL validation
    if url.startswith('http') and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        return url
    return None

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def fetch_single_feed(source_name):
    """Fetch articles from a single RSS feed"""
    feed_url = FEEDS[source_name]
    articles = []
    
    try:
        feed = feedparser.parse(feed_url)
        
        if not hasattr(feed, 'entries') or len(feed.entries) == 0:
            logging.warning(f"No entries found for {source_name}")
            return articles
        
        for entry in feed.entries:
            # Extract image URL
            image_url = None
            
            if hasattr(entry, 'media_content') and entry.media_content:
                image_url = entry.media_content[0].get('url')
            elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get('url')
            elif hasattr(entry, 'links'):
                for link in entry.links:
                    if link.get('type', '').startswith('image/'):
                        image_url = link.get('href')
                        break
            
            # Validate image URL
            image_url = validate_image_url(image_url)
            
            article = {
                'title': entry.get('title', 'No title'),
                'summary': clean_html(entry.get('summary', 'No summary available')),
                'link': entry.get('link', '#'),
                'published': entry.get('published', 'Unknown date'),
                'published_parsed': entry.get('published_parsed', None),
                'source': source_name,
                'image': image_url,
                'id': entry.get('id', entry.get('link', ''))
            }
            articles.append(article)
            
    except Exception as e:
        logging.error(f"Error fetching from {source_name}: {str(e)}")
        return []
    
    return articles

@st.cache_data(ttl=300)
def fetch_articles_parallel(selected_feeds):
    """Fetch articles from multiple feeds in parallel"""
    if not selected_feeds:
        return []
    
    with ThreadPoolExecutor(max_workers=min(len(selected_feeds), 4)) as executor:
        results = executor.map(fetch_single_feed, selected_feeds)
    
    articles = [article for result in results for article in result]
    return articles

def deduplicate_articles(articles):
    """Remove duplicate articles based on normalized titles"""
    seen_titles = set()
    unique_articles = []
    
    for article in articles:
        title_normalized = article['title'].lower().strip()
        # Create a simple hash of title for comparison
        title_hash = ''.join(c for c in title_normalized if c.isalnum())
        
        if title_hash not in seen_titles:
            seen_titles.add(title_hash)
            unique_articles.append(article)
    
    return unique_articles

def parse_and_sort_articles(articles):
    """Sort articles by publication date (newest first)"""
    for article in articles:
        try:
            if article['published_parsed']:
                # Convert struct_time to datetime
                article['parsed_date'] = datetime(*article['published_parsed'][:6])
            else:
                article['parsed_date'] = date_parser.parse(article['published'])
        except:
            article['parsed_date'] = datetime.min
    
    return sorted(articles, key=lambda x: x['parsed_date'], reverse=True)

def fuzzy_search(articles, search_terms):
    """Search articles with support for multiple terms"""
    if not search_terms:
        return articles
    
    # Split by comma for multiple terms
    terms = [term.strip().lower() for term in search_terms.split(',') if term.strip()]
    
    if not terms:
        return articles
    
    filtered = []
    for article in articles:
        title_lower = article['title'].lower()
        summary_lower = article['summary'].lower()
        combined_text = f"{title_lower} {summary_lower}"
        
        # Check if ANY term matches (OR logic)
        if any(term in combined_text for term in terms):
            filtered.append(article)
    
    return filtered

def get_source_stats(articles):
    """Calculate article count per source"""
    stats = {}
    for article in articles:
        source = article['source']
        stats[source] = stats.get(source, 0) + 1
    return stats

def export_articles_csv(articles):
    """Convert articles to CSV format"""
    export_data = []
    for article in articles:
        export_data.append({
            'Title': article['title'],
            'Source': article['source'],
            'Published': article['published'],
            'Summary': article['summary'],
            'Link': article['link']
        })
    
    df = pd.DataFrame(export_data)
    return df.to_csv(index=False)

def toggle_bookmark(article_id):
    """Add or remove article from bookmarks"""
    if article_id in st.session_state.bookmarks:
        st.session_state.bookmarks.remove(article_id)
    else:
        st.session_state.bookmarks.append(article_id)

def mark_as_read(article_id):
    """Mark article as read"""
    st.session_state.read_articles.add(article_id)

# =============================================================================
# SIDEBAR CONTROLS
# =============================================================================
st.sidebar.header("📋 Settings")

# Dark mode toggle
dark_mode = st.sidebar.checkbox(
    "🌙 Dark Mode",
    value=st.session_state.preferences['dark_mode'],
    key='dark_mode_toggle'
)
if dark_mode != st.session_state.preferences['dark_mode']:
    st.session_state.preferences['dark_mode'] = dark_mode
    st.rerun()

# Source selection
st.sidebar.subheader("Select News Sources")
selected_sources = st.sidebar.multiselect(
    "Choose one or more sources:",
    options=list(FEEDS.keys()),
    default=st.session_state.preferences['sources'] if st.session_state.preferences['sources'] else list(FEEDS.keys())
)

# Update preferences
if selected_sources != st.session_state.preferences['sources']:
    st.session_state.preferences['sources'] = selected_sources

# Search functionality
st.sidebar.subheader("🔍 Search Articles")
search_term = st.sidebar.text_input(
    "Search (use commas for multiple terms):",
    placeholder="e.g., Arsenal, Liverpool, transfer"
)
st.sidebar.caption("💡 Tip: Use commas to search multiple terms")

# Filter options
st.sidebar.subheader("⚙️ Filter Options")

show_read = st.sidebar.checkbox("Show read articles", value=True)
show_bookmarked_only = st.sidebar.checkbox("Show bookmarked only", value=False)

# Number of articles
num_articles = st.sidebar.slider(
    "Number of articles to display:",
    min_value=5,
    max_value=50,
    value=st.session_state.preferences['num_articles'],
    step=5
)
st.session_state.preferences['num_articles'] = num_articles

# Refresh button
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col2:
    if st.button("🗑️ Clear Read", use_container_width=True):
        st.session_state.read_articles.clear()
        st.rerun()

# =============================================================================
# MAIN CONTENT
# =============================================================================

if not selected_sources:
    st.warning("⚠️ Please select at least one news source from the sidebar.")
else:
    with st.spinner("🔄 Fetching latest news..."):
        articles = fetch_articles_parallel(selected_sources)
    
    if not articles:
        st.error("❌ Failed to fetch articles from selected sources. Please try again later.")
    else:
        # Deduplicate articles
        articles = deduplicate_articles(articles)
        
        # Sort by date
        articles = parse_and_sort_articles(articles)
        
        # Apply search filter
        if search_term:
            articles = fuzzy_search(articles, search_term)
        
        # Apply read filter
        if not show_read:
            articles = [a for a in articles if a['id'] not in st.session_state.read_articles]
        
        # Apply bookmark filter
        if show_bookmarked_only:
            articles = [a for a in articles if a['id'] in st.session_state.bookmarks]
        
        if not articles:
            st.warning("😕 No articles found. Try adjusting your filters or search terms.")
        else:
            # =============================================================================
            # SUMMARY METRICS
            # =============================================================================
            source_stats = get_source_stats(articles)
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("📰 Total Articles", len(articles))
            with col2:
                st.metric("👁️ Displaying", min(num_articles, len(articles)))
            with col3:
                st.metric("📡 Sources", len(selected_sources))
            with col4:
                st.metric("🔖 Bookmarks", len(st.session_state.bookmarks))
            with col5:
                st.metric("✅ Read", len(st.session_state.read_articles))
            
            # Export button
            if articles:
                csv_data = export_articles_csv(articles[:num_articles])
                st.download_button(
                    label="📥 Export to CSV",
                    data=csv_data,
                    file_name=f"news_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=False
                )
            
            # Source breakdown
            with st.expander("📊 Articles by Source"):
                for source, count in sorted(source_stats.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"**{source}**: {count} articles")
            
            st.divider()
            
            # =============================================================================
            # ARTICLE DISPLAY GRID
            # =============================================================================
            num_cols = 3
            article_tiles = [articles[i:i+num_cols] for i in range(0, min(num_articles, len(articles)), num_cols)]
            
            for row in article_tiles:
                cols = st.columns(num_cols)
                for col, article in zip(cols, row):
                    with col:
                        is_read = article['id'] in st.session_state.read_articles
                        is_bookmarked = article['id'] in st.session_state.bookmarks
                        
                        # Container styling
                        container_class = "read-article" if is_read else ""
                        st.markdown(
                            f"<div class='article-container {container_class}' style='border:1px solid {theme['border']}; border-radius:8px; padding:12px; margin-bottom:10px; background:{theme['bg_secondary']};'>",
                            unsafe_allow_html=True
                        )
                        
                        # Image display
                        if article['image']:
                            try:
                                st.image(article['image'], use_container_width=True)
                            except Exception:
                                st.info("🖼️ Image unavailable")
                        else:
                            st.info("📷 No image available")
                        
                        # Title
                        st.markdown(
                            f"<div style='font-size:16px; font-weight:600; margin-top:10px; color:{theme['link']}'>{article['title']}</div>",
                            unsafe_allow_html=True
                        )
                        
                        # Summary
                        summary = article['summary']
                        if len(summary) > 200:
                            summary = summary[:200] + "..."
                        st.markdown(
                            f"<div style='font-size:13px; margin-top:6px; color:{theme['text_primary']}'>{summary}</div>",
                            unsafe_allow_html=True
                        )
                        
                        # Metadata
                        time_ago = humanize_time(article['published'])
                        st.caption(f"🕒 {time_ago} • 📰 {article['source']}")
                        
                        # Action buttons
                        btn_col1, btn_col2, btn_col3 = st.columns(3)
                        
                        with btn_col1:
                            if st.button("📖 Read", key=f"read_{article['id']}", use_container_width=True):
                                mark_as_read(article['id'])
                                st.rerun()
                        
                        with btn_col2:
                            bookmark_label = "⭐" if is_bookmarked else "☆"
                            if st.button(bookmark_label, key=f"bookmark_{article['id']}", use_container_width=True):
                                toggle_bookmark(article['id'])
                                st.rerun()
                        
                        with btn_col3:
                            st.link_button("🔗", article['link'], use_container_width=True)
                        
                        st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# SIDEBAR FOOTER
# =============================================================================
st.sidebar.divider()
st.sidebar.caption("💡 **Tips:**")
st.sidebar.caption("• Use commas to search multiple terms")
st.sidebar.caption("• Click ⭐ to bookmark articles")
st.sidebar.caption("• Click 📖 to mark as read")
st.sidebar.caption("• Articles refresh every 5 minutes")
st.sidebar.caption(f"🔖 {len(st.session_state.bookmarks)} bookmarked • ✅ {len(st.session_state.read_articles)} read")