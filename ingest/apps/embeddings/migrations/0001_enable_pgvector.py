"""
Enable pgvector extension for PostgreSQL.
This migration ensures the vector extension is available before creating vector fields.
"""

from django.db import migrations


class Migration(migrations.Migration):
    
    initial = True
    
    dependencies = []
    
    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;",
        ),
    ]
