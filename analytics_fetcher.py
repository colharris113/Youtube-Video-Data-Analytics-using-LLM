"""
YouTube Analytics API Fetcher

Fetches advanced analytics data from YouTube Analytics API.
Requires OAuth 2.0 authentication via AuthManager.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging

# Local imports
from auth_manager import get_auth_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalyticsFetcher:
    """Fetches data from YouTube Analytics API."""

    # Common metrics and dimensions
    METRICS = {
        'views': 'views',
        'estimated_minutes_watched': 'estimatedMinutesWatched',
        'average_view_duration': 'averageViewDuration',
        'average_view_percentage': 'averageViewPercentage',
        'subscribers_gained': 'subscribersGained',
        'subscribers_lost': 'subscribersLost',
        'likes': 'likes',
        'dislikes': 'dislikes',
        'comments': 'comments',
        'shares': 'shares',
        'estimated_revenue': 'estimatedRevenue',
        'ad_impressions': 'adImpressions',
        'monetized_playbacks': 'monetizedPlaybacks'
    }

    DIMENSIONS = {
        'day': 'day',
        'month': 'month',
        'video': 'video',
        'playlist': 'playlist',
        'channel': 'channel',
        'traffic_source': 'trafficSource',
        'device_type': 'deviceType',
        'operating_system': 'operatingSystem',
        'country': 'country',
        'province': 'province',
        'age_group': 'ageGroup',
        'gender': 'gender',
        'subscription_status': 'subscriptionStatus',
        'playback_location': 'playbackLocationType',
        'insight_type': 'insightTrafficSourceType'
    }

    def __init__(self):
        """Initialize the analytics fetcher."""
        self.auth_manager = get_auth_manager()
        self.analytics_service = None

    def _get_service(self):
        """Get authenticated analytics service."""
        if not self.analytics_service:
            self.analytics_service = self.auth_manager.get_analytics_service()
        return self.analytics_service

    def _validate_date_range(self, start_date: str, end_date: str) -> Tuple[str, str]:
        """
        Validate and format date range for YouTube Analytics API.
        Converts relative dates (e.g., '30daysAgo', 'today') to YYYY-MM-DD format.

        Args:
            start_date: Start date in YYYY-MM-DD format or relative string
            end_date: End date in YYYY-MM-DD format or relative string

        Returns:
            Tuple of validated (start_date, end_date) in YYYY-MM-DD format
        """
        from datetime import datetime, timedelta

        # Helper function to parse relative dates
        def parse_relative_date(date_str: str) -> str:
            today = datetime.now().date()

            if date_str == 'today':
                return today.strftime('%Y-%m-%d')
            elif date_str == 'yesterday':
                return (today - timedelta(days=1)).strftime('%Y-%m-%d')
            elif date_str.endswith('daysAgo'):
                try:
                    days_ago = int(date_str.replace('daysAgo', ''))
                    return (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                except ValueError:
                    # Default to 30 days ago if parsing fails
                    return (today - timedelta(days=30)).strftime('%Y-%m-%d')
            else:
                # Assume it's already in YYYY-MM-DD format
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    return date_str
                except ValueError:
                    # Default to 30 days ago if invalid
                    return (today - timedelta(days=30)).strftime('%Y-%m-%d')

        # Parse both dates
        parsed_start = parse_relative_date(start_date)
        parsed_end = parse_relative_date(end_date)

        # Ensure start date is before end date
        start_dt = datetime.strptime(parsed_start, '%Y-%m-%d')
        end_dt = datetime.strptime(parsed_end, '%Y-%m-%d')

        if start_dt > end_dt:
            # Swap if start is after end
            return parsed_end, parsed_start

        return parsed_start, parsed_end

    def fetch_report(self, metrics: List[str], dimensions: List[str],
                     start_date: str = '30daysAgo', end_date: str = 'today',
                     filters: Optional[str] = None, sort: Optional[str] = None,
                     max_results: int = 100) -> pd.DataFrame:
        """
        Fetch a report from YouTube Analytics API.

        Args:
            metrics: List of metric names (see METRICS dict)
            dimensions: List of dimension names (see DIMENSIONS dict)
            start_date: Start date (YYYY-MM-DD or relative like '7daysAgo')
            end_date: End date (YYYY-MM-DD or relative like 'today')
            filters: Optional filter string
            sort: Optional sort string
            max_results: Maximum number of results

        Returns:
            DataFrame with report data
        """
        service = self._get_service()
        if not service:
            logger.error("Analytics service not available. Authentication required.")
            return pd.DataFrame()

        # Validate date range
        start_date, end_date = self._validate_date_range(start_date, end_date)

        # Convert metric/dimension names to API format
        api_metrics = [self.METRICS.get(m, m) for m in metrics]
        api_dimensions = [self.DIMENSIONS.get(d, d) for d in dimensions]

        logger.info(f"Fetching report: metrics={api_metrics}, dimensions={api_dimensions}, "
                   f"date_range={start_date} to {end_date}")

        try:
            # Build the request
            request = service.reports().query(
                ids='channel==MINE',
                startDate=start_date,
                endDate=end_date,
                metrics=','.join(api_metrics),
                dimensions=','.join(api_dimensions) if api_dimensions else None,
                filters=filters,
                sort=sort,
                maxResults=max_results
            )

            # Execute the request
            response = request.execute()

            # Parse the response
            df = self._parse_response(response, metrics, dimensions)
            logger.info(f"Fetched {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch report: {e}")
            return pd.DataFrame()

    def _parse_response(self, response: Dict, metrics: List[str], dimensions: List[str]) -> pd.DataFrame:
        """
        Parse API response into DataFrame.

        Args:
            response: API response dictionary
            metrics: Original metric names
            dimensions: Original dimension names

        Returns:
            DataFrame with parsed data
        """
        if 'rows' not in response:
            return pd.DataFrame()

        rows = response['rows']
        if not rows:
            return pd.DataFrame()

        # Create column names
        columns = dimensions + metrics

        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=columns)

        # Convert numeric columns
        for metric in metrics:
            if metric in df.columns:
                df[metric] = pd.to_numeric(df[metric], errors='coerce')

        return df

    def get_traffic_sources(self, start_date: str = '30daysAgo', end_date: str = 'today') -> pd.DataFrame:
        """
        Get traffic source analysis.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with traffic source data
        """
        metrics = ['views', 'estimated_minutes_watched', 'average_view_duration']
        dimensions = ['traffic_source']

        df = self.fetch_report(metrics, dimensions, start_date, end_date)

        if not df.empty:
            # Calculate percentages
            total_views = df['views'].sum()
            if total_views > 0:
                df['views_percentage'] = (df['views'] / total_views * 100).round(2)

            # Sort by views
            df = df.sort_values('views', ascending=False)

        return df

    def get_demographics(self, start_date: str = '30daysAgo', end_date: str = 'today') -> Dict[str, pd.DataFrame]:
        """
        Get demographic insights.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with age, gender, and geography DataFrames
        """
        result = {}

        # Age group demographics
        age_metrics = ['views', 'estimated_minutes_watched']
        age_dimensions = ['age_group']
        age_df = self.fetch_report(age_metrics, age_dimensions, start_date, end_date)
        if not age_df.empty:
            age_df = age_df.sort_values('views', ascending=False)
            result['age_groups'] = age_df

        # Gender demographics
        gender_metrics = ['views', 'estimated_minutes_watched']
        gender_dimensions = ['gender']
        gender_df = self.fetch_report(gender_metrics, gender_dimensions, start_date, end_date)
        if not gender_df.empty:
            result['genders'] = gender_df

        # Geography demographics
        geo_metrics = ['views', 'estimated_minutes_watched']
        geo_dimensions = ['country']
        geo_df = self.fetch_report(geo_metrics, geo_dimensions, start_date, end_date)
        if not geo_df.empty:
            geo_df = geo_df.sort_values('views', ascending=False)
            result['countries'] = geo_df

        return result

    def get_device_usage(self, start_date: str = '30daysAgo', end_date: str = 'today') -> pd.DataFrame:
        """
        Get device usage patterns.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with device usage data
        """
        metrics = ['views', 'estimated_minutes_watched', 'average_view_duration']
        dimensions = ['device_type']

        df = self.fetch_report(metrics, dimensions, start_date, end_date)

        if not df.empty:
            # Calculate percentages
            total_views = df['views'].sum()
            if total_views > 0:
                df['views_percentage'] = (df['views'] / total_views * 100).round(2)

            # Sort by views
            df = df.sort_values('views', ascending=False)

        return df

    def get_subscriber_analytics(self, start_date: str = '30daysAgo', end_date: str = 'today') -> pd.DataFrame:
        """
        Get subscriber analytics.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with subscriber data
        """
        metrics = ['subscribers_gained', 'subscribers_lost']
        dimensions = ['day']

        df = self.fetch_report(metrics, dimensions, start_date, end_date)

        if not df.empty:
            # Convert day to datetime
            df['day'] = pd.to_datetime(df['day'])

            # Calculate net subscribers
            df['subscribers_net'] = df['subscribers_gained'] - df['subscribers_lost']

            # Calculate cumulative net subscribers
            df['subscribers_cumulative'] = df['subscribers_net'].cumsum()

            # Sort by date
            df = df.sort_values('day')

        return df

    def get_video_performance(self, video_ids: Optional[List[str]] = None,
                              start_date: str = '30daysAgo', end_date: str = 'today') -> pd.DataFrame:
        """
        Get performance metrics for specific videos or all videos.

        Args:
            video_ids: List of video IDs (None for all videos)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with video performance data
        """
        metrics = ['views', 'estimated_minutes_watched', 'average_view_duration',
                   'average_view_percentage', 'likes', 'dislikes', 'comments', 'shares']
        dimensions = ['video']

        # Build filter if video_ids provided
        filters = None
        if video_ids:
            filters = f'video=={",".join(video_ids)}'

        df = self.fetch_report(metrics, dimensions, start_date, end_date, filters=filters)

        if not df.empty:
            # Calculate engagement rate
            df['engagement_rate'] = ((df['likes'] + df['comments'] + df['shares']) / df['views'] * 100).round(2)

            # Sort by views
            df = df.sort_values('views', ascending=False)

        return df

    def get_audience_retention(self, video_id: str) -> pd.DataFrame:
        """
        Get audience retention data for a specific video.

        Args:
            video_id: YouTube video ID

        Returns:
            DataFrame with audience retention data
        """
        service = self._get_service()
        if not service:
            logger.error("Analytics service not available. Authentication required.")
            return pd.DataFrame()

        try:
            # Note: Audience retention requires different endpoint
            # This is a simplified implementation
            request = service.videos().list(
                part='contentDetails,statistics',
                id=video_id
            )
            response = request.execute()

            if 'items' in response and response['items']:
                video_data = response['items'][0]
                # Extract relevant metrics
                data = {
                    'video_id': video_id,
                    'duration': video_data.get('contentDetails', {}).get('duration', 'PT0S'),
                    'views': int(video_data.get('statistics', {}).get('viewCount', 0)),
                    'likes': int(video_data.get('statistics', {}).get('likeCount', 0)),
                    'comments': int(video_data.get('statistics', {}).get('commentCount', 0))
                }
                return pd.DataFrame([data])

        except Exception as e:
            logger.error(f"Failed to get audience retention for video {video_id}: {e}")

        return pd.DataFrame()

    def get_daily_trends(self, start_date: str = '30daysAgo', end_date: str = 'today') -> pd.DataFrame:
        """
        Get daily performance trends.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with daily trends
        """
        metrics = ['views', 'estimated_minutes_watched', 'subscribers_gained', 'subscribers_lost']
        dimensions = ['day']

        df = self.fetch_report(metrics, dimensions, start_date, end_date)

        if not df.empty:
            # Convert day to datetime
            df['day'] = pd.to_datetime(df['day'])

            # Calculate net subscribers
            df['subscribers_net'] = df['subscribers_gained'] - df['subscribers_lost']

            # Calculate 7-day moving averages
            df['views_7d_avg'] = df['views'].rolling(window=7, min_periods=1).mean().round(1)
            df['watch_time_7d_avg'] = df['estimated_minutes_watched'].rolling(window=7, min_periods=1).mean().round(1)

            # Sort by date
            df = df.sort_values('day')

        return df


# Helper functions
def get_analytics_fetcher() -> AnalyticsFetcher:
    """Get the AnalyticsFetcher instance."""
    return AnalyticsFetcher()


if __name__ == "__main__":
    # Test the analytics fetcher
    print("Testing AnalyticsFetcher...")

    # Check authentication
    auth_manager = get_auth_manager()
    if not auth_manager.is_authenticated():
        print("Not authenticated. Please run auth_manager.py first to authenticate.")
        exit(1)

    # Create fetcher
    fetcher = AnalyticsFetcher()

    # Test traffic sources
    print("\n1. Testing traffic sources...")
    traffic_df = fetcher.get_traffic_sources('7daysAgo', 'today')
    if not traffic_df.empty:
        print(f"Traffic sources ({len(traffic_df)} sources):")
        print(traffic_df.head())
    else:
        print("No traffic source data available")

    # Test demographics
    print("\n2. Testing demographics...")
    demographics = fetcher.get_demographics('7daysAgo', 'today')
    for demo_type, df in demographics.items():
        if not df.empty:
            print(f"{demo_type} ({len(df)} rows):")
            print(df.head())

    # Test device usage
    print("\n3. Testing device usage...")
    device_df = fetcher.get_device_usage('7daysAgo', 'today')
    if not device_df.empty:
        print(f"Device usage ({len(device_df)} devices):")
        print(device_df.head())

    # Test daily trends
    print("\n4. Testing daily trends...")
    trends_df = fetcher.get_daily_trends('30daysAgo', 'today')
    if not trends_df.empty:
        print(f"Daily trends ({len(trends_df)} days):")
        print(trends_df[['day', 'views', 'estimated_minutes_watched', 'subscribers_net']].head())

    print("\nAnalyticsFetcher test completed!")