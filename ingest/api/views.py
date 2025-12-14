from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
# from drf_spectacular.utils import extend_schema
from django.db import connection
from django.conf import settings

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    _S3_AVAILABLE = True
except Exception:
    boto3 = None
    Config = None
    ClientError = Exception
    _S3_AVAILABLE = False


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

            if not _S3_AVAILABLE:
                return {"status": "disabled", "message": "S3 dependencies not installed"}

            bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
            access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
            secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
            if not bucket or not access_key or not secret_key:
                return {"status": "disabled", "message": "S3 credentials/bucket not configured"}

            s3 = boto3.client(
                's3',
                endpoint_url=minio_endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(signature_version='s3v4'),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
            )

            # Validate connectivity with a lightweight call
            s3.head_bucket(Bucket=bucket)
            return {"status": "ok", "message": "Storage connection successful", "endpoint": minio_endpoint, "bucket": bucket}
            
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
            if not _S3_AVAILABLE:
                return Response(
                    {"error": "Storage dependencies not installed"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            endpoint = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
            bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
            access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
            secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)

            if not endpoint or not bucket or not access_key or not secret_key:
                return Response(
                    {"error": "Storage is not configured"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            s3 = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(signature_version='s3v4'),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
            )

            upload_url = s3.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': bucket,
                    'Key': object_key,
                    'ContentType': content_type,
                },
                ExpiresIn=60 * 10,
            )

            download_url = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket,
                    'Key': object_key,
                },
                ExpiresIn=60 * 10,
            )

            return Response(
                {
                    'object_key': object_key,
                    'bucket': bucket,
                    'upload_url': upload_url,
                    'download_url': download_url,
                    'expires_in': 60 * 10,
                },
                status=status.HTTP_200_OK,
            )
            
        except Exception as e:
            return Response(
                {"error": f"Storage service unavailable: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
