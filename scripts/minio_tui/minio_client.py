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

    def create_bucket(self, bucket_name):
        """Creates a new bucket."""
        self.client.create_bucket(Bucket=bucket_name)

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
