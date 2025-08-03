# MinIO Development Guide

This guide covers working with MinIO S3-compatible object storage, specifically the insights gained while building the MinIO TUI.

## Overview

MinIO is an S3-compatible object storage server. This guide focuses on using boto3 to interact with MinIO programmatically and the specific considerations for building client applications.

## Core Concepts

### 1. S3 vs MinIO

**S3 Compatibility:**
- MinIO implements the S3 API, so boto3 works directly
- Some features may have slight differences or limitations
- Object Lock (WORM) support varies by MinIO version
- Performance characteristics differ from AWS S3

**Key Differences:**
```python
# AWS S3
client = boto3.client('s3')

# MinIO
client = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',  # Required for MinIO
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin'
)
```

### 2. Client Configuration

```python
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

class MinioClient:
    def __init__(self, endpoint_url, access_key, secret_key):
        try:
            self.client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                # Important: Disable SSL verification for local MinIO
                verify=False,  # Only for development
                # Configure timeouts
                config=boto3.session.Config(
                    connect_timeout=10,
                    read_timeout=30,
                    retries={'max_attempts': 3}
                )
            )
        except Exception as e:
            raise ValueError(f"Failed to create MinIO client: {e}")
```

**Configuration Best Practices:**
- Always validate credentials on initialization
- Use environment variables for configuration
- Implement proper timeout handling
- Consider SSL/TLS for production environments

## Bucket Operations

### 1. Basic Bucket Management

```python
def list_buckets(self):
    """Lists all buckets - simple and reliable."""
    try:
        response = self.client.list_buckets()
        return [bucket['Name'] for bucket in response['Buckets']]
    except ClientError as e:
        # Handle specific S3 errors
        if e.response['Error']['Code'] == 'AccessDenied':
            raise Exception("Access denied - check credentials")
        raise Exception(f"Failed to list buckets: {e}")

def create_bucket(self, bucket_name):
    """Create bucket with error handling."""
    try:
        self.client.create_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'BucketAlreadyExists':
            raise Exception(f"Bucket '{bucket_name}' already exists")
        elif error_code == 'InvalidBucketName':
            raise Exception(f"Invalid bucket name: {bucket_name}")
        raise Exception(f"Failed to create bucket: {e}")
```

### 2. Object Lock (WORM) Support

Object Lock provides Write Once Read Many (WORM) compliance:

```python
def create_bucket_with_object_lock(self, bucket_name, default_retention_days=None):
    """Create bucket with Object Lock enabled."""
    # Object Lock must be enabled at bucket creation time
    create_params = {
        'Bucket': bucket_name,
        'ObjectLockEnabledForBucket': True
    }
    
    self.client.create_bucket(**create_params)
    
    # Set default retention policy
    if default_retention_days:
        self.client.put_object_lock_configuration(
            Bucket=bucket_name,
            ObjectLockConfiguration={
                'ObjectLockEnabled': 'Enabled',
                'Rule': {
                    'DefaultRetention': {
                        'Mode': 'GOVERNANCE',  # or 'COMPLIANCE'
                        'Days': default_retention_days
                    }
                }
            }
        )
```

**Object Lock Key Points:**
- Must be enabled at bucket creation (cannot be added later)
- Two modes: GOVERNANCE (can be overridden) and COMPLIANCE (cannot be deleted)
- Supports both time-based retention and legal holds
- Essential for regulatory compliance use cases

## Object Operations

### 1. Listing Objects with Metadata

```python
def list_objects_with_metadata(self, bucket_name):
    """List objects with useful metadata."""
    try:
        response = self.client.list_objects_v2(Bucket=bucket_name)
        objects = []
        
        for obj in response.get('Contents', []):
            objects.append({
                'key': obj['Key'],
                'size': obj['Size'],
                'last_modified': obj['LastModified'],
                'etag': obj.get('ETag', '').strip('"'),
                'storage_class': obj.get('StorageClass', 'STANDARD')
            })
        
        return objects
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            raise Exception(f"Bucket '{bucket_name}' does not exist")
        raise Exception(f"Failed to list objects: {e}")
```

### 2. File Upload with Progress

**Simple Upload (Small Files):**
```python
def upload_file_simple(self, bucket_name, object_name, file_path):
    """Simple upload for small files."""
    self.client.upload_file(file_path, bucket_name, object_name)
```

**Chunked Upload with Progress (Large Files):**
```python
def upload_file_chunked(self, bucket_name, object_name, file_path, 
                       progress_callback=None, cancel_event=None):
    """Upload with progress tracking and cancellation."""
    file_size = os.path.getsize(file_path)
    chunk_size = 64 * 1024  # 64KB chunks
    
    if file_size <= chunk_size:
        # Small file - single put_object
        with open(file_path, 'rb') as f:
            data = f.read()
            if cancel_event and cancel_event.is_set():
                raise Exception("Upload cancelled")
            
            self.client.put_object(
                Bucket=bucket_name,
                Key=object_name,
                Body=data
            )
            if progress_callback:
                progress_callback(file_size)
    else:
        # Large file - multipart upload
        self._multipart_upload(bucket_name, object_name, file_path,
                              progress_callback, cancel_event)

def _multipart_upload(self, bucket_name, object_name, file_path,
                     progress_callback, cancel_event):
    """Handle multipart upload with proper cleanup."""
    response = self.client.create_multipart_upload(
        Bucket=bucket_name,
        Key=object_name
    )
    upload_id = response['UploadId']
    parts = []
    
    try:
        with open(file_path, 'rb') as f:
            part_number = 1
            bytes_uploaded = 0
            
            while True:
                if cancel_event and cancel_event.is_set():
                    # Cancel requested - abort upload
                    self.client.abort_multipart_upload(
                        Bucket=bucket_name,
                        Key=object_name,
                        UploadId=upload_id
                    )
                    raise Exception("Upload cancelled")
                
                chunk = f.read(64 * 1024)
                if not chunk:
                    break
                
                # Upload part
                part_response = self.client.upload_part(
                    Bucket=bucket_name,
                    Key=object_name,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk
                )
                
                parts.append({
                    'ETag': part_response['ETag'],
                    'PartNumber': part_number
                })
                
                bytes_uploaded += len(chunk)
                if progress_callback:
                    progress_callback(bytes_uploaded)
                
                part_number += 1
        
        # Complete multipart upload
        self.client.complete_multipart_upload(
            Bucket=bucket_name,
            Key=object_name,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )
        
    except Exception as e:
        # Always abort on failure to prevent orphaned parts
        try:
            self.client.abort_multipart_upload(
                Bucket=bucket_name,
                Key=object_name,
                UploadId=upload_id
            )
        except:
            pass  # Ignore cleanup errors
        raise e
```

**Key Upload Insights:**
- Use `upload_file()` for simple cases (small files, no progress needed)
- Implement chunked/multipart upload for large files with progress
- Always abort multipart uploads on cancellation/failure
- 64KB chunks provide good balance of responsiveness and performance
- Progress callbacks should be called from the same thread doing the upload

### 3. File Download with Progress

```python
def download_file_chunked(self, bucket_name, object_name, file_path,
                         progress_callback=None, cancel_event=None):
    """Download with progress and cancellation support."""
    try:
        response = self.client.get_object(Bucket=bucket_name, Key=object_name)
        total_size = response['ContentLength']
        
        # Use temporary file during download
        temp_file = file_path + '.tmp'
        bytes_downloaded = 0
        
        try:
            with open(temp_file, 'wb') as f:
                while True:
                    if cancel_event and cancel_event.is_set():
                        os.unlink(temp_file)  # Clean up
                        raise Exception("Download cancelled")
                    
                    chunk = response['Body'].read(64 * 1024)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    
                    if progress_callback:
                        progress_callback(bytes_downloaded)
            
            # Move temp file to final location
            if os.path.exists(file_path):
                os.unlink(file_path)
            os.rename(temp_file, file_path)
            
        except Exception as e:
            # Clean up temp file on any error
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            raise e
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise Exception(f"Object '{object_name}' not found")
        raise Exception(f"Download failed: {e}")
```

### 4. Object Metadata and Content Preview

```python
def get_object_metadata(self, bucket_name, object_key):
    """Get comprehensive object metadata."""
    try:
        response = self.client.head_object(Bucket=bucket_name, Key=object_key)
        return {
            'size': response['ContentLength'],
            'last_modified': response['LastModified'],
            'content_type': response.get('ContentType', 'application/octet-stream'),
            'etag': response.get('ETag', '').strip('"'),
            'storage_class': response.get('StorageClass', 'STANDARD'),
            'metadata': response.get('Metadata', {})
        }
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        raise Exception(f"Failed to get metadata: {e}")

def get_object_content_preview(self, bucket_name, object_name, max_size=10240):
    """Get object content for preview (text files only)."""
    metadata = self.get_object_metadata(bucket_name, object_name)
    if not metadata or metadata['size'] > max_size:
        raise Exception(f"File too large for preview")
    
    response = self.client.get_object(Bucket=bucket_name, Key=object_name)
    content = response['Body'].read()
    
    # Detect binary content
    if b'\x00' in content:  # Null bytes indicate binary
        raise Exception("Binary file cannot be previewed")
    
    # Check printable character ratio
    printable_chars = sum(1 for byte in content 
                         if 32 <= byte <= 126 or byte in [9, 10, 13])
    if len(content) > 0 and (printable_chars / len(content)) < 0.8:
        raise Exception("File appears to be binary")
    
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return content.decode('latin-1')
        except UnicodeDecodeError:
            raise Exception("Unable to decode file as text")
```

## Directory Operations

MinIO doesn't have native directories, but we can simulate them:

```python
def create_directory(self, bucket_name, directory_name):
    """Create directory by uploading empty object with trailing slash."""
    if not directory_name.endswith('/'):
        directory_name += '/'
    
    self.client.put_object(
        Bucket=bucket_name,
        Key=directory_name,
        Body=b''  # Empty content creates directory marker
    )

def delete_directory(self, bucket_name, directory_name):
    """Delete empty directory (remove directory marker)."""
    if not directory_name.endswith('/'):
        directory_name += '/'
    
    # Check if directory is empty
    response = self.client.list_objects_v2(
        Bucket=bucket_name,
        Prefix=directory_name,
        MaxKeys=2
    )
    
    objects = response.get('Contents', [])
    non_marker_objects = [obj for obj in objects if obj['Key'] != directory_name]
    
    if non_marker_objects:
        raise Exception(f"Directory '{directory_name}' is not empty")
    
    # Safe to delete
    self.client.delete_object(Bucket=bucket_name, Key=directory_name)
```

## Object Lock Advanced Features

### 1. Retention Policies

```python
def set_object_retention(self, bucket_name, object_name, retain_until_date, mode='GOVERNANCE'):
    """Set retention period on specific object."""
    from datetime import datetime
    
    if isinstance(retain_until_date, str):
        retain_until_date = datetime.fromisoformat(retain_until_date)
    
    self.client.put_object_retention(
        Bucket=bucket_name,
        Key=object_name,
        Retention={
            'Mode': mode,  # 'GOVERNANCE' or 'COMPLIANCE'
            'RetainUntilDate': retain_until_date
        }
    )

def get_object_retention(self, bucket_name, object_name):
    """Get retention information for object."""
    try:
        response = self.client.get_object_retention(
            Bucket=bucket_name,
            Key=object_name
        )
        return response.get('Retention', {})
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchObjectLockConfiguration':
            return {}  # No retention set
        raise e
```

### 2. Legal Holds

```python
def set_legal_hold(self, bucket_name, object_name, status='ON'):
    """Set legal hold on object (independent of retention)."""
    self.client.put_object_legal_hold(
        Bucket=bucket_name,
        Key=object_name,
        LegalHold={'Status': status}  # 'ON' or 'OFF'
    )

def get_legal_hold(self, bucket_name, object_name):
    """Get legal hold status."""
    try:
        response = self.client.get_object_legal_hold(
            Bucket=bucket_name,
            Key=object_name
        )
        return response.get('LegalHold', {})
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchObjectLockConfiguration':
            return {}
        raise e
```

## Presigned URLs

```python
def generate_presigned_url(self, bucket_name, object_name, expires_in=3600, method='get_object'):
    """Generate presigned URL for temporary access."""
    try:
        return self.client.generate_presigned_url(
            method,
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expires_in
        )
    except ClientError as e:
        raise Exception(f"Failed to generate presigned URL: {e}")

def generate_upload_url(self, bucket_name, object_name, expires_in=3600):
    """Generate presigned URL for uploads."""
    return self.generate_presigned_url(
        bucket_name, 
        object_name, 
        expires_in, 
        'put_object'
    )
```

## Error Handling Patterns

```python
def handle_client_error(self, e: ClientError, operation: str):
    """Centralized error handling for common S3 errors."""
    error_code = e.response['Error']['Code']
    
    error_mapping = {
        'NoSuchBucket': f"Bucket does not exist",
        'NoSuchKey': f"Object not found",
        'AccessDenied': f"Access denied - check permissions",
        'BucketAlreadyExists': f"Bucket already exists",
        'InvalidBucketName': f"Invalid bucket name",
        'BucketNotEmpty': f"Bucket is not empty",
        'NoSuchObjectLockConfiguration': f"Object Lock not configured",
    }
    
    if error_code in error_mapping:
        raise Exception(f"{operation} failed: {error_mapping[error_code]}")
    else:
        raise Exception(f"{operation} failed: {e}")
```

## Performance Considerations

### 1. Connection Pooling

```python
# Configure boto3 for better performance
import boto3
from botocore.config import Config

config = Config(
    max_pool_connections=50,  # Increase connection pool
    retries={'max_attempts': 3, 'mode': 'adaptive'},
    connect_timeout=10,
    read_timeout=30
)

client = boto3.client('s3', config=config, ...)
```

### 2. Batching Operations

```python
def delete_multiple_objects(self, bucket_name, object_keys):
    """Delete multiple objects efficiently."""
    # S3 supports deleting up to 1000 objects per request
    batch_size = 1000
    
    for i in range(0, len(object_keys), batch_size):
        batch = object_keys[i:i + batch_size]
        delete_objects = [{'Key': key} for key in batch]
        
        self.client.delete_objects(
            Bucket=bucket_name,
            Delete={'Objects': delete_objects}
        )
```

### 3. Memory Management for Large Files

```python
def process_large_object(self, bucket_name, object_name):
    """Stream large objects without loading into memory."""
    response = self.client.get_object(Bucket=bucket_name, Key=object_name)
    
    # Process in chunks to avoid memory issues
    for chunk in response['Body'].iter_chunks(chunk_size=1024*1024):
        process_chunk(chunk)  # Your processing logic
```

## Testing Strategies

### 1. Mock Client for Unit Tests

```python
from unittest.mock import MagicMock, patch

class TestMinioClient:
    def setup_method(self):
        self.mock_client = MagicMock()
        self.minio_client = MinioClient(client=self.mock_client)
    
    def test_list_buckets(self):
        self.mock_client.list_buckets.return_value = {
            'Buckets': [{'Name': 'test-bucket'}]
        }
        
        buckets = self.minio_client.list_buckets()
        assert buckets == ['test-bucket']
        self.mock_client.list_buckets.assert_called_once()
```

### 2. Integration Tests with Test Server

```python
import pytest
from minio import Minio

@pytest.fixture
def test_minio_client():
    # Assumes MinIO test server running on localhost:9000
    client = MinioClient(
        endpoint_url='http://localhost:9000',
        access_key='minioadmin',
        secret_key='minioadmin'
    )
    
    # Clean up any existing test data
    try:
        client.delete_bucket('test-bucket')
    except:
        pass
    
    yield client
    
    # Cleanup after test
    try:
        client.delete_bucket('test-bucket')
    except:
        pass
```

## Common Pitfalls and Solutions

1. **Endpoint URL Format:**
   - ❌ `endpoint_url='localhost:9000'`
   - ✅ `endpoint_url='http://localhost:9000'`

2. **SSL/TLS Issues:**
   - Development: Use `verify=False` in boto3 config
   - Production: Properly configure SSL certificates

3. **Object Lock Requirements:**
   - Must be enabled at bucket creation time
   - Cannot be enabled on existing buckets

4. **Large File Uploads:**
   - Use multipart upload for files > 100MB
   - Implement proper progress tracking and cancellation

5. **Directory Handling:**
   - S3/MinIO doesn't have directories, only key prefixes
   - Use trailing slashes to simulate directories

6. **Error Handling:**
   - Always handle `ClientError` specifically
   - Map S3 error codes to user-friendly messages

7. **Memory Usage:**
   - Stream large files instead of loading into memory
   - Use chunked reading/writing for large objects

## Configuration Best Practices

```python
# Configuration structure
class MinioConfig:
    def __init__(self):
        self.endpoint_url = os.getenv('MINIO_ENDPOINT_URL')
        self.access_key = os.getenv('MINIO_ACCESS_KEY')
        self.secret_key = os.getenv('MINIO_SECRET_KEY')
        self.region = os.getenv('MINIO_REGION', 'us-east-1')
        self.use_ssl = os.getenv('MINIO_USE_SSL', 'false').lower() == 'true'
        
        self.validate()
    
    def validate(self):
        required = ['endpoint_url', 'access_key', 'secret_key']
        missing = [field for field in required if not getattr(self, field)]
        if missing:
            raise ValueError(f"Missing required config: {missing}")
```

This guide provides a comprehensive foundation for working with MinIO/S3 APIs and building robust client applications.