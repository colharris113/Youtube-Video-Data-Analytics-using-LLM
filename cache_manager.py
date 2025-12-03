"""
Cache Manager for YouTube Video Data Analytics

Provides intelligent API response caching to:
1. Reduce API quota usage
2. Improve performance with faster responses
3. Enable offline analysis capability
4. Prevent data loss on page refresh
"""

import sqlite3
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import logging
from pathlib import Path
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheManager:
    """Manages API response caching with SQLite backend."""

    def __init__(self, db_path: str = None):
        """
        Initialize the cache manager.

        Args:
            db_path: Path to SQLite database file (default: youtube_cache.db in app directory)
        """
        if db_path is None:
            # Use absolute path in the same directory as this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(current_dir, "youtube_cache.db")
        else:
            self.db_path = db_path

        logger.info(f"Cache manager using database: {self.db_path}")
        self._init_database()
        self.quota_usage = self._load_quota_usage()

        # Default TTL values (in seconds)
        self.ttl_config = {
            'channel_data': 86400,  # 24 hours
            'video_data': 43200,    # 12 hours
            'analytics_data': 21600,  # 6 hours
            'search_results': 3600,   # 1 hour
            'default': 7200          # 2 hours
        }

        logger.info(f"Cache manager initialized with database: {db_path}")

    def _init_database(self):
        """Initialize the cache database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                params_hash TEXT NOT NULL,
                response_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                hit_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Enhanced quota tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quota_tracking (
                date TEXT PRIMARY KEY,
                total_calls INTEGER DEFAULT 0,
                cached_calls INTEGER DEFAULT 0,
                quota_units_used INTEGER DEFAULT 0,
                data_api_calls INTEGER DEFAULT 0,
                analytics_api_calls INTEGER DEFAULT 0,
                data_api_units INTEGER DEFAULT 0,
                analytics_api_units INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Detailed endpoint tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS endpoint_tracking (
                tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                api_type TEXT NOT NULL,  -- 'data_api' or 'analytics_api'
                call_count INTEGER DEFAULT 0,
                quota_units INTEGER DEFAULT 0,
                avg_response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (date) REFERENCES quota_tracking (date) ON DELETE CASCADE
            )
        ''')

        # Session state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_state (
                session_id TEXT PRIMARY KEY,
                session_name TEXT,
                session_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_endpoint ON cache(endpoint)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_expires ON session_state(expires_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_endpoint_tracking_date ON endpoint_tracking(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_endpoint_tracking_endpoint ON endpoint_tracking(endpoint)')

        conn.commit()
        conn.close()

    def _load_quota_usage(self) -> Dict[str, int]:
        """Load quota usage from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            '''SELECT total_calls, cached_calls, quota_units_used,
                      data_api_calls, analytics_api_calls,
                      data_api_units, analytics_api_units
               FROM quota_tracking WHERE date = ?''',
            (today,)
        )
        row = cursor.fetchone()

        conn.close()

        if row:
            return {
                'total_calls': row[0],
                'cached_calls': row[1],
                'quota_units_used': row[2],
                'data_api_calls': row[3],
                'analytics_api_calls': row[4],
                'data_api_units': row[5],
                'analytics_api_units': row[6]
            }
        else:
            return {
                'total_calls': 0,
                'cached_calls': 0,
                'quota_units_used': 0,
                'data_api_calls': 0,
                'analytics_api_calls': 0,
                'data_api_units': 0,
                'analytics_api_units': 0
            }

    def _update_quota_usage(self, is_cached: bool = False, quota_units: int = 1,
                           endpoint: str = None, api_type: str = "data_api",
                           response_time_ms: int = None):
        """
        Update quota usage tracking with detailed endpoint information.

        Args:
            is_cached: Whether this was a cached call
            quota_units: Quota units used (default 1)
            endpoint: API endpoint (e.g., 'search.channels', 'videos.list')
            api_type: Type of API ('data_api' or 'analytics_api')
            response_time_ms: Response time in milliseconds
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        if is_cached:
            self.quota_usage['cached_calls'] += 1
        else:
            self.quota_usage['total_calls'] += 1
            self.quota_usage['quota_units_used'] += quota_units

            # Track by API type
            if api_type == "data_api":
                self.quota_usage['data_api_calls'] += 1
                self.quota_usage['data_api_units'] += quota_units
            elif api_type == "analytics_api":
                self.quota_usage['analytics_api_calls'] += 1
                self.quota_usage['analytics_api_units'] += quota_units

        # Update main quota tracking
        cursor.execute('''
            INSERT OR REPLACE INTO quota_tracking
            (date, total_calls, cached_calls, quota_units_used,
             data_api_calls, analytics_api_calls,
             data_api_units, analytics_api_units, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            today,
            self.quota_usage['total_calls'],
            self.quota_usage['cached_calls'],
            self.quota_usage['quota_units_used'],
            self.quota_usage['data_api_calls'],
            self.quota_usage['analytics_api_calls'],
            self.quota_usage['data_api_units'],
            self.quota_usage['analytics_api_units']
        ))

        # Track endpoint details for non-cached calls
        if endpoint and not is_cached:
            # Check if endpoint already tracked today
            cursor.execute('''
                SELECT tracking_id, call_count, quota_units, avg_response_time_ms
                FROM endpoint_tracking
                WHERE date = ? AND endpoint = ? AND api_type = ?
            ''', (today, endpoint, api_type))

            existing = cursor.fetchone()

            if existing:
                # Update existing entry
                tracking_id, old_count, old_units, old_avg_time = existing
                new_count = old_count + 1
                new_units = old_units + quota_units

                # Update average response time
                if response_time_ms is not None:
                    if old_avg_time:
                        new_avg_time = int((old_avg_time * old_count + response_time_ms) / new_count)
                    else:
                        new_avg_time = response_time_ms
                else:
                    new_avg_time = old_avg_time

                cursor.execute('''
                    UPDATE endpoint_tracking
                    SET call_count = ?, quota_units = ?, avg_response_time_ms = ?
                    WHERE tracking_id = ?
                ''', (new_count, new_units, new_avg_time, tracking_id))
            else:
                # Insert new entry
                cursor.execute('''
                    INSERT INTO endpoint_tracking
                    (date, endpoint, api_type, call_count, quota_units, avg_response_time_ms)
                    VALUES (?, ?, ?, 1, ?, ?)
                ''', (today, endpoint, api_type, quota_units, response_time_ms))

        conn.commit()
        conn.close()

    def generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Generate a unique cache key for an API request.

        Args:
            endpoint: API endpoint (e.g., 'channels.list', 'videos.list')
            params: Request parameters

        Returns:
            Unique cache key
        """
        # Sort params for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(sorted_params.encode()).hexdigest()

        return f"{endpoint}:{params_hash}"

    def get(self, endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Get cached response for an API request.

        Args:
            endpoint: API endpoint
            params: Request parameters

        Returns:
            Cached response data or None if not found/expired
        """
        cache_key = self.generate_cache_key(endpoint, params)
        params_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT response_data, expires_at FROM cache
            WHERE cache_key = ? AND params_hash = ?
        ''', (cache_key, params_hash))

        row = cursor.fetchone()

        if row:
            response_data, expires_at = row

            # Check if cache is expired
            if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                logger.debug(f"Cache expired for {endpoint}")
                cursor.execute('DELETE FROM cache WHERE cache_key = ?', (cache_key,))
                conn.commit()
                conn.close()
                return None

            # Update hit count and last accessed
            cursor.execute('''
                UPDATE cache
                SET hit_count = hit_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE cache_key = ?
            ''', (cache_key,))

            conn.commit()
            conn.close()

            # Update quota usage (cached call)
            self._update_quota_usage(is_cached=True, endpoint=endpoint)

            logger.debug(f"Cache hit for {endpoint}")
            return json.loads(response_data)
        else:
            conn.close()
            return None

    def set(self, endpoint: str, params: Dict[str, Any], response_data: Any,
            ttl_seconds: Optional[int] = None):
        """
        Cache an API response.

        Args:
            endpoint: API endpoint
            params: Request parameters
            response_data: Response data to cache
            ttl_seconds: Time to live in seconds (uses default if None)
        """
        if ttl_seconds is None:
            ttl_seconds = self.ttl_config.get(endpoint.split('.')[0], self.ttl_config['default'])

        cache_key = self.generate_cache_key(endpoint, params)
        params_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()

        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO cache
            (cache_key, endpoint, params_hash, response_data, expires_at, hit_count, last_accessed)
            VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        ''', (
            cache_key,
            endpoint,
            params_hash,
            json.dumps(response_data),
            expires_at.isoformat()
        ))

        conn.commit()
        conn.close()

        logger.debug(f"Cached response for {endpoint} (TTL: {ttl_seconds}s)")

    def invalidate(self, endpoint: Optional[str] = None, pattern: Optional[str] = None):
        """
        Invalidate cached entries.

        Args:
            endpoint: Specific endpoint to invalidate (None for all)
            pattern: SQL LIKE pattern for endpoint matching
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if endpoint:
            cursor.execute('DELETE FROM cache WHERE endpoint = ?', (endpoint,))
            logger.info(f"Invalidated cache for endpoint: {endpoint}")
        elif pattern:
            cursor.execute('DELETE FROM cache WHERE endpoint LIKE ?', (pattern,))
            logger.info(f"Invalidated cache for pattern: {pattern}")
        else:
            cursor.execute('DELETE FROM cache')
            logger.info("Invalidated all cache entries")

        conn.commit()
        conn.close()

    def cleanup_expired(self):
        """Remove expired cache entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM cache WHERE expires_at < CURRENT_TIMESTAMP')
        deleted_count = cursor.rowcount

        cursor.execute('DELETE FROM session_state WHERE expires_at < CURRENT_TIMESTAMP')
        session_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted_count > 0 or session_deleted > 0:
            logger.info(f"Cleaned up {deleted_count} expired cache entries and {session_deleted} expired sessions")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics with detailed quota tracking."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        # Total cache entries
        cursor.execute('SELECT COUNT(*) FROM cache')
        total_entries = cursor.fetchone()[0]

        # Expired entries
        cursor.execute('SELECT COUNT(*) FROM cache WHERE expires_at < CURRENT_TIMESTAMP')
        expired_entries = cursor.fetchone()[0]

        # Top endpoints by hit count
        cursor.execute('''
            SELECT endpoint, SUM(hit_count) as total_hits, COUNT(*) as entry_count
            FROM cache
            GROUP BY endpoint
            ORDER BY total_hits DESC
            LIMIT 10
        ''')
        top_endpoints = [
            {'endpoint': row[0], 'hits': row[1], 'entries': row[2]}
            for row in cursor.fetchall()
        ]

        # Get today's endpoint breakdown
        cursor.execute('''
            SELECT endpoint, api_type, call_count, quota_units, avg_response_time_ms
            FROM endpoint_tracking
            WHERE date = ?
            ORDER BY quota_units DESC
        ''', (today,))

        endpoint_breakdown = [
            {
                'endpoint': row[0],
                'api_type': row[1],
                'call_count': row[2],
                'quota_units': row[3],
                'avg_response_time_ms': row[4]
            }
            for row in cursor.fetchall()
        ]

        # Calculate API limits
        data_api_limit = 10000  # YouTube Data API v3 daily limit
        analytics_api_limit = 100000  # YouTube Analytics API daily limit

        data_api_used = self.quota_usage.get('data_api_units', 0)
        analytics_api_used = self.quota_usage.get('analytics_api_units', 0)

        data_api_percentage = (data_api_used / data_api_limit * 100) if data_api_limit > 0 else 0
        analytics_api_percentage = (analytics_api_used / analytics_api_limit * 100) if analytics_api_limit > 0 else 0

        # Cache hit rate (estimated)
        total_hits = sum(item['hits'] for item in top_endpoints)
        hit_rate = total_hits / (total_hits + self.quota_usage['total_calls']) * 100 if (total_hits + self.quota_usage['total_calls']) > 0 else 0

        conn.close()

        return {
            'total_entries': total_entries,
            'expired_entries': expired_entries,
            'valid_entries': total_entries - expired_entries,
            'top_endpoints': top_endpoints,
            'endpoint_breakdown': endpoint_breakdown,
            'quota_usage': self.quota_usage,
            'api_limits': {
                'data_api': {
                    'used': data_api_used,
                    'limit': data_api_limit,
                    'percentage': round(data_api_percentage, 2),
                    'remaining': data_api_limit - data_api_used
                },
                'analytics_api': {
                    'used': analytics_api_used,
                    'limit': analytics_api_limit,
                    'percentage': round(analytics_api_percentage, 2),
                    'remaining': analytics_api_limit - analytics_api_used
                }
            },
            'estimated_hit_rate': round(hit_rate, 2),
            'quota_saved_percentage': round(
                self.quota_usage['cached_calls'] / (self.quota_usage['total_calls'] + self.quota_usage['cached_calls']) * 100, 2
            ) if (self.quota_usage['total_calls'] + self.quota_usage['cached_calls']) > 0 else 0,
            'cost_savings': self._estimate_cost_savings()
        }

    def _estimate_cost_savings(self) -> Dict[str, Any]:
        """Estimate cost savings from caching."""
        quota_usage = self.quota_usage
        cached_calls = quota_usage.get('cached_calls', 0)

        if cached_calls == 0:
            return {
                'calls_saved': 0,
                'quota_units_saved': 0,
                'estimated_cost_savings_usd': 0.0
            }

        # Estimate average quota units per call
        total_units = quota_usage.get('quota_units_used', 0)
        total_calls = quota_usage.get('total_calls', 0)

        if total_calls > 0:
            avg_units_per_call = total_units / total_calls
        else:
            avg_units_per_call = 50  # Conservative estimate

        quota_units_saved = int(cached_calls * avg_units_per_call)

        # Estimate cost savings (YouTube Data API costs $0.01 per 10,000 units)
        cost_per_10k = 0.01
        estimated_cost_savings = (quota_units_saved / 10000) * cost_per_10k

        return {
            'calls_saved': cached_calls,
            'quota_units_saved': quota_units_saved,
            'estimated_cost_savings_usd': round(estimated_cost_savings, 4)
        }

    def save_session_state(self, session_id: str, session_data: Dict[str, Any],
                          session_name: Optional[str] = None,
                          ttl_days: int = 7):
        """
        Save session state to persistent storage.

        Args:
            session_id: Unique session identifier
            session_data: Session data to save
            session_name: Optional descriptive name
            ttl_days: Days until session expires (default 7)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        expires_at = datetime.now() + timedelta(days=ttl_days)

        cursor.execute('''
            INSERT OR REPLACE INTO session_state
            (session_id, session_name, session_data, last_accessed, expires_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (
            session_id,
            session_name,
            json.dumps(session_data),
            expires_at.isoformat()
        ))

        conn.commit()
        conn.close()

        logger.debug(f"Saved session state: {session_id}")

    def load_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session state from persistent storage.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found/expired
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT session_data, expires_at FROM session_state
            WHERE session_id = ?
        ''', (session_id,))

        row = cursor.fetchone()

        if row:
            session_data, expires_at = row

            # Check if session is expired
            if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                logger.debug(f"Session expired: {session_id}")
                cursor.execute('DELETE FROM session_state WHERE session_id = ?', (session_id,))
                conn.commit()
                conn.close()
                return None

            # Update last accessed
            cursor.execute('''
                UPDATE session_state
                SET last_accessed = CURRENT_TIMESTAMP
                WHERE session_id = ?
            ''', (session_id,))

            conn.commit()
            conn.close()

            logger.debug(f"Loaded session state: {session_id}")
            return json.loads(session_data)
        else:
            conn.close()
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT session_id, session_name, created_at, last_accessed, expires_at
            FROM session_state
            ORDER BY last_accessed DESC
        ''')

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'session_id': row[0],
                'session_name': row[1],
                'created_at': row[2],
                'last_accessed': row[3],
                'expires_at': row[4],
                'is_expired': row[4] and datetime.fromisoformat(row[4]) < datetime.now()
            })

        conn.close()
        return sessions

    def delete_session(self, session_id: str):
        """Delete a saved session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM session_state WHERE session_id = ?', (session_id,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted:
            logger.info(f"Deleted session: {session_id}")
        else:
            logger.warning(f"Session not found: {session_id}")


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def estimate_quota_units(endpoint: str, params: Dict[str, Any]) -> int:
    """
    Estimate quota units for a YouTube API call.

    YouTube Data API v3 quota units:
    - Search: 100 units
    - Videos.list: 1 unit per video (capped)
    - Channels.list: 1 unit
    - CommentThreads.list: 1 unit
    - Playlists.list: 1 unit

    YouTube Analytics API:
    - Reports.query: 1 unit per request

    Args:
        endpoint: API endpoint
        params: Request parameters

    Returns:
        Estimated quota units
    """
    # YouTube Data API v3 endpoints
    if endpoint == "search.channels" or endpoint == "search.videos":
        return 100  # Search operations cost 100 units

    elif endpoint == "videos.list":
        # Videos.list costs 1 unit per video, but capped
        video_ids = params.get("id", "")
        if video_ids:
            num_videos = len(video_ids.split(","))
            # Cap at reasonable number
            return min(num_videos, 50)
        return 1

    elif endpoint in ["channels.list", "commentThreads.list", "playlists.list"]:
        return 1

    # YouTube Analytics API endpoints
    elif "analytics" in endpoint.lower():
        return 1

    # Default estimate
    return 1


def cached_api_call(endpoint: str, ttl_seconds: Optional[int] = None):
    """
    Decorator for caching API calls.

    Args:
        endpoint: API endpoint name
        ttl_seconds: Cache TTL in seconds
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            # Extract params from function arguments
            # Assuming the function signature includes params as first argument or keyword
            params = {}
            if args and len(args) > 0 and isinstance(args[0], dict):
                params = args[0]
            elif 'params' in kwargs:
                params = kwargs['params']

            # Try to get from cache
            cached_response = cache_manager.get(endpoint, params)
            if cached_response is not None:
                return cached_response

            # Call the actual API function
            response = func(*args, **kwargs)

            # Cache the response
            if response is not None:
                cache_manager.set(endpoint, params, response, ttl_seconds)

            # Update quota usage (actual API call)
            # Estimate quota units based on endpoint type
            quota_units = estimate_quota_units(endpoint, params)
            api_type = "analytics_api" if "analytics" in endpoint.lower() else "data_api"
            cache_manager._update_quota_usage(
                is_cached=False,
                quota_units=quota_units,
                endpoint=endpoint,
                api_type=api_type
            )

            return response
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test the cache manager
    print("Testing CacheManager...")

    # Create cache manager
    cm = CacheManager("test_cache.db")

    # Test cache operations
    test_endpoint = "channels.list"
    test_params = {"part": "snippet,statistics", "id": "test_channel"}
    test_response = {"items": [{"id": "test_channel", "statistics": {"subscriberCount": "1000"}}]}

    print("\n1. Testing cache set/get...")
    cm.set(test_endpoint, test_params, test_response, ttl_seconds=60)

    cached = cm.get(test_endpoint, test_params)
    if cached:
        print(f"   Cache hit: {cached}")
    else:
        print("   Cache miss")

    print("\n2. Testing cache stats...")
    stats = cm.get_cache_stats()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Quota usage: {stats['quota_usage']}")
    print(f"   Estimated hit rate: {stats['estimated_hit_rate']}%")

    print("\n3. Testing session state...")
    session_data = {"channel_name": "Test Channel", "videos_fetched": 50}
    cm.save_session_state("test_session", session_data, "Test Session")

    loaded = cm.load_session_state("test_session")
    if loaded:
        print(f"   Session loaded: {loaded}")

    print("\n4. Testing session listing...")
    sessions = cm.list_sessions()
    for session in sessions:
        print(f"   Session: {session['session_id']} - {session['session_name']}")

    print("\n5. Testing cleanup...")
    cm.cleanup_expired()

    print("\nCacheManager test completed!")
    print("\nNote: Test database 'test_cache.db' can be deleted.")