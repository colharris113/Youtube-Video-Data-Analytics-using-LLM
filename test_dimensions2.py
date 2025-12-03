"""
Simple test to find valid YouTube Analytics API dimensions.
"""
import sys
sys.path.append('.')

from auth_manager import get_auth_manager

def test_simple_dimensions():
    """Test simple dimension names."""
    auth_manager = get_auth_manager()
    if not auth_manager.is_authenticated():
        print("Not authenticated.")
        return

    service = auth_manager.get_analytics_service()
    if not service:
        print("No analytics service.")
        return

    # Test some basic dimensions that should work
    test_cases = [
        ('day', 'Basic time dimension'),
        ('video', 'Video dimension'),
        ('country', 'Geography dimension'),
        ('ageGroup', 'Demographic dimension'),
        ('gender', 'Demographic dimension'),
        ('deviceType', 'Device dimension'),
        ('trafficSourceType', 'Traffic source - what we want'),
        ('trafficSource', 'Traffic source - alternative'),
        ('trafficSourceDetail', 'Traffic source detail'),
        ('insightTrafficSourceType', 'Insight traffic source'),
    ]

    print("Testing dimensions (using views metric)...")
    for dimension, description in test_cases:
        try:
            request = service.reports().query(
                ids='channel==MINE',
                startDate='2025-11-01',
                endDate='2025-11-30',
                metrics='views',
                dimensions=dimension,
                maxResults=5
            )
            response = request.execute()
            rows = response.get('rows', [])
            print(f"OK: {dimension:25} - {description:30} - Rows: {len(rows)}")
        except Exception as e:
            error = str(e)
            if 'Unknown identifier' in error:
                print(f"BAD: {dimension:25} - {description:30} - Unknown dimension")
            else:
                print(f"ERR: {dimension:25} - {description:30} - {error[:60]}")

if __name__ == "__main__":
    test_simple_dimensions()