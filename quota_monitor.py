"""
Quota Monitor for YouTube Video Data Analytics

Streamlit components for displaying API quota usage and cache statistics.
Provides real-time monitoring of API usage with alerts and recommendations.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from typing import Dict, Any, Optional

# Optional Streamlit import
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    # Create a mock st object for testing
    class MockStreamlit:
        def markdown(self, *args, **kwargs): pass
        def sidebar(self): return self
        def warning(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
        def success(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def button(self, *args, **kwargs): return False
        def spinner(self, *args, **kwargs):
            class SpinnerContext:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return SpinnerContext()
        def selectbox(self, *args, **kwargs): return None
        def slider(self, *args, **kwargs): return 0
        def columns(self, *args, **kwargs): return [self] * args[0]
        def metric(self, *args, **kwargs): pass
        def progress(self, *args, **kwargs): pass
        def dataframe(self, *args, **kwargs): pass
        def plotly_chart(self, *args, **kwargs): pass
        def rerun(self, *args, **kwargs): pass
        def session_state(self): return type('obj', (object,), {'__dict__': {}})()
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    st = MockStreamlit()

from cache_manager import get_cache_manager
from data_manager import get_data_manager


class QuotaMonitor:
    """Streamlit components for API quota monitoring."""

    def __init__(self):
        """Initialize quota monitor."""
        self.cache_manager = get_cache_manager()
        self.data_manager = get_data_manager()

    def display_quota_dashboard(self):
        """Display comprehensive quota dashboard."""
        st.markdown("### 📊 API Quota Dashboard")

        # Get cache stats
        cache_stats = self.cache_manager.get_cache_stats()

        # Display in columns
        col1, col2, col3 = st.columns(3)

        with col1:
            self._display_quota_usage_card(cache_stats)

        with col2:
            self._display_cache_effectiveness_card(cache_stats)

        with col3:
            self._display_cost_savings_card(cache_stats)

        # API Limits Progress Bars
        st.markdown("#### API Usage vs. Daily Limits")
        self._display_api_limits_progress(cache_stats)

        # Endpoint Breakdown
        st.markdown("#### Endpoint Usage Breakdown")
        self._display_endpoint_breakdown(cache_stats)

        # Recommendations
        st.markdown("#### 💡 Recommendations")
        self._display_recommendations(cache_stats)

    def _display_quota_usage_card(self, cache_stats: Dict[str, Any]):
        """Display quota usage card."""
        quota_usage = cache_stats.get('quota_usage', {})
        api_limits = cache_stats.get('api_limits', {})

        data_api = api_limits.get('data_api', {})
        analytics_api = api_limits.get('analytics_api', {})

        st.metric(
            label="YouTube Data API v3",
            value=f"{data_api.get('used', 0):,} / {data_api.get('limit', 10000):,}",
            delta=f"{data_api.get('remaining', 10000):,} remaining",
            delta_color="normal" if data_api.get('percentage', 0) < 80 else "inverse"
        )

        st.metric(
            label="YouTube Analytics API",
            value=f"{analytics_api.get('used', 0):,} / {analytics_api.get('limit', 100000):,}",
            delta=f"{analytics_api.get('remaining', 100000):,} remaining",
            delta_color="normal" if analytics_api.get('percentage', 0) < 80 else "inverse"
        )

    def _display_cache_effectiveness_card(self, cache_stats: Dict[str, Any]):
        """Display cache effectiveness card."""
        quota_usage = cache_stats.get('quota_usage', {})
        hit_rate = cache_stats.get('estimated_hit_rate', 0)
        saved_percentage = cache_stats.get('quota_saved_percentage', 0)

        total_calls = quota_usage.get('total_calls', 0)
        cached_calls = quota_usage.get('cached_calls', 0)

        st.metric(
            label="Cache Hit Rate",
            value=f"{hit_rate:.1f}%",
            delta=f"{cached_calls:,} cached calls"
        )

        st.metric(
            label="Quota Saved",
            value=f"{saved_percentage:.1f}%",
            delta=f"{total_calls:,} API calls"
        )

    def _display_cost_savings_card(self, cache_stats: Dict[str, Any]):
        """Display cost savings card."""
        cost_savings = cache_stats.get('cost_savings', {})

        calls_saved = cost_savings.get('calls_saved', 0)
        quota_saved = cost_savings.get('quota_units_saved', 0)
        cost_saved = cost_savings.get('estimated_cost_savings_usd', 0.0)

        st.metric(
            label="Calls Saved",
            value=f"{calls_saved:,}",
            delta="via caching"
        )

        st.metric(
            label="Estimated Cost Savings",
            value=f"${cost_saved:.4f}",
            delta=f"{quota_saved:,} quota units"
        )

    def _display_api_limits_progress(self, cache_stats: Dict[str, Any]):
        """Display API limits as progress bars."""
        api_limits = cache_stats.get('api_limits', {})

        data_api = api_limits.get('data_api', {})
        analytics_api = api_limits.get('analytics_api', {})

        # Create progress bars with color coding
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**YouTube Data API v3**")
            data_percentage = data_api.get('percentage', 0)
            data_color = self._get_progress_color(data_percentage)
            st.progress(
                data_percentage / 100,
                text=f"{data_api.get('used', 0):,} / {data_api.get('limit', 10000):,} units ({data_percentage:.1f}%)"
            )

            # Show warning if near limit
            if data_percentage > 80:
                st.warning(f"⚠️ Data API usage at {data_percentage:.1f}% of daily limit")

        with col2:
            st.markdown("**YouTube Analytics API**")
            analytics_percentage = analytics_api.get('percentage', 0)
            analytics_color = self._get_progress_color(analytics_percentage)
            st.progress(
                analytics_percentage / 100,
                text=f"{analytics_api.get('used', 0):,} / {analytics_api.get('limit', 100000):,} units ({analytics_percentage:.1f}%)"
            )

            # Show warning if near limit
            if analytics_percentage > 80:
                st.warning(f"⚠️ Analytics API usage at {analytics_percentage:.1f}% of daily limit")

    def _get_progress_color(self, percentage: float) -> str:
        """Get color for progress bar based on percentage."""
        if percentage < 50:
            return "green"
        elif percentage < 80:
            return "orange"
        else:
            return "red"

    def _display_endpoint_breakdown(self, cache_stats: Dict[str, Any]):
        """Display endpoint usage breakdown."""
        endpoint_breakdown = cache_stats.get('endpoint_breakdown', [])

        if not endpoint_breakdown:
            st.info("No endpoint usage data yet. Make some API calls to see breakdown.")
            return

        # Convert to DataFrame
        df = pd.DataFrame(endpoint_breakdown)

        if df.empty:
            return

        # Display as table
        st.dataframe(
            df[['endpoint', 'api_type', 'call_count', 'quota_units', 'avg_response_time_ms']],
            use_container_width=True
        )

        # Create visualization
        fig = self._create_endpoint_chart(df)
        st.plotly_chart(fig, use_container_width=True)

    def _create_endpoint_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create endpoint usage chart."""
        # Group by endpoint and sum quota units
        endpoint_totals = df.groupby('endpoint')['quota_units'].sum().reset_index()
        endpoint_totals = endpoint_totals.sort_values('quota_units', ascending=False).head(10)

        # Create bar chart
        fig = px.bar(
            endpoint_totals,
            x='endpoint',
            y='quota_units',
            title='Top 10 Endpoints by Quota Usage',
            labels={'endpoint': 'API Endpoint', 'quota_units': 'Quota Units Used'},
            color='quota_units',
            color_continuous_scale='Viridis'
        )

        fig.update_layout(
            xaxis_tickangle=-45,
            showlegend=False,
            height=400
        )

        return fig

    def _display_recommendations(self, cache_stats: Dict[str, Any]):
        """Display recommendations based on usage patterns."""
        recommendations = []

        api_limits = cache_stats.get('api_limits', {})
        data_api = api_limits.get('data_api', {})
        analytics_api = api_limits.get('analytics_api', {})

        endpoint_breakdown = cache_stats.get('endpoint_breakdown', [])
        hit_rate = cache_stats.get('estimated_hit_rate', 0)

        # Check Data API usage
        data_percentage = data_api.get('percentage', 0)
        if data_percentage > 90:
            recommendations.append("🚨 **CRITICAL**: Data API usage over 90%. Consider reducing API calls or increasing cache TTL.")
        elif data_percentage > 75:
            recommendations.append("⚠️ **WARNING**: Data API usage over 75%. Review endpoint usage below.")
        elif data_percentage > 50:
            recommendations.append("ℹ️ **INFO**: Data API usage over 50%. Monitor usage throughout the day.")

        # Check Analytics API usage
        analytics_percentage = analytics_api.get('percentage', 0)
        if analytics_percentage > 90:
            recommendations.append("🚨 **CRITICAL**: Analytics API usage over 90%.")
        elif analytics_percentage > 75:
            recommendations.append("⚠️ **WARNING**: Analytics API usage over 75%.")

        # Check cache effectiveness
        if hit_rate < 30:
            recommendations.append("💡 **OPTIMIZATION**: Cache hit rate below 30%. Consider increasing cache TTL for frequently accessed data.")
        elif hit_rate > 70:
            recommendations.append("✅ **GOOD**: Cache hit rate above 70%. Caching is working effectively.")

        # Check for expensive endpoints
        expensive_endpoints = [ep for ep in endpoint_breakdown if ep.get('quota_units', 0) > 100]
        if expensive_endpoints:
            expensive_list = ", ".join([ep['endpoint'] for ep in expensive_endpoints[:3]])
            recommendations.append(f"💰 **COSTLY**: High quota usage from: {expensive_list}. Consider optimizing these calls.")

        # General recommendations
        if not recommendations:
            recommendations.extend([
                "✅ **GOOD**: API usage within safe limits.",
                "💡 **TIP**: Use the cached YouTube API functions to automatically reduce quota usage.",
                "💡 **TIP**: Consider increasing cache TTL for data that doesn't change frequently."
            ])

        # Display recommendations
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")

    def display_sidebar_quota_widget(self):
        """Display quota widget in sidebar."""
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📈 API Quota Status")

        # Get cache stats
        try:
            cache_stats = self.cache_manager.get_cache_stats()
            # Debug: print stats to console
            print(f"Quota Monitor - Cache stats: {cache_stats}")
        except Exception as e:
            st.sidebar.error(f"Error getting quota stats: {e}")
            import traceback
            traceback.print_exc()
            return

        api_limits = cache_stats.get('api_limits', {})

        data_api = api_limits.get('data_api', {})
        analytics_api = api_limits.get('analytics_api', {})

        # Data API status
        data_percentage = data_api.get('percentage', 0)
        data_color = self._get_status_color(data_percentage)
        st.sidebar.markdown(f"**Data API**: :{data_color}[{data_api.get('used', 0):,}/{data_api.get('limit', 10000):,}]")

        # Analytics API status
        analytics_percentage = analytics_api.get('percentage', 0)
        analytics_color = self._get_status_color(analytics_percentage)
        st.sidebar.markdown(f"**Analytics API**: :{analytics_color}[{analytics_api.get('used', 0):,}/{analytics_api.get('limit', 100000):,}]")

        # Cache effectiveness
        hit_rate = cache_stats.get('estimated_hit_rate', 0)
        hit_color = "green" if hit_rate > 50 else "orange" if hit_rate > 30 else "red"
        st.sidebar.markdown(f"**Cache Hit Rate**: :{hit_color}[{hit_rate:.1f}%]")

        # Refresh button - uses a different approach to avoid st.rerun()
        if st.sidebar.button("🔄 Refresh Quota Stats", key="refresh_quota"):
            # Just let the button click cause the normal script rerun
            # The stats will be refreshed automatically when the script runs again
            pass

        # Link to full dashboard
        if st.sidebar.button("📊 View Full Dashboard", key="view_dashboard"):
            # Set a flag to show the dashboard
            st.session_state.show_quota_dashboard = True
            # No st.rerun() needed - the script will run again due to button click

    def _get_status_color(self, percentage: float) -> str:
        """Get color for status indicator."""
        if percentage < 50:
            return "green"
        elif percentage < 80:
            return "orange"
        else:
            return "red"

    def display_quota_alerts(self):
        """Display quota alerts if near limits."""
        cache_stats = self.cache_manager.get_cache_stats()
        api_limits = cache_stats.get('api_limits', {})

        data_api = api_limits.get('data_api', {})
        analytics_api = api_limits.get('analytics_api', {})

        alerts = []

        # Check Data API
        data_percentage = data_api.get('percentage', 0)
        if data_percentage > 90:
            alerts.append(("🚨 CRITICAL", f"Data API usage at {data_percentage:.1f}%", "red"))
        elif data_percentage > 75:
            alerts.append(("⚠️ WARNING", f"Data API usage at {data_percentage:.1f}%", "orange"))

        # Check Analytics API
        analytics_percentage = analytics_api.get('percentage', 0)
        if analytics_percentage > 90:
            alerts.append(("🚨 CRITICAL", f"Analytics API usage at {analytics_percentage:.1f}%", "red"))
        elif analytics_percentage > 75:
            alerts.append(("⚠️ WARNING", f"Analytics API usage at {analytics_percentage:.1f}%", "orange"))

        # Display alerts
        if alerts:
            st.markdown("### 🔔 Quota Alerts")
            for icon, message, color in alerts:
                st.markdown(f":{color}[{icon} {message}]")

    def get_quota_summary_text(self) -> str:
        """Get quota summary as text for logging or reporting."""
        cache_stats = self.cache_manager.get_cache_stats()
        api_limits = cache_stats.get('api_limits', {})

        data_api = api_limits.get('data_api', {})
        analytics_api = api_limits.get('analytics_api', {})

        summary = f"""
        Quota Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        ===========================================
        YouTube Data API v3: {data_api.get('used', 0):,}/{data_api.get('limit', 10000):,} ({data_api.get('percentage', 0):.1f}%)
        YouTube Analytics API: {analytics_api.get('used', 0):,}/{analytics_api.get('limit', 100000):,} ({analytics_api.get('percentage', 0):.1f}%)
        Cache Hit Rate: {cache_stats.get('estimated_hit_rate', 0):.1f}%
        Quota Saved: {cache_stats.get('quota_saved_percentage', 0):.1f}%
        Estimated Cost Savings: ${cache_stats.get('cost_savings', {}).get('estimated_cost_savings_usd', 0):.4f}
        ===========================================
        """
        return summary


# Global quota monitor instance
_quota_monitor = None


def get_quota_monitor() -> QuotaMonitor:
    """Get the global quota monitor instance."""
    global _quota_monitor
    if _quota_monitor is None:
        _quota_monitor = QuotaMonitor()
    return _quota_monitor


def display_quota_dashboard():
    """Display quota dashboard (convenience function)."""
    monitor = get_quota_monitor()
    monitor.display_quota_dashboard()


def display_sidebar_quota_widget():
    """Display sidebar quota widget (convenience function)."""
    monitor = get_quota_monitor()
    monitor.display_sidebar_quota_widget()


def display_quota_alerts():
    """Display quota alerts (convenience function)."""
    monitor = get_quota_monitor()
    monitor.display_quota_alerts()


if __name__ == "__main__":
    # Test the quota monitor
    print("Testing QuotaMonitor...")

    # Create quota monitor
    monitor = QuotaMonitor()

    # Get summary text
    summary = monitor.get_quota_summary_text()
    print(summary)

    print("\nQuotaMonitor test completed!")
    print("\nNote: Run with Streamlit to see visual components.")