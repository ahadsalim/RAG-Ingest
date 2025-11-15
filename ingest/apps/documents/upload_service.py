"""
File upload service for handling MinIO uploads with proper error handling.
"""
import hashlib
import uuid
from typing import Optional, Dict, Any
from django.db import transaction
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
import logging

# Optional imports for S3/MinIO functionality
try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    S3_DEPENDENCIES_AVAILABLE = True
except ImportError:
    boto3 = None
    Config = None
    ClientError = Exception
    S3_DEPENDENCIES_AVAILABLE = False

from .models import FileAsset

logger = logging.getLogger(__name__)


class FileUploadService:
    """Service for uploading files to MinIO and creating database records."""
    
    def __init__(self):
        self.s3_client = None
        self._init_s3_client()
    
    def _init_s3_client(self):
        """Initialize S3/MinIO client."""
        if not S3_DEPENDENCIES_AVAILABLE:
            logger.warning("S3 dependencies (boto3, botocore) not available. File upload functionality disabled.")
            self.s3_client = None
            return
            
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=Config(signature_version='s3v4'),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            )
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            self.s3_client = None
    
    def _calculate_sha256(self, file_content: bytes) -> str:
        """Calculate SHA256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()
    
    def _generate_object_key(self, filename: str, file_hash: str) -> str:
        """Generate unique object key for MinIO storage."""
        file_uuid = str(uuid.uuid4())
        # Use first 8 chars of hash for deduplication
        hash_prefix = file_hash[:8]
        return f"uploads/{hash_prefix}/{file_uuid}_{filename}"
    
    def _upload_to_minio(self, file_content: bytes, object_key: str, content_type: str) -> bool:
        """Upload file content to MinIO."""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False
        
        try:
            self.s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=object_key,
                Body=file_content,
                ContentType=content_type,
                ServerSideEncryption='AES256'  # Optional encryption
            )
            logger.info(f"Successfully uploaded file to MinIO: {object_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file to MinIO: {str(e)}")
            return False
    
    def _delete_from_minio(self, object_key: str) -> bool:
        """Delete file from MinIO (cleanup on failure)."""
        if not self.s3_client:
            return False
        
        try:
            self.s3_client.delete_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=object_key
            )
            logger.info(f"Deleted file from MinIO: {object_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from MinIO: {str(e)}")
            return False
    
    @transaction.atomic
    def upload_file(
        self,
        uploaded_file: UploadedFile,
        uploaded_by,
        legal_unit=None,
        manifestation=None
    ) -> Optional[FileAsset]:
        """
        Upload file to MinIO first, then create database record.
        
        Args:
            uploaded_file: Django UploadedFile instance
            uploaded_by: User who uploaded the file
            legal_unit: Optional LegalUnit reference
            manifestation: Optional InstrumentManifestation reference
            
        Returns:
            FileAsset instance if successful, None if failed
        """
        if not uploaded_file:
            logger.error("No file provided for upload")
            return None
        
        if not S3_DEPENDENCIES_AVAILABLE:
            logger.error("S3 dependencies not available. File upload functionality disabled.")
            return None
        
        # Read file content
        try:
            file_content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset file pointer
        except Exception as e:
            logger.error(f"Failed to read uploaded file: {str(e)}")
            return None
        
        # Calculate file hash
        file_hash = self._calculate_sha256(file_content)
        
        # Generate object key
        object_key = self._generate_object_key(uploaded_file.name, file_hash)
        
        # Step 1: Upload to MinIO first
        upload_success = self._upload_to_minio(
            file_content=file_content,
            object_key=object_key,
            content_type=uploaded_file.content_type or 'application/octet-stream'
        )
        
        if not upload_success:
            logger.error("Failed to upload file to MinIO, aborting database creation")
            return None
        
        # Step 2: Create database record only after successful MinIO upload
        try:
            file_asset = FileAsset.objects.create(
                legal_unit=legal_unit,
                manifestation=manifestation,
                bucket=settings.AWS_STORAGE_BUCKET_NAME,
                object_key=object_key,
                original_filename=uploaded_file.name,
                content_type=uploaded_file.content_type or 'application/octet-stream',
                size_bytes=len(file_content),
                sha256=file_hash,
                uploaded_by=uploaded_by
            )
            
            logger.info(f"Successfully created FileAsset record: {file_asset.id}")
            return file_asset
            
        except Exception as e:
            logger.error(f"Failed to create FileAsset record: {str(e)}")
            
            # Cleanup: Delete file from MinIO since DB creation failed
            self._delete_from_minio(object_key)
            
            # Re-raise the exception to trigger transaction rollback
            raise
    
    def delete_file(self, file_asset: FileAsset) -> bool:
        """
        Delete file from both MinIO and database.
        
        Args:
            file_asset: FileAsset instance to delete
            
        Returns:
            True if successful, False otherwise
        """
        object_key = file_asset.object_key
        
        # Delete from MinIO first
        minio_deleted = self._delete_from_minio(object_key)
        
        # Delete database record regardless of MinIO result
        try:
            file_asset.delete()
            logger.info(f"Deleted FileAsset record: {file_asset.id}")
            return minio_deleted  # Return MinIO deletion status
        except Exception as e:
            logger.error(f"Failed to delete FileAsset record: {str(e)}")
            return False


# Service instance
file_upload_service = FileUploadService()
