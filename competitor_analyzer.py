"""
Competitor Analyzer for YouTube Video Data Analytics

Analyzes and compares performance against rival channels to provide:
1. Multi-channel performance comparison
2. Normalized metrics (per subscriber, per video)
3. Competitive gap analysis
4. Growth rate comparisons
5. Content strategy differences
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import logging
from datetime import datetime, timedelta

# Local imports
try:
    from config import RIVAL_CHANNELS
except ImportError:
    RIVAL_CHANNELS = []

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CompetitorAnalyzer:
    """Analyzes and compares performance against competitor channels."""

    def __init__(self, api_key: str):
        """
        Initialize the competitor analyzer.

        Args:
            api_key: YouTube Data API v3 key
        """
        self.api_key = api_key
        self.competitor_data = {}  # Cache for competitor channel data

    def fetch_channel_data(self, channel_name: str, max_results: int = 50) -> Optional[Dict[str, Any]]:
        """
        Fetch basic channel data and video statistics.

        Args:
            channel_name: YouTube channel name
            max_results: Maximum number of videos to fetch

        Returns:
            Dictionary with channel data or None if fetch fails
        """
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError

            youtube = build('youtube', 'v3', developerKey=self.api_key, cache_discovery=False)

            # First, search for the channel
            search_response = youtube.search().list(
                q=channel_name,
                type='channel',
                part='id,snippet',
                maxResults=1
            ).execute()

            if not search_response.get('items'):
                logger.warning(f"Channel not found: {channel_name}")
                return None

            channel_id = search_response['items'][0]['id']['channelId']
            channel_title = search_response['items'][0]['snippet']['title']

            # Get channel statistics
            channel_response = youtube.channels().list(
                id=channel_id,
                part='statistics,snippet,contentDetails'
            ).execute()

            if not channel_response.get('items'):
                logger.warning(f"Channel statistics not found: {channel_name}")
                return None

            channel_info = channel_response['items'][0]
            stats = channel_info.get('statistics', {})

            # Get channel videos
            playlist_id = channel_info['contentDetails']['relatedPlaylists']['uploads']

            videos = []
            next_page_token = None

            while len(videos) < max_results:
                playlist_response = youtube.playlistItems().list(
                    playlistId=playlist_id,
                    part='contentDetails,snippet',
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token
                ).execute()

                video_ids = [item['contentDetails']['videoId'] for item in playlist_response.get('items', [])]

                if video_ids:
                    videos_response = youtube.videos().list(
                        id=','.join(video_ids),
                        part='statistics,contentDetails,snippet'
                    ).execute()

                    videos.extend(videos_response.get('items', []))

                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break

            # Calculate aggregated metrics
            total_views = 0
            total_likes = 0
            total_comments = 0
            video_count = len(videos)

            for video in videos:
                video_stats = video.get('statistics', {})
                total_views += int(video_stats.get('viewCount', 0))
                total_likes += int(video_stats.get('likeCount', 0))
                total_comments += int(video_stats.get('commentCount', 0))

            # Calculate averages
            avg_views = total_views / video_count if video_count > 0 else 0
            avg_likes = total_likes / video_count if video_count > 0 else 0
            avg_comments = total_comments / video_count if video_count > 0 else 0

            # Calculate engagement rate (likes + comments per 1000 views)
            engagement_rate = ((total_likes + total_comments) / total_views * 1000) if total_views > 0 else 0

            channel_data = {
                'channel_id': channel_id,
                'channel_name': channel_title,
                'subscriber_count': int(stats.get('subscriberCount', 0)),
                'video_count': int(stats.get('videoCount', 0)),
                'view_count': int(stats.get('viewCount', 0)),
                'total_views_recent': total_views,
                'total_likes_recent': total_likes,
                'total_comments_recent': total_comments,
                'avg_views_per_video': avg_views,
                'avg_likes_per_video': avg_likes,
                'avg_comments_per_video': avg_comments,
                'engagement_rate': engagement_rate,
                'recent_video_count': video_count,
                'fetched_at': datetime.now().isoformat()
            }

            logger.info(f"Fetched data for channel: {channel_title}")
            return channel_data

        except Exception as e:
            logger.error(f"Error fetching channel data for {channel_name}: {e}")
            return None

    def fetch_all_competitors(self, rival_channels: List[str] = None, max_results: int = 50) -> Dict[str, Dict[str, Any]]:
        """
        Fetch data for all competitor channels.

        Args:
            rival_channels: List of channel names (uses RIVAL_CHANNELS from config if None)
            max_results: Maximum videos to fetch per channel

        Returns:
            Dictionary mapping channel names to their data
        """
        if rival_channels is None:
            rival_channels = RIVAL_CHANNELS

        competitor_data = {}

        for channel_name in rival_channels:
            logger.info(f"Fetching data for competitor: {channel_name}")
            channel_data = self.fetch_channel_data(channel_name, max_results)

            if channel_data:
                competitor_data[channel_name] = channel_data
            else:
                logger.warning(f"Failed to fetch data for competitor: {channel_name}")

        self.competitor_data = competitor_data
        return competitor_data

    def compare_channels(self, main_channel_data: Dict[str, Any],
                        competitor_data: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
        """
        Compare main channel against competitors.

        Args:
            main_channel_data: Data for the main channel
            competitor_data: Dictionary of competitor channel data

        Returns:
            DataFrame with comparison metrics
        """
        if not competitor_data:
            return pd.DataFrame()

        comparison_rows = []

        # Add main channel first
        main_row = self._create_comparison_row(main_channel_data, is_main=True)
        comparison_rows.append(main_row)

        # Add competitors
        for channel_name, channel_data in competitor_data.items():
            comp_row = self._create_comparison_row(channel_data, is_main=False)
            comparison_rows.append(comp_row)

        # Create DataFrame
        df = pd.DataFrame(comparison_rows)

        # Calculate relative performance (main channel as baseline = 100%)
        if not df.empty and 'subscriber_count' in df.columns:
            main_subscribers = df[df['is_main_channel']]['subscriber_count'].iloc[0]

            if main_subscribers > 0:
                df['subscribers_relative'] = (df['subscriber_count'] / main_subscribers * 100).round(1)
                df['views_per_subscriber'] = (df['view_count'] / df['subscriber_count']).round(1)
                df['views_per_video'] = (df['view_count'] / df['video_count']).round(1)

        return df

    def _create_comparison_row(self, channel_data: Dict[str, Any], is_main: bool = False) -> Dict[str, Any]:
        """
        Create a standardized comparison row from channel data.

        Args:
            channel_data: Channel data dictionary
            is_main: Whether this is the main channel

        Returns:
            Standardized comparison row
        """
        return {
            'channel_name': channel_data.get('channel_name', 'Unknown'),
            'is_main_channel': is_main,
            'subscriber_count': channel_data.get('subscriber_count', 0),
            'video_count': channel_data.get('video_count', 0),
            'view_count': channel_data.get('view_count', 0),
            'recent_video_count': channel_data.get('recent_video_count', 0),
            'total_views_recent': channel_data.get('total_views_recent', 0),
            'avg_views_per_video': channel_data.get('avg_views_per_video', 0),
            'avg_likes_per_video': channel_data.get('avg_likes_per_video', 0),
            'avg_comments_per_video': channel_data.get('avg_comments_per_video', 0),
            'engagement_rate': channel_data.get('engagement_rate', 0),
            'fetched_at': channel_data.get('fetched_at', '')
        }

    def calculate_gap_analysis(self, main_channel_data: Dict[str, Any],
                             competitor_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Perform gap analysis between main channel and competitors.

        Args:
            main_channel_data: Main channel data
            competitor_data: Competitor channel data

        Returns:
            Dictionary with gap analysis results
        """
        if not competitor_data:
            return {}

        gap_analysis = {
            'strengths': [],
            'weaknesses': [],
            'opportunities': [],
            'competitive_advantages': [],
            'areas_for_improvement': []
        }

        # Calculate averages across competitors
        competitor_metrics = {
            'avg_subscribers': np.mean([c.get('subscriber_count', 0) for c in competitor_data.values()]),
            'avg_views_per_video': np.mean([c.get('avg_views_per_video', 0) for c in competitor_data.values()]),
            'avg_engagement_rate': np.mean([c.get('engagement_rate', 0) for c in competitor_data.values()]),
            'max_subscribers': max([c.get('subscriber_count', 0) for c in competitor_data.values()]),
            'max_engagement': max([c.get('engagement_rate', 0) for c in competitor_data.values()])
        }

        main_subscribers = main_channel_data.get('subscriber_count', 0)
        main_avg_views = main_channel_data.get('avg_views_per_video', 0)
        main_engagement = main_channel_data.get('engagement_rate', 0)

        # Analyze subscriber gap
        if main_subscribers > competitor_metrics['avg_subscribers']:
            gap_analysis['strengths'].append(
                f"Subscriber count ({main_subscribers:,}) is above competitor average "
                f"({competitor_metrics['avg_subscribers']:,.0f})"
            )
        else:
            gap_analysis['areas_for_improvement'].append(
                f"Subscriber growth: {main_subscribers:,} vs competitor average "
                f"{competitor_metrics['avg_subscribers']:,.0f}"
            )

        # Analyze engagement gap
        if main_engagement > competitor_metrics['avg_engagement_rate']:
            gap_analysis['competitive_advantages'].append(
                f"Higher engagement rate ({main_engagement:.1f}) than competitor average "
                f"({competitor_metrics['avg_engagement_rate']:.1f})"
            )
        else:
            gap_analysis['weaknesses'].append(
                f"Engagement rate ({main_engagement:.1f}) below competitor average "
                f"({competitor_metrics['avg_engagement_rate']:.1f})"
            )

        # Analyze views per video
        if main_avg_views > competitor_metrics['avg_views_per_video']:
            gap_analysis['strengths'].append(
                f"Higher average views per video ({main_avg_views:,.0f}) than competitor average "
                f"({competitor_metrics['avg_views_per_video']:,.0f})"
            )
        else:
            gap_analysis['opportunities'].append(
                f"Potential to increase average views per video (currently {main_avg_views:,.0f} vs "
                f"competitor average {competitor_metrics['avg_views_per_video']:,.0f})"
            )

        # Find top competitor
        top_competitor = max(competitor_data.items(),
                           key=lambda x: x[1].get('subscriber_count', 0))

        if top_competitor:
            top_name, top_data = top_competitor
            top_subscribers = top_data.get('subscriber_count', 0)

            if main_subscribers < top_subscribers:
                gap_percentage = ((top_subscribers - main_subscribers) / top_subscribers * 100)
                gap_analysis['opportunities'].append(
                    f"Growth opportunity: {top_name} has {top_subscribers:,} subscribers "
                    f"({gap_percentage:.1f}% more than your channel)"
                )

        return gap_analysis

    def generate_competitive_insights(self, comparison_df: pd.DataFrame,
                                    gap_analysis: Dict[str, Any]) -> List[str]:
        """
        Generate actionable insights from comparison data.

        Args:
            comparison_df: DataFrame with channel comparisons
            gap_analysis: Gap analysis dictionary

        Returns:
            List of actionable insights
        """
        insights = []

        if comparison_df.empty:
            return ["No competitor data available for analysis"]

        # Get main channel data
        main_data = comparison_df[comparison_df['is_main_channel']].iloc[0]

        # Insight 1: Subscriber position
        subscriber_rank = (comparison_df['subscriber_count'].rank(ascending=False, method='min')
                          [comparison_df['is_main_channel']].iloc[0])
        total_channels = len(comparison_df)

        insights.append(
            f"📊 **Competitive Position**: Ranked {int(subscriber_rank)}/{total_channels} "
            f"by subscriber count"
        )

        # Insight 2: Engagement comparison
        engagement_rank = (comparison_df['engagement_rate'].rank(ascending=False, method='min')
                          [comparison_df['is_main_channel']].iloc[0])

        insights.append(
            f"💬 **Engagement Ranking**: {int(engagement_rank)}/{total_channels} "
            f"by engagement rate ({main_data['engagement_rate']:.1f})"
        )

        # Insight 3: Views per video efficiency
        views_per_video_rank = (comparison_df['avg_views_per_video'].rank(ascending=False, method='min')
                               [comparison_df['is_main_channel']].iloc[0])

        insights.append(
            f"👁️ **Content Efficiency**: {int(views_per_video_rank)}/{total_channels} "
            f"by average views per video ({main_data['avg_views_per_video']:,.0f})"
        )

        # Add gap analysis insights
        if gap_analysis.get('strengths'):
            insights.append("✅ **Strengths**: " + "; ".join(gap_analysis['strengths'][:2]))

        if gap_analysis.get('areas_for_improvement'):
            insights.append("🎯 **Improvement Areas**: " + "; ".join(gap_analysis['areas_for_improvement'][:2]))

        if gap_analysis.get('opportunities'):
            insights.append("🚀 **Growth Opportunities**: " + "; ".join(gap_analysis['opportunities'][:2]))

        return insights

    def get_content_strategy_comparison(self, main_channel_videos: pd.DataFrame,
                                      competitor_videos: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Compare content strategies between channels.

        Args:
            main_channel_videos: DataFrame with main channel videos
            competitor_videos: Dictionary mapping competitor names to their video DataFrames

        Returns:
            Dictionary with content strategy comparisons
        """
        comparison = {
            'content_type_distribution': {},
            'publishing_frequency': {},
            'title_patterns': {},
            'video_length_comparison': {}
        }

        # Analyze main channel content
        if not main_channel_videos.empty:
            if 'Content_Type' in main_channel_videos.columns:
                main_content_types = main_channel_videos['Content_Type'].value_counts(normalize=True)
                comparison['content_type_distribution']['main'] = main_content_types.to_dict()

        # Analyze competitor content
        for competitor_name, videos_df in competitor_videos.items():
            if not videos_df.empty and 'Content_Type' in videos_df.columns:
                comp_content_types = videos_df['Content_Type'].value_counts(normalize=True)
                comparison['content_type_distribution'][competitor_name] = comp_content_types.to_dict()

        return comparison


# Helper functions
def get_competitor_analyzer(api_key: str) -> CompetitorAnalyzer:
    """Get a CompetitorAnalyzer instance."""
    return CompetitorAnalyzer(api_key)


if __name__ == "__main__":
    # Test the competitor analyzer
    print("Testing CompetitorAnalyzer...")

    # Check for API key
    import os
    api_key = os.getenv("YOUTUBE_API_KEY", "")

    if not api_key:
        print("ERROR: YOUTUBE_API_KEY environment variable not set")
        print("Set it with: export YOUTUBE_API_KEY='your_api_key_here'")
        exit(1)

    # Create analyzer
    analyzer = CompetitorAnalyzer(api_key)

    # Test with a sample main channel
    print("\n1. Fetching sample main channel data...")
    main_channel_data = analyzer.fetch_channel_data("The Uranium Hunter", max_results=10)

    if main_channel_data:
        print(f"   Main channel: {main_channel_data['channel_name']}")
        print(f"   Subscribers: {main_channel_data['subscriber_count']:,}")
        print(f"   Videos: {main_channel_data['video_count']:,}")
        print(f"   Recent avg views: {main_channel_data['avg_views_per_video']:,.0f}")

        # Test competitor fetching
        print("\n2. Testing competitor analysis...")
        competitors = ["MrBeast", "PewDiePie"]  # Example competitors

        competitor_data = analyzer.fetch_all_competitors(competitors, max_results=10)

        if competitor_data:
            print(f"   Fetched {len(competitor_data)} competitors")

            # Test comparison
            print("\n3. Generating comparison...")
            comparison_df = analyzer.compare_channels(main_channel_data, competitor_data)

            if not comparison_df.empty:
                print(f"   Comparison DataFrame shape: {comparison_df.shape}")
                print("\n   Channel Comparison:")
                print(comparison_df[['channel_name', 'subscriber_count', 'avg_views_per_video', 'engagement_rate']].to_string())

                # Test gap analysis
                print("\n4. Gap Analysis:")
                gap_analysis = analyzer.calculate_gap_analysis(main_channel_data, competitor_data)

                for category, items in gap_analysis.items():
                    if items:
                        print(f"   {category.title()}:")
                        for item in items[:2]:  # Show first 2 items
                            print(f"     - {item}")

                # Test insights
                print("\n5. Competitive Insights:")
                insights = analyzer.generate_competitive_insights(comparison_df, gap_analysis)
                for insight in insights:
                    print(f"   {insight}")
            else:
                print("   Comparison failed")
        else:
            print("   No competitor data fetched")
    else:
        print("   Failed to fetch main channel data")

    print("\nCompetitorAnalyzer test completed!")