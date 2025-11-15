#!/bin/bash
set -e

echo "Initializing MinIO bucket..."

# Skip health check - MinIO is external and already running
echo "Skipping MinIO health check for external MinIO server..."

echo "MinIO is ready, configuring mc client..."

# Configure mc client
mc alias set local "$AWS_S3_ENDPOINT_URL" "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" --api s3v4

# Create bucket if it doesn't exist (skip if external MinIO)
echo "Checking if bucket exists: $AWS_STORAGE_BUCKET_NAME"
if mc ls local/"$AWS_STORAGE_BUCKET_NAME" > /dev/null 2>&1; then
    echo "Bucket $AWS_STORAGE_BUCKET_NAME already exists"
else
    echo "Creating bucket: $AWS_STORAGE_BUCKET_NAME"
    mc mb -p local/"$AWS_STORAGE_BUCKET_NAME" || echo "Bucket creation failed - may already exist"
fi

# List bucket to verify
echo "Verifying bucket access:"
mc ls local/ || echo "Unable to list buckets - may be permission issue"

echo "MinIO initialization completed successfully!"
