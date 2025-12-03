"""
Cached YouTube API Functions

Provides cached versions of YouTube API calls with:
1. Automatic response caching with TTL
2. Quota usage tracking
3. Session integration
4. Error handling and retry logic
"""

import pandas as pd
from googleapiclient.discovery import build
from typing import Dict, Any, Optional, List
import logging
import time

from cache_manager import get_cache_manager, cached_api_call
from data_manager import get_data_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CachedYouTubeAPI:
    """Cached wrapper for YouTube API calls."""

    def __init__(self, api_key: str):
        """
        Initialize with API key.

        Args:
            api_key: YouTube Data API v3 key
        """
        self.api_key = api_key
        self.youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        self.cache_manager = get_cache_manager()
        self.data_manager = get_data_manager()
        logger.info("Cached YouTube API initialized")

    # ==================== Channel Operations ====================

    @cached_api_call("search.channels", ttl_seconds=86400)  # 24 hours
    def search_channels(self, channel_name: str, max_results: int = 1) -> Dict[str, Any]:
        """
        Search for channels by name (cached).

        Args:
            channel_name: Channel name to search for
            max_results: Maximum number of results

        Returns:
            API response
        """
        logger.debug(f"Searching for channel: {channel_name}")
        return self.youtube.search().list(
            part="snippet",
            q=channel_name,
            type="channel",
            maxResults=max_results
        ).execute()

    def get_channel_id(self, channel_name: str) -> Optional[str]:
        """
        Get channel ID from channel name (cached).

        Args:
            channel_name: Channel name

        Returns:
            Channel ID or None if not found
        """
        response = self.search_channels(channel_name, max_results=1)
        if response.get("items"):
            return response["items"][0]["id"]["channelId"]
        return None

    # ==================== Video Operations ====================

    @cached_api_call("search.videos", ttl_seconds=43200)  # 12 hours
    def search_channel_videos(self, channel_id: str, max_results: int = 50,
                             order: str = "date") -> Dict[str, Any]:
        """
        Search for videos in a channel (cached).

        Args:
            channel_id: Channel ID
            max_results: Maximum number of videos
            order: Sort order ('date', 'viewCount', 'rating', 'relevance')

        Returns:
            API response
        """
        logger.debug(f"Searching videos for channel: {channel_id}")
        return self.youtube.search().list(
            part="snippet",
            channelId=channel_id,
            type="video",
            order=order,
            maxResults=max_results
        ).execute()

    @cached_api_call("videos.list", ttl_seconds=43200)  # 12 hours
    def get_video_details(self, video_ids: List[str]) -> Dict[str, Any]:
        """
        Get detailed video information (cached).

        Args:
            video_ids: List of video IDs

        Returns:
            API response
        """
        logger.debug(f"Getting details for {len(video_ids)} videos")
        return self.youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids)
        ).execute()

    # ==================== Combined Operations ====================

    def get_channel_videos_df(self, channel_name: str, max_results: int = 50,
                             order: str = "date") -> pd.DataFrame:
        """
        Get channel videos as DataFrame with caching at multiple levels.

        Args:
            channel_name: Channel name
            max_results: Maximum number of videos
            order: Sort order

        Returns:
            DataFrame with video data
        """
        from utils import (
            parse_duration_to_seconds,
            classify_content_type,
            calculate_video_performance_score,
            format_duration_human_readable
        )

        # Try to get from session cache first
        cache_key = f"channel_videos_{channel_name}_{max_results}_{order}"
        cached_df = self.data_manager.load_dataframe(cache_key)
        if cached_df is not None and not cached_df.empty:
            logger.info(f"Loaded channel videos from session cache: {channel_name}")
            return cached_df

        # Get channel ID (cached)
        channel_id = self.get_channel_id(channel_name)
        if not channel_id:
            logger.error(f"Channel not found: {channel_name}")
            return pd.DataFrame()

        # Get video list (cached)
        search_response = self.search_channel_videos(channel_id, max_results, order)
        video_items = search_response.get("items", [])
        if not video_items:
            logger.warning(f"No videos found for channel: {channel_name}")
            return pd.DataFrame()

        video_ids = [item["id"]["videoId"] for item in video_items]

        # Get video details (cached)
        details_response = self.get_video_details(video_ids)
        video_details = details_response.get("items", [])

        # Process video data
        data = []
        for item in video_details:
            sn = item["snippet"]
            stt = item.get("statistics", {})
            det = item.get("contentDetails", {})

            # Parse duration and classify content type
            duration_iso = det.get("duration", "")
            duration_seconds = parse_duration_to_seconds(duration_iso)
            live_status = sn.get("liveBroadcastContent", "none")
            content_type = classify_content_type(duration_seconds, live_status)

            # Calculate engagement rates
            views = int(stt.get("viewCount", 0))
            likes = int(stt.get("likeCount", 0))
            comments = int(stt.get("commentCount", 0))

            engagement_rate = (likes / views * 100) if views > 0 else 0
            comment_rate = (comments / views * 100) if views > 0 else 0

            # Calculate performance scores
            performance_data = calculate_video_performance_score(
                views, likes, comments, duration_seconds
            )

            # Format duration for display
            duration_display = format_duration_human_readable(duration_seconds)

            data.append({
                "Title": sn.get("title"),
                "Published": pd.to_datetime(sn.get("publishedAt")),
                "Description": sn.get("description", ""),
                "Video_ID": item["id"],
                "URL": f"https://www.youtube.com/watch?v={item['id']}",
                "Duration": duration_iso,
                "Duration_Display": duration_display,
                "Duration_Seconds": duration_seconds,
                "Content_Type": content_type,
                "Live_Status": live_status,
                "Views": views,
                "Likes": likes,
                "Comments": comments,
                "Engagement_Rate": round(engagement_rate, 2),
                "Comment_Rate": round(comment_rate, 2),
                "Performance_Score": performance_data["performance_score"],
                "Performance_Grade": performance_data["performance_grade"],
                "Engagement_Score": performance_data["engagement_score"],
                "Popularity_Score": performance_data["popularity_score"],
                "Interaction_Score": performance_data["interaction_score"],
                "Thumbnail": sn.get("thumbnails", {}).get("high", {}).get("url", "")
            })

        df = pd.DataFrame(data)

        # Save to session cache
        if not df.empty:
            self.data_manager.save_dataframe(cache_key, df)

        return df

    # ==================== Channel Statistics ====================

    @cached_api_call("channels.list", ttl_seconds=86400)  # 24 hours
    def get_channel_statistics(self, channel_id: str) -> Dict[str, Any]:
        """
        Get channel statistics (cached).

        Args:
            channel_id: Channel ID

        Returns:
            API response
        """
        logger.debug(f"Getting statistics for channel: {channel_id}")
        return self.youtube.channels().list(
            part="snippet,statistics",
            id=channel_id
        ).execute()

    def get_channel_stats_df(self, channel_name: str) -> Optional[pd.DataFrame]:
        """
        Get channel statistics as DataFrame.

        Args:
            channel_name: Channel name

        Returns:
            DataFrame with channel statistics
        """
        channel_id = self.get_channel_id(channel_name)
        if not channel_id:
            return None

        response = self.get_channel_statistics(channel_id)
        if not response.get("items"):
            return None

        item = response["items"][0]
        snippet = item["snippet"]
        stats = item["statistics"]

        data = {
            "channel_id": channel_id,
            "channel_name": snippet.get("title"),
            "description": snippet.get("description", "")[:200],  # Truncate
            "published_at": snippet.get("publishedAt"),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "custom_url": snippet.get("customUrl"),
            "country": snippet.get("country"),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", "")
        }

        return pd.DataFrame([data])

    # ==================== Playlist Operations ====================

    @cached_api_call("playlists.list", ttl_seconds=86400)  # 24 hours
    def get_channel_playlists(self, channel_id: str, max_results: int = 20) -> Dict[str, Any]:
        """
        Get channel playlists (cached).

        Args:
            channel_id: Channel ID
            max_results: Maximum number of playlists

        Returns:
            API response
        """
        logger.debug(f"Getting playlists for channel: {channel_id}")
        return self.youtube.playlists().list(
            part="snippet,contentDetails",
            channelId=channel_id,
            maxResults=max_results
        ).execute()

    # ==================== Comment Operations ====================

    @cached_api_call("commentThreads.list", ttl_seconds=3600)  # 1 hour
    def get_video_comments(self, video_id: str, max_results: int = 100) -> Dict[str, Any]:
        """
        Get video comments (cached).

        Args:
            video_id: Video ID
            max_results: Maximum number of comments

        Returns:
            API response
        """
        logger.debug(f"Getting comments for video: {video_id}")
        return self.youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="relevance"
        ).execute()

    # ==================== Utility Methods ====================

    def get_quota_usage(self) -> Dict[str, Any]:
        """Get current API quota usage."""
        return self.data_manager.get_quota_usage()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_cache_stats()

    def invalidate_channel_cache(self, channel_name: str):
        """
        Invalidate cache for a specific channel.

        Args:
            channel_name: Channel name
        """
        channel_id = self.get_channel_id(channel_name)
        if channel_id:
            # Invalidate all cache entries related to this channel
            patterns = [
                f"%{channel_id}%",
                f"%{channel_name}%",
                "search.channels%",
                "search.videos%",
                "videos.list%"
            ]
            for pattern in patterns:
                self.cache_manager.invalidate(pattern=pattern)

            logger.info(f"Invalidated cache for channel: {channel_name}")

    def cleanup_expired_cache(self):
        """Clean up expired cache entries."""
        self.cache_manager.cleanup_expired()


# Global instance management
_cached_youtube_api = {}


def get_cached_youtube_api(api_key: str) -> CachedYouTubeAPI:
    """
    Get or create a CachedYouTubeAPI instance for an API key.

    Args:
        api_key: YouTube API key

    Returns:
        CachedYouTubeAPI instance
    """
    global _cached_youtube_api
    if api_key not in _cached_youtube_api:
        _cached_youtube_api[api_key] = CachedYouTubeAPI(api_key)
    return _cached_youtube_api[api_key]


def clear_api_cache(api_key: str = None):
    """
    Clear API cache for a specific API key or all.

    Args:
        api_key: API key to clear cache for (None for all)
    """
    global _cached_youtube_api
    if api_key:
        if api_key in _cached_youtube_api:
            del _cached_youtube_api[api_key]
            logger.info(f"Cleared cache for API key: {api_key[:8]}...")
    else:
        _cached_youtube_api.clear()
        logger.info("Cleared all API cache instances")


if __name__ == "__main__":
    # Test the cached YouTube API
    print("Testing CachedYouTubeAPI...")

    # Note: This requires a valid API key
    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        print("Skipping tests - no API key found")
        print("Set YOUTUBE_API_KEY in .env file to run tests")
    else:
        print(f"\n1. Initializing with API key: {api_key[:8]}...")
        youtube_api = get_cached_youtube_api(api_key)

        print("\n2. Testing channel search...")
        try:
            response = youtube_api.search_channels("YouTube", max_results=1)
            if response.get("items"):
                print(f"   Found channel: {response['items'][0]['snippet']['title']}")
        except Exception as e:
            print(f"   Error: {e}")

        print("\n3. Testing cache stats...")
        stats = youtube_api.get_cache_stats()
        print(f"   Cache entries: {stats['total_entries']}")
        print(f"   Quota usage: {stats['quota_usage']}")

        print("\nCachedYouTubeAPI test completed!")