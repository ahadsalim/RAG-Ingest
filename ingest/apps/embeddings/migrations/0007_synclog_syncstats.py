# Generated migration

from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('embeddings', '0006_delete_embeddingmodel'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('node_id', models.UUIDField(db_index=True, help_text='UUID نود در Core/Qdrant', verbose_name='Node ID')),
                ('embedding_id', models.UUIDField(db_index=True, help_text='UUID امبدینگ در Ingest', verbose_name='Embedding ID')),
                ('synced_at', models.DateTimeField(db_index=True, verbose_name='زمان Sync')),
                ('verified_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان Verification')),
                ('status', models.CharField(choices=[('synced', 'Synced'), ('verified', 'Verified'), ('failed', 'Failed'), ('pending_retry', 'Pending Retry')], db_index=True, default='synced', max_length=20, verbose_name='وضعیت')),
                ('retry_count', models.PositiveIntegerField(default=0, verbose_name='تعداد تلاش مجدد')),
                ('error_message', models.TextField(blank=True, verbose_name='پیام خطا')),
                ('core_response', models.JSONField(blank=True, null=True, verbose_name='Response از Core')),
            ],
            options={
                'verbose_name': 'Sync Log',
                'verbose_name_plural': 'Sync Logs',
                'ordering': ['-synced_at'],
            },
        ),
        migrations.CreateModel(
            name='SyncStats',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان')),
                ('total_embeddings', models.IntegerField(verbose_name='کل Embeddings')),
                ('synced_count', models.IntegerField(verbose_name='Synced')),
                ('verified_count', models.IntegerField(verbose_name='Verified')),
                ('failed_count', models.IntegerField(verbose_name='Failed')),
                ('pending_count', models.IntegerField(verbose_name='Pending')),
                ('core_total_nodes', models.IntegerField(blank=True, null=True, verbose_name='تعداد نودها در Core')),
                ('sync_percentage', models.FloatField(default=0.0, verbose_name='درصد Sync')),
                ('verification_percentage', models.FloatField(default=0.0, verbose_name='درصد Verification')),
            ],
            options={
                'verbose_name': 'Sync Stats',
                'verbose_name_plural': 'Sync Stats',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['node_id', 'status'], name='embeddings_node_id_status_idx'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['embedding_id', 'status'], name='embeddings_embedding_id_status_idx'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['status', 'synced_at'], name='embeddings_status_synced_at_idx'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['status', 'retry_count'], name='embeddings_status_retry_count_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='synclog',
            unique_together={('node_id', 'embedding_id')},
        ),
    ]
