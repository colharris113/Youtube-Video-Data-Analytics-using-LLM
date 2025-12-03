"""
State Manager for YouTube Video Data Analytics

Provides comprehensive session state management to:
1. Prevent data loss on page refresh
2. Enable resume functionality across sessions
3. Manage multiple analysis sessions
4. Integrate with API caching system
5. Provide auto-save functionality
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import logging
import pickle
import pandas as pd
from pathlib import Path
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StateManager:
    """Manages session state persistence with SQLite backend."""

    def __init__(self, db_path: str = None):
        """
        Initialize the state manager.

        Args:
            db_path: Path to SQLite database file (default: youtube_state.db in app directory)
        """
        if db_path is None:
            # Use absolute path in the same directory as this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(current_dir, "youtube_state.db")
        else:
            self.db_path = db_path

        self._init_database()
        logger.info(f"State manager initialized with database: {self.db_path}")

    def _init_database(self):
        """Initialize the state database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                session_name TEXT NOT NULL,
                session_type TEXT NOT NULL,
                channel_name TEXT,
                api_key_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                metadata TEXT
            )
        ''')

        # Session data table (stores serialized data)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_data (
                data_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                data_type TEXT NOT NULL,
                data_key TEXT NOT NULL,
                data_blob BLOB,
                data_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            )
        ''')

        # User preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                preferences TEXT NOT NULL,  -- JSON preferences
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_type ON sessions(session_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_data_type ON session_data(data_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_data_session ON session_data(session_id)')

        conn.commit()
        conn.close()

    def create_session(self, session_name: str, session_type: str,
                      channel_name: Optional[str] = None,
                      api_key: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      ttl_days: int = 30) -> str:
        """
        Create a new analysis session.

        Args:
            session_name: Descriptive name for the session
            session_type: Type of analysis ('channel_analysis', 'competitor_analysis', 'content_analysis')
            channel_name: Channel being analyzed
            api_key: API key (hashed for storage)
            metadata: Additional metadata about the session
            ttl_days: Days until session expires (default 30)

        Returns:
            Session ID
        """
        # Generate session ID
        timestamp = datetime.now().isoformat()
        session_id = hashlib.md5(f"{session_name}{timestamp}".encode()).hexdigest()[:16]

        # Hash API key for security
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else None

        expires_at = datetime.now() + timedelta(days=ttl_days)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO sessions
            (session_id, session_name, session_type, channel_name, api_key_hash, expires_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            session_name,
            session_type,
            channel_name,
            api_key_hash,
            expires_at.isoformat(),
            json.dumps(metadata) if metadata else None
        ))

        conn.commit()
        conn.close()

        logger.info(f"Created session: {session_id} - {session_name}")
        return session_id

    def save_data(self, session_id: str, data_type: str, data_key: str,
                 data: Any, use_json: bool = False):
        """
        Save data to a session.

        Args:
            session_id: Session identifier
            data_type: Type of data ('video_data', 'channel_data', 'analysis_results', 'settings')
            data_key: Key for this data
            data: Data to save
            use_json: Whether to store as JSON (for simple structures) or pickle (for complex)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if data already exists
        cursor.execute('''
            SELECT data_id FROM session_data
            WHERE session_id = ? AND data_type = ? AND data_key = ?
        ''', (session_id, data_type, data_key))

        existing = cursor.fetchone()

        if use_json or isinstance(data, (dict, list, str, int, float, bool, type(None))):
            # Store as JSON
            data_json = json.dumps(data, default=str)
            data_blob = None
        else:
            # Store as pickle
            data_blob = pickle.dumps(data)
            data_json = None

        if existing:
            # Update existing
            cursor.execute('''
                UPDATE session_data
                SET data_blob = ?, data_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE data_id = ?
            ''', (data_blob, data_json, existing[0]))
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO session_data (session_id, data_type, data_key, data_blob, data_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, data_type, data_key, data_blob, data_json))

        # Update session last accessed
        cursor.execute('''
            UPDATE sessions
            SET last_accessed = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (session_id,))

        conn.commit()
        conn.close()

        logger.debug(f"Saved data: {session_id}/{data_type}/{data_key}")

    def load_data(self, session_id: str, data_type: str, data_key: str) -> Optional[Any]:
        """
        Load data from a session.

        Args:
            session_id: Session identifier
            data_type: Type of data
            data_key: Key for this data

        Returns:
            Loaded data or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT data_blob, data_json FROM session_data
            WHERE session_id = ? AND data_type = ? AND data_key = ?
        ''', (session_id, data_type, data_key))

        row = cursor.fetchone()

        if row:
            data_blob, data_json = row

            # Update session last accessed
            cursor.execute('''
                UPDATE sessions
                SET last_accessed = CURRENT_TIMESTAMP
                WHERE session_id = ?
            ''', (session_id,))

            conn.commit()
            conn.close()

            if data_blob:
                # Load from pickle
                return pickle.loads(data_blob)
            elif data_json:
                # Load from JSON
                return json.loads(data_json)
        else:
            conn.close()

        return None

    def save_dataframe(self, session_id: str, df_key: str, df: pd.DataFrame):
        """
        Save a pandas DataFrame to a session.

        Args:
            session_id: Session identifier
            df_key: Key for this DataFrame
            df: DataFrame to save
        """
        # Convert DataFrame to JSON for storage
        if not df.empty:
            # Store as JSON for DataFrames (more portable than pickle)
            df_json = df.to_json(orient='split', date_format='iso')
            self.save_data(session_id, 'dataframe', df_key, df_json, use_json=True)
            logger.debug(f"Saved DataFrame: {session_id}/{df_key} ({len(df)} rows)")
        else:
            logger.warning(f"Attempted to save empty DataFrame: {df_key}")

    def load_dataframe(self, session_id: str, df_key: str) -> Optional[pd.DataFrame]:
        """
        Load a pandas DataFrame from a session.

        Args:
            session_id: Session identifier
            df_key: Key for this DataFrame

        Returns:
            Loaded DataFrame or None if not found
        """
        df_json = self.load_data(session_id, 'dataframe', df_key)
        if df_json:
            try:
                df = pd.read_json(df_json, orient='split')
                logger.debug(f"Loaded DataFrame: {session_id}/{df_key} ({len(df)} rows)")
                return df
            except Exception as e:
                logger.error(f"Error loading DataFrame {df_key}: {e}")
                return None
        return None

    def save_session_state(self, session_id: str, state_dict: Dict[str, Any]):
        """
        Save complete session state (multiple data items).

        Args:
            session_id: Session identifier
            state_dict: Dictionary of data items to save
        """
        for key, value in state_dict.items():
            if isinstance(value, pd.DataFrame):
                self.save_dataframe(session_id, key, value)
            else:
                self.save_data(session_id, 'state', key, value, use_json=True)

        logger.info(f"Saved session state: {session_id} ({len(state_dict)} items)")

    def load_session_state(self, session_id: str) -> Dict[str, Any]:
        """
        Load complete session state.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary of loaded data items
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT data_key, data_blob, data_json FROM session_data
            WHERE session_id = ? AND data_type IN ('state', 'dataframe')
        ''', (session_id,))

        rows = cursor.fetchall()

        # Update session last accessed
        cursor.execute('''
            UPDATE sessions
            SET last_accessed = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (session_id,))

        conn.commit()
        conn.close()

        state_dict = {}
        for data_key, data_blob, data_json in rows:
            if data_blob:
                state_dict[data_key] = pickle.loads(data_blob)
            elif data_json:
                try:
                    # Try to parse as DataFrame first
                    if data_key.endswith('_df') or 'dataframe' in data_key.lower():
                        state_dict[data_key] = pd.read_json(data_json, orient='split')
                    else:
                        state_dict[data_key] = json.loads(data_json)
                except:
                    state_dict[data_key] = data_json

        logger.info(f"Loaded session state: {session_id} ({len(state_dict)} items)")
        return state_dict

    def list_sessions(self, session_type: Optional[str] = None,
                     active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all saved sessions.

        Args:
            session_type: Filter by session type
            active_only: Only show active sessions

        Returns:
            List of session information dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT session_id, session_name, session_type, channel_name,
                   created_at, last_accessed, expires_at, is_active, metadata
            FROM sessions
            WHERE 1=1
        '''
        params = []

        if session_type:
            query += ' AND session_type = ?'
            params.append(session_type)

        if active_only:
            query += ' AND is_active = 1'

        query += ' ORDER BY last_accessed DESC'

        cursor.execute(query, params)

        sessions = []
        for row in cursor.fetchall():
            expires_at = row[6]
            is_expired = expires_at and datetime.fromisoformat(expires_at) < datetime.now()

            sessions.append({
                'session_id': row[0],
                'session_name': row[1],
                'session_type': row[2],
                'channel_name': row[3],
                'created_at': row[4],
                'last_accessed': row[5],
                'expires_at': expires_at,
                'is_active': bool(row[7]),
                'is_expired': is_expired,
                'metadata': json.loads(row[8]) if row[8] else {},
                'data_count': self._get_session_data_count(row[0])
            })

        conn.close()
        return sessions

    def _get_session_data_count(self, session_id: str) -> int:
        """Get count of data items in a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM session_data WHERE session_id = ?
        ''', (session_id,))

        count = cursor.fetchone()[0]
        conn.close()
        return count

    def delete_session(self, session_id: str):
        """
        Delete a session and all its data.

        Args:
            session_id: Session identifier
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete session data (cascade)
        cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted:
            logger.info(f"Deleted session: {session_id}")
        else:
            logger.warning(f"Session not found: {session_id}")

    def deactivate_session(self, session_id: str):
        """
        Deactivate a session (soft delete).

        Args:
            session_id: Session identifier
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE sessions SET is_active = 0 WHERE session_id = ?
        ''', (session_id,))

        updated = cursor.rowcount
        conn.commit()
        conn.close()

        if updated:
            logger.info(f"Deactivated session: {session_id}")
        else:
            logger.warning(f"Session not found: {session_id}")

    def cleanup_expired(self, delete_data: bool = True):
        """
        Clean up expired sessions.

        Args:
            delete_data: Whether to delete data or just deactivate
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if delete_data:
            # Delete expired sessions and their data
            cursor.execute('''
                DELETE FROM sessions
                WHERE expires_at < CURRENT_TIMESTAMP AND is_active = 1
            ''')
            deleted = cursor.rowcount
            action = "deleted"
        else:
            # Just deactivate expired sessions
            cursor.execute('''
                UPDATE sessions
                SET is_active = 0
                WHERE expires_at < CURRENT_TIMESTAMP AND is_active = 1
            ''')
            deleted = cursor.rowcount
            action = "deactivated"

        conn.commit()
        conn.close()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired sessions ({action})")

    def save_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """
        Save user preferences.

        Args:
            user_id: User identifier
            preferences: Preferences dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO user_preferences (user_id, preferences, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, json.dumps(preferences)))

        conn.commit()
        conn.close()

        logger.debug(f"Saved preferences for user: {user_id}")

    def load_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Load user preferences.

        Args:
            user_id: User identifier

        Returns:
            Preferences dictionary or empty dict if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT preferences FROM user_preferences WHERE user_id = ?
        ''', (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        return {}

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored sessions.

        Returns:
            Statistics dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total sessions
        cursor.execute('SELECT COUNT(*) FROM sessions')
        total_sessions = cursor.fetchone()[0]

        # Active sessions
        cursor.execute('SELECT COUNT(*) FROM sessions WHERE is_active = 1')
        active_sessions = cursor.fetchone()[0]

        # Expired sessions
        cursor.execute('''
            SELECT COUNT(*) FROM sessions
            WHERE expires_at < CURRENT_TIMESTAMP AND is_active = 1
        ''')
        expired_sessions = cursor.fetchone()[0]

        # Total data items
        cursor.execute('SELECT COUNT(*) FROM session_data')
        total_data_items = cursor.fetchone()[0]

        # Sessions by type
        cursor.execute('''
            SELECT session_type, COUNT(*)
            FROM sessions
            WHERE is_active = 1
            GROUP BY session_type
        ''')
        sessions_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'expired_sessions': expired_sessions,
            'total_data_items': total_data_items,
            'sessions_by_type': sessions_by_type,
            'database_size_mb': self._get_database_size_mb()
        }

    def _get_database_size_mb(self) -> float:
        """Get database file size in MB."""
        try:
            size_bytes = Path(self.db_path).stat().st_size
            return round(size_bytes / (1024 * 1024), 2)
        except:
            return 0.0


# Global state manager instance
_state_manager = None


def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def auto_save_session(session_id: str, state_vars: Dict[str, Any],
                     interval_minutes: int = 5):
    """
    Decorator for auto-saving session state at intervals.

    Args:
        session_id: Session identifier
        state_vars: Dictionary of state variables to save
        interval_minutes: Auto-save interval in minutes
    """
    last_save = datetime.now()

    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal last_save

            # Call the function
            result = func(*args, **kwargs)

            # Check if it's time to auto-save
            now = datetime.now()
            if (now - last_save).total_seconds() >= interval_minutes * 60:
                state_manager = get_state_manager()
                state_manager.save_session_state(session_id, state_vars)
                last_save = now
                logger.debug(f"Auto-saved session: {session_id}")

            return result
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test the state manager
    print("Testing StateManager...")

    # Create state manager
    sm = StateManager("test_state.db")

    # Test session creation
    print("\n1. Testing session creation...")
    session_id = sm.create_session(
        session_name="Test Analysis",
        session_type="channel_analysis",
        channel_name="Test Channel",
        api_key="test_api_key",
        metadata={"test": "data"}
    )
    print(f"   Created session: {session_id}")

    # Test data saving
    print("\n2. Testing data saving...")
    test_data = {"key1": "value1", "key2": 123, "key3": [1, 2, 3]}
    sm.save_data(session_id, "test_data", "test_key", test_data, use_json=True)
    print("   Saved test data")

    # Test DataFrame saving
    print("\n3. Testing DataFrame saving...")
    test_df = pd.DataFrame({
        "A": [1, 2, 3],
        "B": ["x", "y", "z"]
    })
    sm.save_dataframe(session_id, "test_df", test_df)
    print(f"   Saved DataFrame: {len(test_df)} rows")

    # Test data loading
    print("\n4. Testing data loading...")
    loaded_data = sm.load_data(session_id, "test_data", "test_key")
    print(f"   Loaded data: {loaded_data}")

    loaded_df = sm.load_dataframe(session_id, "test_df")
    print(f"   Loaded DataFrame: {len(loaded_df)} rows")

    # Test session listing
    print("\n5. Testing session listing...")
    sessions = sm.list_sessions()
    for session in sessions:
        print(f"   Session: {session['session_name']} - {session['session_type']}")

    # Test session state
    print("\n6. Testing session state...")
    state_dict = {
        "df_videos": test_df,
        "settings": {"max_results": 50, "order": "date"},
        "analysis_results": {"score": 85, "grade": "B"}
    }
    sm.save_session_state(session_id, state_dict)

    loaded_state = sm.load_session_state(session_id)
    print(f"   Loaded state with {len(loaded_state)} items")

    # Test stats
    print("\n7. Testing statistics...")
    stats = sm.get_session_stats()
    print(f"   Active sessions: {stats['active_sessions']}")
    print(f"   Total data items: {stats['total_data_items']}")

    print("\nStateManager test completed!")
    print("\nNote: Test database 'test_state.db' can be deleted.")