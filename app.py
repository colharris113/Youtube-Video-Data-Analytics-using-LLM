"""
YouTube Analytics Platform - Main Entry Point

This is the main entry point for the YouTube Analytics Platform.
It sets up the basic configuration and redirects to the multi-page app structure.
"""

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="YouTube Growth Analytics Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Welcome message
st.title("🚀 YouTube Growth Analytics Platform")
st.markdown("""
Welcome to your comprehensive YouTube growth analytics platform.

This platform provides AI-powered insights, competitive intelligence, and actionable recommendations
to help grow your YouTube channel.

### Getting Started:
1. **Navigate to the Home page** using the sidebar or button below
2. **Configure your YouTube API Key** in the sidebar
3. **Enter your Channel Name** to analyze
4. **Explore different analysis pages** for detailed insights

### Available Features:
- **📊 Basic Analytics**: Video performance, content type analysis, trends
- **🧠 AI Content Analysis**: Topic modeling, clustering, recommendations
- **🥊 Competitive Intelligence**: Compare with rival channels
- **📈 Growth Recommendations**: AI-powered strategy suggestions
- **🎯 Topic Explorer**: Advanced topic analysis and title suggestions
- **📁 Export Reports**: Download data in multiple formats
""")

# Quick navigation
st.markdown("---")
st.subheader("🚀 Quick Start")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Go to Home", use_container_width=True):
        st.switch_page("pages/01_Home.py")

with col2:
    if st.button("📊 View Demo", use_container_width=True):
        st.info("""
        **Demo Mode:**
        - Sample data will be loaded
        - All features available
        - No API key required
        """)
        # In a real implementation, you would load sample data here

with col3:
    if st.button("📚 Documentation", use_container_width=True):
        st.info("""
        **Documentation:**
        - Check the README.md file
        - See config.py for configuration options
        - Each page has its own documentation
        """)

# Configuration status
st.markdown("---")
st.subheader("⚙️ Configuration Status")

try:
    from config import YOUTUBE_API_KEY, DEFAULT_CHANNEL

    col1, col2 = st.columns(2)

    with col1:
        if YOUTUBE_API_KEY:
            st.success("✅ YouTube API Key: Configured")
        else:
            st.warning("⚠️ YouTube API Key: Not configured")
            st.info("Set YOUTUBE_API_KEY in .env file or config.py")

    with col2:
        if DEFAULT_CHANNEL:
            st.info(f"📺 Default Channel: {DEFAULT_CHANNEL}")
        else:
            st.info("📺 Default Channel: Not set")

except ImportError:
    st.warning("⚠️ Configuration file not found")
    st.info("Create a config.py file or set environment variables")

# Sidebar navigation
st.sidebar.title("🎯 Navigation")
st.sidebar.markdown("Use the buttons below to navigate to different sections:")

pages = [
    ("🏠 Home", "pages/01_Home.py"),
    ("📊 Content Analysis", "pages/02_Content_Analysis.py"),
    ("🥊 Competitive Analysis", "pages/03_Competitive_Analysis.py"),
    ("📈 Growth Recommendations", "pages/04_Growth_Recommendations.py"),
    ("🎯 Topic Explorer", "pages/05_Topic_Explorer.py"),
    ("📁 Export Reports", "pages/06_Export_Reports.py"),
]

for page_name, page_path in pages:
    if st.sidebar.button(page_name, use_container_width=True, key=f"nav_{page_name}"):
        st.switch_page(page_path)

# App info
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ App Info")
st.sidebar.markdown("**Version:** 2.0.0")
st.sidebar.markdown("**Multi-page:** ✅ Enabled")
st.sidebar.markdown("**Caching:** ✅ Enabled")

# Run instructions
st.sidebar.markdown("---")
st.sidebar.subheader("🚀 Run Instructions")
st.sidebar.code("streamlit run app.py", language="bash")

# Note about the old file
st.sidebar.markdown("---")
st.sidebar.info("""
**Note:** The application has been refactored into a multi-page structure.
Old file: `youtube_analytics_app.py` → New: `youtube_utils.py` + `pages/` directory
""")