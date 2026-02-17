import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from typing import Optional


def get_s3_client():
    """Get configured S3 client for S3-compatible storage (external MinIO)."""
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        use_ssl=settings.AWS_S3_USE_SSL
    )


def generate_presigned_url(bucket: str, object_key: str, expires_in: int = 3600) -> str:
    """Generate presigned URL for downloading a file."""
    s3_client = get_s3_client()
    
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': object_key},
            ExpiresIn=expires_in
        )
        return response
    except ClientError as e:
        raise Exception(f"Failed to generate presigned URL: {e}")


def generate_presigned_upload_url(bucket: str, object_key: str, content_type: str, expires_in: int = 3600) -> str:
    """Generate presigned URL for uploading a file."""
    s3_client = get_s3_client()
    
    try:
        response = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket, 
                'Key': object_key,
                'ContentType': content_type
            },
            ExpiresIn=expires_in
        )
        return response
    except ClientError as e:
        raise Exception(f"Failed to generate presigned upload URL: {e}")


def create_bucket_if_not_exists(bucket: str) -> bool:
    """Create S3 bucket if it doesn't exist."""
    s3_client = get_s3_client()
    
    try:
        s3_client.head_bucket(Bucket=bucket)
        return False  # Bucket already exists
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            # Bucket doesn't exist, create it
            try:
                s3_client.create_bucket(Bucket=bucket)
                return True  # Bucket created
            except ClientError as create_error:
                raise Exception(f"Failed to create bucket {bucket}: {create_error}")
        else:
            raise Exception(f"Error checking bucket {bucket}: {e}")


def upload_file(file_obj, bucket: str, object_key: str, content_type: Optional[str] = None) -> dict:
    """Upload file to S3 and return metadata."""
    s3_client = get_s3_client()
    
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    
    try:
        s3_client.upload_fileobj(file_obj, bucket, object_key, ExtraArgs=extra_args)
        
        # Get object metadata
        response = s3_client.head_object(Bucket=bucket, Key=object_key)
        
        return {
            'bucket': bucket,
            'object_key': object_key,
            'size_bytes': response['ContentLength'],
            'content_type': response.get('ContentType', 'application/octet-stream'),
            'etag': response['ETag'].strip('"')
        }
    except ClientError as e:
        raise Exception(f"Failed to upload file: {e}")


def delete_file(bucket: str, object_key: str) -> bool:
    """Delete file from S3."""
    s3_client = get_s3_client()
    
    try:
        s3_client.delete_object(Bucket=bucket, Key=object_key)
        return True
    except ClientError as e:
        raise Exception(f"Failed to delete file: {e}")


def file_exists(bucket: str, object_key: str) -> bool:
    """Check if file exists in S3."""
    s3_client = get_s3_client()
    
    try:
        s3_client.head_object(Bucket=bucket, Key=object_key)
        return True
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            return False
        else:
            raise Exception(f"Error checking file existence: {e}")
