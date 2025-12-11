"""
Topic Explorer - YouTube Analytics
Advanced topic analysis, trend identification, and title suggestion engine.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import re
from collections import Counter

# Page configuration
st.set_page_config(
    page_title="YouTube Analytics - Topic Explorer",
    page_icon="🎯",
    layout="wide"
)

# Title and description
st.title("🎯 Topic Explorer")
st.markdown("""
Advanced topic analysis, trend identification, and AI-powered title suggestions.
Discover what topics resonate with your audience and get creative title ideas.
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

# Topic Analysis Section
st.header("📊 Topic Analysis")

# Extract and analyze keywords from titles
if not df.empty and "Title" in df.columns:
    # Simple keyword extraction
    all_titles = " ".join(df["Title"].astype(str).tolist())

    # Clean and tokenize
    words = re.findall(r'\b\w{3,}\b', all_titles.lower())

    # Remove common stopwords
    stopwords = set(['the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'what', 'when',
                     'where', 'why', 'how', 'which', 'who', 'you', 'your', 'they', 'their', 'them',
                     'are', 'was', 'were', 'has', 'had', 'will', 'would', 'could', 'should', 'about',
                     'like', 'just', 'then', 'than', 'more', 'most', 'some', 'very', 'much', 'many',
                     'also', 'only', 'not', 'but', 'because', 'into', 'through', 'during', 'before',
                     'after', 'above', 'below', 'between', 'under', 'over', 'again', 'further',
                     'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both',
                     'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'too',
                     'very', 'can', 'will', 'just', 'don', 'should', 'now'])

    filtered_words = [word for word in words if word not in stopwords and not word.isdigit()]

    # Count word frequencies
    word_counts = Counter(filtered_words)
    top_keywords = word_counts.most_common(20)

    if top_keywords:
        # Display top keywords
        st.subheader("🔑 Top Keywords in Titles")

        keywords_df = pd.DataFrame(top_keywords, columns=["Keyword", "Frequency"])
        st.dataframe(keywords_df, use_container_width=True)

        # Keyword visualization
        fig, ax = plt.subplots(figsize=(12, 6))
        keywords, frequencies = zip(*top_keywords)

        bars = ax.barh(keywords, frequencies, color='lightgreen')
        ax.set_xlabel('Frequency')
        ax.set_title('Top Keywords in Video Titles')
        ax.invert_yaxis()  # Highest frequency at top

        # Add value labels
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2,
                   f'{int(width)}', ha='left', va='center')

        st.pyplot(fig)

        # Keyword performance analysis
        st.subheader("📈 Keyword Performance")

        # Analyze performance of videos containing top keywords
        keyword_performance = []

        for keyword, _ in top_keywords[:10]:  # Analyze top 10 keywords
            # Find videos containing this keyword
            keyword_videos = df[df["Title"].str.contains(keyword, case=False, na=False)]

            if not keyword_videos.empty:
                avg_views = keyword_videos["Views"].mean()
                avg_engagement = keyword_videos["Engagement_Rate"].mean()
                count = len(keyword_videos)

                keyword_performance.append({
                    "Keyword": keyword,
                    "Video Count": count,
                    "Avg Views": int(avg_views),
                    "Avg Engagement": f"{avg_engagement:.1f}%"
                })

        if keyword_performance:
            perf_df = pd.DataFrame(keyword_performance)
            perf_df = perf_df.sort_values("Avg Views", ascending=False)
            st.dataframe(perf_df, use_container_width=True)

# Title Pattern Analysis
st.header("🔤 Title Pattern Analysis")

if not df.empty and "Title" in df.columns:
    # Common title patterns
    patterns = {
        "How-to/ Tutorial": r'\b(how to|tutorial|guide|step by step)\b',
        "List/ Numbered": r'\b(\d+ (ways|tips|reasons|facts|secrets)|top \d+)\b',
        "Question Titles": r'^\s*(what|why|how|when|where|who|which)\s+',
        "Comparison Titles": r'\b(vs\.?|versus|compared to|better than|worse than)\b',
        "Review Titles": r'\b(review|unboxing|first look|hands on)\b',
        "Challenge Titles": r'\b(challenge|experiment|test|trying)\b'
    }

    pattern_counts = {}
    pattern_performance = {}

    for pattern_name, pattern_regex in patterns.items():
        # Count videos matching pattern
        matches = df["Title"].str.contains(pattern_regex, case=False, na=False, regex=True)
        count = matches.sum()

        if count > 0:
            pattern_counts[pattern_name] = count

            # Calculate performance
            matching_videos = df[matches]
            avg_views = matching_videos["Views"].mean()
            avg_engagement = matching_videos["Engagement_Rate"].mean()

            pattern_performance[pattern_name] = {
                "Video Count": count,
                "Avg Views": int(avg_views),
                "Avg Engagement": f"{avg_engagement:.1f}%"
            }

    if pattern_counts:
        # Display pattern distribution
        st.subheader("Title Pattern Distribution")

        patterns_df = pd.DataFrame(list(pattern_counts.items()), columns=["Pattern", "Count"])
        patterns_df = patterns_df.sort_values("Count", ascending=False)

        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(patterns_df["Pattern"], patterns_df["Count"], color='orange')
        ax.set_xlabel('Title Pattern')
        ax.set_ylabel('Number of Videos')
        ax.set_title('Title Pattern Distribution')
        ax.tick_params(axis='x', rotation=45)

        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{int(height)}', ha='center', va='bottom')

        st.pyplot(fig)

        # Display pattern performance
        st.subheader("Pattern Performance")

        if pattern_performance:
            perf_df = pd.DataFrame(pattern_performance).T
            perf_df = perf_df.sort_values("Avg Views", ascending=False)
            st.dataframe(perf_df, use_container_width=True)

# Title Suggestion Engine
st.header("🤖 Title Suggestion Engine")

# Title generation parameters
col1, col2 = st.columns(2)

with col1:
    suggestion_type = st.selectbox(
        "Suggestion Type",
        ["List/Numbered", "How-to/Tutorial", "Question", "Comparison", "Review", "Challenge"],
        key="suggestion_type"
    )

with col2:
    keyword_input = st.text_input(
        "Primary Keyword/Topic",
        placeholder="Enter main topic or keyword",
        key="title_keyword"
    )

# Generate title suggestions
if st.button("Generate Title Suggestions", key="generate_titles"):
    if keyword_input:
        with st.spinner("Generating title suggestions..."):
            # Base templates for different suggestion types
            templates = {
                "List/Numbered": [
                    f"{keyword_input}: {num} {things} You Need to Know",
                    f"Top {num} {keyword_input} {things} That Will Change Your Mind",
                    f"{num} {keyword_input} {things} Nobody Tells You About",
                    f"The {num} Best {keyword_input} {things} of All Time",
                    f"{num} {keyword_input} {things} That Actually Work"
                ],
                "How-to/Tutorial": [
                    f"How to {keyword_input}: A Complete Beginner's Guide",
                    f"The Ultimate Guide to {keyword_input}",
                    f"{keyword_input} Made Easy: Step-by-Step Tutorial",
                    f"Master {keyword_input} in 30 Minutes or Less",
                    f"How I {keyword_input} (And How You Can Too)"
                ],
                "Question": [
                    f"What is {keyword_input} and Why Should You Care?",
                    f"Why {keyword_input} is Changing Everything",
                    f"How {keyword_input} Actually Works (The Truth)",
                    f"When Should You Use {keyword_input}?",
                    f"Where to Find the Best {keyword_input} Resources"
                ],
                "Comparison": [
                    f"{keyword_input} vs. The Competition: Which is Better?",
                    f"{keyword_input}: Before and After Results",
                    f"Traditional vs. Modern {keyword_input} Methods",
                    f"{keyword_input} Compared: Which One Wins?",
                    f"The Truth About {keyword_input}: Pros and Cons"
                ],
                "Review": [
                    f"{keyword_input} Review: Is It Worth It?",
                    f"My Honest Review of {keyword_input}",
                    f"{keyword_input} Unboxing and First Impressions",
                    f"Testing {keyword_input}: Does It Live Up to the Hype?",
                    f"{keyword_input} Hands-On Review: The Good, The Bad"
                ],
                "Challenge": [
                    f"{keyword_input} Challenge: Can I Do It?",
                    f"Trying {keyword_input} for 30 Days: Results",
                    f"The {keyword_input} Experiment: What Happened",
                    f"I Tried {keyword_input} So You Don't Have To",
                    f"{keyword_input} Challenge: Before and After"
                ]
            }

            # Things to use with numbers
            things_options = ["Tips", "Tricks", "Secrets", "Facts", "Ways", "Methods", "Ideas", "Strategies"]

            # Generate suggestions
            suggestions = []
            selected_templates = templates.get(suggestion_type, [])

            for template in selected_templates:
                if "{num}" in template:
                    for num in [3, 5, 7, 10]:
                        for thing in things_options[:2]:  # Use first 2 options
                            suggestion = template.replace("{num}", str(num)).replace("{things}", thing)
                            suggestions.append(suggestion)
                else:
                    suggestions.append(template)

            # Display suggestions
            st.subheader(f"📝 {suggestion_type} Title Suggestions")

            for i, suggestion in enumerate(suggestions[:10], 1):  # Show top 10
                # Calculate estimated length
                length = len(suggestion)
                length_indicator = "✅" if length <= 70 else "⚠️" if length <= 100 else "❌"

                # Display with formatting
                st.markdown(f"""
                **{i}. {suggestion}**
                *Length: {length} characters {length_indicator}*
                """)

                # Add copy button
                if st.button(f"Copy #{i}", key=f"copy_{i}"):
                    st.code(suggestion, language=None)
                    st.success("Title copied to clipboard!")
    else:
        st.warning("Please enter a keyword or topic to generate suggestions.")

# Trend Analysis
st.header("📈 Trend Analysis")

if not df.empty and "Published" in df.columns and "Title" in df.columns:
    # Analyze trends over time
    df_copy = df.copy()

    # Convert Published column to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df_copy["Published"]):
        df_copy["Published"] = pd.to_datetime(df_copy["Published"], utc=True)

    df_copy["Month"] = df_copy["Published"].dt.to_period("M")

    # Get top keywords by month
    monthly_trends = {}

    for month in sorted(df_copy["Month"].unique()):
        month_data = df_copy[df_copy["Month"] == month]
        month_titles = " ".join(month_data["Title"].astype(str).tolist())

        # Extract keywords for this month
        words = re.findall(r'\b\w{3,}\b', month_titles.lower())
        filtered_words = [word for word in words if word not in stopwords and not word.isdigit()]

        if filtered_words:
            word_counts = Counter(filtered_words)
            top_month_keywords = word_counts.most_common(5)
            monthly_trends[str(month)] = top_month_keywords

    if monthly_trends:
        st.subheader("📅 Monthly Topic Trends")

        # Create trend visualization
        trend_data = []
        for month, keywords in monthly_trends.items():
            for keyword, count in keywords:
                trend_data.append({
                    "Month": month,
                    "Keyword": keyword,
                    "Frequency": count
                })

        if trend_data:
            trend_df = pd.DataFrame(trend_data)

            # Pivot for heatmap-style visualization
            pivot_df = trend_df.pivot(index="Keyword", columns="Month", values="Frequency").fillna(0)

            # Show heatmap
            fig, ax = plt.subplots(figsize=(12, 8))
            im = ax.imshow(pivot_df.values, cmap="YlOrRd", aspect="auto")

            ax.set_xticks(np.arange(len(pivot_df.columns)))
            ax.set_yticks(np.arange(len(pivot_df.index)))
            ax.set_xticklabels(pivot_df.columns, rotation=45)
            ax.set_yticklabels(pivot_df.index)

            # Add colorbar
            cbar = ax.figure.colorbar(im, ax=ax)
            cbar.ax.set_ylabel("Frequency", rotation=-90, va="bottom")

            ax.set_title("Keyword Trends Over Time (Heatmap)")
            plt.tight_layout()

            st.pyplot(fig)

# Sidebar
st.sidebar.title("🎯 Topic Explorer")

# Data info
st.sidebar.markdown(f"**Videos Analyzed:** {len(df)}")
if "Title" in df.columns:
    avg_title_length = df["Title"].str.len().mean() if not df.empty else 0
    st.sidebar.markdown(f"**Avg Title Length:** {avg_title_length:.0f} chars")

# Analysis settings
st.sidebar.markdown("---")
st.sidebar.subheader("Analysis Settings")

min_word_length = st.sidebar.slider("Minimum Word Length", 3, 8, 4, key="min_word_len")
top_n_keywords = st.sidebar.slider("Top N Keywords", 10, 50, 20, key="top_n_keywords")

# Clear analysis cache
if st.sidebar.button("🔄 Clear Analysis Cache", key="clear_topic_cache"):
    if "top_keywords" in locals():
        del top_keywords
    if "pattern_counts" in locals():
        del pattern_counts
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
if st.sidebar.button("Growth Recommendations"):
    st.switch_page("pages/04_Growth_Recommendations.py")
if st.sidebar.button("Export Reports"):
    st.switch_page("pages/06_Export_Reports.py")