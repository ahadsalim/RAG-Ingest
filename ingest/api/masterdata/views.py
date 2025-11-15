from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
# from drf_spectacular.utils import extend_schema_view, extend_schema

from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Vocabulary, VocabularyTerm
from .serializers import (
    JurisdictionSerializer, IssuingAuthoritySerializer, 
    VocabularySerializer, VocabularyTermSerializer
)


# @extend_schema_view(
#     list=extend_schema(summary="List jurisdictions", tags=["Masterdata"]),
#     create=extend_schema(summary="Create jurisdiction", tags=["Masterdata"]),
#     retrieve=extend_schema(summary="Get jurisdiction", tags=["Masterdata"]),
#     update=extend_schema(summary="Update jurisdiction", tags=["Masterdata"]),
#     destroy=extend_schema(summary="Delete jurisdiction", tags=["Masterdata"]),
# )
class JurisdictionViewSet(viewsets.ModelViewSet):
    queryset = Jurisdiction.objects.all()
    serializer_class = JurisdictionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']


# @extend_schema_view(
#     list=extend_schema(summary="List issuing authorities", tags=["Masterdata"]),
#     create=extend_schema(summary="Create issuing authority", tags=["Masterdata"]),
#     retrieve=extend_schema(summary="Get issuing authority", tags=["Masterdata"]),
#     update=extend_schema(summary="Update issuing authority", tags=["Masterdata"]),
#     destroy=extend_schema(summary="Delete issuing authority", tags=["Masterdata"]),
# )
class IssuingAuthorityViewSet(viewsets.ModelViewSet):
    queryset = IssuingAuthority.objects.select_related('jurisdiction')
    serializer_class = IssuingAuthoritySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'jurisdiction']
    search_fields = ['name', 'code', 'description', 'jurisdiction__name']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']


# @extend_schema_view(
#     list=extend_schema(summary="List vocabularies", tags=["Masterdata"]),
#     create=extend_schema(summary="Create vocabulary", tags=["Masterdata"]),
#     retrieve=extend_schema(summary="Get vocabulary", tags=["Masterdata"]),
#     update=extend_schema(summary="Update vocabulary", tags=["Masterdata"]),
#     destroy=extend_schema(summary="Delete vocabulary", tags=["Masterdata"]),
# )
class VocabularyViewSet(viewsets.ModelViewSet):
    queryset = Vocabulary.objects.prefetch_related('terms')
    serializer_class = VocabularySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']


# @extend_schema_view(
#     list=extend_schema(summary="List vocabulary terms", tags=["Masterdata"]),
#     create=extend_schema(summary="Create vocabulary term", tags=["Masterdata"]),
#     retrieve=extend_schema(summary="Get vocabulary term", tags=["Masterdata"]),
#     update=extend_schema(summary="Update vocabulary term", tags=["Masterdata"]),
#     destroy=extend_schema(summary="Delete vocabulary term", tags=["Masterdata"]),
# )
class VocabularyTermViewSet(viewsets.ModelViewSet):
    queryset = VocabularyTerm.objects.select_related('vocabulary')
    serializer_class = VocabularyTermSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'vocabulary']
    search_fields = ['term', 'code', 'description', 'vocabulary__name']
    ordering_fields = ['term', 'code', 'created_at']
    ordering = ['vocabulary__name', 'term']
