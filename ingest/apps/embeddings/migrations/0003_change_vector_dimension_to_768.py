# Generated migration for changing vector dimension from 1024 to 768

from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('embeddings', '0002_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop the old vector column and recreate with new dimension
            sql="""
                ALTER TABLE embeddings_embedding 
                DROP COLUMN IF EXISTS vector CASCADE;
                
                ALTER TABLE embeddings_embedding 
                ADD COLUMN vector vector(768);
                
                -- Drop old indexes if they exist
                DROP INDEX IF EXISTS embeddings_embedding_vector_idx;
                
                -- Create new index for vector search
                CREATE INDEX embeddings_embedding_vector_idx 
                ON embeddings_embedding 
                USING ivfflat (vector vector_cosine_ops) 
                WITH (lists = 100);
                
                -- Also update historical table if it exists
                ALTER TABLE embeddings_historicalembedding 
                DROP COLUMN IF EXISTS vector CASCADE;
                
                ALTER TABLE embeddings_historicalembedding 
                ADD COLUMN vector vector(768);
            """,
            reverse_sql="""
                ALTER TABLE embeddings_embedding 
                DROP COLUMN IF EXISTS vector CASCADE;
                
                ALTER TABLE embeddings_embedding 
                ADD COLUMN vector vector(1024);
                
                DROP INDEX IF EXISTS embeddings_embedding_vector_idx;
                
                CREATE INDEX embeddings_embedding_vector_idx 
                ON embeddings_embedding 
                USING ivfflat (vector vector_cosine_ops) 
                WITH (lists = 100);
                
                ALTER TABLE embeddings_historicalembedding 
                DROP COLUMN IF EXISTS vector CASCADE;
                
                ALTER TABLE embeddings_historicalembedding 
                ADD COLUMN vector vector(1024);
            """
        ),
        migrations.AlterField(
            model_name='embedding',
            name='vector',
            field=pgvector.django.VectorField(dimensions=768, verbose_name='بردار'),
        ),
    ]
