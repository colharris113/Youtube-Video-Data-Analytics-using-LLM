"""
YouTube Video Data Analytics Configuration

Configuration loading order (highest priority first):
1. System environment variables
2. .env file (if exists)
3. Default values in this file

Create a .env file from .env.example for sensitive data.
"""

import os
from typing import Optional

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Try to load from .env file in current directory
    env_loaded = load_dotenv()
    if env_loaded:
        print("[OK] Loaded environment variables from .env file")
    else:
        print("[INFO] No .env file found, using system environment variables and defaults")
except ImportError:
    print("[WARNING] python-dotenv not installed, skipping .env file loading")
    env_loaded = False

# ==================== YouTube API Configuration ====================
# Priority: 1. Environment variable 2. .env file 3. Empty string (no default)
# WARNING: Never hardcode API keys in source code!
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
DEFAULT_CHANNEL = os.getenv("DEFAULT_YOUTUBE_CHANNEL", "")

# ==================== OAuth 2.0 Configuration ====================
# Required for YouTube Analytics API (watch time, demographics, traffic sources)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

# ==================== Ollama Configuration ====================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")  # Default model for summarization

# ==================== App Configuration ====================
DEFAULT_MAX_RESULTS = int(os.getenv("DEFAULT_MAX_RESULTS", "50"))
DEFAULT_ORDER = os.getenv("DEFAULT_ORDER", "date")

# ==================== Analytics Configuration ====================
# Content type classification thresholds (seconds)
SHORT_MAX_DURATION = int(os.getenv("SHORT_MAX_DURATION", "60"))  # Videos under 60 seconds are considered Shorts
LONG_MIN_DURATION = int(os.getenv("LONG_MIN_DURATION", "1800"))  # Videos over 30 minutes are considered Long-form

# ==================== Rival Channels Configuration ====================
# List of competitor channels to compare against
# Format in .env: RIVAL_CHANNELS=Channel1,Channel2,Channel3
RIVAL_CHANNELS_STR = os.getenv("RIVAL_CHANNELS", "")
RIVAL_CHANNELS = [channel.strip() for channel in RIVAL_CHANNELS_STR.split(",") if channel.strip()]

# ==================== Validation Functions ====================
def validate_config() -> bool:
    """Validate configuration and return True if valid."""
    errors = []
    warnings = []

    # Critical errors (will cause app to fail)
    if not YOUTUBE_API_KEY:
        errors.append("YouTube API key is required. Set YOUTUBE_API_KEY environment variable or in .env file.")

    if not DEFAULT_CHANNEL:
        warnings.append("No default channel set. Set DEFAULT_YOUTUBE_CHANNEL environment variable or in .env file.")

    # OAuth configuration warnings (optional for basic functionality)
    oauth_configured = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    if not oauth_configured:
        warnings.append("OAuth credentials not configured. YouTube Analytics API features (watch time, demographics, traffic sources) will not be available. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env file.")
    else:
        print("[OK] OAuth credentials configured for YouTube Analytics API")

    # Check for client_secret.json file
    if os.path.exists("client_secret.json"):
        print("[OK] Found client_secret.json file for OAuth authentication")
    elif oauth_configured:
        print("[INFO] Using OAuth credentials from environment variables")

    # Warnings (app will work but might not be optimal)
    if YOUTUBE_API_KEY and len(YOUTUBE_API_KEY) < 20:
        warnings.append("YouTube API key appears to be too short. Please verify your API key.")

    if errors:
        print("Configuration ERRORS (must be fixed):")
        for error in errors:
            print(f"  - {error}")
        return False

    if warnings:
        print("Configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    return True

def get_config_summary() -> dict:
    """Return a summary of the current configuration."""
    return {
        "youtube_api_key_set": bool(YOUTUBE_API_KEY),
        "youtube_api_key_length": len(YOUTUBE_API_KEY) if YOUTUBE_API_KEY else 0,
        "default_channel": DEFAULT_CHANNEL or "[Not set]",
        "oauth_configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "client_secret_file_exists": os.path.exists("client_secret.json"),
        "ollama_configured": OLLAMA_BASE_URL != "http://localhost:11434",
        "ollama_model": OLLAMA_MODEL,
        "max_results": DEFAULT_MAX_RESULTS,
        "order": DEFAULT_ORDER,
        "rival_channels_count": len(RIVAL_CHANNELS),
        "short_max_duration": SHORT_MAX_DURATION,
        "long_min_duration": LONG_MIN_DURATION,
    }