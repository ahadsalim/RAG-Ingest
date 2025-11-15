"""
Management command برای تست دریافت Node از Core
"""
from django.core.management.base import BaseCommand
import requests
import json
from ingest.apps.embeddings.models import CoreConfig
from ingest.apps.documents.models import Chunk


class Command(BaseCommand):
    help = 'تست دریافت یک نمونه Node از Core API'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('🔍 تست: دریافت یک نمونه Node از Core')
        self.stdout.write('=' * 80)
        
        # پیدا کردن یک chunk با node_id
        chunk = Chunk.objects.filter(node_id__isnull=False).first()
        
        if not chunk:
            self.stdout.write(self.style.ERROR('❌ هیچ Chunk با node_id یافت نشد'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'✅ Chunk یافت شد: {chunk.id}'))
        self.stdout.write(f'   • node_id: {chunk.node_id}')
        self.stdout.write(f'   • text: {chunk.chunk_text[:80]}...')
        
        if chunk.unit:
            self.stdout.write(f'   • از LegalUnit: {chunk.unit_id}')
        elif chunk.qaentry:
            self.stdout.write(f'   • از QAEntry: {chunk.qaentry_id}')
        
        self.stdout.write('')
        self.stdout.write('📡 دریافت از Core API...')
        
        # دریافت از Core
        config = CoreConfig.get_config()
        url = f'{config.core_api_url}/api/v1/sync/node/{chunk.node_id}'
        
        try:
            response = requests.get(
                url,
                headers={'X-API-Key': config.core_api_key},
                timeout=30
            )
            
            self.stdout.write(f'Status Code: {response.status_code}')
            
            if response.status_code == 200:
                node_data = response.json()
                
                self.stdout.write('')
                self.stdout.write('=' * 80)
                self.stdout.write('📦 اطلاعات کامل Node:')
                self.stdout.write('=' * 80)
                self.stdout.write(json.dumps(node_data, indent=2, ensure_ascii=False))
                
                self.stdout.write('')
                self.stdout.write('=' * 80)
                self.stdout.write('📋 تحلیل ساختار:')
                self.stdout.write('=' * 80)
                
                if 'id' in node_data:
                    self.stdout.write(f'🆔 Node ID: {node_data["id"]}')
                
                if 'vector' in node_data:
                    vector = node_data['vector']
                    self.stdout.write('🔢 Vector:')
                    self.stdout.write(f'   • Dimension: {len(vector)}')
                    self.stdout.write(f'   • Type: {type(vector).__name__}')
                    self.stdout.write(f'   • Sample (5 اول): {vector[:5]}')
                    self.stdout.write(f'   • Sample (5 آخر): {vector[-5:]}')
                
                if 'payload' in node_data:
                    payload = node_data['payload']
                    self.stdout.write('')
                    self.stdout.write(f'📝 Payload ({len(payload)} fields):')
                    for key, value in payload.items():
                        value_type = type(value).__name__
                        if isinstance(value, str):
                            if len(value) > 150:
                                self.stdout.write(f'   • {key} ({value_type}): {value[:150]}...')
                            else:
                                self.stdout.write(f'   • {key} ({value_type}): {value}')
                        elif isinstance(value, dict):
                            self.stdout.write(f'   • {key} ({value_type}): {len(value)} items')
                        elif isinstance(value, list):
                            self.stdout.write(f'   • {key} ({value_type}): {len(value)} items')
                        else:
                            self.stdout.write(f'   • {key} ({value_type}): {value}')
                
                self.stdout.write('')
                self.stdout.write('=' * 80)
                self.stdout.write(self.style.SUCCESS('✅ موفقیت‌آمیز! Node در Core موجود است'))
                self.stdout.write('=' * 80)
            else:
                self.stdout.write(self.style.ERROR(f'❌ خطا: {response.status_code}'))
                self.stdout.write(f'Response: {response.text[:500]}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Exception: {e}'))
            import traceback
            traceback.print_exc()
