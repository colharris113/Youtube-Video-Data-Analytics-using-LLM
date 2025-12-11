# youtube_analytics_app.py — Enhanced version with clickable video links and stats

from googleapiclient.discovery import build
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import numpy as np
import os, tempfile, re, subprocess, math

# Import configuration
try:
    from config import (
        YOUTUBE_API_KEY,
        DEFAULT_CHANNEL,
        DEFAULT_MAX_RESULTS,
        DEFAULT_ORDER,
        OLLAMA_BASE_URL,
        OLLAMA_MODEL,
        SHORT_MAX_DURATION,
        LONG_MIN_DURATION,
        RIVAL_CHANNELS,
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET,
        GOOGLE_REDIRECT_URI,
        validate_config,
        get_config_summary
    )
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    # Fallback defaults
    YOUTUBE_API_KEY = ""
    DEFAULT_CHANNEL = "The Uranium Hunter"
    GOOGLE_CLIENT_ID = ""
    GOOGLE_CLIENT_SECRET = ""
    GOOGLE_REDIRECT_URI = "http://localhost:8501"
    DEFAULT_MAX_RESULTS = 50
    DEFAULT_ORDER = "date"
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "gpt-oss:20b"
    SHORT_MAX_DURATION = 60
    LONG_MIN_DURATION = 1800
    RIVAL_CHANNELS = []

# LangChain components
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

try:
    from langchain_community.llms import Ollama
    OLLAMA_IMPORTED = True
except Exception:
    OLLAMA_IMPORTED = False

# Import authentication and analytics modules
try:
    from auth_manager import get_auth_manager
    from analytics_fetcher import AnalyticsFetcher
    AUTH_MODULES_AVAILABLE = True
except ImportError as e:
    AUTH_MODULES_AVAILABLE = False
    print(f"[WARNING] Auth modules not available: {e}")

# Import content analyzer for Phase 3
try:
    from content_analyzer import ContentAnalyzer
    CONTENT_ANALYZER_AVAILABLE = True
except ImportError as e:
    CONTENT_ANALYZER_AVAILABLE = False
    print(f"[WARNING] Content analyzer not available: {e}")

# Import competitor analyzer for Phase 3.2
try:
    from competitor_analyzer import CompetitorAnalyzer
    COMPETITOR_ANALYZER_AVAILABLE = True
except ImportError as e:
    COMPETITOR_ANALYZER_AVAILABLE = False
    print(f"[WARNING] Competitor analyzer not available: {e}")

# Import utility functions
try:
    from utils import (
        parse_duration_to_seconds,
        classify_content_type,
        calculate_video_performance_score,
        format_duration_human_readable,
        extract_keywords,
        keyword_filter_indices
    )
    UTILS_AVAILABLE = True
except ImportError as e:
    UTILS_AVAILABLE = False
    print(f"[WARNING] Utility functions not available: {e}")
    # Define fallback functions
    def parse_duration_to_seconds(duration_iso: str) -> int:
        return 0
    def classify_content_type(duration_seconds: int, live_status: str = None) -> str:
        return "Regular"
    def calculate_video_performance_score(views: int, likes: int, comments: int, duration_seconds: int) -> dict:
        return {"performance_score": 0, "performance_grade": "F"}
    def format_duration_human_readable(duration_seconds: int) -> str:
        return "0:00"
    def extract_keywords(query: str) -> list:
        return []
    def keyword_filter_indices(df, keywords: list) -> list:
        return []

# Import Phase 4: Save State Management & API Caching modules
CACHING_MODULES_AVAILABLE = False
try:
    # First try to import plotly (required for quota_monitor visualizations)
    import plotly.graph_objects as go
    import plotly.express as px

    # Now try to import our modules
    from cached_youtube_api import get_cached_youtube_api
    from data_manager import get_data_manager
    from quota_monitor import get_quota_monitor, display_sidebar_quota_widget, display_quota_alerts
    CACHING_MODULES_AVAILABLE = True
except ImportError as e:
    CACHING_MODULES_AVAILABLE = False
    error_msg = str(e)
    print(f"[WARNING] Caching modules not available: {error_msg}")

    # Provide helpful installation instructions
    if "plotly" in error_msg.lower():
        print("[INFO] Install plotly with: pip install plotly")
    elif "streamlit" in error_msg.lower():
        print("[INFO] Streamlit should already be installed for this app")
    else:
        print("[INFO] Make sure all dependencies are installed")


# ==================== Streamlit Setup ====================
st.set_page_config(page_title="YouTube Growth Analytics Platform", layout="wide")
st.title("🚀 YouTube Growth Analytics Platform")
st.markdown("Advanced analytics with AI-powered insights, competitive intelligence, and growth recommendations.")

# App instructions
with st.expander("📋 How to use this platform", expanded=True):
    st.markdown("""
    ### Getting Started:
    1. **Enter YouTube API Key** in sidebar (Data API v3)
    2. **Enter Channel Name** to analyze
    3. **Click '🚀 Fetch Channel Data'** to load basic analytics
    4. **Authenticate with Google** for advanced YouTube Analytics API features

    ### Available Features:
    - **Basic Analytics**: Video performance, content type analysis, trends
    - **Advanced Analytics** (requires OAuth): Traffic sources, demographics, device usage, subscriber growth
    - **AI Insights**: Content recommendations, competitive analysis
    - **Smart Search**: Semantic search across your channel content
    """)


# ==================== Session State ====================
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "vectordb" not in st.session_state:
    st.session_state.vectordb = None

# Try to restore session from data manager if caching modules are available
if CACHING_MODULES_AVAILABLE:
    try:
        from data_manager import get_data_manager
        data_manager = get_data_manager()

        # Try to resume the last session
        # In a real app, you might want to let users select which session to resume
        # For now, we'll try to resume the most recent session
        sessions = data_manager.state_manager.list_sessions(active_only=True)
        if sessions:
            # Try to resume the most recent session
            latest_session = sessions[0]  # list_sessions returns most recent first
            if data_manager.resume_session(latest_session['session_id']):
                st.info(f"Resumed session: {latest_session['session_name']}")
    except Exception as e:
        # Don't show error if data manager fails - it might not be fully initialized yet
        pass


# ==================== Utility Functions ====================
def ollama_available() -> bool:
    if not OLLAMA_IMPORTED:
        return False
    try:
        subprocess.run(["ollama", "list"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def get_channel_videos_df(api_key: str, channel_name: str, max_results: int = 50, order: str = "date") -> pd.DataFrame:
    youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
    ch_resp = youtube.search().list(part="snippet", q=channel_name, type="channel", maxResults=1).execute()
    if not ch_resp.get("items"):
        st.error(f"No channel found for '{channel_name}'.")
        return pd.DataFrame()

    channel_id = ch_resp["items"][0]["id"]["channelId"]
    v_resp = youtube.search().list(part="snippet", channelId=channel_id, type="video", order=order, maxResults=max_results).execute()
    video_ids = [i["id"]["videoId"] for i in v_resp.get("items", [])]

    if not video_ids:
        return pd.DataFrame()

    s_resp = youtube.videos().list(part="snippet,statistics,contentDetails", id=",".join(video_ids)).execute()
    data = []
    for item in s_resp.get("items", []):
        sn = item["snippet"]
        stt = item.get("statistics", {})
        det = item.get("contentDetails", {})

        # Parse duration and classify content type
        duration_iso = det.get("duration", "")
        duration_seconds = parse_duration_to_seconds(duration_iso)
        live_status = sn.get("liveBroadcastContent", "none")
        content_type = classify_content_type(duration_seconds, live_status)

        # Calculate engagement rates
        views = int(stt.get("viewCount", 0))
        likes = int(stt.get("likeCount", 0))
        comments = int(stt.get("commentCount", 0))

        engagement_rate = (likes / views * 100) if views > 0 else 0
        comment_rate = (comments / views * 100) if views > 0 else 0

        # Calculate performance scores
        performance_data = calculate_video_performance_score(views, likes, comments, duration_seconds)

        # Format duration for display
        duration_display = format_duration_human_readable(duration_seconds)

        data.append({
            "Title": sn.get("title"),
            "Published": pd.to_datetime(sn.get("publishedAt"), utc=True),
            "Description": sn.get("description", ""),
            "Video_ID": item["id"],
            "URL": f"https://www.youtube.com/watch?v={item['id']}",
            "Duration": duration_iso,
            "Duration_Display": duration_display,
            "Duration_Seconds": duration_seconds,
            "Content_Type": content_type,
            "Live_Status": live_status,
            "Views": views,
            "Likes": likes,
            "Comments": comments,
            "Engagement_Rate": round(engagement_rate, 2),
            "Comment_Rate": round(comment_rate, 2),
            "Performance_Score": performance_data["performance_score"],
            "Performance_Grade": performance_data["performance_grade"],
            "Engagement_Score": performance_data["engagement_score"],
            "Popularity_Score": performance_data["popularity_score"],
            "Interaction_Score": performance_data["interaction_score"],
            "Thumbnail": sn.get("thumbnails", {}).get("high", {}).get("url", "")
        })
    return pd.DataFrame(data)


def get_channel_videos_df_cached(api_key: str, channel_name: str, max_results: int = 50, order: str = "date") -> pd.DataFrame:
    """
    Get channel videos using cached YouTube API.

    Args:
        api_key: YouTube API key
        channel_name: Channel name
        max_results: Maximum number of videos
        order: Sort order

    Returns:
        DataFrame with video data
    """
    if not CACHING_MODULES_AVAILABLE:
        # Fall back to original function
        return get_channel_videos_df(api_key, channel_name, max_results, order)

    try:
        # Use cached YouTube API
        youtube_api = get_cached_youtube_api(api_key)
        df = youtube_api.get_channel_videos_df(channel_name, max_results, order)

        # Save to session state if we have a data manager
        data_manager = get_data_manager()
        # Clean channel name for cache key (replace spaces with underscores)
        clean_channel_name = channel_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        cache_key = f"channel_videos_{clean_channel_name}_{max_results}_{order}"
        data_manager.save_dataframe(cache_key, df)

        return df
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.warning(f"Using cached API failed: {e}. Falling back to direct API.")
        print(f"Cached API error details: {error_details}")  # Print to console for debugging
        return get_channel_videos_df(api_key, channel_name, max_results, order)


def plot_trend_over_time(df, metric="Views"):
    if df.empty:
        return
    df2 = df.sort_values("Published")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df2["Published"], df2[metric], marker="o", linewidth=2, color="tab:blue")
    ax.set_title(f"{metric} Trend Over Time", fontsize=14, weight="bold")
    ax.set_xlabel("Published Date")
    ax.set_ylabel(metric)
    ax.grid(alpha=0.5)
    plt.xticks(rotation=30)
    st.pyplot(fig)


def plot_top_videos(df, metric="Views", top_n=10):
    if df.empty:
        return
    df2 = df.sort_values(metric, ascending=False).head(top_n)
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(df2["Title"], df2[metric], color="skyblue", edgecolor="black")
    ax.set_title(f"Top {top_n} Videos by {metric}", fontsize=14, weight="bold")
    ax.set_xlabel(metric)
    ax.set_ylabel("Video Title")
    ax.invert_yaxis()
    for bar in bars:
        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2, f"{int(bar.get_width()):,}", va="center")
    plt.tight_layout()
    st.pyplot(fig)


def plot_content_type_distribution(df):
    """Plot pie chart showing distribution of content types."""
    if df.empty or "Content_Type" not in df.columns:
        return

    content_counts = df["Content_Type"].value_counts()
    if content_counts.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = plt.cm.Set3(np.linspace(0, 1, len(content_counts)))
    wedges, texts, autotexts = ax.pie(
        content_counts.values,
        labels=content_counts.index,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90
    )
    ax.set_title("Content Type Distribution", fontsize=14, weight="bold")
    plt.setp(autotexts, size=10, weight="bold")
    plt.setp(texts, size=11)
    st.pyplot(fig)


def plot_content_type_performance(df, metric="Views"):
    """Plot bar chart comparing performance metrics by content type."""
    if df.empty or "Content_Type" not in df.columns or metric not in df.columns:
        return

    # Calculate average metric by content type
    performance = df.groupby("Content_Type")[metric].mean().sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(performance.index, performance.values, color="lightcoral", edgecolor="black")
    ax.set_title(f"Average {metric} by Content Type", fontsize=14, weight="bold")
    ax.set_xlabel("Content Type")
    ax.set_ylabel(f"Average {metric}")
    ax.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.01 * max(performance.values),
                f"{int(height):,}" if metric in ["Views", "Likes", "Comments"] else f"{height:.2f}",
                ha='center', va='bottom')

    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)


def plot_content_type_trends(df, metric="Views"):
    """Plot trend of metric over time by content type."""
    if df.empty or "Content_Type" not in df.columns or metric not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot each content type separately
    for content_type in df["Content_Type"].unique():
        type_data = df[df["Content_Type"] == content_type].sort_values("Published")
        if not type_data.empty:
            ax.plot(type_data["Published"], type_data[metric], marker="o", linewidth=2,
                   label=content_type, markersize=6)

    ax.set_title(f"{metric} Trend by Content Type", fontsize=14, weight="bold")
    ax.set_xlabel("Published Date")
    ax.set_ylabel(metric)
    ax.legend(title="Content Type")
    ax.grid(alpha=0.3)
    plt.xticks(rotation=30)
    plt.tight_layout()
    st.pyplot(fig)


def plot_duration_distribution(df):
    """Plot histogram of video durations."""
    if df.empty or "Duration_Seconds" not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    # Create bins for duration
    durations = df["Duration_Seconds"]
    max_duration = min(durations.max(), 7200)  # Cap at 2 hours for visualization

    # Create histogram
    ax.hist(durations, bins=30, range=(0, max_duration), edgecolor='black', alpha=0.7)
    ax.set_title("Video Duration Distribution", fontsize=14, weight="bold")
    ax.set_xlabel("Duration (seconds)")
    ax.set_ylabel("Number of Videos")
    ax.grid(alpha=0.3)

    # Add vertical lines for classification thresholds
    ax.axvline(x=SHORT_MAX_DURATION, color='red', linestyle='--', alpha=0.7,
              label=f'Shorts threshold ({SHORT_MAX_DURATION}s)')
    ax.axvline(x=LONG_MIN_DURATION, color='blue', linestyle='--', alpha=0.7,
              label=f'Long-form threshold ({LONG_MIN_DURATION}s)')

    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)




def build_vector_db(df):
    if df.empty:
        return None
    docs, metas = [], []
    for i, r in df.reset_index(drop=True).iterrows():
        text = (
            f"Title: {r['Title']}\n"
            f"Description: {r['Description']}\n"
            f"Views: {r['Views']} Likes: {r['Likes']} Comments: {r['Comments']}"
        )
        docs.append(text)
        metas.append({"row": int(i), "title": r["Title"], "views": int(r["Views"]), "url": r["URL"]})
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb = Chroma.from_texts(docs, embedding=embeddings, metadatas=metas)
    return vectordb


def summarize_with_ollama(question, hits):
    context = "\n\n".join([f"Title: {t}\nSnippet: {s}" for t, s, _ in hits])
    prompt = (
        f"You are an assistant summarizing YouTube videos.\n\n"
        f"Question: {question}\n\n"
        f"Relevant videos:\n{context}\n\n"
        "Summarize and list the most relevant videos with bullet points and short explanations."
    )
    llm = Ollama(model="mistral", temperature=0.2)
    return llm(prompt)


def chat_with_channel(df, vectordb, question, use_kw=True, use_sum=True):
    if vectordb is None or df.empty:
        return "Please fetch data and build knowledge base first."

    kw = extract_keywords(question) if use_kw else []
    idx = keyword_filter_indices(df, kw) if kw else []
    filt = {"row": {"$in": idx}} if idx else None

    docs = vectordb.similarity_search(question, k=5, filter=filt)
    if not docs:
        return "No relevant results found."

    hits = []
    for d in docs:
        title = d.metadata["title"]
        snippet = d.page_content[:300].replace("\n", " ").strip()
        url = d.metadata.get("url", "")
        hits.append((title, snippet, url))

    if use_sum and ollama_available():
        try:
            return summarize_with_ollama(question, hits)
        except Exception:
            pass

    # clickable results
    formatted = "🔍 **Top Related Videos:**\n\n"
    for t, s, u in hits:
        stats_row = df[df["URL"] == u]
        if not stats_row.empty:
            views = int(stats_row["Views"].iloc[0])
            likes = int(stats_row["Likes"].iloc[0])
            comments = int(stats_row["Comments"].iloc[0])
            formatted += f"🎥 **[{t}]({u})**  \n👁️ {views:,} views | 👍 {likes:,} likes | 💬 {comments:,} comments  \n{s}\n\n"
        else:
            formatted += f"🎥 **[{t}]({u})**  \n{s}\n\n"
    return formatted


# ==================== Sidebar Controls ====================
st.sidebar.header("Settings")

# Configuration status
if CONFIG_LOADED:
    config_status = "✅ Loaded"
    config_color = "green"
else:
    config_status = "⚠️ Using fallback defaults"
    config_color = "orange"

st.sidebar.markdown(f"**Config Status:** :{config_color}[{config_status}]")

# API Key input - show placeholder if config provides one
api_key_placeholder = YOUTUBE_API_KEY if YOUTUBE_API_KEY else ""
api_key = st.sidebar.text_input("YouTube API Key", value=api_key_placeholder, type="password", key="api_key_input")

# Show warning if no API key is configured
if not YOUTUBE_API_KEY:
    st.sidebar.warning("⚠️ No API key configured. Set YOUTUBE_API_KEY in .env file or enter it above.")

# YouTube Analytics API Authentication
st.sidebar.markdown("---")
st.sidebar.subheader("🔐 YouTube Analytics API")

if AUTH_MODULES_AVAILABLE:
    # Initialize auth manager
    auth_manager = get_auth_manager()

    # Check authentication status
    auth_status = auth_manager.get_auth_status()

    if auth_status["authenticated"]:
        st.sidebar.success("✅ Authenticated with YouTube Analytics API")

        # Show authentication details in expander
        with st.sidebar.expander("Authentication Details"):
            st.write(f"**Status:** Authenticated")
            if auth_status["expires_at"]:
                from datetime import datetime
                expires_at = datetime.fromisoformat(auth_status["expires_at"].replace('Z', '+00:00'))
                st.write(f"**Expires:** {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            st.write(f"**Scopes:** {', '.join(auth_status['scopes'])}")

            # Logout button
            if st.button("Logout"):
                auth_manager.logout()
                st.rerun()
    else:
        st.sidebar.warning("⚠️ Not authenticated")
        st.sidebar.info("YouTube Analytics API provides advanced metrics: watch time, demographics, traffic sources, subscriber analytics.")

        # Authentication button
        if st.sidebar.button("Authenticate with Google"):
            with st.spinner("Starting authentication..."):
                if auth_manager.authenticate():
                    st.success("Authentication successful!")
                    st.rerun()
                else:
                    st.error("Authentication failed. Check console for details.")
else:
    st.sidebar.warning("⚠️ Authentication modules not available")
    st.sidebar.info("Install required packages: `pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client`")

# Channel name input - use default from config
channel_name = st.sidebar.text_input("Channel Name", value=DEFAULT_CHANNEL, key="channel_name_input")

# Other settings with config defaults
max_results = st.sidebar.slider("Number of Videos", 10, 100, DEFAULT_MAX_RESULTS)
order = st.sidebar.selectbox("Order By", ["date", "viewCount", "rating", "relevance"], index=["date", "viewCount", "rating", "relevance"].index(DEFAULT_ORDER) if DEFAULT_ORDER in ["date", "viewCount", "rating", "relevance"] else 0, key="order_select")

# Configuration management
with st.sidebar.expander("⚙️ Advanced Configuration"):
    st.markdown("### Configuration Summary")

    # Cache management
    st.markdown("### Cache Management")
    if st.button("Clear Video Cache", key="clear_cache"):
        try:
            from cache_manager import get_cache_manager
            cache_manager = get_cache_manager()
            # Clear video-related cache using patterns
            cache_manager.invalidate_cache(pattern="search.videos%")
            cache_manager.invalidate_cache(pattern="videos.list%")
            # Also clear session cache for channel videos
            try:
                from data_manager import get_data_manager
                data_manager = get_data_manager()
                # Find and remove channel video cache keys
                import re
                pattern = re.compile(r"channel_videos_.*")
                keys_to_remove = []
                # This would need access to session keys - for now just note it
                st.info("Session cache may still contain old data. Restart app to fully clear.")
            except:
                pass
            st.success("Video cache cleared! Fetch will use fresh API data.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to clear cache: {e}")

    if CONFIG_LOADED:
        config_summary = get_config_summary()
        st.json(config_summary)

        if st.button("Validate Configuration"):
            if validate_config():
                st.success("Configuration is valid!")
            else:
                st.warning("Configuration has warnings (check console)")
    else:
        st.warning("Configuration file not loaded. Using fallback defaults.")

    st.markdown("### Environment Variables")
    st.code("""
# Set these in your environment or .env file:
YOUTUBE_API_KEY=your_api_key_here
DEFAULT_YOUTUBE_CHANNEL=your_channel_name
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
DEFAULT_MAX_RESULTS=50
DEFAULT_ORDER=date
    """)

if st.sidebar.button("🚀 Fetch Channel Data"):
    if not api_key or not channel_name:
        st.warning("Please enter your YouTube API key and channel name.")
    else:
        with st.spinner("Fetching channel data..."):
            df = get_channel_videos_df_cached(api_key, channel_name, max_results=max_results, order=order)
        if not df.empty:
            st.session_state.df = df
            st.success(f"Fetched {len(df)} videos from '{channel_name}'.")
        else:
            st.error("No data found.")

# Add quota monitoring to sidebar
if CACHING_MODULES_AVAILABLE:
    try:
        display_sidebar_quota_widget()
    except Exception as e:
        st.sidebar.warning(f"Quota monitoring error: {e}")
else:
    st.sidebar.info("💡 Install caching modules for API quota monitoring")


# ==================== Dashboard ====================
if not st.session_state.df.empty:
    df = st.session_state.df

    # Initialize auth manager for dashboard section
    auth_status = {"authenticated": False}
    if AUTH_MODULES_AVAILABLE:
        try:
            auth_manager = get_auth_manager()
            auth_status = auth_manager.get_auth_status()
        except Exception as e:
            st.warning(f"Authentication error: {e}")

    # Display dataframe with new columns
    st.markdown("### 📊 Video Data")
    display_columns = ["Title", "Published", "Content_Type", "Views", "Likes", "Comments", "Engagement_Rate", "Duration"]
    st.dataframe(df[display_columns])

    # Content Type Analytics Section
    st.markdown("### 🎬 Content Type Analytics")
    st.markdown(f"**Classification thresholds:** Shorts (< {SHORT_MAX_DURATION}s), Long-form (> {LONG_MIN_DURATION}s)")

    # Content Type Distribution
    st.markdown("#### Content Type Distribution")
    c1, c2 = st.columns(2)
    with c1:
        plot_content_type_distribution(df)
    with c2:
        plot_duration_distribution(df)

    # Content Type Performance
    st.markdown("#### Performance by Content Type")
    perf_metric = st.selectbox("Performance Metric", ["Views", "Likes", "Comments", "Engagement_Rate"], key="perf_metric")
    c3, c4 = st.columns(2)
    with c3:
        plot_content_type_performance(df, perf_metric)
    with c4:
        plot_content_type_trends(df, perf_metric)

    # Traditional Channel Visualizations
    st.markdown("### 📈 Channel Visualizations")
    metric = st.selectbox("Metric", ["Views", "Likes", "Comments"], key="main_metric")
    top_n = st.slider("Top N Videos", 5, 20, 10, key="top_n")
    c5, c6 = st.columns(2)
    with c5:
        plot_top_videos(df, metric, top_n)
    with c6:
        plot_trend_over_time(df, metric)

    # Content Analysis Section (Phase 3)
    if CONTENT_ANALYZER_AVAILABLE and not df.empty:
        st.markdown("---")
        st.markdown("### 🧠 AI Content Analysis")
        st.info("Phase 3: Intelligent content analysis using NLP and machine learning to identify patterns and opportunities.")

        # Initialize content analyzer
        analyzer = ContentAnalyzer()

        # Content analysis tabs
        content_tabs = st.tabs(["Content Insights", "Content Clustering", "Recommendations"])

        with content_tabs[0]:
            st.markdown("#### Content Insights")
            if st.button("Analyze Content Patterns", key="analyze_content"):
                with st.spinner("Analyzing content patterns..."):
                    insights = analyzer.generate_content_insights(df)

                    # Display title analysis
                    title_analysis = insights.get("title_analysis", {})
                    if title_analysis:
                        st.markdown("##### Title Analysis")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Avg Title Length", f"{title_analysis.get('avg_title_length', 0):.1f} chars")
                        with col2:
                            st.metric("Min Title Length", title_analysis.get('min_title_length', 0))
                        with col3:
                            st.metric("Max Title Length", title_analysis.get('max_title_length', 0))

                        # Display top keywords
                        keywords = title_analysis.get('title_keywords', [])
                        if keywords:
                            st.markdown(f"**Top Title Keywords:** {', '.join(keywords[:10])}")

                    # Display content patterns
                    patterns = insights.get("content_patterns", {})
                    if patterns:
                        st.markdown("##### Content Patterns")
                        for pattern_name, pattern_titles in patterns.items():
                            st.markdown(f"**{pattern_name.replace('_', ' ').title()}:** {len(pattern_titles)} videos")
                            if len(pattern_titles) > 0:
                                with st.expander(f"Show {len(pattern_titles)} {pattern_name.replace('_', ' ')}"):
                                    for title in pattern_titles[:5]:
                                        st.markdown(f"- {title}")

        with content_tabs[1]:
            st.markdown("#### Content Clustering")
            st.markdown("Group similar videos based on title and description content.")

            num_clusters = st.slider("Number of Clusters", 2, 10, 5, key="num_clusters")

            if st.button("Cluster Content", key="cluster_content"):
                with st.spinner(f"Clustering content into {num_clusters} groups..."):
                    clustered_df = analyzer.cluster_content(df, num_clusters=num_clusters)

                    if clustered_df is not None and 'Cluster' in clustered_df.columns:
                        st.success(f"Created {clustered_df['Cluster'].nunique()} content clusters")

                        # Display cluster distribution
                        cluster_counts = clustered_df['Cluster'].value_counts().sort_index()
                        fig, ax = plt.subplots(figsize=(10, 6))
                        bars = ax.bar(cluster_counts.index.astype(str), cluster_counts.values)
                        ax.set_xlabel('Cluster')
                        ax.set_ylabel('Number of Videos')
                        ax.set_title('Content Cluster Distribution')

                        # Add value labels on bars
                        for bar in bars:
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                                   f'{int(height)}', ha='center', va='bottom')

                        st.pyplot(fig)

                        # Display cluster details
                        st.markdown("##### Cluster Details")
                        for cluster_id in sorted(clustered_df['Cluster'].unique()):
                            cluster_data = clustered_df[clustered_df['Cluster'] == cluster_id]
                            keywords = cluster_data['Cluster_Keywords'].iloc[0] if 'Cluster_Keywords' in cluster_data.columns else []

                            with st.expander(f"Cluster {cluster_id}: {len(cluster_data)} videos"):
                                if keywords:
                                    st.markdown(f"**Keywords:** {', '.join(keywords)}")

                                # Show top videos in cluster
                                if 'Views' in cluster_data.columns and 'Title' in cluster_data.columns:
                                    top_videos = cluster_data.nlargest(3, 'Views')[['Title', 'Views']]
                                    st.markdown("**Top Performing Videos:**")
                                    for idx, row in top_videos.iterrows():
                                        st.markdown(f"- {row['Title']} ({row['Views']:,} views)")
                    else:
                        st.warning("Content clustering failed. Make sure you have scikit-learn installed: `pip install scikit-learn`")

        with content_tabs[2]:
            st.markdown("#### Content Strategy Recommendations")
            if st.button("Generate Recommendations", key="generate_recommendations"):
                with st.spinner("Generating content strategy recommendations..."):
                    insights = analyzer.generate_content_insights(df)
                    recommendations = insights.get("recommendations", [])

                    if recommendations:
                        st.success(f"Generated {len(recommendations)} recommendations")
                        for i, rec in enumerate(recommendations, 1):
                            st.markdown(f"{i}. {rec}")
                    else:
                        st.info("No specific recommendations generated. Try analyzing more content or check your data.")
    elif not CONTENT_ANALYZER_AVAILABLE:
        st.markdown("---")
        st.markdown("### 🧠 AI Content Analysis (Phase 3)")
        st.warning("Content analyzer not available. Install required packages: `pip install nltk scikit-learn`")
        st.info("Phase 3 features include content clustering, topic modeling, and AI-powered recommendations.")

    # Competitor Analysis Section (Phase 3.2)
    if COMPETITOR_ANALYZER_AVAILABLE and api_key and not df.empty:
        st.markdown("---")
        st.markdown("### 🥊 Competitive Intelligence")
        st.info("Phase 3.2: Compare your channel against competitors to identify strengths, weaknesses, and growth opportunities.")

        # Initialize competitor analyzer
        competitor_analyzer = CompetitorAnalyzer(api_key)

        # Check if we already have competitor data in session state
        has_cached_data = (
            'competitor_data' in st.session_state and
            'main_channel_data' in st.session_state and
            'comparison_df' in st.session_state
        )

        # Get rival channels from config
        try:
            from config import RIVAL_CHANNELS
            rival_channels = RIVAL_CHANNELS
        except ImportError:
            rival_channels = []

        if rival_channels:
            st.markdown(f"**Configured Competitors:** {', '.join(rival_channels)}")

            if st.button("Analyze Competitors", key="analyze_competitors"):
                with st.spinner("Fetching competitor data and performing analysis..."):
                    # Fetch main channel data (including subscriber count)
                    with st.spinner("Fetching your channel data..."):
                        main_channel_data = competitor_analyzer.fetch_channel_data(channel_name, max_results=20)

                    if not main_channel_data:
                        st.error(f"Could not fetch data for your channel: {channel_name}")
                        st.stop()

                    # Show what channel was found
                    actual_channel_name = main_channel_data.get('channel_name', channel_name)
                    if actual_channel_name.lower() != channel_name.lower():
                        st.info(f"Channel found: '{actual_channel_name}' (searched for: '{channel_name}')")

                    # Enhance with video data from the DataFrame
                    main_channel_data['video_count'] = len(df)
                    main_channel_data['recent_video_count'] = len(df)
                    main_channel_data['total_views_recent'] = df['Views'].sum() if 'Views' in df.columns else 0
                    main_channel_data['avg_views_per_video'] = df['Views'].mean() if 'Views' in df.columns else 0
                    main_channel_data['avg_likes_per_video'] = df['Likes'].mean() if 'Likes' in df.columns else 0
                    main_channel_data['avg_comments_per_video'] = df['Comments'].mean() if 'Comments' in df.columns else 0
                    main_channel_data['engagement_rate'] = df['Engagement_Rate'].mean() if 'Engagement_Rate' in df.columns else 0

                    # Fetch competitor data
                    competitor_data = competitor_analyzer.fetch_all_competitors(rival_channels, max_results=20)

                    if competitor_data:
                        st.success(f"Fetched data for {len(competitor_data)} competitors")

                        # Save to session state
                        st.session_state.competitor_data = competitor_data
                        st.session_state.main_channel_data = main_channel_data

                        # Create comparison
                        comparison_df = competitor_analyzer.compare_channels(main_channel_data, competitor_data)

                        # Save comparison to session state
                        st.session_state.comparison_df = comparison_df

                        if not comparison_df.empty:
                            # Display comparison table
                            st.markdown("#### 📈 Channel Comparison")
                            display_cols = ['channel_name', 'subscriber_count', 'video_count',
                                          'avg_views_per_video', 'engagement_rate']
                            if 'subscribers_relative' in comparison_df.columns:
                                display_cols.append('subscribers_relative')

                            st.dataframe(comparison_df[display_cols])

                            # Create visualizations
                            st.markdown("#### 📊 Competitive Analysis")

                            # Subscriber comparison chart
                            fig1, ax1 = plt.subplots(figsize=(10, 6))
                            bars1 = ax1.bar(comparison_df['channel_name'], comparison_df['subscriber_count'])
                            ax1.set_xlabel('Channel')
                            ax1.set_ylabel('Subscribers')
                            ax1.set_title('Subscriber Count Comparison')
                            ax1.tick_params(axis='x', rotation=45)

                            # Highlight main channel
                            main_idx = comparison_df[comparison_df['is_main_channel']].index[0]
                            bars1[main_idx].set_color('green')

                            st.pyplot(fig1)

                            # Engagement rate comparison
                            fig2, ax2 = plt.subplots(figsize=(10, 6))
                            bars2 = ax2.bar(comparison_df['channel_name'], comparison_df['engagement_rate'])
                            ax2.set_xlabel('Channel')
                            ax2.set_ylabel('Engagement Rate')
                            ax2.set_title('Engagement Rate Comparison (likes + comments per 1000 views)')
                            ax2.tick_params(axis='x', rotation=45)
                            bars2[main_idx].set_color('green')
                            st.pyplot(fig2)

                            # Gap analysis
                            st.markdown("#### 🔍 Gap Analysis")
                            gap_analysis = competitor_analyzer.calculate_gap_analysis(main_channel_data, competitor_data)

                            if gap_analysis:
                                col1, col2 = st.columns(2)

                                with col1:
                                    if gap_analysis.get('strengths'):
                                        st.markdown("##### ✅ Your Strengths")
                                        for strength in gap_analysis['strengths'][:3]:
                                            st.markdown(f"- {strength}")

                                    if gap_analysis.get('competitive_advantages'):
                                        st.markdown("##### 🏆 Competitive Advantages")
                                        for advantage in gap_analysis['competitive_advantages'][:3]:
                                            st.markdown(f"- {advantage}")

                                with col2:
                                    if gap_analysis.get('weaknesses'):
                                        st.markdown("##### ⚠️ Areas to Watch")
                                        for weakness in gap_analysis['weaknesses'][:3]:
                                            st.markdown(f"- {weakness}")

                                    if gap_analysis.get('opportunities'):
                                        st.markdown("##### 🚀 Growth Opportunities")
                                        for opportunity in gap_analysis['opportunities'][:3]:
                                            st.markdown(f"- {opportunity}")

                            # Generate insights
                            st.markdown("#### 💡 Competitive Insights")
                            insights = competitor_analyzer.generate_competitive_insights(comparison_df, gap_analysis)

                            for insight in insights:
                                st.info(insight)

                        else:
                            st.warning("Could not generate comparison. Check your data.")
                    else:
                        st.warning("No competitor data fetched. Check competitor channel names and API key.")
        else:
            st.warning("No competitor channels configured. Add channels to RIVAL_CHANNELS in config.py")
            st.info("Example configuration in config.py:\n```python\nRIVAL_CHANNELS = [\n    'Competitor Channel 1',\n    'Competitor Channel 2',\n]\n```")
    elif not COMPETITOR_ANALYZER_AVAILABLE:
        st.markdown("---")
        st.markdown("### 🥊 Competitive Intelligence (Phase 3.2)")
        st.warning("Competitor analyzer not available. Make sure competitor_analyzer.py is in the project directory.")
        st.info("Phase 3.2 features include multi-channel comparison, gap analysis, and competitive insights.")

    # YouTube Analytics API Data (if authenticated)
    if AUTH_MODULES_AVAILABLE and auth_status.get("authenticated", False):
        st.markdown("---")
        st.markdown("### 📊 YouTube Analytics API Data")
        st.info("Advanced metrics from YouTube Analytics API (requires OAuth authentication)")

        # Create analytics fetcher
        analytics_fetcher = AnalyticsFetcher()

        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.selectbox(
                "Start Date",
                ["7daysAgo", "30daysAgo", "90daysAgo", "custom"],
                index=1,
                key="analytics_start"
            )
            if start_date == "custom":
                start_date = st.date_input("Custom Start Date", value=pd.Timestamp.now() - pd.Timedelta(days=30))
                start_date = start_date.strftime("%Y-%m-%d")

        with col2:
            end_date = st.selectbox(
                "End Date",
                ["today", "yesterday", "custom"],
                index=0,
                key="analytics_end"
            )
            if end_date == "custom":
                end_date = st.date_input("Custom End Date", value=pd.Timestamp.now())
                end_date = end_date.strftime("%Y-%m-%d")

        # Analytics tabs
        analytics_tabs = st.tabs(["Traffic Sources", "Demographics", "Device Usage", "Subscriber Analytics"])

        with analytics_tabs[0]:
            st.markdown("#### Traffic Source Analysis")
            if st.button("Fetch Traffic Sources", key="fetch_traffic"):
                with st.spinner("Fetching traffic source data..."):
                    traffic_df = analytics_fetcher.get_traffic_sources(start_date, end_date)
                    if not traffic_df.empty:
                        st.dataframe(traffic_df)
                        # Create pie chart
                        fig, ax = plt.subplots(figsize=(8, 6))
                        ax.pie(traffic_df['views'], labels=traffic_df['traffic_source'], autopct='%1.1f%%')
                        ax.set_title('Traffic Sources by Views')
                        st.pyplot(fig)
                    else:
                        st.warning("No traffic source data available")

        with analytics_tabs[1]:
            st.markdown("#### Demographic Insights")
            if st.button("Fetch Demographics", key="fetch_demo"):
                with st.spinner("Fetching demographic data..."):
                    demographics = analytics_fetcher.get_demographics(start_date, end_date)
                    if demographics:
                        for demo_type, demo_df in demographics.items():
                            if not demo_df.empty:
                                st.markdown(f"**{demo_type.replace('_', ' ').title()}**")
                                st.dataframe(demo_df)
                    else:
                        st.warning("No demographic data available")

        with analytics_tabs[2]:
            st.markdown("#### Device Usage")
            if st.button("Fetch Device Usage", key="fetch_device"):
                with st.spinner("Fetching device usage data..."):
                    device_df = analytics_fetcher.get_device_usage(start_date, end_date)
                    if not device_df.empty:
                        st.dataframe(device_df)
                        # Create bar chart
                        fig, ax = plt.subplots(figsize=(10, 6))
                        ax.bar(device_df['device_type'], device_df['views'])
                        ax.set_xlabel('Device Type')
                        ax.set_ylabel('Views')
                        ax.set_title('Views by Device Type')
                        plt.xticks(rotation=45)
                        st.pyplot(fig)
                    else:
                        st.warning("No device usage data available")

        with analytics_tabs[3]:
            st.markdown("#### Subscriber Analytics")
            if st.button("Fetch Subscriber Data", key="fetch_subs"):
                with st.spinner("Fetching subscriber data..."):
                    subs_df = analytics_fetcher.get_subscriber_analytics(start_date, end_date)
                    if not subs_df.empty:
                        st.dataframe(subs_df)
                        # Create line chart
                        fig, ax = plt.subplots(figsize=(12, 6))
                        ax.plot(subs_df['day'], subs_df['subscribers_net'], marker='o')
                        ax.set_xlabel('Date')
                        ax.set_ylabel('Net Subscribers')
                        ax.set_title('Daily Subscriber Growth')
                        plt.xticks(rotation=45)
                        st.pyplot(fig)
                    else:
                        st.warning("No subscriber data available")
    elif AUTH_MODULES_AVAILABLE:
        st.markdown("---")
        st.markdown("### 📊 YouTube Analytics API Data")
        st.warning("⚠️ Not authenticated. Click 'Authenticate with Google' in the sidebar to access advanced analytics.")

    # Quota Monitoring Dashboard
    if CACHING_MODULES_AVAILABLE:
        st.markdown("---")
        st.markdown("### 📈 API Quota & Cache Dashboard")

        # Display quota alerts if any
        try:
            display_quota_alerts()
        except Exception as e:
            st.warning(f"Could not display quota alerts: {e}")

        # Quota dashboard expander
        with st.expander("View Detailed Quota Dashboard", expanded=False):
            try:
                from quota_monitor import display_quota_dashboard
                display_quota_dashboard()
            except Exception as e:
                st.error(f"Could not load quota dashboard: {e}")

    st.markdown("### 🧠 Chat with the Channel (Offline)")
    use_kw = st.checkbox("Use Keyword/Entity Filter", True)
    use_sum = st.checkbox("Use Local Summarizer (Ollama)", True)
    st.write("Ollama Available:", "✅" if ollama_available() else "❌")

    if st.button("Build Channel Knowledge Base"):
        with st.spinner("Building local embeddings..."):
            vectordb = build_vector_db(df)
        if vectordb:
            st.session_state.vectordb = vectordb
            st.success("Knowledge base created successfully!")

    if st.session_state.vectordb:
        query = st.text_area("Ask about the channel:", "Videos related to Virat Kohli")
        if st.button("Ask"):
            with st.spinner("Searching and analyzing..."):
                answer = chat_with_channel(df, st.session_state.vectordb, query, use_kw, use_sum)
            st.markdown(answer)
