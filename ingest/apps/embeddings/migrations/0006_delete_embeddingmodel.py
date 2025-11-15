# Generated manually to remove unused EmbeddingModel

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('embeddings', '0004_add_sync_fields_and_coreconfig'),
    ]

    operations = [
        migrations.DeleteModel(
            name='EmbeddingModel',
        ),
    ]
