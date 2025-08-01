import boto3
import os
import sys
from .config import settings

class MinioClient:
    def __init__(self, client=None):
        if client:
            self.client = client
        else:
            # Use .get() to safely access potentially missing keys
            endpoint_url = settings.get("MINIO.ENDPOINT_URL")
            access_key = settings.get("MINIO.ACCESS_KEY")
            secret_key = settings.get("MINIO.SECRET_KEY")

            # Now, check if any of the required values are missing
            if not all([endpoint_url, access_key, secret_key]):
                missing = []
                if not endpoint_url: missing.append("MINIO.ENDPOINT_URL")
                if not access_key: missing.append("MINIO.ACCESS_KEY")
                if not secret_key: missing.append("MINIO.SECRET_KEY")
                raise ValueError(
                    f"Missing configuration: {', '.join(missing)}. "
                    "Please create a config.toml or .env file in your current directory, "
                    "or set the corresponding environment variables. "
                    "See the README in the 'scripts' directory for more details."
                )

            self.client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )

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

    def upload_file(self, bucket_name, object_name, file_path):
        """Uploads a file to a bucket."""
        self.client.upload_file(file_path, bucket_name, object_name)

    def download_file(self, bucket_name, object_name, file_path):
        """Downloads a file from a bucket."""
        self.client.download_file(bucket_name, object_name, file_path)

    def generate_presigned_url(self, bucket_name, object_name, expires_in=3600):
        """Generates a presigned URL for an object."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
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
