import boto3
import os
import sys
from .simple_config import settings

class MinioClient:
    def __init__(self, client=None):
        if client:
            self.client = client
        else:
            # Get MinIO configuration using the simplified config system
            try:
                minio_config = settings.get_minio_config()
                self.client = boto3.client(
                    "s3",
                    endpoint_url=minio_config["endpoint_url"],
                    aws_access_key_id=minio_config["access_key"],
                    aws_secret_access_key=minio_config["secret_key"],
                )
            except ValueError as e:
                raise ValueError(str(e))

    def list_buckets(self):
        """Lists all buckets in the MinIO instance."""
        response = self.client.list_buckets()
        return [bucket["Name"] for bucket in response["Buckets"]]

    def create_bucket(self, bucket_name, object_lock_enabled=False, default_retention_days=None, default_retention_mode='GOVERNANCE'):
        """Creates a new bucket, optionally with Object Lock enabled."""
        create_params = {'Bucket': bucket_name}
        
        # Enable Object Lock if requested
        if object_lock_enabled:
            create_params['ObjectLockEnabledForBucket'] = True
        
        self.client.create_bucket(**create_params)
        
        # Set default retention configuration if specified and Object Lock is enabled
        if object_lock_enabled and default_retention_days:
            from datetime import timedelta
            try:
                self.client.put_object_lock_configuration(
                    Bucket=bucket_name,
                    ObjectLockConfiguration={
                        'ObjectLockEnabled': 'Enabled',
                        'Rule': {
                            'DefaultRetention': {
                                'Mode': default_retention_mode,
                                'Days': default_retention_days
                            }
                        }
                    }
                )
            except Exception as e:
                # If setting default retention fails, the bucket is still created
                # but without default retention
                raise Exception(f"Bucket created but failed to set default retention: {str(e)}")

    def delete_bucket(self, bucket_name):
        """Deletes a bucket."""
        self.client.delete_bucket(Bucket=bucket_name)

    def list_objects(self, bucket_name):
        """Lists all objects in a bucket."""
        response = self.client.list_objects_v2(Bucket=bucket_name)
        return [obj["Key"] for obj in response.get("Contents", [])]

    def list_objects_with_metadata(self, bucket_name):
        """Lists all objects in a bucket with metadata."""
        response = self.client.list_objects_v2(Bucket=bucket_name)
        objects = []
        for obj in response.get("Contents", []):
            objects.append({
                'key': obj["Key"],
                'size': obj["Size"],
                'last_modified': obj["LastModified"],
                'etag': obj.get("ETag", "").strip('"'),
                'storage_class': obj.get("StorageClass", "STANDARD")
            })
        return objects

    def get_object_metadata(self, bucket_name, object_key):
        """Get detailed metadata for a specific object."""
        try:
            response = self.client.head_object(Bucket=bucket_name, Key=object_key)
            return {
                'size': response["ContentLength"],
                'last_modified': response["LastModified"],
                'content_type': response.get("ContentType", "application/octet-stream"),
                'etag': response.get("ETag", "").strip('"'),
                'storage_class': response.get("StorageClass", "STANDARD"),
                'metadata': response.get("Metadata", {})
            }
        except Exception as e:
            # If we can't get metadata, return minimal info
            return {
                'size': 0,
                'last_modified': None,
                'content_type': 'unknown',
                'etag': '',
                'storage_class': 'STANDARD',
                'metadata': {}
            }

    def upload_file(self, bucket_name, object_name, file_path, progress_callback=None, cancel_event=None):
        """Uploads a file to a bucket with optional progress tracking and cancellation."""
        if progress_callback or cancel_event:
            # Use chunked upload for progress tracking and cancellation support
            self._upload_file_chunked(bucket_name, object_name, file_path, progress_callback, cancel_event)
        else:
            # Use simple upload without progress
            self.client.upload_file(file_path, bucket_name, object_name)
    
    def _upload_file_chunked(self, bucket_name, object_name, file_path, progress_callback=None, cancel_event=None):
        """Upload a file in chunks to support progress tracking and cancellation."""
        import os
        
        file_size = os.path.getsize(file_path)
        chunk_size = 64 * 1024  # 64KB chunks
        bytes_uploaded = 0
        
        try:
            with open(file_path, 'rb') as file_obj:
                # For small files, use put_object directly
                if file_size <= chunk_size:
                    data = file_obj.read()
                    if cancel_event and cancel_event.is_set():
                        raise Exception("Upload cancelled")
                    
                    self.client.put_object(
                        Bucket=bucket_name,
                        Key=object_name,
                        Body=data
                    )
                    bytes_uploaded = file_size
                    if progress_callback:
                        progress_callback(bytes_uploaded)
                else:
                    # For larger files, use multipart upload
                    response = self.client.create_multipart_upload(
                        Bucket=bucket_name,
                        Key=object_name
                    )
                    upload_id = response['UploadId']
                    parts = []
                    part_number = 1
                    
                    try:
                        while True:
                            if cancel_event and cancel_event.is_set():
                                # Abort the multipart upload
                                self.client.abort_multipart_upload(
                                    Bucket=bucket_name,
                                    Key=object_name,
                                    UploadId=upload_id
                                )
                                raise Exception("Upload cancelled")
                            
                            chunk = file_obj.read(chunk_size)
                            if not chunk:
                                break
                            
                            # Upload the part
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
                        
                        # Complete the multipart upload
                        if not (cancel_event and cancel_event.is_set()):
                            self.client.complete_multipart_upload(
                                Bucket=bucket_name,
                                Key=object_name,
                                UploadId=upload_id,
                                MultipartUpload={'Parts': parts}
                            )
                        
                    except Exception as e:
                        # Abort the multipart upload on any error
                        try:
                            self.client.abort_multipart_upload(
                                Bucket=bucket_name,
                                Key=object_name,
                                UploadId=upload_id
                            )
                        except:
                            pass  # Ignore errors when aborting
                        raise e
                        
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                raise Exception("Upload cancelled")
            raise e

    def download_file(self, bucket_name, object_name, file_path, progress_callback=None, cancel_event=None):
        """Downloads a file from a bucket with optional progress tracking and cancellation."""
        if progress_callback or cancel_event:
            # Use chunked download for progress tracking and cancellation support
            self._download_file_chunked(bucket_name, object_name, file_path, progress_callback, cancel_event)
        else:
            # Use simple download without progress
            self.client.download_file(bucket_name, object_name, file_path)
    
    def _download_file_chunked(self, bucket_name, object_name, file_path, progress_callback=None, cancel_event=None):
        """Download a file in chunks to support progress tracking and cancellation."""
        import os
        
        try:
            # Get object info
            response = self.client.get_object(Bucket=bucket_name, Key=object_name)
            file_size = response['ContentLength']
            chunk_size = 64 * 1024  # 64KB chunks
            bytes_downloaded = 0
            
            # Create a temporary file first
            temp_file_path = file_path + '.tmp'
            
            try:
                with open(temp_file_path, 'wb') as file_obj:
                    body = response['Body']
                    
                    while True:
                        if cancel_event and cancel_event.is_set():
                            # Clean up temp file
                            try:
                                os.unlink(temp_file_path)
                            except:
                                pass
                            raise Exception("Download cancelled")
                        
                        chunk = body.read(chunk_size)
                        if not chunk:
                            break
                        
                        file_obj.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(bytes_downloaded)
                
                # If we got here without cancellation, move temp file to final location
                if not (cancel_event and cancel_event.is_set()):
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                    os.rename(temp_file_path, file_path)
                    
            except Exception as e:
                # Clean up temp file on any error
                try:
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                except:
                    pass
                raise e
                    
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                raise Exception("Download cancelled")
            raise e

    def generate_presigned_url(self, bucket_name, object_name, expires_in=3600):
        """Generates a presigned URL for downloading an object."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=expires_in,
        )

    def generate_upload_presigned_url(self, bucket_name, object_name, expires_in=3600, content_type=None):
        """Generates a presigned URL for uploading an object."""
        params = {"Bucket": bucket_name, "Key": object_name}
        
        # Add content type if specified
        if content_type:
            params["ContentType"] = content_type
        
        return self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def delete_object(self, bucket_name, object_name):
        """Deletes an object from a bucket."""
        self.client.delete_object(Bucket=bucket_name, Key=object_name)

    def rename_object(self, bucket_name, old_name, new_name):
        """Renames an object by copying it to the new name and deleting the old one."""
        # Copy the object to the new name
        copy_source = {'Bucket': bucket_name, 'Key': old_name}
        self.client.copy_object(
            CopySource=copy_source,
            Bucket=bucket_name,
            Key=new_name
        )
        # Delete the old object
        self.client.delete_object(Bucket=bucket_name, Key=old_name)

    def create_directory(self, bucket_name, directory_name):
        """Creates a directory by uploading an empty object with trailing slash."""
        # Ensure directory name ends with /
        if not directory_name.endswith('/'):
            directory_name += '/'
        
        # Upload empty content to create the directory marker
        self.client.put_object(
            Bucket=bucket_name,
            Key=directory_name,
            Body=b''
        )

    def delete_directory(self, bucket_name, directory_name):
        """Deletes an empty directory (removes the directory marker object)."""
        # Ensure directory name ends with /
        if not directory_name.endswith('/'):
            directory_name += '/'
        
        # Check if directory is empty by listing objects with the prefix
        response = self.client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=directory_name,
            MaxKeys=2  # We only need to know if there's more than just the directory marker
        )
        
        objects = response.get('Contents', [])
        
        # Filter out the directory marker itself
        non_marker_objects = [obj for obj in objects if obj['Key'] != directory_name]
        
        if non_marker_objects:
            raise Exception(f"Directory '{directory_name}' is not empty")
        
        # Directory is empty, safe to delete the marker
        self.client.delete_object(Bucket=bucket_name, Key=directory_name)

    def set_object_retention(self, bucket_name, object_name, retain_until_date, mode='GOVERNANCE'):
        """Set object retention period (Object Lock)."""
        from datetime import datetime
        
        # Ensure retain_until_date is a datetime object
        if isinstance(retain_until_date, str):
            retain_until_date = datetime.fromisoformat(retain_until_date)
        
        try:
            self.client.put_object_retention(
                Bucket=bucket_name,
                Key=object_name,
                Retention={
                    'Mode': mode,  # GOVERNANCE or COMPLIANCE
                    'RetainUntilDate': retain_until_date
                }
            )
        except Exception as e:
            raise Exception(f"Failed to set object retention: {str(e)}")

    def get_object_retention(self, bucket_name, object_name):
        """Get object retention information."""
        try:
            response = self.client.get_object_retention(
                Bucket=bucket_name,
                Key=object_name
            )
            return response.get('Retention', {})
        except Exception:
            # Object may not have retention set
            return {}

    def set_object_legal_hold(self, bucket_name, object_name, status='ON'):
        """Set object legal hold (Object Lock)."""
        try:
            self.client.put_object_legal_hold(
                Bucket=bucket_name,
                Key=object_name,
                LegalHold={'Status': status}  # ON or OFF
            )
        except Exception as e:
            raise Exception(f"Failed to set legal hold: {str(e)}")

    def get_object_legal_hold(self, bucket_name, object_name):
        """Get object legal hold status."""
        try:
            response = self.client.get_object_legal_hold(
                Bucket=bucket_name,
                Key=object_name
            )
            return response.get('LegalHold', {})
        except Exception:
            # Object may not have legal hold set
            return {}

    def get_object_content(self, bucket_name, object_name, max_size=10 * 1024):
        """Get object content for preview (limited to max_size bytes)."""
        try:
            # Get object metadata first to check size
            metadata = self.get_object_metadata(bucket_name, object_name)
            file_size = metadata.get('size', 0)
            
            # Limit preview to max_size bytes (default 10KB)
            if file_size > max_size:
                raise Exception(f"File too large for preview ({format_size(file_size)}). Maximum preview size is {format_size(max_size)}")
            
            # Download the object content
            response = self.client.get_object(
                Bucket=bucket_name,
                Key=object_name
            )
            
            # Read the content
            content = response['Body'].read()
            
            # Try to decode as text
            try:
                # Try UTF-8 first
                text_content = content.decode('utf-8')
                # Check for common binary indicators even if it decodes
                if self._contains_binary_indicators(content):
                    raise Exception("File contains binary data and cannot be previewed as text")
                return text_content
            except UnicodeDecodeError:
                try:
                    # Try latin-1 as fallback
                    text_content = content.decode('latin-1')
                    # Check for common binary indicators
                    if self._contains_binary_indicators(content):
                        raise Exception("File contains binary data and cannot be previewed as text")
                    return text_content
                except UnicodeDecodeError:
                    raise Exception("File contains binary data and cannot be previewed as text")
                    
        except Exception as e:
            raise Exception(f"Failed to get object content: {str(e)}")

    def _contains_binary_indicators(self, content: bytes) -> bool:
        """Check if content contains common binary file indicators."""
        # Check for null bytes (common in binary files)
        if b'\x00' in content:
            return True
        
        # Check for high percentage of non-printable characters
        printable_chars = 0
        for byte in content:
            # Count ASCII printable characters, tabs, newlines, carriage returns
            if (32 <= byte <= 126) or byte in [9, 10, 13]:
                printable_chars += 1
        
        # If less than 80% are printable, consider it binary
        if len(content) > 0 and (printable_chars / len(content)) < 0.8:
            return True
            
        return False

def format_size(size_bytes):
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    if i == 0:
        return f"{int(size_bytes)} {size_names[i]}"
    else:
        return f"{size_bytes:.1f} {size_names[i]}"
