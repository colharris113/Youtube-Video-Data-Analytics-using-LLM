"""
Test script to find valid YouTube Analytics API dimensions.
"""
import sys
sys.path.append('.')

from auth_manager import get_auth_manager

# Common dimension names to test
DIMENSIONS_TO_TEST = [
    'trafficSourceDetail',
    'trafficSourceType',  # Original with capital T
    'trafficSource',      # What we tried
    'traffic_source',     # Maybe with underscore
    'insightTrafficSourceDetail',
    'insightTrafficSourceType',
]

def test_dimensions():
    """Test which dimension names are valid."""
    auth_manager = get_auth_manager()
    if not auth_manager.is_authenticated():
        print("Not authenticated. Please authenticate first.")
        return

    service = auth_manager.get_analytics_service()
    if not service:
        print("Failed to get analytics service")
        return

    print("Testing dimension names...")
    print("=" * 50)

    for dimension in DIMENSIONS_TO_TEST:
        print(f"\nTesting dimension: {dimension}")
        try:
            # Try a simple query
            request = service.reports().query(
                ids='channel==MINE',
                startDate='2025-11-01',
                endDate='2025-11-30',
                metrics='views',
                dimensions=dimension,
                maxResults=10
            )
            response = request.execute()
            print(f"✅ SUCCESS: {dimension} is valid")
            if 'rows' in response:
                print(f"   Found {len(response.get('rows', []))} rows")
        except Exception as e:
            error_msg = str(e)
            if 'Unknown identifier' in error_msg:
                print(f"❌ FAILED: {dimension} - Unknown identifier")
            else:
                print(f"❌ FAILED: {dimension} - {error_msg[:100]}...")

    print("\n" + "=" * 50)
    print("Testing common dimension combinations...")

    # Test some known valid dimensions first
    KNOWN_VALID = ['day', 'video', 'country', 'ageGroup', 'gender']
    for dimension in KNOWN_VALID:
        print(f"\nTesting known dimension: {dimension}")
        try:
            request = service.reports().query(
                ids='channel==MINE',
                startDate='2025-11-01',
                endDate='2025-11-30',
                metrics='views',
                dimensions=dimension,
                maxResults=10
            )
            response = request.execute()
            print(f"✅ {dimension} works")
        except Exception as e:
            print(f"❌ {dimension} failed: {str(e)[:100]}...")

if __name__ == "__main__":
    test_dimensions()