from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.utils.timezone import localdate
from datetime import datetime, date
# from drf_spectacular.utils import extend_schema_view, extend_schema

from ingest.apps.documents.models import (
    LegalUnit, FileAsset, QAEntry,
    InstrumentWork, InstrumentExpression, InstrumentManifestation,
)
from ingest.apps.documents.upload_service import file_upload_service
from .serializers import (
    LegalUnitSerializer, FileAssetSerializer, QAEntrySerializer, QAEntryListSerializer
)
from ingest.api.mixins import FullyOptimizedViewMixin


"""Legacy LegalDocument API removed. Use FRBR endpoints (Work/Expression/Manifestation) if needed."""


# @extend_schema_view(
#     list=extend_schema(summary="List legal units", tags=["Documents"]),
#     create=extend_schema(summary="Create legal unit", tags=["Documents"]),
#     retrieve=extend_schema(summary="Get legal unit", tags=["Documents"]),
#     update=extend_schema(summary="Update legal unit", tags=["Documents"]),
#     destroy=extend_schema(summary="Delete legal unit", tags=["Documents"]),
# )
class LegalUnitViewSet(FullyOptimizedViewMixin, viewsets.ModelViewSet):
    queryset = LegalUnit.objects.all()
    serializer_class = LegalUnitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['unit_type', 'parent', 'work', 'expr', 'manifestation', 'valid_from', 'valid_to']
    search_fields = ['path_label', 'content', 'work__title_official']
    ordering_fields = ['order_index', 'created_at', 'tree_id', 'lft', 'valid_from', 'valid_to']
    ordering = ['tree_id', 'lft']

    def get_queryset(self):
        """Get queryset with optional temporal filtering."""
        qs = LegalUnit.objects.select_related('work', 'expr', 'manifestation', 'parent').prefetch_related('files', 'changes')
        
        # Check for as_of parameter for temporal queries
        as_of_param = self.request.query_params.get('as_of')
        if as_of_param:
            try:
                # Parse date in YYYY-MM-DD format
                as_of_date = datetime.strptime(as_of_param, '%Y-%m-%d').date()
                qs = qs.as_of(as_of_date)
            except ValueError:
                # If date parsing fails, ignore the parameter
                pass
        
        # Check for active_only parameter
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() in ['true', '1', 'yes']:
            qs = qs.active()
        
        return qs
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only currently active legal units."""
        queryset = self.get_queryset().active()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """Get only expired legal units."""
        queryset = self.get_queryset().expired()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def as_of(self, request):
        """Get legal units as they were on a specific date."""
        date_param = request.query_params.get('date')
        if not date_param:
            return Response(
                {'error': 'پارامتر date الزامی است. فرمت: YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'فرمت تاریخ نامعتبر است. فرمت صحیح: YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().as_of(target_date)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# @extend_schema_view(
#     list=extend_schema(summary="List file assets", tags=["Documents"]),
#     create=extend_schema(summary="Create file asset", tags=["Documents"]),
#     retrieve=extend_schema(summary="Get file asset", tags=["Documents"]),
#     update=extend_schema(summary="Update file asset", tags=["Documents"]),
#     destroy=extend_schema(summary="Delete file asset", tags=["Documents"]),
# )
class FileAssetViewSet(FullyOptimizedViewMixin, viewsets.ModelViewSet):
    queryset = FileAsset.objects.all()
    serializer_class = FileAssetSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['content_type', 'legal_unit', 'manifestation', 'uploaded_by']
    search_fields = ['original_filename', 'legal_unit__label', 'manifestation__expr__work__title_official']
    ordering_fields = ['original_filename', 'size_bytes', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = FileAsset.objects.select_related('legal_unit', 'manifestation', 'uploaded_by')
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Custom create method to handle file upload with MinIO-first approach."""
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'No file provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get optional references
        legal_unit_id = request.data.get('legal_unit')
        manifestation_id = request.data.get('manifestation')
        
        legal_unit = None
        manifestation = None
        
        if legal_unit_id:
            try:
                legal_unit = LegalUnit.objects.get(id=legal_unit_id)
            except LegalUnit.DoesNotExist:
                return Response(
                    {'error': 'Legal unit not found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if manifestation_id:
            try:
                manifestation = InstrumentManifestation.objects.get(id=manifestation_id)
            except InstrumentManifestation.DoesNotExist:
                return Response(
                    {'error': 'Manifestation not found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Upload file using service (MinIO first, then DB)
        file_asset = file_upload_service.upload_file(
            uploaded_file=uploaded_file,
            uploaded_by=request.user,
            legal_unit=legal_unit,
            manifestation=manifestation
        )
        
        if not file_asset:
            return Response(
                {'error': 'File upload failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(file_asset)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        """Custom destroy method to delete from MinIO as well."""
        file_upload_service.delete_file(instance)


# @extend_schema_view(
#     list=extend_schema(summary="List QA entries", tags=["Documents"]),
#     create=extend_schema(summary="Create QA entry", tags=["Documents"]),
#     retrieve=extend_schema(summary="Get QA entry", tags=["Documents"]),
#     update=extend_schema(summary="Update QA entry", tags=["Documents"]),
#     destroy=extend_schema(summary="Delete QA entry", tags=["Documents"]),
# )
class QAEntryViewSet(FullyOptimizedViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for QAEntry with permission-based access.
    
    - Anonymous users: Can only view APPROVED entries
    - Staff users: Full CRUD access to all entries
    """
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'source_work', 'source_unit', 'tags', 'created_by']
    search_fields = ['question', 'answer', 'canonical_question']
    ordering_fields = ['created_at', 'updated_at', 'approved_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = QAEntry.objects.select_related(
            'created_by', 'approved_by', 'source_work', 'source_unit'
        ).prefetch_related('tags')
        
        # Anonymous users only see approved entries
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status='approved')
        
        # Staff can see all entries
        elif self.request.user.is_staff:
            pass  # No filtering for staff
        
        # Regular authenticated users see their own + approved entries
        else:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(status='approved') | Q(created_by=self.request.user)
            )
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == 'list':
            return QAEntryListSerializer
        return QAEntrySerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            # Anyone can read (but queryset is filtered)
            permission_classes = []
        else:
            # Only authenticated users can create/update/delete
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Set created_by when creating new QA entry."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve a QA entry (staff only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'تنها کارکنان می‌توانند ورودی‌ها را تأیید کنند.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        qa_entry = self.get_object()
        qa_entry.approve(request.user)
        
        serializer = self.get_serializer(qa_entry)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject a QA entry (staff only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'تنها کارکنان می‌توانند ورودی‌ها را رد کنند.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        qa_entry = self.get_object()
        qa_entry.reject()
        
        serializer = self.get_serializer(qa_entry)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def approved(self, request):
        """Get only approved QA entries (public endpoint)."""
        queryset = self.get_queryset().filter(status='approved')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_entries(self, request):
        """Get current user's QA entries."""
        queryset = self.get_queryset().filter(created_by=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
