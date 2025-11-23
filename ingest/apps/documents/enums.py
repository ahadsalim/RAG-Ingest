from django.db import models


class ConsolidationLevel(models.TextChoices):
    """Consolidation levels for legal expressions."""
    BASE = 'base', 'پایه'
    CONSOLIDATED = 'consolidated', 'تجمیع شده'
    ANNOTATED = 'annotated', 'حاشیه نویسی'


class DocumentType(models.TextChoices):
    LAW = 'law', 'قانون'
    BYLAW = 'bylaw', 'آیین‌نامه'
    CIRCULAR = 'circular', 'بخشنامه'
    RULING = 'ruling', 'رأی'
    DECREE = 'decree', 'مصوبه'
    REGULATION = 'regulation', 'مقررات'
    INSTRUCTION = 'instruction', 'دستورالعمل'
    OTHER = 'other', 'سایر'


class DocumentStatus(models.TextChoices):
    DRAFT = 'draft', 'پیش‌نویس'
    UNDER_REVIEW = 'under_review', 'در حال بررسی'
    APPROVED = 'approved', 'تأیید شده'
    REJECTED = 'rejected', 'رد شده'


class RelationType(models.TextChoices):
    AMENDS = 'amends', 'اصلاح می‌کند'
    AMENDED_BY = 'amended_by', 'اصلاح شده توسط'
    REPEALS = 'repeals', 'لغو می‌کند'
    REPEALED_BY = 'repealed_by', 'لغو شده توسط'
    REFERS_TO = 'refers_to', 'ارجاع به'
    IMPLEMENTS = 'implements', 'اجرا می‌کند'
    IMPLEMENTED_BY = 'implemented_by', 'اجرا شده توسط'


class UnitType(models.TextChoices):
    PART = 'part', 'باب'
    CHAPTER = 'chapter', 'فصل'
    SECTION = 'section', 'قسمت'
    ARTICLE = 'article', 'ماده'
    CLAUSE = 'clause', 'بند'
    SUBCLAUSE = 'subclause', 'زیربند'
    NOTE = 'note', 'تبصره'
    APPENDIX = 'appendix', 'ضمیمه'


class QAStatus(models.TextChoices):
    DRAFT = 'draft', 'پیش‌نویس'
    UNDER_REVIEW = 'under_review', 'در حال بررسی'
    APPROVED = 'approved', 'تأیید شده'
    REJECTED = 'rejected', 'رد شده'


class IngestStatus(models.TextChoices):
    PENDING = 'pending', 'در انتظار'
    PROCESSING = 'processing', 'در حال پردازش'
    COMPLETED = 'completed', 'تکمیل شده'
    FAILED = 'failed', 'ناموفق'
