from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
# from drf_spectacular.utils import extend_schema
from django.db import connection
from django.conf import settings

# from ingest.common.s3 import generate_presigned_upload_url, generate_presigned_url


class HealthCheckView(APIView):
    """Health check endpoint."""
    permission_classes = []

    # @extend_schema(
    #     summary="Health Check",
    #     description="Check system health including database and storage connectivity"
    # )
    def get(self, request):
        health_data = {
            "status": "healthy",
            "database": self._check_database(),
            "storage": self._check_storage(),
            "version": "1.0.0"
        }
        
        overall_status = all([
            health_data["database"]["status"] == "ok",
            health_data["storage"]["status"] in ["ok", "disabled"]
        ])
        
        if not overall_status:
            health_data["status"] = "unhealthy"
            return Response(health_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return Response(health_data)

    def _check_database(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {"status": "ok", "message": "Database connection successful"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _check_storage(self):
        try:
            # Check MinIO configuration
            minio_endpoint = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
            if not minio_endpoint:
                return {"status": "disabled", "message": "MinIO endpoint not configured"}
            
            # Storage functionality temporarily disabled
            return {"status": "disabled", "message": "Storage functionality temporarily disabled", "endpoint": minio_endpoint}
        except Exception as e:
            return {"status": "disabled", "message": f"Storage disabled: {str(e)}"}


class PresignURLView(APIView):
    """Generate presigned URLs for file upload and download."""
    permission_classes = [IsAuthenticated]

    # @extend_schema(
    #     summary="Generate Presigned URLs",
    #     description="Generate presigned URLs for file upload (PUT) and download (GET)",
    #     request={
    #         'application/json': {
    #             'type': 'object',
    #             'properties': {
    #                 'filename': {'type': 'string', 'description': 'Original filename'},
    #                 'content_type': {'type': 'string', 'description': 'MIME content type'},
    #                 'document_id': {'type': 'string', 'format': 'uuid', 'description': 'Document ID (optional)'},
    #                 'unit_id': {'type': 'string', 'format': 'uuid', 'description': 'Unit ID (optional)'}
    #             },
    #             'required': ['filename', 'content_type']
    #         }
    #     }
    # )
    def post(self, request):
        filename = request.data.get('filename')
        content_type = request.data.get('content_type')
        document_id = request.data.get('document_id')
        unit_id = request.data.get('unit_id')
        
        if not filename or not content_type:
            return Response(
                {"error": "filename and content_type are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate object key based on context
        if document_id:
            object_key = f"documents/{document_id}/source/{filename}"
        elif unit_id:
            object_key = f"units/{unit_id}/attachments/{filename}"
        else:
            object_key = f"uploads/{request.user.id}/{filename}"
        
        try:
            # Storage functionality temporarily disabled
            return Response(
                {"error": "Storage functionality temporarily disabled"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
        except Exception as e:
            return Response(
                {"error": f"Storage service unavailable: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
