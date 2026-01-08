import uuid
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class BaseModel(models.Model):
    """Base model with common fields."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class Jurisdiction(BaseModel):
    """Legal jurisdiction (e.g., Iran, Tehran Province)."""
    name = models.CharField(max_length=200, verbose_name='نام')
    code = models.CharField(max_length=50, unique=True, verbose_name='کد')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'حوزه قضایی'
        verbose_name_plural = 'حوزه‌های قضایی'
        ordering = ['name']

    def __str__(self):
        return self.name


class IssuingAuthority(BaseModel):
    """Authority that issues legal documents."""
    name = models.CharField(max_length=200, verbose_name='نام')
    short_name = models.CharField(max_length=50, unique=True, verbose_name='نام کوتاه')
    jurisdiction = models.ForeignKey(
        Jurisdiction, 
        on_delete=models.CASCADE, 
        related_name='authorities',
        verbose_name='حوزه قضایی'
    )
    uri = models.URLField(blank=True, verbose_name='URI')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'مرجع صادرکننده'
        verbose_name_plural = 'مراجع صادرکننده'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.jurisdiction.name})"


class Language(BaseModel):
    """Language for vocabulary categorization."""
    name = models.CharField(max_length=100, verbose_name='نام')
    code = models.CharField(max_length=10, unique=True, verbose_name='کد')  # e.g., 'fa', 'en', 'ar'
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'زبان'
        verbose_name_plural = 'زبان‌ها'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Scheme(BaseModel):
    """Classification scheme for vocabularies."""
    name = models.CharField(max_length=200, verbose_name='نام')
    code = models.CharField(max_length=50, unique=True, verbose_name='کد')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'طرح کلی'
        verbose_name_plural = 'طرح‌های کلی'
        ordering = ['name']

    def __str__(self):
        return self.name


class Vocabulary(BaseModel):
    """Vocabulary for categorizing terms."""
    name = models.CharField(max_length=200, verbose_name='نام')
    code = models.CharField(max_length=50, unique=True, verbose_name='کد')
    scheme = models.ForeignKey(
        Scheme, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='vocabularies',
        verbose_name='طرح کلی'
    )
    lang = models.ForeignKey(
        Language, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='vocabularies',
        verbose_name='زبان'
    )
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'موضوع'
        verbose_name_plural = 'موضوعات'
        ordering = ['name']

    def __str__(self):
        return self.name


class VocabularyTerm(BaseModel):
    """Terms within a vocabulary."""
    vocabulary = models.ForeignKey(
        Vocabulary, 
        on_delete=models.CASCADE, 
        related_name='terms',
        verbose_name='واژگان'
    )
    term = models.CharField(max_length=200, verbose_name='اصطلاح')
    code = models.CharField(max_length=50, verbose_name='کد')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'واژه'
        verbose_name_plural = 'واژگان'
        ordering = ['vocabulary__name', 'term']
        unique_together = ['vocabulary', 'code']
    
    def save(self, *args, **kwargs):
        """Normalize term text before saving."""
        from ingest.core.text_processing import prepare_for_embedding
        
        if self.term:
            self.term = prepare_for_embedding(self.term)
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vocabulary.name}: {self.term}"
