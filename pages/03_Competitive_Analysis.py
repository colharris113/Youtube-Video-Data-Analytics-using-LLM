"""
🥊 Competitive Analysis - YouTube Analytics
Compare your channel with competitors, analyze market share, and identify gaps.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="YouTube Analytics - Competitive Analysis",
    page_icon="🥊",
    layout="wide"
)

# Title and description
st.title("🥊 Competitive Analysis")
st.markdown("""
Compare your channel with competitors to understand your market position,
identify strengths and weaknesses, and discover growth opportunities.
""")

# Check if we have main channel data - try to load from cache first
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
                st.warning("⚠️ No main channel data loaded yet.")
                st.info("Please go to the Home page to fetch your channel data first.")
                if st.button("🏠 Go to Home"):
                    st.switch_page("pages/01_Home.py")
                st.stop()
        else:
            st.warning("⚠️ No main channel data loaded yet.")
            st.info("Please go to the Home page to fetch your channel data first.")
            if st.button("🏠 Go to Home"):
                st.switch_page("pages/01_Home.py")
            st.stop()

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.warning(f"⚠️ Cache loading error: {e}")
        st.info("Please go to the Home page to fetch your channel data first.")
        # Debug info
        with st.expander("Debug Info"):
            st.code(error_details)
        if st.button("🏠 Go to Home"):
            st.switch_page("pages/01_Home.py")
        st.stop()

main_df = st.session_state.df

# Initialize data_manager for competitor data restoration
try:
    from data_manager import get_data_manager
    data_manager = get_data_manager()
    DATA_MANAGER_AVAILABLE = True
except:
    DATA_MANAGER_AVAILABLE = False
    data_manager = None

# Get rival channels from config
try:
    from config import RIVAL_CHANNELS
    rival_channels = RIVAL_CHANNELS if RIVAL_CHANNELS else []
except:
    rival_channels = []
    st.warning("⚠️ No rival channels configured. Add them to `.env` as `RIVAL_CHANNELS=Channel1,Channel2,Channel3`")

# Competitive Analysis Section
st.header("📊 Channel Comparison")

if rival_channels:
    # Check if we have competitor data cached
    competitor_data = None
    comparison_df = None

    # First check session state (in-memory cache)
    if "competitor_data" in st.session_state:
        competitor_data = st.session_state.competitor_data
        st.success("✅ Using cached competitor data (session state)")
    # Then check data_manager (persistent cache)
    elif DATA_MANAGER_AVAILABLE and data_manager:
        # Try to load competitor data from data_manager
        try:
            competitor_data = data_manager.get_session_value("competitor_data")
            if competitor_data:
                st.session_state.competitor_data = competitor_data
                st.success("✅ Loaded competitor data from persistent cache")
        except:
            competitor_data = None

    # Check for comparison_df in session state
    if "comparison_df" in st.session_state and not st.session_state.comparison_df.empty:
        comparison_df = st.session_state.comparison_df
        st.success("✅ Using cached comparison data (session state)")
    # Check for comparison_df in data_manager
    elif DATA_MANAGER_AVAILABLE and data_manager:
        try:
            comparison_df = data_manager.load_dataframe("competitor_comparison_df")
            if comparison_df is not None and not comparison_df.empty:
                st.session_state.comparison_df = comparison_df
                st.success("✅ Loaded comparison data from persistent cache")
        except:
            comparison_df = None

    # Check for main_channel_data in session state
    if "main_channel_data" not in st.session_state and DATA_MANAGER_AVAILABLE and data_manager:
        try:
            main_channel_data = data_manager.get_session_value("main_channel_data")
            if main_channel_data:
                st.session_state.main_channel_data = main_channel_data
                st.success("✅ Loaded main channel data from persistent cache")
        except:
            pass

    # Check if we have valid competitor data and comparison data
    has_competitor_data = competitor_data is not None and competitor_data != {}

    # Check comparison_df - it could be None, empty DataFrame, or valid DataFrame
    if comparison_df is None:
        has_comparison_data = False
    elif isinstance(comparison_df, pd.DataFrame):
        has_comparison_data = not comparison_df.empty
    else:
        # comparison_df is some other type (shouldn't happen)
        has_comparison_data = False

    if not has_competitor_data or not has_comparison_data:
        st.info("Competitor data not cached. Click 'Fetch Competitor Data' to analyze.")

    # Fetch competitor data button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🚀 Fetch Competitor Data", key="fetch_competitors"):
            with st.spinner("Fetching competitor data..."):
                try:
                    from competitor_analyzer import CompetitorAnalyzer
                    from config import YOUTUBE_API_KEY

                    analyzer = CompetitorAnalyzer(api_key=YOUTUBE_API_KEY)

                    # Fetch competitor data
                    competitor_data = analyzer.fetch_all_competitors(
                        rival_channels=rival_channels,
                        max_results=20
                    )

                    # Fetch main channel data for comparison
                    # Get channel name from config
                    try:
                        from config import DEFAULT_CHANNEL
                        main_channel_name = DEFAULT_CHANNEL
                    except ImportError:
                        main_channel_name = "Your Channel"

                    if not main_channel_name:
                        main_channel_name = "Your Channel"

                    main_channel_data = analyzer.fetch_channel_data(
                        channel_name=main_channel_name,
                        max_results=20
                    )

                    if competitor_data and main_channel_data:
                        # Store in session state
                        st.session_state.competitor_data = competitor_data
                        st.session_state.main_channel_data = main_channel_data

                        # Perform comparison
                        comparison_df = analyzer.compare_channels(
                            main_channel_data,
                            competitor_data
                        )
                        st.session_state.comparison_df = comparison_df

                        # Save to data_manager for persistent caching
                        if DATA_MANAGER_AVAILABLE and data_manager:
                            try:
                                data_manager.save_session_value("competitor_data", competitor_data)
                                data_manager.save_session_value("main_channel_data", main_channel_data)
                                data_manager.save_dataframe("competitor_comparison_df", comparison_df)
                                st.success("✅ Saved competitor data to persistent cache")
                            except Exception as save_error:
                                st.warning(f"⚠️ Could not save to persistent cache: {save_error}")

                        st.success(f"✅ Fetched data for {len(competitor_data)} competitors")
                        st.rerun()
                    else:
                        st.error("❌ Failed to fetch competitor data")

                except Exception as e:
                    st.error(f"❌ Error fetching competitor data: {e}")

    # Display comparison if available
    if "comparison_df" in st.session_state and not st.session_state.comparison_df.empty:
        comparison_df = st.session_state.comparison_df

        # Key metrics comparison
        st.subheader("📈 Key Metrics Comparison")

        # Select metrics to compare - use actual column names from competitor_analyzer
        # First, check what columns are actually available
        available_metrics = []
        metric_names = {}

        if "subscriber_count" in comparison_df.columns:
            available_metrics.append("subscriber_count")
            metric_names["subscriber_count"] = "Subscribers"

        # Use view_count instead of total_views
        if "view_count" in comparison_df.columns:
            available_metrics.append("view_count")
            metric_names["view_count"] = "Total Views"
        elif "total_views_recent" in comparison_df.columns:
            available_metrics.append("total_views_recent")
            metric_names["total_views_recent"] = "Recent Views"

        if "video_count" in comparison_df.columns:
            available_metrics.append("video_count")
            metric_names["video_count"] = "Total Videos"

        if "avg_views_per_video" in comparison_df.columns:
            available_metrics.append("avg_views_per_video")
            metric_names["avg_views_per_video"] = "Avg Views/Video"

        if "engagement_rate" in comparison_df.columns:
            available_metrics.append("engagement_rate")
            metric_names["engagement_rate"] = "Engagement Rate"

        # If no metrics available, use defaults
        if not available_metrics:
            available_metrics = ["subscriber_count", "view_count", "video_count", "avg_views_per_video", "engagement_rate"]
            metric_names = {
                "subscriber_count": "Subscribers",
                "view_count": "Total Views",
                "video_count": "Total Videos",
                "avg_views_per_video": "Avg Views/Video",
                "engagement_rate": "Engagement Rate"
            }

        selected_metric = st.selectbox(
            "Select Metric to Compare",
            options=available_metrics,
            format_func=lambda x: metric_names.get(x, x.replace("_", " ").title()),
            key="comp_metric_select"
        )

        # Sort by selected metric
        sorted_df = comparison_df.sort_values(selected_metric, ascending=False)

        # Create comparison chart
        fig, ax = plt.subplots(figsize=(10, 6))

        # Highlight main channel
        colors = ['green' if idx == 0 else 'skyblue' for idx in range(len(sorted_df))]
        bars = ax.barh(sorted_df["channel_name"], sorted_df[selected_metric], color=colors)

        ax.set_xlabel(metric_names[selected_metric])
        ax.set_title(f"Channel Comparison: {metric_names[selected_metric]}")
        ax.invert_yaxis()  # Highest at top

        # Add value labels
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2,
                   f'{width:,.0f}' if selected_metric != 'engagement_rate' else f'{width:.1f}%',
                   ha='left', va='center')

        st.pyplot(fig)

        # Detailed comparison table
        st.subheader("📋 Detailed Comparison Table")
        display_df = comparison_df.copy()

        # Format numbers - use the actual column names from competitor_analyzer
        if "subscriber_count" in display_df.columns:
            display_df["subscriber_count"] = display_df["subscriber_count"].apply(lambda x: f"{x:,}")

        # Use view_count instead of total_views
        if "view_count" in display_df.columns:
            display_df["view_count"] = display_df["view_count"].apply(lambda x: f"{x:,}")
        elif "total_views_recent" in display_df.columns:
            display_df["total_views_recent"] = display_df["total_views_recent"].apply(lambda x: f"{x:,}")

        if "video_count" in display_df.columns:
            display_df["video_count"] = display_df["video_count"].apply(lambda x: f"{x:,}")

        if "avg_views_per_video" in display_df.columns:
            display_df["avg_views_per_video"] = display_df["avg_views_per_video"].apply(lambda x: f"{x:,.0f}")

        if "engagement_rate" in display_df.columns:
            display_df["engagement_rate"] = display_df["engagement_rate"].apply(lambda x: f"{x:.1f}%")

        st.dataframe(display_df, use_container_width=True)

        # Gap Analysis
        st.subheader("🔍 Gap Analysis")

        if "main_channel_data" in st.session_state:
            try:
                from competitor_analyzer import CompetitorAnalyzer
                analyzer = CompetitorAnalyzer(api_key="dummy")  # API key not needed for analysis

                gap_analysis = analyzer.calculate_gap_analysis(
                    st.session_state.main_channel_data,
                    competitor_data
                )

                if gap_analysis:
                    # Display strengths, weaknesses, opportunities
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.markdown("### ✅ Strengths")
                        for strength in gap_analysis.get("strengths", [])[:3]:
                            st.success(strength)

                    with col2:
                        st.markdown("### ⚠️ Weaknesses")
                        for weakness in gap_analysis.get("weaknesses", [])[:3]:
                            st.warning(weakness)

                    with col3:
                        st.markdown("### 🚀 Opportunities")
                        for opportunity in gap_analysis.get("opportunities", [])[:3]:
                            st.info(opportunity)

                    # Show all analysis in expander
                    with st.expander("📊 Full Gap Analysis Details"):
                        st.markdown("#### Strengths")
                        for strength in gap_analysis.get("strengths", []):
                            st.markdown(f"- {strength}")

                        st.markdown("#### Weaknesses")
                        for weakness in gap_analysis.get("weaknesses", []):
                            st.markdown(f"- {weakness}")

                        st.markdown("#### Opportunities")
                        for opportunity in gap_analysis.get("opportunities", []):
                            st.markdown(f"- {opportunity}")

            except Exception as e:
                st.warning(f"Gap analysis not available: {e}")

    else:
        # Show rival channels list
        st.subheader("🎯 Configured Competitors")
        st.write("The following channels are configured for comparison:")
        for i, channel in enumerate(rival_channels, 1):
            st.markdown(f"{i}. {channel}")

        st.info("Click 'Fetch Competitor Data' to start the analysis.")
else:
    st.warning("""
    No rival channels configured. To use competitive analysis:

    1. Edit your `.env` file
    2. Add: `RIVAL_CHANNELS=Channel1,Channel2,Channel3`
    3. Use exact YouTube channel names
    4. Restart the app
    """)

# Market Share Analysis
st.header("📊 Market Share Analysis")

if rival_channels and "comparison_df" in st.session_state and not st.session_state.comparison_df.empty:
    comparison_df = st.session_state.comparison_df

    # Calculate market share (based on subscribers)
    total_subscribers = comparison_df["subscriber_count"].sum()
    comparison_df["market_share"] = (comparison_df["subscriber_count"] / total_subscribers) * 100

    # Market share pie chart
    fig2, ax2 = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax2.pie(
        comparison_df["market_share"],
        labels=comparison_df["channel_name"],
        autopct='%1.1f%%',
        startangle=90
    )

    # Highlight main channel
    for i, (wedge, channel) in enumerate(zip(wedges, comparison_df["channel_name"])):
        if i == 0:  # Main channel
            wedge.set_edgecolor('green')
            wedge.set_linewidth(2)

    ax2.axis('equal')
    ax2.set_title("Market Share by Subscribers")
    st.pyplot(fig2)

    # Growth comparison (placeholder - requires historical data for accurate growth metrics)
    # Note: Growth rate calculation requires historical subscriber data over time
    # To implement: Store historical channel data and calculate growth between time periods
    # st.subheader("📈 Growth Metrics")
    # st.info("Growth metrics require historical data collection over time. This feature is planned for future enhancement.")

# Sidebar
st.sidebar.title("🥊 Competitive Analysis")

# Competitor info
if rival_channels:
    st.sidebar.markdown(f"**Competitors Configured:** {len(rival_channels)}")
    with st.sidebar.expander("View Competitors"):
        for channel in rival_channels:
            st.markdown(f"- {channel}")

# Data management
st.sidebar.markdown("---")
st.sidebar.subheader("Data Management")

if st.sidebar.button("🔄 Clear Competitor Cache", key="clear_comp_cache"):
    keys_to_remove = ["competitor_data", "main_channel_data", "comparison_df"]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# Analysis options
st.sidebar.markdown("---")
st.sidebar.subheader("Analysis Options")

max_results = st.sidebar.slider("Videos per Competitor", 10, 50, 20, key="comp_max_results")

# Navigation
st.sidebar.markdown("---")
st.sidebar.subheader("📄 Navigation")
if st.sidebar.button("🏠 Home"):
    st.switch_page("pages/01_Home.py")
if st.sidebar.button("🧠 Content Analysis"):
    st.switch_page("pages/02_Content_Analysis.py")
if st.sidebar.button("📈 Growth Recommendations"):
    st.switch_page("pages/04_Growth_Recommendations.py")