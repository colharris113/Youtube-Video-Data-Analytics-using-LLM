"""
Utility functions for YouTube Video Data Analytics

Contains helper functions that don't have Streamlit dependencies
to avoid circular imports.
"""

import re
import math
from typing import Optional
from datetime import datetime

# Import config values
try:
    from config import SHORT_MAX_DURATION, LONG_MIN_DURATION
except ImportError:
    # Fallback defaults
    SHORT_MAX_DURATION = 60
    LONG_MIN_DURATION = 1800


def parse_duration_to_seconds(duration_iso: str) -> int:
    """
    Parse ISO 8601 duration string to total seconds.
    Examples: "PT1H30M15S" -> 5415, "PT5M30S" -> 330, "PT60S" -> 60
    """
    if not duration_iso or not duration_iso.startswith("PT"):
        return 0

    # Remove PT prefix
    duration = duration_iso[2:]
    total_seconds = 0

    # Parse hours
    if "H" in duration:
        hours_part = duration.split("H")[0]
        total_seconds += int(hours_part) * 3600
        duration = duration.split("H")[1] if "H" in duration else ""

    # Parse minutes
    if "M" in duration:
        minutes_part = duration.split("M")[0]
        total_seconds += int(minutes_part) * 60
        duration = duration.split("M")[1] if "M" in duration else ""

    # Parse seconds
    if "S" in duration:
        seconds_part = duration.split("S")[0]
        total_seconds += int(seconds_part)

    return total_seconds


def classify_content_type(duration_seconds: int, live_status: str = None) -> str:
    """
    Classify video content type based on duration and live status.
    Uses thresholds from config.py (SHORT_MAX_DURATION, LONG_MIN_DURATION).
    """
    # Check for live streams first (both 'live' and 'upcoming' are live streams)
    if live_status and live_status in ["live", "upcoming"]:
        return "Live"

    # Classify based on duration
    if duration_seconds <= SHORT_MAX_DURATION:
        return "Short"
    elif duration_seconds > LONG_MIN_DURATION:  # Use > not >= for exclusive threshold
        return "Long-form"
    else:
        return "Regular"


def calculate_video_performance_score(views: int, likes: int, comments: int, duration_seconds: int) -> dict:
    """
    Calculate a performance score for a video based on multiple metrics.
    Returns a dictionary with scores and letter grade (A-F).
    """
    if views == 0:
        return {
            "performance_score": 0,
            "performance_grade": "F",
            "engagement_score": 0,
            "popularity_score": 0,
            "interaction_score": 0
        }

    # Engagement score (likes/views ratio) - weighted 40%
    engagement_rate = (likes / views) * 100
    engagement_score = min(engagement_rate * 2, 40)  # Max 40 points

    # Interaction score (comments/views ratio) - weighted 30%
    comment_rate = (comments / views) * 100
    interaction_score = min(comment_rate * 3, 30)  # Max 30 points

    # Popularity score (views scaling) - weighted 30%
    # Logarithmic scale: log10(views) * 10, capped at 30
    if views > 0:
        popularity_score = min(math.log10(views) * 10, 30)
    else:
        popularity_score = 0

    # Total performance score (0-100)
    total_score = engagement_score + interaction_score + popularity_score

    # Letter grade
    if total_score >= 90:
        grade = "A"
    elif total_score >= 80:
        grade = "B"
    elif total_score >= 70:
        grade = "C"
    elif total_score >= 60:
        grade = "D"
    elif total_score >= 40:
        grade = "E"
    else:
        grade = "F"

    return {
        "performance_score": round(total_score, 1),
        "performance_grade": grade,
        "engagement_score": round(engagement_score, 1),
        "popularity_score": round(popularity_score, 1),
        "interaction_score": round(interaction_score, 1)
    }


def format_duration_human_readable(duration_seconds: int) -> str:
    """
    Convert duration in seconds to human-readable format.
    Examples: 65 -> "1:05", 3665 -> "1:01:05"
    """
    if duration_seconds <= 0:
        return "0:00"

    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


# Common stop words for keyword extraction
STOP = set("a an and are as at be but by for from has have i in is it its of on or that the this to was were will with you your we our".split())


def extract_keywords(query: str) -> list:
    """
    Extract keywords from a query string.
    """
    phrases = re.findall(r'\"([^\"]+)\"', query)
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z-']+", query) if len(w) > 3 and w.lower() not in STOP]
    return list(set([w.lower() for w in words + phrases]))


def extract_keyword_frequencies(text: str, top_n: int = 20) -> list:
    """
    Extract keyword frequencies from text.
    Returns list of (keyword, frequency) tuples sorted by frequency.
    """
    # Extract words (similar to extract_keywords but with frequency counting)
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z-']+", text)
             if len(w) > 3 and w.lower() not in STOP]

    # Count frequencies
    freq_dict = {}
    for word in words:
        freq_dict[word] = freq_dict.get(word, 0) + 1

    # Sort by frequency (descending) and get top_n
    sorted_freq = sorted(freq_dict.items(), key=lambda x: x[1], reverse=True)
    return sorted_freq[:top_n]


def keyword_filter_indices(df, keywords: list) -> list:
    """
    Filter DataFrame indices based on keywords in title or description.
    """
    if df.empty or not keywords:
        return []

    mask = False
    for kw in keywords:
        m = df["Title"].str.contains(kw, case=False, na=False) | df["Description"].str.contains(kw, case=False, na=False)
        mask = m if isinstance(mask, bool) and not mask else (mask | m)

    return df[mask].index.astype(int).tolist()


if __name__ == "__main__":
    # Test the utility functions
    print("Testing utility functions...")

    # Test duration parsing
    print("1. Duration parsing:")
    print(f"   PT1H30M15S -> {parse_duration_to_seconds('PT1H30M15S')} seconds")
    print(f"   PT5M30S -> {parse_duration_to_seconds('PT5M30S')} seconds")
    print(f"   PT60S -> {parse_duration_to_seconds('PT60S')} seconds")

    # Test content classification
    print("\n2. Content classification:")
    print(f"   45s -> {classify_content_type(45)}")
    print(f"   120s -> {classify_content_type(120)}")
    print(f"   2000s -> {classify_content_type(2000)}")
    print(f"   Live status -> {classify_content_type(120, 'live')}")

    # Test performance score
    print("\n3. Performance score:")
    score = calculate_video_performance_score(1000, 50, 10, 120)
    print(f"   1000 views, 50 likes, 10 comments: {score}")

    # Test duration formatting
    print("\n4. Duration formatting:")
    print(f"   65 seconds -> {format_duration_human_readable(65)}")
    print(f"   3665 seconds -> {format_duration_human_readable(3665)}")

    print("\nUtility functions test completed!")