"""
Growth Recommendations - YouTube Analytics
AI-powered growth strategy suggestions and optimization tips.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="YouTube Analytics - Growth Recommendations",
    page_icon="📈",
    layout="wide"
)

# Title and description
st.title("📈 Growth Recommendations")
st.markdown("""
Get AI-powered insights and actionable recommendations to grow your YouTube channel.
Identify optimization opportunities and strategic improvements.
""")

# Check if we have data - try to load from cache first
if "df" not in st.session_state or st.session_state.df.empty:
    # Try to load from data manager cache (same as Home page)
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
            else:
                st.warning("⚠️ No channel data loaded yet.")
                st.info("Please go to the Home page to fetch channel data first.")
                if st.button("Go to Home"):
                    st.switch_page("pages/01_Home.py")
                st.stop()
        else:
            st.warning("⚠️ No channel data loaded yet.")
            st.info("Please go to the Home page to fetch channel data first.")
            if st.button("Go to Home"):
                st.switch_page("pages/01_Home.py")
            st.stop()

    except Exception as e:
        st.warning("⚠️ No channel data loaded yet.")
        st.info("Please go to the Home page to fetch channel data first.")
        if st.button("Go to Home"):
            st.switch_page("pages/01_Home.py")
        st.stop()

df = st.session_state.df

# Performance Analysis Section
st.header("📊 Performance Analysis")

# Key performance indicators
col1, col2, col3, col4 = st.columns(4)

with col1:
    avg_views = df["Views"].mean() if not df.empty else 0
    st.metric("Avg Views", f"{avg_views:,.0f}")

with col2:
    avg_engagement = df["Engagement_Rate"].mean() if not df.empty else 0
    st.metric("Avg Engagement", f"{avg_engagement:.1f}%")

with col3:
    if "Performance_Score" in df.columns:
        avg_performance = df["Performance_Score"].mean() if not df.empty else 0
        st.metric("Avg Performance Score", f"{avg_performance:.1f}/100")

with col4:
    if "Published" in df.columns and not df.empty:
        latest_video = df["Published"].max()
        if isinstance(latest_video, pd.Timestamp):
            # Make both timestamps timezone-aware (UTC) for comparison
            now_utc = pd.Timestamp.now(tz='UTC')
            days_ago = (now_utc - latest_video).days
            st.metric("Latest Video", f"{days_ago} days ago")

# Content Performance Analysis
st.subheader("🎬 Content Performance Analysis")

if not df.empty:
    # Performance by content type
    if "Content_Type" in df.columns:
        content_performance = df.groupby("Content_Type").agg({
            "Views": ["mean", "count"],
            "Engagement_Rate": "mean",
            "Likes": "mean"
        }).round(2)

        # Rename columns for display
        content_performance.columns = ["Avg Views", "Video Count", "Avg Engagement %", "Avg Likes"]
        content_performance = content_performance.sort_values("Avg Views", ascending=False)

        st.dataframe(content_performance, use_container_width=True)

        # Visualize performance
        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(content_performance))
        width = 0.35

        # Normalize views for better visualization
        max_views = content_performance["Avg Views"].max()
        normalized_views = content_performance["Avg Views"] / max_views * 100

        bars1 = ax.bar(x - width/2, normalized_views, width, label='Avg Views (normalized)', color='skyblue')
        bars2 = ax.bar(x + width/2, content_performance["Avg Engagement %"], width, label='Engagement %', color='lightcoral')

        ax.set_xlabel('Content Type')
        ax.set_ylabel('Performance')
        ax.set_title('Content Type Performance Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(content_performance.index, rotation=45)
        ax.legend()

        st.pyplot(fig)

# AI-Powered Recommendations
st.header("🤖 AI-Powered Recommendations")

try:
    from content_analyzer import ContentAnalyzer

    # Initialize analyzer
    analyzer = ContentAnalyzer()

    # Generate recommendations
    if st.button("Generate AI Recommendations", key="generate_ai_recs"):
        with st.spinner("Analyzing your channel and generating recommendations..."):
            try:
                # Get content insights
                insights = analyzer.generate_content_insights(df)

                # Display recommendations
                recommendations = insights.get("recommendations", [])

                if recommendations:
                    st.success(f"✅ Generated {len(recommendations)} recommendations")

                    # Categorize recommendations
                    content_recs = []
                    title_recs = []
                    strategy_recs = []

                    for rec in recommendations:
                        rec_lower = rec.lower()
                        if any(keyword in rec_lower for keyword in ["title", "headline", "name"]):
                            title_recs.append(rec)
                        elif any(keyword in rec_lower for keyword in ["content", "video", "topic", "subject"]):
                            content_recs.append(rec)
                        else:
                            strategy_recs.append(rec)

                    # Display in tabs
                    rec_tabs = st.tabs(["Content Ideas", "Title Optimization", "Growth Strategy"])

                    with rec_tabs[0]:
                        st.markdown("### 🎬 Content Ideas")
                        if content_recs:
                            for i, rec in enumerate(content_recs[:5], 1):
                                st.markdown(f"{i}. {rec}")
                        else:
                            st.info("No specific content recommendations. Try analyzing more videos.")

                    with rec_tabs[1]:
                        st.markdown("### 🔤 Title Optimization")
                        if title_recs:
                            for i, rec in enumerate(title_recs[:5], 1):
                                st.markdown(f"{i}. {rec}")
                        else:
                            st.info("No title optimization suggestions.")

                    with rec_tabs[2]:
                        st.markdown("### 🚀 Growth Strategy")
                        if strategy_recs:
                            for i, rec in enumerate(strategy_recs[:5], 1):
                                st.markdown(f"{i}. {rec}")
                        else:
                            st.info("No strategy recommendations.")

                    # Performance insights
                    st.subheader("📈 Performance Insights")

                    # Top performing content analysis
                    if "Views" in df.columns and "Title" in df.columns:
                        top_videos = df.nlargest(5, "Views")[["Title", "Views", "Engagement_Rate", "Content_Type"]]
                        st.markdown("#### Top Performing Videos")
                        st.dataframe(top_videos, use_container_width=True)

                        # Underperforming videos
                        if len(df) > 10:
                            bottom_videos = df.nsmallest(5, "Views")[["Title", "Views", "Engagement_Rate", "Content_Type"]]
                            st.markdown("#### Underperforming Videos (Opportunities)")
                            st.dataframe(bottom_videos, use_container_width=True)

                else:
                    st.warning("No recommendations generated. The analyzer may need more data.")

            except Exception as e:
                st.error(f"Error generating recommendations: {e}")
                st.info("Make sure you have the required packages: `pip install nltk scikit-learn`")

except ImportError:
    st.warning("Content analyzer module not available. Install required packages: `pip install nltk scikit-learn`")
except Exception as e:
    st.error(f"Error initializing analyzer: {e}")

# Optimization Checklist
st.header("✅ Optimization Checklist")

checklist_col1, checklist_col2 = st.columns(2)

with checklist_col1:
    st.markdown("### 🎯 Content Optimization")

    # Thumbnail optimization
    st.checkbox("Use high-contrast, clear thumbnails", value=False, key="thumb_opt")
    st.checkbox("Include text overlay on thumbnails", value=False, key="thumb_text")
    st.checkbox("Show faces/emotions in thumbnails", value=False, key="thumb_faces")

    # Title optimization
    st.checkbox("Use power words in titles", value=False, key="title_power")
    st.checkbox("Keep titles under 70 characters", value=False, key="title_length")
    st.checkbox("Include keywords in titles", value=False, key="title_keywords")

    # Description optimization
    st.checkbox("Write detailed descriptions (200+ words)", value=False, key="desc_detail")
    st.checkbox("Include timestamps in descriptions", value=False, key="desc_timestamps")
    st.checkbox("Add relevant links in descriptions", value=False, key="desc_links")

with checklist_col2:
    st.markdown("### ⚙️ Channel Optimization")

    # Channel branding
    st.checkbox("Custom channel banner", value=False, key="channel_banner")
    st.checkbox("Clear channel description", value=False, key="channel_desc")
    st.checkbox("Organized playlists", value=False, key="channel_playlists")

    # Engagement optimization
    st.checkbox("Use end screens", value=False, key="engage_endscreens")
    st.checkbox("Add cards during videos", value=False, key="engage_cards")
    st.checkbox("Pin important comments", value=False, key="engage_comments")

    # SEO optimization
    st.checkbox("Use relevant tags", value=False, key="seo_tags")
    st.checkbox("Add closed captions", value=False, key="seo_captions")
    st.checkbox("Optimize video metadata", value=False, key="seo_metadata")

# Growth Metrics Tracking
st.header("📊 Growth Metrics Tracking")

if not df.empty and "Published" in df.columns:
    # Calculate monthly growth
    df_copy = df.copy()

    # Convert Published column to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df_copy["Published"]):
        df_copy["Published"] = pd.to_datetime(df_copy["Published"], utc=True)

    df_copy["Month"] = df_copy["Published"].dt.to_period("M")

    monthly_stats = df_copy.groupby("Month").agg({
        "Views": "sum",
        "Likes": "sum",
        "Comments": "sum"
    }).reset_index()

    monthly_stats["Month"] = monthly_stats["Month"].astype(str)

    if len(monthly_stats) > 1:
        st.markdown("#### Monthly Performance Trends")
        st.dataframe(monthly_stats, use_container_width=True)

        # Plot trends
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(monthly_stats["Month"], monthly_stats["Views"], marker="o", label="Views")
        ax.plot(monthly_stats["Month"], monthly_stats["Likes"], marker="s", label="Likes")
        ax.plot(monthly_stats["Month"], monthly_stats["Comments"], marker="^", label="Comments")

        ax.set_xlabel("Month")
        ax.set_ylabel("Count")
        ax.set_title("Monthly Performance Trends")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)

        st.pyplot(fig)
    else:
        st.info("Need more data across multiple months to show trends.")

# Sidebar
st.sidebar.title("📈 Growth Recommendations")

# Data info
st.sidebar.markdown(f"**Videos Analyzed:** {len(df)}")
if "Content_Type" in df.columns:
    content_types = df["Content_Type"].unique()
    st.sidebar.markdown(f"**Content Types:** {len(content_types)}")

# Recommendation settings
st.sidebar.markdown("---")
st.sidebar.subheader("Recommendation Settings")

focus_area = st.sidebar.multiselect(
    "Focus Areas",
    ["Content Ideas", "Title Optimization", "Thumbnail Design", "SEO", "Engagement", "Monetization"],
    default=["Content Ideas", "Title Optimization"]
)

recommendation_count = st.sidebar.slider("Number of Recommendations", 5, 20, 10)

# Clear recommendations cache
if st.sidebar.button("🔄 Clear Recommendations Cache", key="clear_recs_cache"):
    if "recommendations" in locals():
        del recommendations
    st.rerun()

# Navigation
st.sidebar.markdown("---")
st.sidebar.subheader("📄 Navigation")
if st.sidebar.button("Home"):
    st.switch_page("pages/01_Home.py")
if st.sidebar.button("Content Analysis"):
    st.switch_page("pages/02_Content_Analysis.py")
if st.sidebar.button("Competitive Analysis"):
    st.switch_page("pages/03_Competitive_Analysis.py")
if st.sidebar.button("Topic Explorer"):
    st.switch_page("pages/05_Topic_Explorer.py")
if st.sidebar.button("Export Reports"):
    st.switch_page("pages/06_Export_Reports.py")