"""
Data Manager for YouTube Video Data Analytics

Integrates CacheManager and StateManager to provide:
1. Intelligent API response caching with automatic TTL
2. Session state persistence across page refreshes
3. Auto-save functionality for user sessions
4. Resume capability for interrupted analyses
5. Quota management and optimization
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Union
import logging
import pandas as pd

# Optional Streamlit import for session state
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    # Create a mock st object for testing
    class MockStreamlit:
        session_state = type('obj', (object,), {'__dict__': {}})()
    st = MockStreamlit()

from cache_manager import get_cache_manager, cached_api_call
from state_manager import get_state_manager, auto_save_session

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataManager:
    """Integrates caching and state management for YouTube analytics."""

    def __init__(self):
        """Initialize the data manager with cache and state managers."""
        self.cache_manager = get_cache_manager()
        self.state_manager = get_state_manager()
        self.current_session_id = None
        logger.info("Data manager initialized")

    # ==================== Session Management ====================

    def create_analysis_session(self, session_name: str, channel_name: str,
                               api_key: str = None, metadata: Dict[str, Any] = None) -> str:
        """
        Create a new analysis session.

        Args:
            session_name: Descriptive name for the session
            channel_name: Channel being analyzed
            api_key: YouTube API key (optional, for session identification)
            metadata: Additional session metadata

        Returns:
            Session ID
        """
        session_id = self.state_manager.create_session(
            session_name=session_name,
            session_type="channel_analysis",
            channel_name=channel_name,
            api_key=api_key,
            metadata=metadata,
            ttl_days=7
        )

        self.current_session_id = session_id

        # Save initial session state
        self.save_session_state({
            "session_name": session_name,
            "channel_name": channel_name,
            "created_at": datetime.now().isoformat(),
            "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest() if api_key else None
        })

        logger.info(f"Created analysis session: {session_id} - {session_name}")
        return session_id

    def resume_session(self, session_id: str) -> bool:
        """
        Resume a previously saved session.

        Args:
            session_id: Session identifier

        Returns:
            True if session resumed successfully
        """
        try:
            # Load session state
            session_state = self.state_manager.load_session_state(session_id)
            if session_state:
                self.current_session_id = session_id

                # Update Streamlit session state if available
                if STREAMLIT_AVAILABLE:
                    for key, value in session_state.items():
                        if key not in st.session_state or key == "df":
                            st.session_state[key] = value

                logger.info(f"Resumed session: {session_id}")
                return True
            else:
                logger.warning(f"Session not found or empty: {session_id}")
                return False
        except Exception as e:
            logger.error(f"Error resuming session {session_id}: {e}")
            return False

    def save_current_session(self):
        """Save the current session state."""
        if not self.current_session_id:
            logger.warning("No active session to save")
            return

        # Collect data from Streamlit session state if available
        session_data = {}
        if STREAMLIT_AVAILABLE:
            for key in st.session_state.keys():
                if key.startswith("df_") or key in ["df", "settings", "analysis_results"]:
                    session_data[key] = st.session_state[key]

        self.state_manager.save_session_state(self.current_session_id, session_data)
        logger.debug(f"Auto-saved session: {self.current_session_id}")

    def list_available_sessions(self) -> list:
        """List all available sessions for resuming."""
        return self.state_manager.list_sessions(active_only=True)

    # ==================== API Caching Integration ====================

    def cached_youtube_api_call(self, endpoint: str, params: Dict[str, Any],
                               ttl_seconds: Optional[int] = None) -> Callable:
        """
        Decorator for caching YouTube API calls with session integration.

        Args:
            endpoint: API endpoint name
            params: Request parameters
            ttl_seconds: Cache TTL in seconds

        Returns:
            Decorated function
        """
        return cached_api_call(endpoint, ttl_seconds)

    def get_cached_or_fetch(self, endpoint: str, params: Dict[str, Any],
                           fetch_func: Callable, ttl_seconds: Optional[int] = None) -> Any:
        """
        Get data from cache or fetch from API.

        Args:
            endpoint: API endpoint
            params: Request parameters
            fetch_func: Function to call if cache miss
            ttl_seconds: Cache TTL in seconds

        Returns:
            Response data
        """
        # Try cache first
        cached = self.cache_manager.get(endpoint, params)
        if cached is not None:
            logger.debug(f"Cache hit for {endpoint}")
            return cached

        # Cache miss, fetch from API
        logger.debug(f"Cache miss for {endpoint}, fetching...")
        response = fetch_func()

        # Cache the response
        if response is not None:
            self.cache_manager.set(endpoint, params, response, ttl_seconds)

        return response

    # ==================== Data Persistence ====================

    def save_dataframe(self, df_key: str, df: pd.DataFrame):
        """
        Save a DataFrame to the current session.

        Args:
            df_key: Key for the DataFrame
            df: DataFrame to save
        """
        if not self.current_session_id:
            logger.warning("No active session for saving DataFrame")
            return

        self.state_manager.save_dataframe(self.current_session_id, df_key, df)

        # Also update Streamlit session state if available
        if STREAMLIT_AVAILABLE:
            st.session_state[df_key] = df

    def load_dataframe(self, df_key: str) -> Optional[pd.DataFrame]:
        """
        Load a DataFrame from the current session.

        Args:
            df_key: Key for the DataFrame

        Returns:
            Loaded DataFrame or None
        """
        if not self.current_session_id:
            return None

        df = self.state_manager.load_dataframe(self.current_session_id, df_key)
        if df is not None and STREAMLIT_AVAILABLE:
            # Update Streamlit session state
            st.session_state[df_key] = df

        return df

    def save_session_state(self, state_dict: Dict[str, Any]):
        """
        Save session state.

        Args:
            state_dict: Dictionary of state variables
        """
        if not self.current_session_id:
            logger.warning("No active session for saving state")
            return

        self.state_manager.save_session_state(self.current_session_id, state_dict)

        # Update Streamlit session state if available
        if STREAMLIT_AVAILABLE:
            for key, value in state_dict.items():
                st.session_state[key] = value

    def load_session_state(self) -> Dict[str, Any]:
        """
        Load session state.

        Returns:
            Dictionary of state variables
        """
        if not self.current_session_id:
            return {}

        return self.state_manager.load_session_state(self.current_session_id)

    def save_session_value(self, key: str, value: Any):
        """
        Save a single session value.

        Args:
            key: Key for the value
            value: Value to save
        """
        if not self.current_session_id:
            logger.warning("No active session for saving value")
            return

        # Load current state, update with new value, and save
        current_state = self.load_session_state()
        current_state[key] = value
        self.save_session_state(current_state)

    def get_session_value(self, key: str, default: Any = None) -> Any:
        """
        Get a single session value.

        Args:
            key: Key for the value
            default: Default value if key not found

        Returns:
            The value or default
        """
        if not self.current_session_id:
            return default

        state = self.load_session_state()
        return state.get(key, default)

    # ==================== Auto-save Functionality ====================

    def enable_auto_save(self, interval_minutes: int = 5):
        """
        Enable auto-save for the current session.

        Args:
            interval_minutes: Auto-save interval in minutes
        """
        if not self.current_session_id:
            logger.warning("No active session for auto-save")
            return

        # Create auto-save decorator
        auto_save_decorator = auto_save_session(
            self.current_session_id,
            self._get_auto_save_state(),
            interval_minutes
        )

        # Apply to relevant functions
        self._wrap_functions_with_auto_save(auto_save_decorator)

        logger.info(f"Auto-save enabled for session {self.current_session_id} "
                   f"(interval: {interval_minutes} minutes)")

    def _get_auto_save_state(self) -> Dict[str, Any]:
        """Get state variables to auto-save."""
        state_vars = {}
        if STREAMLIT_AVAILABLE:
            for key in st.session_state.keys():
                if key.startswith("df_") or key in ["df", "settings", "analysis_results"]:
                    state_vars[key] = st.session_state[key]
        return state_vars

    def _wrap_functions_with_auto_save(self, decorator):
        """Wrap relevant functions with auto-save decorator."""
        # This would be implemented based on specific app functions
        pass

    # ==================== Quota Management ====================

    def get_quota_usage(self) -> Dict[str, Any]:
        """Get current API quota usage statistics."""
        cache_stats = self.cache_manager.get_cache_stats()
        return {
            "total_calls": cache_stats["quota_usage"]["total_calls"],
            "cached_calls": cache_stats["quota_usage"]["cached_calls"],
            "quota_units_used": cache_stats["quota_usage"]["quota_units_used"],
            "quota_saved_percentage": cache_stats["quota_saved_percentage"],
            "cache_hit_rate": cache_stats["estimated_hit_rate"],
            "cache_entries": cache_stats["total_entries"]
        }

    def get_quota_savings(self) -> Dict[str, Any]:
        """Calculate quota savings from caching."""
        quota_usage = self.get_quota_usage()
        total_calls = quota_usage["total_calls"]
        cached_calls = quota_usage["cached_calls"]

        if total_calls + cached_calls == 0:
            return {"percentage": 0, "calls_saved": 0}

        percentage = (cached_calls / (total_calls + cached_calls)) * 100
        calls_saved = cached_calls

        return {
            "percentage": round(percentage, 2),
            "calls_saved": calls_saved,
            "estimated_cost_savings": self._estimate_cost_savings(calls_saved)
        }

    def _estimate_cost_savings(self, calls_saved: int) -> float:
        """Estimate cost savings from cached calls."""
        # YouTube Data API v3: 10,000 units per day free
        # Assume average 100 units per call
        units_per_call = 100
        total_units_saved = calls_saved * units_per_call

        # If over free tier, estimate cost at $0.01 per 10,000 units
        if total_units_saved > 10000:
            cost_per_10k = 0.01
            return round((total_units_saved / 10000) * cost_per_10k, 4)
        return 0.0

    # ==================== Cache Management ====================

    def cleanup_expired_cache(self):
        """Clean up expired cache entries."""
        self.cache_manager.cleanup_expired()

    def invalidate_cache(self, endpoint: Optional[str] = None, pattern: Optional[str] = None):
        """
        Invalidate cached entries.

        Args:
            endpoint: Specific endpoint to invalidate
            pattern: SQL LIKE pattern for endpoint matching
        """
        self.cache_manager.invalidate(endpoint, pattern)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache_manager.get_cache_stats()

    # ==================== State Management ====================

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return self.state_manager.get_session_stats()

    def cleanup_expired_sessions(self, delete_data: bool = True):
        """
        Clean up expired sessions.

        Args:
            delete_data: Whether to delete data or just deactivate
        """
        self.state_manager.cleanup_expired(delete_data)

    # ==================== User Preferences ====================

    def save_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """
        Save user preferences.

        Args:
            user_id: User identifier
            preferences: Preferences dictionary
        """
        self.state_manager.save_user_preferences(user_id, preferences)

    def load_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Load user preferences.

        Args:
            user_id: User identifier

        Returns:
            Preferences dictionary
        """
        return self.state_manager.load_user_preferences(user_id)

    # ==================== Utility Functions ====================

    def generate_session_id(self, channel_name: str, api_key: str) -> str:
        """
        Generate a deterministic session ID.

        Args:
            channel_name: Channel name
            api_key: API key

        Returns:
            Session ID
        """
        # Create a hash of channel name and API key (first 8 chars)
        hash_input = f"{channel_name}:{api_key}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:8]

    def is_session_valid(self, session_id: str) -> bool:
        """
        Check if a session is still valid (not expired).

        Args:
            session_id: Session identifier

        Returns:
            True if session is valid
        """
        sessions = self.state_manager.list_sessions(active_only=True)
        for session in sessions:
            if session["session_id"] == session_id and not session["is_expired"]:
                return True
        return False


# Global data manager instance
_data_manager = None


def get_data_manager() -> DataManager:
    """Get the global data manager instance."""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


def with_data_persistence(session_id_key: str = "current_session_id"):
    """
    Decorator for functions that should trigger auto-save.

    Args:
        session_id_key: Key for session ID in function arguments
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Call the function
            result = func(*args, **kwargs)

            # Get session ID from args or kwargs
            session_id = None
            if session_id_key in kwargs:
                session_id = kwargs[session_id_key]
            else:
                # Try to find in args by parameter name
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if session_id_key in params:
                    idx = params.index(session_id_key)
                    if idx < len(args):
                        session_id = args[idx]

            # Auto-save if we have a session ID
            if session_id:
                data_manager = get_data_manager()
                if data_manager.current_session_id == session_id:
                    data_manager.save_current_session()

            return result
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test the data manager
    print("Testing DataManager...")

    # Create data manager
    dm = get_data_manager()

    # Test session creation
    print("\n1. Testing session creation...")
    session_id = dm.create_analysis_session(
        session_name="Test Session",
        channel_name="Test Channel",
        api_key="test_api_key_123"
    )
    print(f"   Created session: {session_id}")

    # Test DataFrame saving
    print("\n2. Testing DataFrame saving...")
    test_df = pd.DataFrame({
        "Video_ID": ["vid1", "vid2", "vid3"],
        "Title": ["Video 1", "Video 2", "Video 3"],
        "Views": [1000, 2000, 3000]
    })
    dm.save_dataframe("df_videos", test_df)
    print(f"   Saved DataFrame: {len(test_df)} rows")

    # Test quota tracking
    print("\n3. Testing quota tracking...")
    quota_usage = dm.get_quota_usage()
    print(f"   Quota usage: {quota_usage}")

    # Test cache stats
    print("\n4. Testing cache stats...")
    cache_stats = dm.get_cache_stats()
    print(f"   Cache entries: {cache_stats['total_entries']}")

    # Test session listing
    print("\n5. Testing session listing...")
    sessions = dm.list_available_sessions()
    print(f"   Available sessions: {len(sessions)}")

    # Test session resuming
    print("\n6. Testing session resuming...")
    if sessions:
        resumed = dm.resume_session(sessions[0]["session_id"])
        print(f"   Resumed session: {resumed}")

    print("\nDataManager test completed!")