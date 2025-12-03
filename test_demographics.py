"""
Test demographic dimensions with different metrics.
"""
import sys
sys.path.append('.')

from auth_manager import get_auth_manager

def test_demographic_dimensions():
    """Test demographic dimension names with different metrics."""
    auth_manager = get_auth_manager()
    if not auth_manager.is_authenticated():
        print("Not authenticated.")
        return

    service = auth_manager.get_analytics_service()
    if not service:
        print("No analytics service.")
        return

    # Test demographic dimensions with different metrics
    dimensions = ['ageGroup', 'gender']
    metrics_list = ['views', 'estimatedMinutesWatched', 'averageViewDuration']

    print("Testing demographic dimensions...")
    for dimension in dimensions:
        print(f"\n--- Testing {dimension} ---")
        for metrics in metrics_list:
            try:
                request = service.reports().query(
                    ids='channel==MINE',
                    startDate='2025-11-01',
                    endDate='2025-11-30',
                    metrics=metrics,
                    dimensions=dimension,
                    maxResults=5
                )
                response = request.execute()
                rows = response.get('rows', [])
                print(f"  OK with {metrics:25} - Rows: {len(rows)}")
            except Exception as e:
                error = str(e)
                if 'Unknown identifier' in error:
                    print(f"  BAD with {metrics:25} - Unknown dimension")
                elif 'invalid' in error.lower():
                    print(f"  BAD with {metrics:25} - Invalid combination")
                else:
                    print(f"  ERR with {metrics:25} - {error[:60]}")

if __name__ == "__main__":
    test_demographic_dimensions()