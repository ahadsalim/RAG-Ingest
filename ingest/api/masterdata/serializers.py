from rest_framework import serializers
from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Vocabulary, VocabularyTerm


class JurisdictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Jurisdiction
        fields = ['id', 'name', 'code', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class IssuingAuthoritySerializer(serializers.ModelSerializer):
    jurisdiction_name = serializers.CharField(source='jurisdiction.name', read_only=True)
    
    class Meta:
        model = IssuingAuthority
        fields = [
            'id', 'name', 'code', 'jurisdiction', 'jurisdiction_name', 
            'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'jurisdiction_name']


class VocabularyTermSerializer(serializers.ModelSerializer):
    vocabulary_name = serializers.CharField(source='vocabulary.name', read_only=True)
    
    class Meta:
        model = VocabularyTerm
        fields = [
            'id', 'vocabulary', 'vocabulary_name', 'term', 'code', 
            'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'vocabulary_name']


class VocabularySerializer(serializers.ModelSerializer):
    terms = VocabularyTermSerializer(many=True, read_only=True)
    terms_count = serializers.IntegerField(source='terms.count', read_only=True)
    
    class Meta:
        model = Vocabulary
        fields = [
            'id', 'name', 'code', 'description', 'terms_count', 
            'terms', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'terms_count', 'terms']
