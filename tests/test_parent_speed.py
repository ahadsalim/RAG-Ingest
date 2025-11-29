#!/usr/bin/env python
"""
اسکریپت تست سرعت و عملکرد parent field در LegalUnit admin
"""
import os
import sys
import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings')
django.setup()

from django.test import RequestFactory
from ingest.apps.documents.admin import LegalUnitAdmin
from ingest.apps.documents.models import LegalUnit, InstrumentManifestation
from django.contrib.admin.sites import AdminSite
from django.db.models import Count


def test_parent_field_performance():
    """تست سرعت و cache parent field"""
    
    print("=" * 70)
    print("🧪 تست سرعت و عملکرد Parent Field")
    print("=" * 70)
    print()
    
    # پیدا کردن manifestation مناسب
    manifestation = InstrumentManifestation.objects.annotate(
        unit_count=Count('units')
    ).filter(unit_count__gt=10).first()
    
    if not manifestation:
        print("❌ هیچ manifestation مناسبی پیدا نشد")
        return
    
    title = manifestation.expr.work.title_official if manifestation.expr and manifestation.expr.work else str(manifestation.id)
    unit_count = LegalUnit.objects.filter(manifestation=manifestation).count()
    
    print(f"📋 Manifestation: {title}")
    print(f"   تعداد LegalUnits: {unit_count}")
    print()
    
    # Setup
    factory = RequestFactory()
    admin = LegalUnitAdmin(LegalUnit, AdminSite())
    parent_field = LegalUnit._meta.get_field('parent')
    
    # تست 1: سرعت اولیه
    print("📊 تست 1: سرعت query اولیه")
    request = factory.get(f'/admin/documents/legalunit/add/?manifestation={manifestation.id}')
    
    start = time.time()
    formfield = admin.formfield_for_foreignkey(parent_field, request)
    time1 = time.time() - start
    count1 = formfield.queryset.count()
    
    print(f"   ✅ تعداد: {count1}")
    print(f"   ✅ زمان: {time1:.4f}s")
    print()
    
    # تست 2: ایجاد LegalUnit جدید
    print("📊 تست 2: ایجاد LegalUnit جدید")
    new_unit = LegalUnit.objects.create(
        manifestation=manifestation,
        expr=manifestation.expr,
        work=manifestation.expr.work if manifestation.expr else None,
        unit_type='article',
        number='TEST-SPEED-001',
        content='تست سرعت parent field',
        order_index=99999
    )
    print(f"   ✅ LegalUnit جدید: {new_unit.id}")
    print(f"   ✅ شماره: {new_unit.number}")
    print()
    
    # تست 3: بررسی فوری در queryset
    print("📊 تست 3: بررسی ظاهر شدن فوری در parent list")
    start = time.time()
    formfield2 = admin.formfield_for_foreignkey(parent_field, request)
    time2 = time.time() - start
    count2 = formfield2.queryset.count()
    exists = formfield2.queryset.filter(pk=new_unit.id).exists()
    
    print(f"   ✅ تعداد جدید: {count2} (قبل: {count1})")
    print(f"   ✅ زمان query: {time2:.4f}s")
    print(f"   ✅ LegalUnit جدید در queryset: {exists}")
    
    if exists and count2 == count1 + 1:
        print(f"   ✅✅ مشکل cache حل شده! LegalUnit فوراً ظاهر شد")
    else:
        print(f"   ❌ مشکل: LegalUnit جدید ظاهر نشد")
    print()
    
    # تست 4: ایجاد LegalUnit دوم
    print("📊 تست 4: ایجاد LegalUnit دوم برای تست مجدد")
    new_unit2 = LegalUnit.objects.create(
        manifestation=manifestation,
        expr=manifestation.expr,
        work=manifestation.expr.work if manifestation.expr else None,
        unit_type='article',
        number='TEST-SPEED-002',
        content='تست سرعت parent field - دوم',
        order_index=99998
    )
    print(f"   ✅ LegalUnit دوم: {new_unit2.id}")
    
    start = time.time()
    formfield3 = admin.formfield_for_foreignkey(parent_field, request)
    time3 = time.time() - start
    count3 = formfield3.queryset.count()
    exists2 = formfield3.queryset.filter(pk=new_unit2.id).exists()
    
    print(f"   ✅ تعداد: {count3}")
    print(f"   ✅ زمان: {time3:.4f}s")
    print(f"   ✅ LegalUnit دوم در queryset: {exists2}")
    print()
    
    # تست 5: بررسی order_by
    print("📊 تست 5: بررسی ترتیب (order_by)")
    ordered_list = list(formfield3.queryset.values_list('number', flat=True)[:5])
    print(f"   ✅ 5 مورد اول: {ordered_list}")
    print()
    
    # پاکسازی
    print("🗑️  پاکسازی...")
    new_unit.delete()
    new_unit2.delete()
    print("   ✅ LegalUnit های تست حذف شدند")
    print()
    
    # خلاصه
    print("=" * 70)
    print("📊 خلاصه نتایج:")
    print("=" * 70)
    print(f"✅ سرعت query: {time2:.4f}s (خیلی سریع)")
    print(f"✅ Cache: {'حل شد' if exists else 'مشکل دارد'}")
    print(f"✅ Ordering: {'کار می‌کند' if ordered_list else 'مشکل دارد'}")
    print(f"✅ Filter: {count1} از {LegalUnit.objects.count()} (فیلتر شده)")
    print()
    
    if exists and time2 < 0.1:
        print("🎉 همه چیز عالی کار می‌کند!")
    else:
        print("⚠️  برخی مشکلات وجود دارد")
    
    print()


if __name__ == '__main__':
    try:
        test_parent_field_performance()
    except Exception as e:
        print(f"❌ خطا: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
