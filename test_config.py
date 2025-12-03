#!/usr/bin/env python3
"""
Test script for YouTube Analytics configuration system.
Tests configuration loading from:
1. System environment variables (highest priority)
2. .env file (if exists)
3. Default values in config.py (lowest priority)
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing YouTube Analytics Configuration System")
print("=" * 50)
print("Configuration loading order:")
print("1. [PRIORITY 1] System environment variables (highest priority)")
print("2. [PRIORITY 2] .env file (if exists)")
print("3. [PRIORITY 3] Default values in config.py (lowest priority)")
print("=" * 50)

try:
    from config import (
        YOUTUBE_API_KEY,
        DEFAULT_CHANNEL,
        DEFAULT_MAX_RESULTS,
        DEFAULT_ORDER,
        OLLAMA_BASE_URL,
        OLLAMA_MODEL,
        SHORT_MAX_DURATION,
        LONG_MIN_DURATION,
        RIVAL_CHANNELS,
        validate_config,
        get_config_summary
    )

    print("[OK] Configuration module imported successfully")
    print()

    # Test configuration values
    print("Configuration Values:")
    print(f"  YouTube API Key: {'[SET]' if YOUTUBE_API_KEY and YOUTUBE_API_KEY != 'AIzaSyAh-_Q2C198OuyuZJTHqMUDr2hsGTp7lQ4' else '[DEFAULT - Set YOUTUBE_API_KEY]'}")
    print(f"  Default Channel: {DEFAULT_CHANNEL}")
    print(f"  Max Results: {DEFAULT_MAX_RESULTS}")
    print(f"  Default Order: {DEFAULT_ORDER}")
    print(f"  Ollama URL: {OLLAMA_BASE_URL}")
    print(f"  Ollama Model: {OLLAMA_MODEL}")
    print(f"  Short Max Duration: {SHORT_MAX_DURATION}s (videos < {SHORT_MAX_DURATION}s are Shorts)")
    print(f"  Long Min Duration: {LONG_MIN_DURATION}s (videos > {LONG_MIN_DURATION}s are Long-form)")
    print(f"  Rival Channels: {len(RIVAL_CHANNELS)} configured")
    print()

    # Test validation
    print("Configuration Validation:")
    is_valid = validate_config()
    print(f"  Valid: {is_valid}")
    print()

    # Test summary
    print("Configuration Summary:")
    summary = get_config_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print()
    print("[OK] All configuration tests passed!")

except ImportError as e:
    print(f"[ERROR] Failed to import configuration: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error during configuration test: {e}")
    sys.exit(1)

print()
print("=" * 50)
print("Configuration test completed successfully!")
print()
print("Next steps:")
print("1. Copy .env.example to .env and fill in your values:")
print("   cp .env.example .env")
print("   # Edit .env with your API key and channel name")
print()
print("2. Add rival channels to RIVAL_CHANNELS list in config.py")
print("   # Open config.py and add channel names to the RIVAL_CHANNELS list")
print()
print("3. Run the Streamlit app:")
print("   streamlit run youtube_analytics_app.py")
print()
print("Pro tip: Use environment variables for production:")
print("   export YOUTUBE_API_KEY=your_key_here")
print("   export DEFAULT_YOUTUBE_CHANNEL=your_channel_name")