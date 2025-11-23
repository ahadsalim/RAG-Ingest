#!/usr/bin/env python
"""
تست LUnit Admin برای پیدا کردن خطا
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings')
sys.path.insert(0, '/srv/ingest')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from ingest.apps.documents.admin_lunit import LUnitAdmin
from ingest.apps.documents.models import LUnit, InstrumentManifestation
from ingest.admin import admin_site

print('=' * 60)
print('🧪 تست LUnit Admin')
print('=' * 60)
print()

# 1. تست Admin Class
print('1. تست Admin Class:')
try:
    admin = LUnitAdmin(LUnit, admin_site)
    print('   ✅ LUnitAdmin instantiated')
except Exception as e:
    print(f'   ❌ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 2. تست Changelist View
print('2. تست Changelist View:')
try:
    factory = RequestFactory()
    request = factory.get('/admin/documents/lunit/')
    request.user = User.objects.filter(is_superuser=True).first()
    
    response = admin.changelist_view(request)
    print(f'   ✅ Response status: {response.status_code}')
    
    if response.status_code == 200:
        print('   ✅ Changelist view OK')
    else:
        print(f'   ⚠️  Status: {response.status_code}')
        
except Exception as e:
    print(f'   ❌ Error: {e}')
    import traceback
    traceback.print_exc()

print()

# 3. تست Add View
print('3. تست Add View (با manifestation):')
try:
    manif = InstrumentManifestation.objects.first()
    if manif:
        request = factory.get(f'/admin/documents/lunit/add/?manifestation={manif.id}')
        request.user = User.objects.filter(is_superuser=True).first()
        
        # Get form
        form_class = admin.get_form(request)
        print(f'   ✅ Form class: {form_class.__name__}')
        
        # Instantiate form
        form = form_class()
        print(f'   ✅ Form instantiated')
        print(f'   ✅ Fields: {list(form.fields.keys())[:5]}...')
        
        # بررسی parent field
        if 'parent' in form.fields:
            parent_field = form.fields['parent']
            print(f'   ✅ Parent widget: {type(parent_field.widget).__name__}')
    else:
        print('   ⚠️  No manifestation found')
        
except Exception as e:
    print(f'   ❌ Error: {e}')
    import traceback
    traceback.print_exc()

print()

# 4. تست Search Parents
print('4. تست Search Parents:')
try:
    manif = InstrumentManifestation.objects.first()
    if manif:
        request = factory.get(f'/admin/documents/lunit/search-parents/?q=1&manifestation_id={manif.id}')
        request.user = User.objects.filter(is_superuser=True).first()
        
        response = admin.search_parents_view(request)
        print(f'   ✅ Response status: {response.status_code}')
        
        if response.status_code == 200:
            import json
            data = json.loads(response.content)
            print(f'   ✅ Results: {len(data.get("results", []))} items')
    else:
        print('   ⚠️  No manifestation found')
        
except Exception as e:
    print(f'   ❌ Error: {e}')
    import traceback
    traceback.print_exc()

print()
print('=' * 60)
print('✅ تست تکمیل شد')
print('=' * 60)
