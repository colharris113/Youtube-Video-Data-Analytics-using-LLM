"""
🧠 Content Analysis - YouTube Analytics
Content clustering, topic modeling, and performance analysis by content type.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Page configuration
st.set_page_config(
    page_title="YouTube Analytics - Content Analysis",
    page_icon="🧠",
    layout="wide"
)

# Title and description
st.title("🧠 Content Analysis")
st.markdown("""
Analyze your content performance through topic modeling, clustering, and pattern recognition.
Identify what works best for your channel.
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
                if st.button("🏠 Go to Home"):
                    st.switch_page("pages/01_Home.py")
                st.stop()
        else:
            st.warning("⚠️ No channel data loaded yet.")
            st.info("Please go to the Home page to fetch channel data first.")
            if st.button("🏠 Go to Home"):
                st.switch_page("pages/01_Home.py")
            st.stop()

    except Exception as e:
        st.warning("⚠️ No channel data loaded yet.")
        st.info("Please go to the Home page to fetch channel data first.")
        if st.button("🏠 Go to Home"):
            st.switch_page("pages/01_Home.py")
        st.stop()

df = st.session_state.df

# Content Type Analysis
st.header("🎬 Content Type Analysis")

col1, col2 = st.columns(2)

with col1:
    # Content type distribution
    if "Content_Type" in df.columns:
        content_counts = df["Content_Type"].value_counts()
        fig1, ax1 = plt.subplots(figsize=(6, 4))
        ax1.pie(content_counts.values, labels=content_counts.index, autopct='%1.1f%%', startangle=90)
        ax1.axis('equal')
        ax1.set_title("Content Type Distribution")
        st.pyplot(fig1)

with col2:
    # Performance by content type
    if "Content_Type" in df.columns and "Views" in df.columns:
        performance_by_type = df.groupby("Content_Type")["Views"].mean().sort_values(ascending=False)
        fig2, ax2 = plt.subplots(figsize=(6, 4))
        performance_by_type.plot(kind="bar", ax=ax2, color="skyblue")
        ax2.set_title("Average Views by Content Type")
        ax2.set_ylabel("Average Views")
        ax2.tick_params(axis='x', rotation=45)
        st.pyplot(fig2)

# Content Clustering (if content_analyzer is available)
st.header("📊 Content Clustering")

try:
    from content_analyzer import ContentAnalyzer

    # Initialize analyzer
    analyzer = ContentAnalyzer()

    # Clustering options
    col1, col2 = st.columns(2)

    with col1:
        num_clusters = st.slider("Number of Clusters", 2, 10, 5, key="content_clusters")

    with col2:
        use_keywords = st.checkbox("Use Keyword Extraction", value=True, key="use_keywords")

    if st.button("🔍 Analyze Content Clusters", key="analyze_clusters"):
        with st.spinner("Analyzing content clusters..."):
            # Perform clustering using the actual method
            clustered_df = analyzer.cluster_content(df, num_clusters=num_clusters)

            if clustered_df is not None and 'Cluster' in clustered_df.columns:
                # Display cluster results
                st.subheader("Cluster Analysis Results")

                # Cluster distribution
                cluster_counts = clustered_df['Cluster'].value_counts().sort_index()
                fig3, ax3 = plt.subplots(figsize=(8, 4))
                cluster_counts.plot(kind="bar", ax=ax3, color="lightgreen")
                ax3.set_title("Video Distribution Across Clusters")
                ax3.set_xlabel("Cluster")
                ax3.set_ylabel("Number of Videos")
                st.pyplot(fig3)

                # Show cluster details
                st.subheader("Cluster Details")
                for cluster_id in sorted(clustered_df['Cluster'].unique()):
                    cluster_data = clustered_df[clustered_df['Cluster'] == cluster_id]

                    with st.expander(f"Cluster {cluster_id}: {len(cluster_data)} videos"):
                        # Show top videos in cluster
                        if 'Views' in cluster_data.columns and 'Title' in cluster_data.columns:
                            top_videos = cluster_data.nlargest(3, 'Views')[['Title', 'Views', 'Engagement_Rate']]
                            st.markdown("**Top Performing Videos:**")
                            for idx, row in top_videos.iterrows():
                                st.markdown(f"- {row['Title']} ({row['Views']:,} views, {row['Engagement_Rate']:.1f}% engagement)")

except ImportError:
    st.warning("Content analyzer module not available. Install required packages: `pip install nltk scikit-learn`")
except Exception as e:
    st.error(f"Error in content analysis: {e}")

# Title Pattern Analysis
st.header("🔤 Title Pattern Analysis")

try:
    from content_analyzer import ContentAnalyzer

    if "analyzer" not in locals():
        analyzer = ContentAnalyzer()

    # Analyze video titles
    title_analysis = analyzer.analyze_video_titles(df)

    if title_analysis:
        col1, col2 = st.columns(2)

        with col1:
            # Title length analysis
            st.markdown("##### Title Length Analysis")
            st.metric("Avg Title Length", f"{title_analysis.get('avg_title_length', 0):.1f} chars")
            st.metric("Min Title Length", title_analysis.get('min_title_length', 0))
            st.metric("Max Title Length", title_analysis.get('max_title_length', 0))

        with col2:
            # Top keywords
            keywords = title_analysis.get('title_keywords', [])
            if keywords:
                st.markdown("##### Top Title Keywords")
                st.write(", ".join(keywords[:10]))

        # Get content insights which includes recommendations
        insights = analyzer.generate_content_insights(df)
        recommendations = insights.get("recommendations", [])

        if recommendations:
            st.subheader("📈 Content Recommendations")
            for i, rec in enumerate(recommendations[:5], 1):
                st.info(f"{i}. {rec}")

except Exception as e:
    st.warning(f"Title pattern analysis not available: {e}")

# Keyword Analysis
st.header("🔑 Keyword Analysis")

try:
    from utils import extract_keyword_frequencies

    # Extract keywords from titles
    all_titles = " ".join(df["Title"].astype(str).tolist())
    keywords = extract_keyword_frequencies(all_titles, top_n=20)

    if keywords:
        # Display keywords
        keywords_df = pd.DataFrame(keywords, columns=["Keyword", "Frequency"])
        st.dataframe(keywords_df, use_container_width=True)

        # Keyword cloud (if wordcloud is available)
        try:
            from wordcloud import WordCloud
            import matplotlib.pyplot as plt

            wordcloud = WordCloud(width=800, height=400, background_color='white').generate_from_frequencies(dict(keywords))

            fig5, ax5 = plt.subplots(figsize=(10, 5))
            ax5.imshow(wordcloud, interpolation='bilinear')
            ax5.axis('off')
            ax5.set_title("Keyword Cloud from Video Titles")
            st.pyplot(fig5)
        except ImportError:
            st.info("Install `wordcloud` package for visual keyword clouds: `pip install wordcloud`")

except Exception as e:
    st.warning(f"Keyword analysis not available: {e}")

# Sidebar
st.sidebar.title("🧠 Content Analysis")

# Data info
st.sidebar.markdown(f"**Videos Loaded:** {len(df)}")
if "Content_Type" in df.columns:
    content_types = df["Content_Type"].unique()
    st.sidebar.markdown(f"**Content Types:** {', '.join(content_types)}")

# Analysis options
st.sidebar.markdown("---")
st.sidebar.subheader("Analysis Options")

# Clear analysis cache
if st.sidebar.button("🔄 Clear Analysis Cache", key="clear_analysis_cache"):
    if "cluster_results" in locals():
        del cluster_results
    st.rerun()

# Navigation
st.sidebar.markdown("---")
st.sidebar.subheader("📄 Navigation")
if st.sidebar.button("🏠 Home"):
    st.switch_page("pages/01_Home.py")
if st.sidebar.button("🥊 Competitive Analysis"):
    st.switch_page("pages/03_Competitive_Analysis.py")
if st.sidebar.button("📈 Growth Recommendations"):
    st.switch_page("pages/04_Growth_Recommendations.py")