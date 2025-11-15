from rest_framework import serializers
from ingest.apps.documents.models import (
    LegalUnit, FileAsset, QAEntry,
    InstrumentWork, InstrumentExpression, InstrumentManifestation,
)
from ingest.apps.masterdata.models import VocabularyTerm


class FileAssetSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = FileAsset
        fields = [
            'id', 'legal_unit', 'manifestation', 'bucket', 'object_key', 
            'original_filename', 'content_type', 'size_bytes', 'size_mb',
            'sha256', 'uploaded_by', 'uploaded_by_username', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'bucket', 'object_key', 'sha256', 'size_bytes', 
            'uploaded_by', 'uploaded_by_username', 'created_at', 'updated_at'
        ]
    
    def get_size_mb(self, obj):
        return round(obj.size_bytes / (1024 * 1024), 2)


class LegalUnitSerializer(serializers.ModelSerializer):
    files = FileAssetSerializer(many=True, read_only=True)
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = LegalUnit
        fields = [
            'id', 'parent', 'unit_type', 'label', 'number', 
            'order_index', 'path_label', 'content', 'work', 'expr', 'manifestation', 'files', 'children',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'path_label', 'created_at', 'updated_at']
    
    def get_children(self, obj):
        children = obj.get_children()
        return LegalUnitSerializer(children, many=True, context=self.context).data


"""Removed LegalDocument and DocumentRelation serializers."""


class QAEntrySerializer(serializers.ModelSerializer):
    """Serializer for QAEntry model with full CRUD support."""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True)
    source_work_title = serializers.CharField(source='source_work.title_official', read_only=True)
    source_unit_label = serializers.CharField(source='source_unit.label', read_only=True)
    tag_names = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    is_approved = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = QAEntry
        fields = [
            'id', 'question', 'answer', 'status', 'canonical_question',
            'source_work', 'source_work_title', 'source_unit', 'source_unit_label',
            'tags', 'tag_names', 'created_by', 'created_by_username',
            'approved_by', 'approved_by_username', 'approved_at',
            'is_approved', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'canonical_question', 'created_by', 'created_by_username',
            'approved_by', 'approved_by_username', 'approved_at', 'is_approved',
            'source_work_title', 'source_unit_label', 'tag_names',
            'created_at', 'updated_at'
        ]
    
    def validate_question(self, value):
        """Validate question field."""
        if not value or not value.strip():
            raise serializers.ValidationError("سؤال نمی‌تواند خالی باشد.")
        if len(value.strip()) < 10:
            raise serializers.ValidationError("سؤال باید حداقل ۱۰ کاراکتر باشد.")
        return value.strip()
    
    def validate_answer(self, value):
        """Validate answer field."""
        if not value or not value.strip():
            raise serializers.ValidationError("پاسخ نمی‌تواند خالی باشد.")
        if len(value.strip()) < 10:
            raise serializers.ValidationError("پاسخ باید حداقل ۱۰ کاراکتر باشد.")
        return value.strip()


class QAEntryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for QAEntry list views."""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    source_work_title = serializers.CharField(source='source_work.title_official', read_only=True)
    short_question = serializers.CharField(read_only=True)
    
    class Meta:
        model = QAEntry
        fields = [
            'id', 'short_question', 'status', 'source_work_title',
            'created_by_username', 'approved_at', 'created_at'
        ]
