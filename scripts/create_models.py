#!/usr/bin/env python3
import os
import sys
import django

# Add the project root to Python path
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings.production')

django.setup()

from ingest.apps.embeddings.models import EmbeddingModel

# Create default models
base_model, created = EmbeddingModel.objects.get_or_create(
    name='intfloat/multilingual-e5-base',
    defaults={
        'display_name': 'E5 Base (768d)',
        'dimension': 768,
        'is_active': True,
        'description': 'Multilingual E5 Base model with 768 dimensions'
    }
)
print(f'Base model: {"created" if created else "already exists"}')
print('Default embedding models setup completed!')
