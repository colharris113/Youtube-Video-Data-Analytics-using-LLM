"""
🏠 Home - YouTube Analytics Dashboard
Main overview page with key metrics and quick access to all features.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="YouTube Analytics - Home",
    page_icon="🏠",
    layout="wide"
)

# Title and description
st.title("🏠 YouTube Analytics Dashboard")
st.markdown("""
Welcome to your comprehensive YouTube growth analytics platform.
This dashboard provides AI-powered insights, competitive intelligence, and actionable recommendations.
""")

# Check if we have data loaded - try to load from cache first
if "df" not in st.session_state or st.session_state.df.empty:
    # Try to load from data manager cache
    try:
        from data_manager import get_data_manager
        data_manager = get_data_manager()

        # First, try to resume the most recent session if we don't have a current session
        if not data_manager.current_session_id:
            sessions = data_manager.list_available_sessions()
            if sessions:
                # Try to resume the most recent session
                latest_session = sessions[0]  # Should be most recent
                if data_manager.resume_session(latest_session['session_id']):
                    st.info(f"Resumed session: {latest_session['session_name']}")

        # Try to get the last channel analyzed
        last_channel = data_manager.get_session_value("last_channel")
        last_max_results = data_manager.get_session_value("last_max_results", 50)
        last_order = data_manager.get_session_value("last_order", "date")

        if last_channel:
            # Clean channel name for cache key (same as in youtube_utils.py)
            clean_channel_name = last_channel.replace(" ", "_").replace("/", "_").replace("\\", "_")
            cache_key = f"channel_videos_{clean_channel_name}_{last_max_results}_{last_order}"
            cached_df = data_manager.load_dataframe(cache_key)

            if cached_df is not None and not cached_df.empty:
                st.session_state.df = cached_df
                st.success(f"✅ Loaded {len(cached_df)} videos from cache for '{last_channel}'")
                st.info("Data restored from cache. Click 'Fetch Channel Data' for fresh data.")
            else:
                st.warning("⚠️ No cached data found.")
                st.info("Please use the sidebar to configure and fetch channel data.")
        else:
            st.warning("⚠️ No channel data loaded yet.")
            st.info("Please use the sidebar to configure and fetch channel data.")

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.warning(f"⚠️ Cache loading error: {e}")
        st.info("Please use the sidebar to configure and fetch channel data.")
        # Debug info (commented out for production)
        with st.expander("Debug Info"):
            st.code(error_details)

    # Quick setup guide
    with st.expander("📋 Quick Setup Guide"):
        st.markdown("""
        1. **Configure API Key** in `.env` file or environment variables
        2. **Enter Channel Name** in the sidebar
        3. **Adjust Settings** like number of videos and order
        4. **Click 'Fetch Channel Data'** to load your videos
        5. **Explore different pages** for detailed analysis

        **Advanced Features:**
        - 🔐 **YouTube Analytics API**: Authenticate for advanced metrics (watch time, demographics)
        - 🥊 **Competitive Analysis**: Compare with rival channels
        - 🧠 **AI Insights**: Get content recommendations
        - 📊 **Export Reports**: Generate PDF/CSV reports
        """)
else:
    # We have data - show overview
    df = st.session_state.df

    # Key metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Videos", len(df))

    with col2:
        avg_views = df["Views"].mean() if not df.empty else 0
        st.metric("Avg Views", f"{avg_views:,.0f}")

    with col3:
        avg_engagement = df["Engagement_Rate"].mean() if not df.empty else 0
        st.metric("Avg Engagement", f"{avg_engagement:.1f}%")

    with col4:
        latest_video = df["Published"].max() if not df.empty else "N/A"
        if latest_video != "N/A":
            # Convert to datetime if needed
            if not isinstance(latest_video, pd.Timestamp):
                latest_video = pd.to_datetime(latest_video, utc=True)

            # Make both timestamps timezone-aware (UTC) for comparison
            now_utc = pd.Timestamp.now(tz='UTC')
            days_ago = (now_utc - latest_video).days
            st.metric("Latest Video", f"{days_ago} days ago")

    # Recent videos table
    st.subheader("📺 Recent Videos")
    if not df.empty:
        recent_df = df.sort_values("Published", ascending=False).head(5)
        display_df = recent_df[["Title", "Published", "Views", "Likes", "Engagement_Rate", "Content_Type"]].copy()

        # Convert Published column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(display_df["Published"]):
            display_df["Published"] = pd.to_datetime(display_df["Published"], utc=True)

        display_df["Published"] = display_df["Published"].dt.strftime("%Y-%m-%d")
        st.dataframe(display_df, use_container_width=True)

    # Content type distribution
    st.subheader("🎬 Content Type Distribution")
    if not df.empty and "Content_Type" in df.columns:
        content_counts = df["Content_Type"].value_counts()
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.pie(content_counts.values, labels=content_counts.index, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')
        st.pyplot(fig)

    # Quick links to other pages
    st.subheader("🚀 Quick Navigation")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 🧠 Content Analysis")
        st.markdown("""
        - Topic modeling & clustering
        - Title pattern analysis
        - Performance by content type
        """)
        if st.button("Go to Content Analysis", key="goto_content"):
            st.switch_page("pages/02_Content_Analysis.py")

    with col2:
        st.markdown("### 🥊 Competitive Analysis")
        st.markdown("""
        - Rival channel comparisons
        - Market share analysis
        - Gap identification
        """)
        if st.button("Go to Competitive Analysis", key="goto_competitive"):
            st.switch_page("pages/03_Competitive_Analysis.py")

    with col3:
        st.markdown("### 📈 Growth Recommendations")
        st.markdown("""
        - AI-powered insights
        - Content strategy suggestions
        - Optimization tips
        """)
        if st.button("Go to Growth Recommendations", key="goto_growth"):
            st.switch_page("pages/04_Growth_Recommendations.py")

# Sidebar configuration (shared across pages)
st.sidebar.title("⚙️ Configuration")

# API key check
try:
    from config import YOUTUBE_API_KEY, DEFAULT_CHANNEL
    if YOUTUBE_API_KEY:
        st.sidebar.success("✅ API Key Configured")
    else:
        st.sidebar.error("❌ API Key Missing")
except:
    st.sidebar.warning("⚠️ Configuration not loaded")

# Channel input
channel_name = st.sidebar.text_input("Channel Name", value="The Uranium Hunter", key="home_channel_input")

# Fetch button
if st.sidebar.button("🚀 Fetch Channel Data", key="home_fetch_button"):
    with st.spinner("Fetching channel data..."):
        try:
            from youtube_utils import get_channel_videos_df_cached
            from config import YOUTUBE_API_KEY
            from data_manager import get_data_manager

            # Create a session BEFORE fetching data so it's available during save
            data_manager = get_data_manager()
            if not data_manager.current_session_id:
                session_id = data_manager.create_analysis_session(
                    session_name=f"Analysis: {channel_name}",
                    channel_name=channel_name,
                    api_key=YOUTUBE_API_KEY[:10] + "..." if YOUTUBE_API_KEY else "no_key"
                )

            df = get_channel_videos_df_cached(
                api_key=YOUTUBE_API_KEY,
                channel_name=channel_name,
                max_results=50,
                order="date"
            )

            if not df.empty:
                st.session_state.df = df
                st.success(f"✅ Loaded {len(df)} videos from {channel_name}")

                # Save the channel name and parameters
                try:
                    data_manager.save_session_value("last_channel", channel_name)
                    data_manager.save_session_value("last_max_results", 50)
                    data_manager.save_session_value("last_order", "date")
                except Exception as e:
                    st.warning(f"Note: Could not save session values: {e}")

                st.rerun()
            else:
                st.error("❌ No videos found or API error")

        except Exception as e:
            st.error(f"❌ Error fetching data: {e}")

# Clear data button
if st.sidebar.button("🗑️ Clear Data", key="home_clear_button"):
    if "df" in st.session_state:
        del st.session_state.df
    st.rerun()

# Page navigation in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📄 Pages")
pages = [
    ("Home", "pages/01_Home.py"),
    ("Content Analysis", "pages/02_Content_Analysis.py"),
    ("Competitive Analysis", "pages/03_Competitive_Analysis.py"),
    ("Growth Recommendations", "pages/04_Growth_Recommendations.py"),
    ("Topic Explorer", "pages/05_Topic_Explorer.py"),
    ("Export Reports", "pages/06_Export_Reports.py"),
]

for page_name, page_path in pages:
    if st.sidebar.button(page_name, key=f"nav_{page_name}"):
        st.switch_page(page_path)