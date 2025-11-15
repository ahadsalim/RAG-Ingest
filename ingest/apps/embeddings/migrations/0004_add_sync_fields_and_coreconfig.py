# Generated manually for Core sync functionality

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('embeddings', '0003_change_vector_dimension_to_768'),
    ]

    operations = [
        # Add sync tracking fields to Embedding model
        migrations.AddField(
            model_name='embedding',
            name='synced_to_core',
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name='همگام‌سازی با Core',
                help_text='آیا این embedding به Core ارسال شده است؟'
            ),
        ),
        migrations.AddField(
            model_name='embedding',
            name='synced_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='زمان همگام‌سازی',
                help_text='آخرین زمان ارسال به Core'
            ),
        ),
        migrations.AddField(
            model_name='embedding',
            name='sync_error',
            field=models.TextField(
                blank=True,
                default='',
                verbose_name='خطای همگام‌سازی',
                help_text='پیام خطا در صورت شکست sync'
            ),
        ),
        migrations.AddField(
            model_name='embedding',
            name='sync_retry_count',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='تعداد تلاش مجدد'
            ),
        ),
        migrations.AddField(
            model_name='embedding',
            name='metadata_hash',
            field=models.CharField(
                max_length=64,
                blank=True,
                default='',
                db_index=True,
                verbose_name='هش متادیتا',
                help_text='هش SHA256 از metadata برای detect کردن تغییرات'
            ),
        ),
        migrations.AddField(
            model_name='embedding',
            name='last_metadata_sync',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='آخرین sync متادیتا'
            ),
        ),
        
        # Create CoreConfig model
        migrations.CreateModel(
            name='CoreConfig',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('core_api_url', models.URLField(default='http://localhost:7001', help_text='مثال: http://localhost:7001', verbose_name='آدرس API Core')),
                ('core_api_key', models.CharField(blank=True, help_text='API Key برای احراز هویت', max_length=200, verbose_name='کلید API')),
                ('qdrant_host', models.CharField(blank=True, default='localhost', max_length=200, verbose_name='آدرس Qdrant')),
                ('qdrant_port', models.PositiveIntegerField(default=7333, verbose_name='پورت Qdrant')),
                ('qdrant_api_key', models.CharField(blank=True, max_length=200, verbose_name='Qdrant API Key')),
                ('qdrant_collection', models.CharField(default='legal_documents', max_length=100, verbose_name='نام Collection')),
                ('auto_sync_enabled', models.BooleanField(default=True, help_text='فعال‌سازی sync خودکار به Core', verbose_name='همگام‌سازی خودکار')),
                ('sync_batch_size', models.PositiveIntegerField(default=100, verbose_name='تعداد رکورد در هر batch')),
                ('sync_interval_minutes', models.PositiveIntegerField(default=5, verbose_name='فاصله زمانی sync (دقیقه)')),
                ('retry_on_error', models.BooleanField(default=True, verbose_name='تلاش مجدد در صورت خطا')),
                ('max_retries', models.PositiveIntegerField(default=3, verbose_name='حداکثر تلاش مجدد')),
                ('track_metadata_changes', models.BooleanField(default=True, help_text='در صورت تغییر metadata، دوباره به Core ارسال شود', verbose_name='پیگیری تغییرات metadata')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('last_successful_sync', models.DateTimeField(blank=True, null=True, verbose_name='آخرین sync موفق')),
                ('last_sync_error', models.TextField(blank=True, verbose_name='آخرین خطا')),
                ('total_synced', models.PositiveIntegerField(default=0, verbose_name='تعداد کل sync شده')),
                ('total_errors', models.PositiveIntegerField(default=0, verbose_name='تعداد کل خطاها')),
            ],
            options={
                'verbose_name': 'تنظیمات Core',
                'verbose_name_plural': 'تنظیمات Core',
            },
        ),
        
        # Add indexes for better performance
        migrations.AddIndex(
            model_name='embedding',
            index=models.Index(fields=['synced_to_core', 'created_at'], name='embeddings_synced_created_idx'),
        ),
        migrations.AddIndex(
            model_name='embedding',
            index=models.Index(fields=['metadata_hash'], name='embeddings_metadata_hash_idx'),
        ),
    ]
