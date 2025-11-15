# Generated migration - Simplify SyncLog (فقط Chunk)

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('embeddings', '0008_redesign_synclog'),
        ('documents', '0008_add_node_id'),
    ]

    operations = [
        # Drop old SyncLog
        migrations.DeleteModel(name='SyncLog'),
        
        # Create new simplified SyncLog
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                
                # Node ID
                ('node_id', models.UUIDField(db_index=True, help_text='UUID نود در Core/Qdrant', verbose_name='Node ID')),
                
                # Reference به Chunk
                ('chunk', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sync_logs',
                    to='documents.chunk',
                    verbose_name='Chunk'
                )),
                
                # Timestamps
                ('synced_at', models.DateTimeField(db_index=True, verbose_name='زمان Sync')),
                ('verified_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان Verification')),
                
                # Status
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('synced', 'Synced'),
                        ('verified', 'Verified'),
                        ('failed', 'Failed'),
                        ('pending_retry', 'Pending Retry')
                    ],
                    db_index=True,
                    default='synced',
                    max_length=20,
                    verbose_name='وضعیت'
                )),
                
                # Retry
                ('retry_count', models.PositiveIntegerField(default=0, verbose_name='تعداد تلاش مجدد')),
                
                # Error tracking
                ('error_message', models.TextField(blank=True, verbose_name='پیام خطا')),
                
                # Core response
                ('core_response', models.JSONField(blank=True, null=True, verbose_name='Response از Core')),
            ],
            options={
                'verbose_name': 'Sync Log',
                'verbose_name_plural': 'Sync Logs',
                'ordering': ['-synced_at'],
            },
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['node_id', 'status'], name='synclog_node_status_idx2'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['chunk', 'status'], name='synclog_chunk_status_idx2'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['status', 'synced_at'], name='synclog_status_synced_idx2'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['status', 'retry_count'], name='synclog_status_retry_idx2'),
        ),
    ]
