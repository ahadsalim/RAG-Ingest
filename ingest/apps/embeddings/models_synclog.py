"""
SyncLog model for tracking node synchronization to Core API.
فقط برای Chunks (هم از LegalUnit و هم از QAEntry)
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from ingest.apps.masterdata.models import BaseModel


class SyncLog(BaseModel):
    """
    Log برای track کردن sync chunks به Core.
    هر Chunk یک node_id در Core/Qdrant دارد.
    """
    
    SYNC_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('verified', 'Verified'),
        ('failed', 'Failed'),
        ('pending_retry', 'Pending Retry'),
    ]
    
    # Node ID در Core/Qdrant
    node_id = models.UUIDField(
        verbose_name='Node ID',
        help_text='UUID نود در Core/Qdrant',
        db_index=True
    )
    
    # Reference به Chunk
    chunk = models.ForeignKey(
        'documents.Chunk',
        on_delete=models.CASCADE,
        related_name='sync_logs',
        verbose_name='Chunk'
    )
    
    # Timestamps
    synced_at = models.DateTimeField(
        verbose_name='زمان Sync',
        db_index=True
    )
    
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان Verification'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default='synced',
        db_index=True,
        verbose_name='وضعیت'
    )
    
    # Retry
    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name='تعداد تلاش مجدد'
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        verbose_name='پیام خطا'
    )
    
    # Core response metadata
    core_response = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Response از Core'
    )
    
    class Meta:
        verbose_name = 'Sync Log'
        verbose_name_plural = 'Sync Logs'
        ordering = ['-synced_at']
        indexes = [
            models.Index(fields=['node_id', 'status']),
            models.Index(fields=['chunk', 'status']),
            models.Index(fields=['status', 'synced_at']),
            models.Index(fields=['status', 'retry_count']),
        ]
    
    def __str__(self):
        return f"SyncLog Chunk {self.chunk_id} - Node {self.node_id} - {self.status}"
    
    def get_source_type(self):
        """تشخیص اینکه Chunk از LegalUnit است یا QAEntry"""
        if self.chunk.unit:
            return 'legalunit'
        elif self.chunk.qaentry:
            return 'qaentry'
        return 'unknown'
    
    @classmethod
    def create_sync_log(cls, node_id: str, chunk, synced_at=None):
        """
        ایجاد log جدید برای sync.
        
        Args:
            node_id: UUID نود در Core
            chunk: Chunk instance
            synced_at: زمان sync (اختیاری)
        """
        if synced_at is None:
            synced_at = timezone.now()
        elif isinstance(synced_at, str):
            from django.utils.dateparse import parse_datetime
            synced_at = parse_datetime(synced_at) or timezone.now()
        
        # Convert to UUID if string
        if isinstance(node_id, str):
            node_id = uuid.UUID(node_id)
        
        return cls.objects.create(
            node_id=node_id,
            chunk=chunk,
            synced_at=synced_at,
            status='synced'
        )
    
    @classmethod
    def get_unverified_logs(cls, limit: int = 100):
        """دریافت log هایی که هنوز verify نشده‌اند."""
        return cls.objects.filter(
            status='synced',
            verified_at__isnull=True
        ).order_by('synced_at')[:limit]
    
    @classmethod
    def get_failed_logs(cls, max_retries: int = 3):
        """دریافت log های failed که می‌توانند retry شوند."""
        return cls.objects.filter(
            status__in=['failed', 'pending_retry'],
            retry_count__lt=max_retries
        ).order_by('synced_at')
    
    def mark_verified(self, core_response: dict = None):
        """علامت‌گذاری به عنوان verified."""
        self.status = 'verified'
        self.verified_at = timezone.now()
        if core_response:
            self.core_response = core_response
        self.save(update_fields=['status', 'verified_at', 'core_response', 'updated_at'])
    
    def mark_failed(self, error_message: str):
        """علامت‌گذاری به عنوان failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])
    
    def mark_pending_retry(self):
        """علامت‌گذاری برای retry."""
        self.status = 'pending_retry'
        self.retry_count += 1
        self.save(update_fields=['status', 'retry_count', 'updated_at'])


class SyncStats(models.Model):
    """
    آمار کلی sync برای monitoring.
    """
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='زمان'
    )
    
    # Local stats
    total_embeddings = models.IntegerField(verbose_name='کل Embeddings')
    synced_count = models.IntegerField(verbose_name='Synced')
    verified_count = models.IntegerField(verbose_name='Verified')
    failed_count = models.IntegerField(verbose_name='Failed')
    pending_count = models.IntegerField(verbose_name='Pending')
    
    # Core stats
    core_total_nodes = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='تعداد نودها در Core'
    )
    
    # Percentages
    sync_percentage = models.FloatField(
        default=0.0,
        verbose_name='درصد Sync'
    )
    
    verification_percentage = models.FloatField(
        default=0.0,
        verbose_name='درصد Verification'
    )
    
    class Meta:
        verbose_name = 'Sync Stats'
        verbose_name_plural = 'Sync Stats'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Stats {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
