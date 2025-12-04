from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericRelation
from django.db.models import Q, F, CheckConstraint
from mptt.models import MPTTModel, TreeForeignKey
from simple_history.models import HistoricalRecords
from datetime import date

from ingest.apps.masterdata.models import BaseModel
from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Language
from .enums import DocumentType, ConsolidationLevel, UnitType, QAStatus


class LegalUnitQuerySet(models.QuerySet):
    """Custom queryset for temporal queries on LegalUnit."""
    
    def as_of(self, on: date):
        """Return units that were valid on the given date."""
        return self.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=on),
            Q(valid_to__isnull=True) | Q(valid_to__gte=on),
        )
    
    def active(self):
        """Return units that are currently active."""
        from django.utils.timezone import localdate
        return self.as_of(localdate())
    
    def expired(self):
        """Return units that have expired."""
        from django.utils.timezone import localdate
        today = localdate()
        return self.filter(valid_to__lt=today)


class LegalUnitManager(models.Manager):
    """Custom manager for LegalUnit with temporal query support."""
    
    def get_queryset(self):
        return LegalUnitQuerySet(self.model, using=self._db)
    
    def as_of(self, on: date):
        """Return units that were valid on the given date."""
        return self.get_queryset().as_of(on)
    
    def active(self):
        """Return units that are currently active."""
        return self.get_queryset().active()
    
    def expired(self):
        """Return units that have expired."""
        return self.get_queryset().expired()


class InstrumentWork(BaseModel):
    """FRBR Work level - abstract legal document."""
    
    class Meta:
        verbose_name = "تعریف سند حقوقی"
        verbose_name_plural = "تعریف اسناد حقوقی"
        # unique_together removed to allow multiple documents from same authority
        indexes = [
            models.Index(fields=['doc_type', 'created_at']),
            models.Index(fields=['jurisdiction', 'authority']),
        ]
        
    title_official = models.CharField(max_length=500, verbose_name='عنوان رسمی')
    doc_type = models.CharField(
        max_length=20, 
        choices=DocumentType.choices, 
        default=DocumentType.LAW,
        verbose_name='نوع سند'
    )
    jurisdiction = models.ForeignKey(
        Jurisdiction,
        on_delete=models.CASCADE,
        related_name='instrument_works',
        verbose_name='حوزه قضایی'
    )
    authority = models.ForeignKey(
        IssuingAuthority,
        on_delete=models.CASCADE,
        related_name='instrument_works',
        verbose_name='مرجع صادرکننده'
    )
    urn_lex = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name='URN LEX',
        help_text='ir:authority:doc_type:yyyy-mm-dd:number<br>مثال: ir:majlis:law:2020-06-01:123'
    )
    primary_language = models.ForeignKey(
        'masterdata.Language',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        verbose_name='زبان اصلی'
    )
    subject_summary = models.TextField(blank=True, verbose_name='خلاصه موضوع')
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.title_official} ({self.get_doc_type_display()})"


class InstrumentExpression(BaseModel):
    """FRBR Expression level - specific language/version of a work."""
    
    class Meta:
        verbose_name = "تعریف نسخه سند"
        verbose_name_plural = "تعریف نسخه سند"
        unique_together = ['work', 'language', 'consolidation_level', 'expression_date']
        indexes = [
            models.Index(fields=['work', 'consolidation_level']),
            models.Index(fields=['expression_date']),
        ]
        
    work = models.ForeignKey(
        InstrumentWork,
        on_delete=models.CASCADE,
        related_name='expressions',
        verbose_name='سند حقوقی'
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='زبان'
    )
    consolidation_level = models.CharField(
        max_length=20,
        choices=ConsolidationLevel.choices,
        default=ConsolidationLevel.BASE,
        verbose_name='سطح تلفیق'
    )
    expression_date = models.DateField(verbose_name='تاریخ تصویب/ابلاغ', null=True, blank=True)
    eli_uri_expr = models.URLField(blank=True, verbose_name='ELI URI بیان')
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.work.title_official} - {self.language} ({self.expression_date})"


class InstrumentManifestation(BaseModel):
    """FRBR Manifestation level - physical/digital embodiment."""
    
    class RepealStatus(models.TextChoices):
        IN_FORCE = 'in_force', 'جاری و لازم الاجرا'
        REPEALED = 'repealed', 'لغو یا منسوخ شده'
    
    class Meta:
        verbose_name = "تعریف انتشار سند"
        verbose_name_plural = "تعریف انتشار سند"
        constraints = [
            models.CheckConstraint(
                check=models.Q(in_force_to__gte=models.F('in_force_from')) | models.Q(in_force_to__isnull=True),
                name='valid_in_force_period'
            )
        ]
        indexes = [
            models.Index(fields=['expr', 'publication_date']),
            models.Index(fields=['repeal_status', 'in_force_from']),
        ]
        
    expr = models.ForeignKey(
        InstrumentExpression,
        on_delete=models.CASCADE,
        related_name='manifestations',
        null=True,
        blank=True,
        verbose_name='نسخه سند'
    )
    publication_date = models.DateField(verbose_name='تاریخ انتشار')
    official_gazette_name = models.CharField(max_length=200, blank=True, verbose_name='نام روزنامه رسمی')
    gazette_issue_no = models.CharField(max_length=50, blank=True, verbose_name='شماره نامه')
    page_start = models.PositiveIntegerField(null=True, blank=True, verbose_name='صفحه شروع-پایان')
    source_url = models.URLField(blank=True, verbose_name='ELI URI / URL منبع')
    checksum_sha256 = models.CharField(max_length=64, unique=True, blank=True, verbose_name='چکسام SHA256')
    in_force_from = models.DateField(null=True, blank=True, verbose_name='اجرا از تاریخ')
    repeal_status = models.CharField(
        max_length=20,
        choices=RepealStatus.choices,
        default=RepealStatus.IN_FORCE,
        verbose_name='وضعیت سند'
    )
    in_force_to = models.DateField(
        null=True, 
        blank=True, 
        verbose_name='اجرا تا تاریخ',
        help_text='در صورتی که وضعیت سند "لغو یا منسوخ شده" باشد، این فیلد الزامی است.'
    )
    retrieval_date = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ بازیابی')
    
    def clean(self):
        super().clean()
        if self.repeal_status == self.RepealStatus.REPEALED and not self.in_force_to:
            raise ValidationError({
                'in_force_to': 'برای اسناد لغو شده، تعیین تاریخ پایان اجرا الزامی است.'
            })
    
    def save(self, *args, **kwargs):
        # تولید چکسام SHA256 خودکار بر اساس فیلدهای فرم
        import hashlib
        
        # ترکیب فیلدهای کلیدی برای تولید چکسام یکتا
        content_parts = [
            str(self.expr_id) if self.expr_id else '',
            str(self.publication_date) if self.publication_date else '',
            self.official_gazette_name or '',
            self.gazette_issue_no or '',
            str(self.page_start) if self.page_start else '',
            self.source_url or '',
            str(self.in_force_from) if self.in_force_from else '',
            self.repeal_status or '',
            str(self.in_force_to) if self.in_force_to else ''
        ]
        
        content = '|'.join(content_parts)
        self.checksum_sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        super().save(*args, **kwargs)
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.expr.work.title_official} - {self.publication_date}"


class LegalUnit(MPTTModel, BaseModel):
    """Hierarchical units within legal documents using MPTT."""
    # New FRBR references
    work = models.ForeignKey(
        'InstrumentWork',
        on_delete=models.CASCADE,
        related_name='units',
        verbose_name='سند حقوقی',
        null=True,
        blank=True,
        help_text='مرجع به سند حقوقی اصلی (FRBR Work)'
    )
    expr = models.ForeignKey(
        'InstrumentExpression',
        on_delete=models.CASCADE,
        related_name='units',
        verbose_name='نسخه سند',
        null=True,
        blank=True,
        help_text='مرجع به نسخه سند (FRBR Expression)'
    )
    manifestation = models.ForeignKey(
        'InstrumentManifestation',
        on_delete=models.SET_NULL,
        related_name='units',
        verbose_name='انتشار سند',
        null=True,
        blank=True
    )
    
    parent = TreeForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='children',
        verbose_name='والد'
    )
    unit_type = models.CharField(
        max_length=20, 
        choices=UnitType.choices,
        verbose_name='نوع واحد'
    )
    number = models.CharField(max_length=50, blank=True, verbose_name='شماره')
    order_index = models.CharField(max_length=50, blank=True, default='', verbose_name='ترتیب')
    path_label = models.CharField(max_length=500, blank=True, verbose_name='مسیر کامل')
    content = models.TextField(verbose_name='محتوا')
    
    # New Akoma Ntoso identifiers
    eli_fragment = models.CharField(max_length=200, blank=True, verbose_name='ELI Fragment')
    xml_id = models.CharField(max_length=100, blank=True, verbose_name='XML ID')
    
    # Many-to-many relationship with VocabularyTerm through intermediate model
    vocabulary_terms = models.ManyToManyField(
        'masterdata.VocabularyTerm',
        through='LegalUnitVocabularyTerm',
        blank=True,
        related_name='legal_units',
        verbose_name='برچسب‌ها'
    )
    
    # Temporal validity fields (Akoma Ntoso semantics)
    valid_from = models.DateField(
        null=True, 
        blank=True, 
        db_index=True,
        verbose_name='تاریخ ابلاغ/اجرا',
        help_text='در صورت عدم ورود مقدار، تاریخ اجرا از سند اصلی درج خواهد شد.'
    )
    valid_to = models.DateField(
        null=True, 
        blank=True, 
        db_index=True,
        verbose_name='تاریخ پایان اعتبار',
        help_text='تاریخ پایان اعتبار - خالی گذاشتن فیلد به معنی بدون تاریخ انقضا است.'
    )
    
    # Custom manager for temporal queries
    objects = LegalUnitManager()
    
    history = HistoricalRecords(excluded_fields=['lft', 'rght', 'tree_id', 'level'])

    class MPTTMeta:
        order_insertion_by = ['order_index']

    class Meta:
        verbose_name = 'جزء سند حقوقی'
        verbose_name_plural = 'اجزاء سند حقوقی'
        ordering = ['tree_id', 'lft']
        constraints = [
            CheckConstraint(
                name="valid_interval_order",
                check=Q(valid_to__gte=F("valid_from")) | Q(valid_to__isnull=True) | Q(valid_from__isnull=True)
            )
        ]
        indexes = [
            models.Index(fields=['work', 'unit_type']),
            models.Index(fields=['manifestation', 'order_index']),
            models.Index(fields=['parent', 'order_index']),
        ]

    def __str__(self):
        ref = self.work.title_official if self.work else 'بدون مرجع'
        return f"{ref} - {self.path_label}"

    @property
    def is_active(self):
        """Check if this unit is currently active based on validity dates."""
        from django.utils.timezone import localdate
        today = localdate()  # Gregorian date
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_to and today > self.valid_to:
            return False
        return True
    
    @property
    def embedding_text(self):
        """Generate normalized text for embedding generation."""
        from ingest.core.text_processing import prepare_for_embedding
        
        # Normalize content for better embedding quality
        if self.content:
            return prepare_for_embedding(self.content)
        return ""
    
    def clean(self):
        """Validate that valid_from <= valid_to when both are present."""
        super().clean()
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValidationError({
                'valid_to': 'تاریخ پایان اعتبار نمی‌تواند قبل از تاریخ شروع اعتبار باشد.'
            })

    def save(self, *args, **kwargs):
        # Auto-generate path_label
        current_label = f"{self.get_unit_type_display()} {self.number}".strip()
        if self.parent:
            self.path_label = f"{self.parent.path_label} > {current_label}"
        else:
            self.path_label = current_label
        
        # Normalize content text before saving
        if self.content:
            from ingest.core.text_processing import prepare_for_embedding
            # Normalize content and store it - chunks will use this normalized version
            self.content = prepare_for_embedding(self.content)
        
        super().save(*args, **kwargs)


class LUnit(LegalUnit):
    """
    Proxy model for LegalUnit with simplified admin interface.
    بازنویسی رابط کاربری LegalUnit با تجربه کاربری بهتر.
    """
    class Meta:
        proxy = True
        verbose_name = 'بند سند حقوقی'
        verbose_name_plural = 'بندهای اسناد حقوقی'


class LegalUnitChange(BaseModel):
    """
    Change log for legal amendments with effective dates.
    Follows Akoma Ntoso semantics for temporal validity.
    """
    
    class ChangeType(models.TextChoices):
        AMEND = "AMEND", "تعدیل"
        REPEAL = "REPEAL", "لغو"
        SUBSTITUTE = "SUBSTITUTE", "جایگزینی"
        ADD = "ADD", "اضافه"
        REMOVE = "REMOVE", "حذف"

    unit = models.ForeignKey(
        LegalUnit, 
        on_delete=models.CASCADE, 
        related_name="changes",
        verbose_name='واحد قانونی'
    )
    change_type = models.CharField(
        max_length=16, 
        choices=ChangeType.choices,
        verbose_name='نوع تغییر'
    )
    effective_date = models.DateField(
        db_index=True,
        verbose_name='تاریخ اجرا',
        help_text='تاریخ اجرای قانونی تغییر (Gregorian)'
    )
    
    # Optional linkage to the instrument/expression introducing the change
    source_expression = models.ForeignKey(
        'InstrumentExpression', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name="introduced_changes",
        verbose_name='نسخه سند مبدأ',
        help_text='نسخه سندی که این تغییر را معرفی کرده'
    )
    
    # Optional pointer to a superseding unit (for substitution cases)
    superseded_by = models.ForeignKey(
        LegalUnit, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name="supersedes",
        verbose_name='جایگزین شده با',
        help_text='واحد قانونی که جایگزین این واحد شده (برای جایگزینی)'
    )
    
    note = models.TextField(
        blank=True,
        verbose_name='یادداشت',
        help_text='توضیحات اضافی درباره تغییر'
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'تغییر واحد قانونی'
        verbose_name_plural = 'تغییرات واحدهای قانونی'
        ordering = ['-effective_date', '-created_at']
        indexes = [
            models.Index(fields=["unit", "effective_date"]),
            models.Index(fields=["effective_date"]),
            models.Index(fields=["change_type", "effective_date"]),
        ]

    def __str__(self):
        return f"{self.unit.path_label} - {self.get_change_type_display()} ({self.effective_date})"


class FileAsset(BaseModel):
    """Simple file storage model."""
    
    # Simple file field using Django's FileField with S3 storage
    file = models.FileField(
        upload_to='documents/',
        verbose_name='فایل',
        help_text='فایل مورد نظر را انتخاب کنید'
    )
    
    # Optional reference to legal unit
    legal_unit = models.ForeignKey(
        LegalUnit, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='files',
        verbose_name='جزء سند حقوقی'
    )
    
    # Optional reference to manifestation
    manifestation = models.ForeignKey(
        'InstrumentManifestation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='files',
        verbose_name='انتشار سند'
    )
    
    # Basic metadata
    description = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name='توضیحات'
    )
    
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True,
        blank=True,
        related_name='uploaded_files',
        verbose_name='آپلودکننده'
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'فایل ضمیمه'
        verbose_name_plural = 'فایل‌های ضمیمه'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.filename} - {self.description or 'بدون توضیحات'}"

    @property
    def filename(self):
        """Get original filename"""
        import os
        return os.path.basename(self.file.name) if self.file else ''
    
    @property
    def file_size(self):
        """Get file size in bytes"""
        try:
            return self.file.size if self.file else 0
        except:
            return 0
    
    @property
    def formatted_size(self):
        """Format file size in human readable format"""
        size = self.file_size
        if size < 1024:
            return f"{size} بایت"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} کیلوبایت"
        else:
            return f"{size / (1024 * 1024):.1f} مگابایت"


# Relations and Citations Models

class InstrumentRelation(BaseModel):
    """Relations between FRBR Works (e.g., amendments, repeals, references)."""
    from_work = models.ForeignKey(
        'InstrumentWork',
        on_delete=models.CASCADE,
        related_name='outgoing_relations',
        verbose_name='اثر مبدأ'
    )
    to_work = models.ForeignKey(
        'InstrumentWork',
        on_delete=models.CASCADE,
        related_name='incoming_relations',
        verbose_name='اثر مقصد'
    )
    relation_type = models.CharField(
        max_length=30,
        choices=[
            ('amends', 'اصلاح می‌کند'),
            ('repeals', 'لغو می‌کند'),
            ('references', 'ارجاع می‌دهد'),
            ('implements', 'اجرا می‌کند'),
            ('derives_from', 'مشتق از'),
            ('supersedes', 'جایگزین می‌شود'),
        ],
        verbose_name='نوع رابطه'
    )
    effective_date = models.DateField(null=True, blank=True, verbose_name='تاریخ اثر')
    notes = models.TextField(blank=True, verbose_name='یادداشت‌ها')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'رابطه ابزار حقوقی'
        verbose_name_plural = 'ارتباط اسناد حقوقی'
        unique_together = ['from_work', 'to_work', 'relation_type']

    def __str__(self):
        return f"{self.from_work.title_official} {self.get_relation_type_display()} {self.to_work.title_official}"


class PinpointCitation(BaseModel):
    """Precise citations between specific units of legal documents."""
    from_unit = models.ForeignKey(
        'LegalUnit',
        on_delete=models.CASCADE,
        related_name='outgoing_citations',
        verbose_name='سند مبدأ'
    )
    to_unit = models.ForeignKey(
        'LegalUnit',
        on_delete=models.CASCADE,
        related_name='incoming_citations',
        verbose_name='سند اشاره شده'
    )
    citation_type = models.CharField(
        max_length=20,
        choices=[
            ('direct', 'ارجاع مستقیم'),
            ('see_also', 'نگاه کنید به'),
            ('cf', 'مقایسه کنید'),
            ('but_see', 'اما نگاه کنید'),
            ('contra', 'در تضاد با'),
        ],
        default='direct',
        verbose_name='نوع ارجاع'
    )
    context_text = models.TextField(blank=True, verbose_name='متن زمینه')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ارجاع دقیق'
        verbose_name_plural = 'ارجاعات دقیق'

    def __str__(self):
        return f"{self.from_unit.path_label} → {self.to_unit.path_label}"


class LegalUnitVocabularyTerm(BaseModel):
    """Through model for LegalUnit-VocabularyTerm relationship with weight."""
    legal_unit = models.ForeignKey(
        'LegalUnit',
        on_delete=models.CASCADE,
        related_name='unit_vocabulary_terms',
        verbose_name='جزء سند'
    )
    vocabulary_term = models.ForeignKey(
        'masterdata.VocabularyTerm',
        on_delete=models.CASCADE,
        related_name='unit_vocabulary_terms',
        verbose_name='واژه'
    )
    weight = models.PositiveSmallIntegerField(
        default=5,
        help_text='وزن ارتباط (1 تا 10)',
        verbose_name='وزن'
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'برچسب جزء سند'
        verbose_name_plural = 'برچسب‌های اجزاء سند'
        unique_together = ['legal_unit', 'vocabulary_term']

    def __str__(self):
        return f"{self.legal_unit.path_label} - {self.vocabulary_term.term} (وزن: {self.weight})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.weight < 1 or self.weight > 10:
            raise ValidationError('وزن باید بین 1 تا 10 باشد.')


# Ingest and RAG Models

class Chunk(BaseModel):
    """Text chunks for embedding and retrieval (from LegalUnit or QAEntry)."""
    expr = models.ForeignKey(
        'InstrumentExpression',
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='نسخه سند',
        null=True,
        blank=True
    )
    unit = models.ForeignKey(
        'LegalUnit',
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='واحد حقوقی',
        null=True,
        blank=True
    )
    qaentry = models.ForeignKey(
        'QAEntry',
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name='ورودی QA',
        null=True,
        blank=True
    )
    
    chunk_text = models.TextField(verbose_name='متن چانک')
    token_count = models.PositiveIntegerField(verbose_name='تعداد توکن')
    overlap_prev = models.PositiveIntegerField(default=0, verbose_name='همپوشانی با قبلی')
    citation_payload_json = models.JSONField(verbose_name='اطلاعات ارجاع')
    hash = models.CharField(max_length=64, verbose_name='هش SHA-256')
    
    # Node ID in Core/Qdrant
    node_id = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name='Node ID در Core'
    )
    
    # Generic relation to embeddings
    embeddings = GenericRelation(
        "embeddings.Embedding",
        related_query_name="chunk",
        content_type_field="content_type",
        object_id_field="object_id",
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'قطعه متن (Chunk)'
        verbose_name_plural = 'قطعات متن (Chunks)'
        ordering = ['expr', 'unit', 'id']
        unique_together = ['expr', 'hash']
        indexes = [
            models.Index(fields=['unit', 'created_at']),
            models.Index(fields=['hash']),
        ]

    def __str__(self):
        return f"{self.unit.path_label} - چانک {self.token_count} توکن"


class IngestLog(BaseModel):
    """Log of data ingestion operations."""
    operation_type = models.CharField(
        max_length=20,
        choices=[
            ('create', 'ایجاد'),
            ('update', 'به‌روزرسانی'),
            ('delete', 'حذف'),
            ('bulk_import', 'واردات انبوه'),
            ('sync', 'همگام‌سازی'),
        ],
        verbose_name='نوع عملیات'
    )
    source_system = models.CharField(max_length=50, verbose_name='سیستم مبدأ', default='manual')
    source_id = models.CharField(max_length=100, blank=True, verbose_name='شناسه مبدأ')
    
    # Target object references
    target_work = models.ForeignKey(
        'InstrumentWork',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ingest_logs',
        verbose_name='اثر هدف'
    )
    target_expression = models.ForeignKey(
        'InstrumentExpression',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ingest_logs',
        verbose_name='بیان هدف'
    )
    target_manifestation = models.ForeignKey(
        'InstrumentManifestation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ingest_logs',
        verbose_name='تجلی هدف'
    )
    
    # Operation details
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'در انتظار'),
            ('processing', 'در حال پردازش'),
            ('success', 'موفق'),
            ('failed', 'ناموفق'),
            ('partial', 'جزئی'),
        ],
        default='pending',
        verbose_name='وضعیت'
    )
    records_processed = models.PositiveIntegerField(default=0, verbose_name='رکوردهای پردازش‌شده')
    records_failed = models.PositiveIntegerField(default=0, verbose_name='رکوردهای ناموفق')
    error_message = models.TextField(blank=True, verbose_name='پیام خطا')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='متادیتا')
    
    started_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='started_ingests',
        null=True,
        blank=True,
        verbose_name='شروع‌کننده'
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'لاگ واردات'
        verbose_name_plural = 'لاگ‌های واردات'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.get_status_display()} ({self.created_at})"


class QAEntry(BaseModel):
    """
    Question-Answer entries for legal document Q&A system.
    Compatible with current FRBR layout and RAG integration.
    """
    
    # Core Q&A content
    question = models.TextField(verbose_name='سؤال')
    answer = models.TextField(verbose_name='پاسخ')
    
    # Status and workflow
    status = models.CharField(
        max_length=20,
        choices=QAStatus.choices,
        default=QAStatus.DRAFT,
        verbose_name='وضعیت'
    )
    
    # Tags for categorization
    tags = models.ManyToManyField(
        'masterdata.VocabularyTerm',
        blank=True,
        related_name='qa_entries',
        verbose_name='برچسب‌ها'
    )
    
    # Provenance - link to source documents
    source_unit = models.ForeignKey(
        'LegalUnit',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='qa_entries',
        verbose_name='واحد حقوقی مرجع'
    )
    
    source_work = models.ForeignKey(
        'InstrumentWork',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qa_entries',
        verbose_name='سند حقوقی مرجع'
    )
    
    # Moderation and approval workflow
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_qa_entries',
        verbose_name='ایجادکننده'
    )
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_qa_entries',
        verbose_name='تأیید کننده'
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان تأیید'
    )
    
    # Indexing and search optimization
    canonical_question = models.CharField(
        max_length=512,
        blank=True,
        db_index=True,
        verbose_name='سؤال نرمال‌سازی شده',
        help_text='نسخه نرمال‌سازی شده سؤال برای جستجو'
    )
    
    # Generic relation for embeddings (via chunks)
    embeddings = GenericRelation('embeddings.Embedding')
    
    # History tracking
    history = HistoricalRecords()
    
    class Meta:
        verbose_name = 'پرسش و پاسخ'
        verbose_name_plural = 'پرسش و پاسخ'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['canonical_question']),
            models.Index(fields=['approved_at']),
        ]
    
    def __str__(self):
        question_preview = self.question[:50] + "..." if len(self.question) > 50 else self.question
        return f"Q: {question_preview} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        """Override save to generate canonical question and normalize answer for indexing."""
        if self.question:
            from ingest.core.text_processing import prepare_for_embedding
            # Use proper Persian text normalization for question
            normalized_question = prepare_for_embedding(self.question)
            self.canonical_question = normalized_question[:512]  # Respect field max_length
        
        # Also normalize answer text for better search and embedding
        if self.answer:
            from ingest.core.text_processing import prepare_for_embedding
            # Normalize answer text (store in same field but process both)
            normalized_answer = prepare_for_embedding(self.answer)
            # We can store both normalized texts in embedding_text property
        
        super().save(*args, **kwargs)
    
    def approve(self, approved_by_user):
        """Approve this QA entry."""
        self.status = QAStatus.APPROVED
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])
    
    def reject(self):
        """Reject this QA entry."""
        self.status = QAStatus.REJECTED
        self.approved_by = None
        self.approved_at = None
        self.save(update_fields=['status', 'approved_by', 'approved_at'])
    
    @property
    def short_question(self):
        """Return shortened question for admin display."""
        return self.question[:100] + "..." if len(self.question) > 100 else self.question
    
    @property
    def is_approved(self):
        """Check if entry is approved."""
        return self.status == QAStatus.APPROVED
    
    @property
    def embedding_text(self):
        """Generate normalized text for embedding generation."""
        from ingest.core.text_processing import prepare_for_embedding
        
        # Use normalized question if available, otherwise normalize on-the-fly
        normalized_question = self.canonical_question if self.canonical_question else prepare_for_embedding(self.question)
        
        # Always normalize answer for embedding
        normalized_answer = prepare_for_embedding(self.answer) if self.answer else ""
        
        return f"Q: {normalized_question}\nA: {normalized_answer}"
