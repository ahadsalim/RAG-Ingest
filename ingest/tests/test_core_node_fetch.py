"""
تست برای خواندن و نمایش یک نمونه Node از Core API
"""
import requests
import json
from django.test import TestCase
from ingest.apps.embeddings.models import CoreConfig, SyncLog
from ingest.apps.documents.models import Chunk


def fetch_node_from_core(node_id: str):
    """
    دریافت یک node از Core API
    
    Args:
        node_id: UUID نود
        
    Returns:
        dict: اطلاعات node یا None
    """
    config = CoreConfig.get_config()
    
    # Endpoint: GET /api/v1/sync/node/{node_id}
    url = f"{config.core_api_url}/api/v1/sync/node/{node_id}"
    
    try:
        response = requests.get(
            url,
            headers={'X-API-Key': config.core_api_key},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ خطا: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


def display_node(node_data: dict):
    """نمایش زیبای اطلاعات node"""
    print("=" * 80)
    print("📦 اطلاعات Node از Core")
    print("=" * 80)
    
    if not node_data:
        print("❌ هیچ داده‌ای دریافت نشد")
        return
    
    print(json.dumps(node_data, indent=2, ensure_ascii=False))
    
    print()
    print("=" * 80)
    print("📋 خلاصه:")
    print("=" * 80)
    
    # استخراج اطلاعات کلیدی
    if 'id' in node_data:
        print(f"🆔 Node ID: {node_data['id']}")
    
    if 'vector' in node_data:
        vector = node_data['vector']
        if isinstance(vector, list):
            print(f"🔢 Vector dimension: {len(vector)}")
            print(f"🔢 First 5 values: {vector[:5]}")
    
    if 'payload' in node_data or 'metadata' in node_data:
        payload = node_data.get('payload') or node_data.get('metadata', {})
        print()
        print("📝 Metadata:")
        for key, value in payload.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"   • {key}: {value[:100]}...")
            else:
                print(f"   • {key}: {value}")
    
    print("=" * 80)


def test_fetch_sample_node():
    """تست دریافت یک نمونه node"""
    
    print()
    print("🔍 جستجوی یک Chunk با node_id...")
    
    # پیدا کردن یک chunk با node_id
    chunk = Chunk.objects.filter(node_id__isnull=False).first()
    
    if not chunk:
        print("❌ هیچ Chunk با node_id یافت نشد")
        return
    
    print(f"✅ Chunk یافت شد: {chunk.id}")
    print(f"   • node_id: {chunk.node_id}")
    print(f"   • text length: {len(chunk.chunk_text)} chars")
    
    if chunk.unit:
        print(f"   • از LegalUnit: {chunk.unit_id}")
    elif chunk.qaentry:
        print(f"   • از QAEntry: {chunk.qaentry_id}")
    
    print()
    print("📡 دریافت از Core...")
    
    # دریافت از Core
    node_data = fetch_node_from_core(str(chunk.node_id))
    
    # نمایش
    if node_data:
        display_node(node_data)
        print()
        print("✅ موفقیت‌آمیز!")
    else:
        print("❌ خطا در دریافت node")


class CoreNodeFetchTest(TestCase):
    """تست‌های واحد برای دریافت Node از Core"""
    
    def test_fetch_node(self):
        """تست دریافت node"""
        test_fetch_sample_node()


if __name__ == '__main__':
    print("❌ این فایل نمی‌تواند مستقیماً اجرا شود.")
    print("✅ از یکی از روش‌های زیر استفاده کنید:")
    print()
    print("1️⃣ از Django shell:")
    print("   docker exec deployment-web-1 python manage.py shell")
    print("   >>> from ingest.tests.test_core_node_fetch import test_fetch_sample_node")
    print("   >>> test_fetch_sample_node()")
    print()
    print("2️⃣ یا از اسکریپت کمکی:")
    print("   docker exec deployment-web-1 python manage.py shell < /app/ingest/tests/run_test.py")
