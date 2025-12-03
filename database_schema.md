# YouTube Analytics Database Schema

## Overview
This document describes the SQLite database schema for the YouTube Video Data Analytics platform. The schema supports API response caching, session state persistence, and historical data storage.

## Database Files

1. **`youtube_cache.db`** - API response caching and quota tracking
2. **`youtube_state.db`** - Session state and user data persistence
3. **`youtube_analytics.db`** - Historical analytics data (future use)

## Schema 1: Cache Database (`youtube_cache.db`)

### Table: `cache`
Stores API responses with TTL (Time To Live) management.

```sql
CREATE TABLE cache (
    cache_key TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    response_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_cache_endpoint` ON `cache(endpoint)`
- `idx_cache_expires` ON `cache(expires_at)`

### Table: `quota_tracking`
Tracks API quota usage by date.

```sql
CREATE TABLE quota_tracking (
    date TEXT PRIMARY KEY,
    total_calls INTEGER DEFAULT 0,
    cached_calls INTEGER DEFAULT 0,
    quota_units_used INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `session_state`
Stores user session data for persistence across page refreshes.

```sql
CREATE TABLE session_state (
    session_id TEXT PRIMARY KEY,
    session_name TEXT,
    session_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

**Index:**
- `idx_session_expires` ON `session_state(expires_at)`

## Schema 2: State Database (`youtube_state.db`)

### Table: `sessions`
Manages analysis sessions with metadata.

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    session_name TEXT NOT NULL,
    session_type TEXT NOT NULL,  -- 'channel_analysis', 'competitor_analysis', 'content_analysis'
    channel_name TEXT,
    api_key_hash TEXT,  -- Hashed for security
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    metadata TEXT  -- JSON metadata about the session
);
```

**Indexes:**
- `idx_sessions_type` ON `sessions(session_type)`
- `idx_sessions_active` ON `sessions(is_active)`

### Table: `session_data`
Stores serialized session data (pickle or JSON).

```sql
CREATE TABLE session_data (
    data_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    data_type TEXT NOT NULL,  -- 'video_data', 'channel_data', 'analysis_results', 'settings'
    data_key TEXT NOT NULL,  -- Key for this data (e.g., 'df_videos', 'df_competitors')
    data_blob BLOB,  -- Serialized data (pickle)
    data_json TEXT,  -- JSON data for simple structures
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
);
```

**Indexes:**
- `idx_session_data_type` ON `session_data(data_type)`
- `idx_session_data_session` ON `session_data(session_id)`

### Table: `user_preferences`
Stores user preferences and settings.

```sql
CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY,
    preferences TEXT NOT NULL,  -- JSON preferences
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Schema 3: Analytics Database (`youtube_analytics.db`) - Future Use

### Table: `channels`
Stores channel metadata.

```sql
CREATE TABLE channels (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT NOT NULL,
    description TEXT,
    subscriber_count INTEGER,
    video_count INTEGER,
    view_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `videos`
Stores video metadata and statistics.

```sql
CREATE TABLE videos (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    published_at TIMESTAMP,
    duration_seconds INTEGER,
    content_type TEXT,  -- 'Short', 'Regular', 'Long-form', 'Live'
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    engagement_rate REAL,
    performance_score REAL,
    performance_grade TEXT,
    thumbnail_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
);
```

### Table: `daily_metrics`
Stores daily performance metrics.

```sql
CREATE TABLE daily_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    video_id TEXT,
    metric_date DATE NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    watch_time_minutes INTEGER,
    subscribers_gained INTEGER,
    subscribers_lost INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels (channel_id),
    FOREIGN KEY (video_id) REFERENCES videos (video_id),
    UNIQUE(channel_id, video_id, metric_date)
);
```

### Table: `traffic_sources`
Stores traffic source analytics.

```sql
CREATE TABLE traffic_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    source_date DATE NOT NULL,
    source_type TEXT NOT NULL,  -- 'YouTube search', 'External', 'Suggested videos', etc.
    views INTEGER DEFAULT 0,
    watch_time_minutes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels (channel_id),
    UNIQUE(channel_id, source_date, source_type)
);
```

### Table: `demographics`
Stores demographic analytics.

```sql
CREATE TABLE demographics (
    demo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    demo_date DATE NOT NULL,
    age_group TEXT,  -- '18-24', '25-34', etc.
    gender TEXT,  -- 'male', 'female', 'other'
    views INTEGER DEFAULT 0,
    watch_time_minutes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels (channel_id),
    UNIQUE(channel_id, demo_date, age_group, gender)
);
```

## Data Flow

### 1. API Response Caching
```
YouTube API Request → CacheManager.get() → Cache Hit → Return Cached Data
                                   ↓ Cache Miss
                                   ↓ YouTube API Call → CacheManager.set() → Store in cache
```

### 2. Session State Management
```
Streamlit Session State → StateManager.save_session_state() → Store in session_data
Page Refresh → StateManager.load_session_state() → Restore Streamlit Session State
```

### 3. Data Persistence Layers
```
Layer 1: In-memory session state (fast, current session)
Layer 2: Local SQLite database (persistent across sessions)
Layer 3: Cached API responses (reduces API calls)
Layer 4: Live API calls (fresh data when needed)
```

## TTL (Time To Live) Configuration

| Data Type | Default TTL | Description |
|-----------|-------------|-------------|
| Channel Data | 24 hours | Channel metadata changes infrequently |
| Video Data | 12 hours | Video statistics update regularly |
| Analytics Data | 6 hours | Analytics data updates daily |
| Search Results | 1 hour | Search results are time-sensitive |
| Session State | 7 days | User sessions expire after a week |
| Cache Default | 2 hours | General cache TTL |

## Security Considerations

1. **API Key Storage**: Only store hashed API keys (`api_key_hash`)
2. **Sensitive Data**: Store in `.env` file, not in database
3. **Data Encryption**: Consider encrypting sensitive session data
4. **Access Control**: SQLite file permissions restrict access

## Migration Strategy

1. **Version 1.0**: Basic cache and session tables
2. **Version 1.1**: Add analytics tables for historical data
3. **Version 1.2**: Add user preferences and advanced metrics
4. **Version 2.0**: Support for multiple users and organizations

## Performance Optimization

1. **Indexes**: All foreign keys and frequently queried columns indexed
2. **Connection Pooling**: Reuse database connections
3. **Batch Operations**: Use transactions for multiple operations
4. **Cleanup Jobs**: Regular cleanup of expired data
5. **Database VACUUM**: Periodic database optimization

## Integration Points

### With CacheManager
```python
from cache_manager import get_cache_manager

cache_manager = get_cache_manager()
cached_response = cache_manager.get(endpoint, params)
if cached_response:
    return cached_response
```

### With StateManager
```python
from state_manager import get_state_manager

state_manager = get_state_manager()
state_manager.save_session_state(session_id, {
    "df_videos": df,
    "settings": settings,
    "analysis_results": results
})
```

### With Streamlit
```python
import streamlit as st
from state_manager import get_state_manager

# Auto-save on state change
@st.cache_data(ttl=300)  # 5 minutes
def get_data_with_cache():
    state_manager = get_state_manager()
    return state_manager.load_session_state("current_session")
```

## Backup and Recovery

1. **Automatic Backups**: Daily backup of database files
2. **Export Functionality**: Export sessions as JSON/CSV
3. **Import Functionality**: Import previous sessions
4. **Data Validation**: Validate data integrity on load

## Monitoring and Maintenance

1. **Database Size**: Monitor growth and clean up old data
2. **Cache Hit Rate**: Track cache effectiveness
3. **API Quota Usage**: Monitor and alert on quota limits
4. **Session Statistics**: Track active sessions and usage patterns

This schema provides a robust foundation for the YouTube Analytics platform with efficient caching, persistent session management, and scalable data storage.