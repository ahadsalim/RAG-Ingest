"""
Signals for tracking metadata changes in related models.
"""
from django.db import models
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from ingest.apps.documents.models import (
    LegalUnit, InstrumentWork, InstrumentExpression, 
    InstrumentManifestation, Chunk, QAEntry
)
from ingest.apps.embeddings.models import Embedding

User = get_user_model()


@receiver(post_save, sender=LegalUnit)
def invalidate_unit_embeddings(sender, instance, **kwargs):
    """
    When a LegalUnit is updated, mark its embeddings for re-sync.
    This ensures metadata changes are propagated to Core.
    """
    if kwargs.get('created', False):
        # Don't invalidate on creation
        return
    
    # Get all chunks related to this unit
    from ingest.apps.documents.models import Chunk
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    
    chunk_ids = instance.chunks.values_list('id', flat=True)
    
    # Mark embeddings for re-sync by clearing metadata_hash
    Embedding.objects.filter(
        content_type=chunk_ct,
        object_id__in=chunk_ids,
        synced_to_core=True
    ).update(
        metadata_hash=''  # This will trigger re-sync on next metadata check
    )


@receiver(post_save, sender=InstrumentWork)
def invalidate_work_embeddings(sender, instance, **kwargs):
    """Mark embeddings for all units in this work for re-sync."""
    if kwargs.get('created', False):
        return
    
    from ingest.apps.documents.models import Chunk
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    
    # Get all chunks for units in this work
    chunk_ids = Chunk.objects.filter(
        unit__work=instance
    ).values_list('id', flat=True)
    
    Embedding.objects.filter(
        content_type=chunk_ct,
        object_id__in=chunk_ids,
        synced_to_core=True
    ).update(metadata_hash='')


@receiver(post_save, sender=InstrumentExpression)
def invalidate_expression_embeddings(sender, instance, **kwargs):
    """Mark embeddings for all chunks in this expression for re-sync."""
    if kwargs.get('created', False):
        return
    
    from ingest.apps.documents.models import Chunk
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    
    chunk_ids = instance.chunks.values_list('id', flat=True)
    
    Embedding.objects.filter(
        content_type=chunk_ct,
        object_id__in=chunk_ids,
        synced_to_core=True
    ).update(metadata_hash='')


@receiver(post_save, sender=InstrumentManifestation)
def invalidate_manifestation_embeddings(sender, instance, **kwargs):
    """Mark embeddings for all units in this manifestation for re-sync."""
    if kwargs.get('created', False):
        return
    
    from ingest.apps.documents.models import Chunk
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    
    chunk_ids = Chunk.objects.filter(
        unit__manifestation=instance
    ).values_list('id', flat=True)
    
    Embedding.objects.filter(
        content_type=chunk_ct,
        object_id__in=chunk_ids,
        synced_to_core=True
    ).update(metadata_hash='')


@receiver(m2m_changed, sender=LegalUnit.vocabulary_terms.through)
def invalidate_unit_tags_embeddings(sender, instance, action, **kwargs):
    """
    When tags are added/removed from a LegalUnit, invalidate embeddings.
    """
    if action not in ['post_add', 'post_remove', 'post_clear']:
        return
    
    from ingest.apps.documents.models import Chunk
    chunk_ct = ContentType.objects.get_for_model(Chunk)
    
    chunk_ids = instance.chunks.values_list('id', flat=True)
    
    Embedding.objects.filter(
        content_type=chunk_ct,
        object_id__in=chunk_ids,
        synced_to_core=True
    ).update(metadata_hash='')


@receiver(post_save, sender=QAEntry)
def invalidate_qa_embeddings(sender, instance, **kwargs):
    """Mark QA entry embedding for re-sync when updated."""
    if kwargs.get('created', False):
        return
    
    qa_ct = ContentType.objects.get_for_model(QAEntry)
    
    Embedding.objects.filter(
        content_type=qa_ct,
        object_id=instance.id,
        synced_to_core=True
    ).update(metadata_hash='')


@receiver(m2m_changed, sender=QAEntry.tags.through)
def invalidate_qa_tags_embeddings(sender, instance, action, **kwargs):
    """When tags are changed on QA entry, invalidate its embedding."""
    if action not in ['post_add', 'post_remove', 'post_clear']:
        return
    
    qa_ct = ContentType.objects.get_for_model(QAEntry)
    
    Embedding.objects.filter(
        content_type=qa_ct,
        object_id=instance.id,
        synced_to_core=True
    ).update(metadata_hash='')


@receiver(m2m_changed, sender=User.user_permissions.through)
def auto_grant_synclog_delete_permission(sender, instance, action, pk_set, **kwargs):
    """
    وقتی کاربر permission ویرایش LegalUnit یا LUnit می‌گیرد،
    خودکار permission حذف SyncLog هم بهش بده.
    """
    if action not in ['post_add']:
        return
    
    if not pk_set:
        return
    
    from django.contrib.auth.models import Permission
    
    # دریافت content types
    try:
        legalunit_ct = ContentType.objects.get(app_label='documents', model='legalunit')
        lunit_ct = ContentType.objects.get(app_label='documents', model='lunit')
        synclog_ct = ContentType.objects.get(app_label='embeddings', model='synclog')
    except ContentType.DoesNotExist:
        return
    
    # چک کنیم آیا permission ویرایش LegalUnit یا LUnit اضافه شده
    has_change_perm = Permission.objects.filter(
        pk__in=pk_set
    ).filter(
        models.Q(content_type=legalunit_ct, codename='change_legalunit') |
        models.Q(content_type=lunit_ct, codename='change_lunit')
    ).exists()
    
    if not has_change_perm:
        return
    
    # دریافت permission حذف SyncLog
    try:
        delete_synclog_perm = Permission.objects.get(
            content_type=synclog_ct,
            codename='delete_synclog'
        )
    except Permission.DoesNotExist:
        return
    
    # اگر قبلاً نداشت، اضافه کن
    if not instance.user_permissions.filter(pk=delete_synclog_perm.pk).exists():
        instance.user_permissions.add(delete_synclog_perm)


@receiver(m2m_changed, sender=User.groups.through)
def auto_grant_synclog_delete_permission_via_group(sender, instance, action, pk_set, **kwargs):
    """
    وقتی کاربر به گروهی اضافه می‌شود که permission ویرایش LegalUnit یا LUnit دارد،
    خودکار permission حذف SyncLog هم بهش بده.
    """
    if action not in ['post_add']:
        return
    
    if not pk_set:
        return
    
    from django.contrib.auth.models import Permission, Group
    
    # دریافت content types
    try:
        legalunit_ct = ContentType.objects.get(app_label='documents', model='legalunit')
        lunit_ct = ContentType.objects.get(app_label='documents', model='lunit')
        synclog_ct = ContentType.objects.get(app_label='embeddings', model='synclog')
    except ContentType.DoesNotExist:
        return
    
    # چک کنیم آیا گروه‌های اضافه شده permission ویرایش LegalUnit یا LUnit دارند
    groups_with_change = Group.objects.filter(
        pk__in=pk_set
    ).filter(
        models.Q(permissions__content_type=legalunit_ct, permissions__codename='change_legalunit') |
        models.Q(permissions__content_type=lunit_ct, permissions__codename='change_lunit')
    )
    
    if not groups_with_change.exists():
        return
    
    # دریافت permission حذف SyncLog
    try:
        delete_synclog_perm = Permission.objects.get(
            content_type=synclog_ct,
            codename='delete_synclog'
        )
    except Permission.DoesNotExist:
        return
    
    # اگر قبلاً نداشت، اضافه کن
    if not instance.user_permissions.filter(pk=delete_synclog_perm.pk).exists():
        instance.user_permissions.add(delete_synclog_perm)
