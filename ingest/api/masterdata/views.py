from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Vocabulary, VocabularyTerm
from .serializers import (
    JurisdictionSerializer, IssuingAuthoritySerializer, 
    VocabularySerializer, VocabularyTermSerializer
)


class JurisdictionViewSet(viewsets.ModelViewSet):
    queryset = Jurisdiction.objects.all()
    serializer_class = JurisdictionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']


class IssuingAuthorityViewSet(viewsets.ModelViewSet):
    queryset = IssuingAuthority.objects.select_related('jurisdiction')
    serializer_class = IssuingAuthoritySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'jurisdiction']
    search_fields = ['name', 'code', 'description', 'jurisdiction__name']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']


class VocabularyViewSet(viewsets.ModelViewSet):
    queryset = Vocabulary.objects.prefetch_related('terms')
    serializer_class = VocabularySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']


class VocabularyTermViewSet(viewsets.ModelViewSet):
    queryset = VocabularyTerm.objects.select_related('vocabulary')
    serializer_class = VocabularyTermSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'vocabulary']
    search_fields = ['term', 'code', 'description', 'vocabulary__name']
    ordering_fields = ['term', 'code', 'created_at']
    ordering = ['vocabulary__name', 'term']
