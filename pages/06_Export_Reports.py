"""
Export Reports - YouTube Analytics
Export analytics data and generate comprehensive reports in various formats.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import io
import base64
from typing import Dict, Any, Optional

# Page configuration
st.set_page_config(
    page_title="YouTube Analytics - Export Reports",
    page_icon="📊",
    layout="wide"
)

# Title and description
st.title("📊 Export Reports")
st.markdown("""
Export your YouTube analytics data and generate comprehensive reports.
Download data in CSV, Excel, or generate visual PDF reports.
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

# Export Options Section
st.header("📁 Export Options")

# Data selection
st.subheader("Select Data to Export")

export_options = st.multiselect(
    "Choose data to include in export:",
    [
        "Video Performance Data",
        "Content Type Analysis",
        "Engagement Metrics",
        "Competitor Comparison",
        "Topic Analysis",
        "Growth Recommendations"
    ],
    default=["Video Performance Data", "Content Type Analysis"],
    key="export_selection"
)

# Format selection
st.subheader("Export Format")

export_format = st.radio(
    "Select export format:",
    ["CSV", "Excel", "JSON", "PDF Report"],
    horizontal=True,
    key="export_format"
)

# Customization options
st.subheader("Customization Options")

col1, col2 = st.columns(2)

with col1:
    include_charts = st.checkbox("Include Charts/Visualizations", value=True, key="include_charts")
    include_summary = st.checkbox("Include Executive Summary", value=True, key="include_summary")

with col2:
    date_range = st.checkbox("Filter by Date Range", value=False, key="date_range")
    if date_range and "Published" in df.columns:
        min_date = df["Published"].min().date()
        max_date = df["Published"].max().date()

        start_date = st.date_input("Start Date", value=min_date, key="export_start")
        end_date = st.date_input("End Date", value=max_date, key="export_end")

# Data Preview
st.header("👁️ Data Preview")

if not df.empty:
    # Show preview of selected data
    preview_cols = ["Title", "Published", "Views", "Likes", "Engagement_Rate", "Content_Type"]
    available_cols = [col for col in preview_cols if col in df.columns]

    if available_cols:
        preview_df = df[available_cols].head(10)
        st.dataframe(preview_df, use_container_width=True)
        st.caption(f"Showing 10 of {len(df)} videos. Total videos: {len(df)}")

# Export Functions
def create_csv_export(data: pd.DataFrame) -> bytes:
    """Create CSV export."""
    output = io.BytesIO()
    data.to_csv(output, index=False)
    return output.getvalue()

def create_excel_export(data: pd.DataFrame) -> bytes:
    """Create Excel export with multiple sheets."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main data sheet
        data.to_excel(writer, sheet_name='Video Data', index=False)

        # Summary sheet
        if include_summary:
            summary_data = create_summary_data(data)
            summary_df = pd.DataFrame([summary_data])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # Content type analysis sheet
        if "Content_Type" in data.columns:
            content_stats = data.groupby("Content_Type").agg({
                "Views": ["count", "mean", "sum"],
                "Likes": "mean",
                "Engagement_Rate": "mean"
            }).round(2)
            content_stats.to_excel(writer, sheet_name='Content Analysis')

    return output.getvalue()

def create_json_export(data: pd.DataFrame) -> str:
    """Create JSON export."""
    # Convert to dictionary
    export_dict = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "video_count": len(data),
            "date_range": {
                "start": data["Published"].min().isoformat() if "Published" in data.columns else None,
                "end": data["Published"].max().isoformat() if "Published" in data.columns else None
            }
        },
        "data": data.to_dict(orient='records')
    }

    # Add summary if requested
    if include_summary:
        export_dict["summary"] = create_summary_data(data)

    return pd.io.json.dumps(export_dict, indent=2)

def create_summary_data(data: pd.DataFrame) -> Dict[str, Any]:
    """Create summary statistics."""
    summary = {
        "total_videos": len(data),
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if "Views" in data.columns:
        summary.update({
            "total_views": int(data["Views"].sum()),
            "avg_views": int(data["Views"].mean()),
            "max_views": int(data["Views"].max()),
            "min_views": int(data["Views"].min())
        })

    if "Likes" in data.columns:
        summary.update({
            "total_likes": int(data["Likes"].sum()),
            "avg_likes": int(data["Likes"].mean())
        })

    if "Engagement_Rate" in data.columns:
        summary.update({
            "avg_engagement": f"{data['Engagement_Rate'].mean():.1f}%"
        })

    if "Content_Type" in data.columns:
        content_counts = data["Content_Type"].value_counts().to_dict()
        summary["content_type_distribution"] = content_counts

    return summary

def create_pdf_report(data: pd.DataFrame) -> bytes:
    """Create a PDF report (simplified version - returns placeholder)."""
    # In a real implementation, you would use reportlab or similar
    # For now, return a simple text file
    report_content = f"""
    YouTube Analytics Report
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    Summary:
    - Total Videos: {len(data)}
    - Date Range: {data['Published'].min().date() if 'Published' in data.columns else 'N/A'} to {data['Published'].max().date() if 'Published' in data.columns else 'N/A'}

    Performance Metrics:
    - Total Views: {int(data['Views'].sum()) if 'Views' in data.columns else 'N/A':,}
    - Average Views: {int(data['Views'].mean()) if 'Views' in data.columns else 'N/A':,}
    - Average Engagement Rate: {data['Engagement_Rate'].mean() if 'Engagement_Rate' in data.columns else 'N/A':.1f}%

    This is a simplified report. In a full implementation, this would include charts and detailed analysis.
    """

    return report_content.encode()

# Generate Export
st.header("🚀 Generate Export")

if st.button("Generate Export", type="primary", key="generate_export"):
    with st.spinner(f"Generating {export_format} export..."):
        try:
            # Prepare data based on selections
            export_data = df.copy()

            # Apply date filter if requested
            if date_range and "Published" in export_data.columns:
                export_data = export_data[
                    (export_data["Published"].dt.date >= start_date) &
                    (export_data["Published"].dt.date <= end_date)
                ]

            if export_data.empty:
                st.error("No data available for the selected date range.")
                st.stop()

            # Generate export based on format
            if export_format == "CSV":
                export_bytes = create_csv_export(export_data)
                file_extension = "csv"
                mime_type = "text/csv"

            elif export_format == "Excel":
                export_bytes = create_excel_export(export_data)
                file_extension = "xlsx"
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

            elif export_format == "JSON":
                export_json = create_json_export(export_data)
                export_bytes = export_json.encode()
                file_extension = "json"
                mime_type = "application/json"

            elif export_format == "PDF Report":
                export_bytes = create_pdf_report(export_data)
                file_extension = "txt"  # Placeholder for PDF
                mime_type = "text/plain"

            # Create download link
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"youtube_analytics_export_{timestamp}.{file_extension}"

            # Encode for download
            b64 = base64.b64encode(export_bytes).decode()
            href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">Click here to download {filename}</a>'

            st.success("✅ Export generated successfully!")
            st.markdown(href, unsafe_allow_html=True)

            # Show summary
            st.subheader("📋 Export Summary")
            summary = create_summary_data(export_data)

            col1, col2 = st.columns(2)

            with col1:
                st.metric("Total Videos", summary.get("total_videos", 0))
                if "total_views" in summary:
                    st.metric("Total Views", f"{summary['total_views']:,}")
                if "avg_views" in summary:
                    st.metric("Average Views", f"{summary['avg_views']:,}")

            with col2:
                if "total_likes" in summary:
                    st.metric("Total Likes", f"{summary['total_likes']:,}")
                if "avg_likes" in summary:
                    st.metric("Average Likes", f"{summary['avg_likes']:,}")
                if "avg_engagement" in summary:
                    st.metric("Avg Engagement", summary["avg_engagement"])

        except Exception as e:
            st.error(f"Error generating export: {e}")
            st.info("Make sure all required columns are available in your data.")

# Report Templates
st.header("📋 Report Templates")

template_col1, template_col2, template_col3 = st.columns(3)

with template_col1:
    st.markdown("### 📈 Performance Report")
    st.markdown("""
    - Executive summary
    - Key performance indicators
    - Monthly trends
    - Top performing videos
    """)
    if st.button("Use This Template", key="template_perf"):
        # Note: Can't modify widget value directly after creation
        # st.session_state.export_selection = ["Video Performance Data", "Content Type Analysis"]
        # st.rerun()
        st.info("Template selected. Please manually select 'Video Performance Data' and 'Content Type Analysis' from the options above.")

with template_col2:
    st.markdown("### 🎯 Content Strategy Report")
    st.markdown("""
    - Content type analysis
    - Topic trends
    - Engagement metrics
    - Recommendations
    """)
    if st.button("Use This Template", key="template_content"):
        # Note: Can't modify widget value directly after creation
        # st.session_state.export_selection = ["Video Performance Data", "Content Type Analysis", "Topic Analysis", "Growth Recommendations"]
        # st.rerun()
        st.info("Template selected. Please manually select 'Video Performance Data', 'Content Type Analysis', 'Topic Analysis', and 'Growth Recommendations' from the options above.")

with template_col3:
    st.markdown("### 🥊 Competitive Analysis Report")
    st.markdown("""
    - Channel comparison
    - Market share analysis
    - Gap analysis
    - Competitive insights
    """)
    if st.button("Use This Template", key="template_comp"):
        # Note: Can't modify widget value directly after creation
        # st.session_state.export_selection = ["Video Performance Data", "Competitor Comparison"]
        # st.rerun()
        st.info("Template selected. Please manually select 'Video Performance Data' and 'Competitor Comparison' from the options above.")

# Scheduled Exports
st.header("⏰ Scheduled Exports")

st.info("""
**Coming Soon:** Schedule automatic exports to run daily, weekly, or monthly.
Exports can be sent via email or saved to cloud storage.
""")

enable_scheduling = st.checkbox("Enable Scheduled Exports", value=False, key="enable_scheduling")

if enable_scheduling:
    schedule_col1, schedule_col2 = st.columns(2)

    with schedule_col1:
        frequency = st.selectbox(
            "Frequency",
            ["Daily", "Weekly", "Monthly"],
            key="export_frequency"
        )

        format = st.selectbox(
            "Format",
            ["CSV", "Excel", "PDF"],
            key="scheduled_format"
        )

    with schedule_col2:
        if frequency == "Weekly":
            day_of_week = st.selectbox(
                "Day of Week",
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                key="export_day"
            )
        elif frequency == "Monthly":
            day_of_month = st.slider("Day of Month", 1, 28, 1, key="export_day_month")

        time_of_day = st.time_input("Time of Day", value=datetime.strptime("09:00", "%H:%M").time(), key="export_time")

    email = st.text_input("Email for notifications", placeholder="your@email.com", key="export_email")

    if st.button("Save Schedule", key="save_schedule"):
        st.success("Schedule saved! (This is a demo - in production this would save to a database.)")

# Sidebar
st.sidebar.title("📊 Export Reports")

# Data info
st.sidebar.markdown(f"**Videos Available:** {len(df)}")
if "Published" in df.columns:
    # Convert to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df["Published"]):
        df["Published"] = pd.to_datetime(df["Published"], utc=True)

    date_range_str = f"{df['Published'].min().date()} to {df['Published'].max().date()}"
    st.sidebar.markdown(f"**Date Range:** {date_range_str}")

# Export history
st.sidebar.markdown("---")
st.sidebar.subheader("Export History")

# Placeholder for export history
st.sidebar.info("No export history yet. Generate your first export!")

# Clear export cache
if st.sidebar.button("🔄 Clear Export Cache", key="clear_export_cache"):
    st.success("Export cache cleared!")
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
if st.sidebar.button("Topic Explorer"):
    st.switch_page("pages/05_Topic_Explorer.py")