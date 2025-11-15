#!/usr/bin/env python
"""Test script to verify user activity report works correctly."""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings.prod')
sys.path.insert(0, '/app')
django.setup()

from datetime import datetime, timedelta
from django.utils import timezone
from ingest.apps.accounts.admin_views import generate_user_activity_report

# Test with last 30 days
end_date = timezone.now().date()
start_date = end_date - timedelta(days=30)

from_date = start_date.strftime('%Y-%m-%d')
to_date = end_date.strftime('%Y-%m-%d')

print(f"Testing report generation from {from_date} to {to_date}")

try:
    report_data = generate_user_activity_report(from_date, to_date)
    print(f"✓ Report generated successfully!")
    print(f"✓ Total records: {len(report_data)}")
    
    if report_data:
        first_row = report_data[0]
        print(f"\n✓ Sample row:")
        print(f"  - User: {first_row.get('user')}")
        print(f"  - Date (object): {first_row.get('date')} (type: {type(first_row.get('date'))})")
        print(f"  - Date (string): {first_row.get('date_str')}")
        print(f"  - Work hours: {first_row.get('work_hours')}")
        print(f"  - Activities: {first_row.get('activities')}")
        
        # Test Jalali conversion
        from ingest.core.jalali import to_jalali_date
        jalali = to_jalali_date(first_row.get('date'))
        print(f"  - Jalali date: {jalali}")
        print(f"\n✓ Jalali conversion works!")
    else:
        print("\nℹ️  No data in the date range (this is normal if no activity logged)")
        
    print("\n✅ All tests passed!")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
