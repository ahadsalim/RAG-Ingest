from django.db import connection
from pgvector.django import VectorExtension, VectorField
from django.db import migrations

def create_vector_extension(apps, schema_editor):
    """Create the vector extension if it doesn't exist."""
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")

class Migration(migrations.Migration):
    """Migration to optimize pgvector for semantic search."""
    
    dependencies = [
        ('embeddings', '0001_initial'),  # Adjust if needed
    ]

    operations = [
        migrations.RunPython(create_vector_extension, reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(
            sql="""
            -- Create IVFFLAT index for approximate search
            CREATE INDEX IF NOT EXISTS embeddings_embedding_ivfflat_idx 
            ON embeddings_embedding 
            USING ivfflat (vector vector_cosine_ops)
            WITH (lists = 1000);
            
            -- Add a generated column for normalized vector (for faster cosine similarity)
            ALTER TABLE embeddings_embedding 
            ADD COLUMN IF NOT EXISTS vector_norm FLOAT GENERATED ALWAYS AS (sqrt(vector <-> vector)) STORED;
            
            -- Create index for filtering by model_name and dimension
            CREATE INDEX IF NOT EXISTS embeddings_model_dimension_idx 
            ON embeddings_embedding (model_name, dimension);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS embeddings_embedding_ivfflat_idx;
            DROP INDEX IF EXISTS embeddings_model_dimension_idx;
            ALTER TABLE embeddings_embedding DROP COLUMN IF EXISTS vector_norm;
            """
        ),
    ]
