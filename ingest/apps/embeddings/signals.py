"""
Signals for tracking metadata changes in related models.
"""
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from ingest.apps.documents.models import (
    LegalUnit, InstrumentWork, InstrumentExpression, 
    InstrumentManifestation, Chunk, QAEntry
)
from ingest.apps.embeddings.models import Embedding


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
