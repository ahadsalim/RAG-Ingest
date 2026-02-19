"""
File upload service for handling S3 storage uploads with proper error handling.
"""
import hashlib
import uuid
from typing import Optional, Dict, Any
from django.db import transaction
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
import logging

# Optional imports for S3 storage functionality
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
    """Service for uploading files to S3 storage and creating database records."""
    
    def __init__(self):
        self.s3_client = None
        self._init_s3_client()
    
    def _init_s3_client(self):
        """Initialize S3 storage client."""
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
        """Generate unique object key for S3 storage."""
        file_uuid = str(uuid.uuid4())
        # Use first 8 chars of hash for deduplication
        hash_prefix = file_hash[:8]
        return f"uploads/{hash_prefix}/{file_uuid}_{filename}"
    
    def _upload_to_s3(self, file_content: bytes, object_key: str, content_type: str) -> bool:
        """Upload file content to S3 storage."""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False
        
        try:
            self.s3_client.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=object_key,
                Body=file_content,
                ContentType=content_type
            )
            logger.info(f"Successfully uploaded file to S3: {object_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {str(e)}")
            return False
    
    def _delete_from_s3(self, object_key: str) -> bool:
        """Delete file from S3 storage (cleanup on failure)."""
        if not self.s3_client:
            return False
        
        try:
            self.s3_client.delete_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=object_key
            )
            logger.info(f"Deleted file from S3: {object_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {str(e)}")
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
        Upload file using Django's FileField with S3 storage backend.
        
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
        
        try:
            # Create FileAsset - Django's FileField with S3 storage handles upload automatically
            file_asset = FileAsset.objects.create(
                file=uploaded_file,
                legal_unit=legal_unit,
                manifestation=manifestation,
                uploaded_by=uploaded_by
            )
            
            logger.info(f"Successfully created FileAsset: {file_asset.id}, file: {file_asset.file.name}")
            return file_asset
            
        except Exception as e:
            logger.error(f"Failed to create FileAsset: {str(e)}")
            raise
    
    def delete_file(self, file_asset: FileAsset) -> bool:
        """
        Delete file from both S3 storage and database.
        Django's FileField with S3 storage backend handles S3 deletion automatically.
        
        Args:
            file_asset: FileAsset instance to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_name = file_asset.file.name
            file_asset.delete()  # Django's storage backend deletes from S3 automatically
            logger.info(f"Deleted FileAsset: {file_asset.id}, file: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete FileAsset: {str(e)}")
            return False


# Service instance
file_upload_service = FileUploadService()
