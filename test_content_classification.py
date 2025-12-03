#!/usr/bin/env python3
"""
Test script for YouTube Analytics Content Type Classification.
Tests the parsing of ISO 8601 durations and content type classification.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing YouTube Analytics Content Type Classification")
print("=" * 60)

try:
    # Import the functions we need to test
    from youtube_analytics_app import parse_duration_to_seconds, classify_content_type
    from config import SHORT_MAX_DURATION, LONG_MIN_DURATION

    print(f"Configuration thresholds:")
    print(f"  Shorts: < {SHORT_MAX_DURATION} seconds")
    print(f"  Long-form: > {LONG_MIN_DURATION} seconds")
    print()

    # Test ISO 8601 duration parsing
    print("Testing ISO 8601 Duration Parsing:")
    test_durations = [
        ("PT30S", 30, "30 seconds"),
        ("PT1M", 60, "1 minute"),
        ("PT1M30S", 90, "1 minute 30 seconds"),
        ("PT5M", 300, "5 minutes"),
        ("PT1H", 3600, "1 hour"),
        ("PT1H30M", 5400, "1 hour 30 minutes"),
        ("PT1H30M15S", 5415, "1 hour 30 minutes 15 seconds"),
        ("PT2H", 7200, "2 hours"),
        ("", 0, "empty string"),
        ("invalid", 0, "invalid format"),
    ]

    all_passed = True
    for duration_iso, expected_seconds, description in test_durations:
        result = parse_duration_to_seconds(duration_iso)
        passed = result == expected_seconds
        status = "PASS" if passed else "FAIL"
        all_passed = all_passed and passed
        print(f"  {status}: {duration_iso:12} -> {result:5} seconds (expected: {expected_seconds:5}) - {description}")

    print()

    # Test content type classification
    print("Testing Content Type Classification:")
    test_cases = [
        # (duration_seconds, live_status, expected_type, description)
        (30, None, "Short", "30s video (Short)"),
        (30, "live", "Live", "30s live stream"),
        (30, "upcoming", "Live", "upcoming live stream"),
        (90, None, "Regular", "1.5m video (Regular)"),
        (300, None, "Regular", "5m video (Regular)"),
        (1800, None, "Regular", "30m video (Regular)"),
        (1801, None, "Long-form", "30m 1s video (Long-form)"),
        (3600, None, "Long-form", "1h video (Long-form)"),
        (7200, None, "Long-form", "2h video (Long-form)"),
        (0, None, "Short", "0 seconds (Short)"),
        (SHORT_MAX_DURATION, None, "Short", f"At threshold ({SHORT_MAX_DURATION}s)"),
        (SHORT_MAX_DURATION + 1, None, "Regular", f"Just above threshold ({SHORT_MAX_DURATION + 1}s)"),
        (LONG_MIN_DURATION, None, "Regular", f"At threshold ({LONG_MIN_DURATION}s)"),
        (LONG_MIN_DURATION - 1, None, "Regular", f"Just below threshold ({LONG_MIN_DURATION - 1}s)"),
    ]

    for duration, live_status, expected_type, description in test_cases:
        result = classify_content_type(duration, live_status)
        passed = result == expected_type
        status = "PASS" if passed else "FAIL"
        all_passed = all_passed and passed
        live_info = f", live: {live_status}" if live_status else ""
        print(f"  {status}: {duration:5}s{live_info:15} -> {result:12} (expected: {expected_type:12}) - {description}")

    print()
    print("=" * 60)

    if all_passed:
        print("[SUCCESS] All content type classification tests passed!")
        print()
        print("Content types will be classified as:")
        print(f"  - Short: Videos ≤ {SHORT_MAX_DURATION} seconds")
        print(f"  - Regular: Videos between {SHORT_MAX_DURATION + 1} and {LONG_MIN_DURATION - 1} seconds")
        print(f"  - Long-form: Videos ≥ {LONG_MIN_DURATION} seconds")
        print(f"  - Live: Any video with liveBroadcastContent = 'live' or 'upcoming'")
    else:
        print("[FAILURE] Some tests failed. Please check the implementation.")
        sys.exit(1)

except ImportError as e:
    print(f"[ERROR] Failed to import modules: {e}")
    print("Make sure you're running from the correct directory and dependencies are installed.")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    sys.exit(1)

print()
print("=" * 60)
print("Next: Run the Streamlit app to see content type analytics in action:")
print("  streamlit run youtube_analytics_app.py")
print()
print("Make sure to:")
print("  1. Create .env file with your YouTube API key")
print("  2. Set your default channel in .env or config.py")
print("  3. Run the app and fetch channel data to see content type analysis")