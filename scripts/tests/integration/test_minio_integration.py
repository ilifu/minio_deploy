import unittest
import time
import os
import tempfile
from pathlib import Path
import sys

# Add the 'scripts' directory to the Python path to allow importing 'minio_tui'
scripts_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(scripts_dir))

from minio_tui.simple_config import Config
from minio_tui.minio_client import MinioClient


class MinIOIntegrationTest(unittest.TestCase):
    """Base class for MinIO integration tests that require a real MinIO server."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment with real MinIO connection."""
        try:
            # Create MinIO client directly with test configuration
            import boto3
            cls.boto3_client = boto3.client(
                "s3",
                endpoint_url="http://localhost:9000",
                aws_access_key_id="testuser",
                aws_secret_access_key="testpass123",
            )
            cls.minio_client = MinioClient(client=cls.boto3_client)
            
            # Test connection by listing buckets
            cls.minio_client.list_buckets()
            print("✅ Successfully connected to MinIO test server")
            
        except Exception as e:
            raise unittest.SkipTest(f"MinIO test server not available: {e}")
    
    def setUp(self):
        """Set up individual test."""
        # Create a unique test bucket name
        self.test_bucket_name = f"test-bucket-{int(time.time())}"
        self.test_objects_created = []
        self.test_buckets_created = []
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up test objects
        for bucket_name, object_name in self.test_objects_created:
            try:
                self.minio_client.delete_object(bucket_name, object_name)
            except Exception:
                pass
        
        # Clean up test buckets
        for bucket_name in self.test_buckets_created:
            try:
                self.minio_client.delete_bucket(bucket_name)
            except Exception:
                pass


class TestMinIOClientIntegration(MinIOIntegrationTest):
    """Integration tests for MinioClient against real MinIO server."""
    
    def test_bucket_lifecycle(self):
        """Test complete bucket lifecycle: create, list, delete."""
        # Create bucket
        self.minio_client.create_bucket(self.test_bucket_name)
        self.test_buckets_created.append(self.test_bucket_name)
        
        # Verify bucket exists
        buckets = self.minio_client.list_buckets()
        self.assertIn(self.test_bucket_name, buckets)
        
        # Delete bucket
        self.minio_client.delete_bucket(self.test_bucket_name)
        self.test_buckets_created.remove(self.test_bucket_name)
        
        # Verify bucket is gone
        buckets = self.minio_client.list_buckets()
        self.assertNotIn(self.test_bucket_name, buckets)
    
    def test_object_lifecycle(self):
        """Test complete object lifecycle: upload, list, download, delete."""
        # Create test bucket
        self.minio_client.create_bucket(self.test_bucket_name)
        self.test_buckets_created.append(self.test_bucket_name)
        
        # Create test file
        test_content = "Hello, MinIO Integration Test!"
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(test_content)
            test_file_path = f.name
        
        try:
            object_name = "test-object.txt"
            
            # Upload file
            self.minio_client.upload_file(self.test_bucket_name, object_name, test_file_path)
            self.test_objects_created.append((self.test_bucket_name, object_name))
            
            # List objects
            objects = self.minio_client.list_objects(self.test_bucket_name)
            self.assertIn(object_name, objects)
            
            # Download file
            with tempfile.NamedTemporaryFile(delete=False) as f:
                download_path = f.name
            
            self.minio_client.download_file(self.test_bucket_name, object_name, download_path)
            
            # Verify content
            with open(download_path, 'r') as f:
                downloaded_content = f.read()
            self.assertEqual(downloaded_content, test_content)
            
            # Get metadata
            metadata = self.minio_client.get_object_metadata(self.test_bucket_name, object_name)
            self.assertGreater(metadata['size'], 0)
            self.assertIsNotNone(metadata['last_modified'])
            
            # Delete object
            self.minio_client.delete_object(self.test_bucket_name, object_name)
            self.test_objects_created.remove((self.test_bucket_name, object_name))
            
            # Verify object is gone
            objects = self.minio_client.list_objects(self.test_bucket_name)
            self.assertNotIn(object_name, objects)
            
        finally:
            # Clean up temp files
            try:
                os.unlink(test_file_path)
                os.unlink(download_path)
            except:
                pass
    
    def test_directory_operations(self):
        """Test directory creation and deletion."""
        # Create test bucket
        self.minio_client.create_bucket(self.test_bucket_name)
        self.test_buckets_created.append(self.test_bucket_name)
        
        # Create directory
        directory_name = "test-folder/"
        self.minio_client.create_directory(self.test_bucket_name, directory_name)
        self.test_objects_created.append((self.test_bucket_name, directory_name))
        
        # Verify directory exists
        objects = self.minio_client.list_objects(self.test_bucket_name)
        self.assertIn(directory_name, objects)
        
        # Delete directory
        self.minio_client.delete_directory(self.test_bucket_name, directory_name)
        self.test_objects_created.remove((self.test_bucket_name, directory_name))
        
        # Verify directory is gone
        objects = self.minio_client.list_objects(self.test_bucket_name)
        self.assertNotIn(directory_name, objects)
    
    def test_presigned_urls(self):
        """Test presigned URL generation."""
        # Create test bucket
        self.minio_client.create_bucket(self.test_bucket_name)
        self.test_buckets_created.append(self.test_bucket_name)
        
        # Create test object
        test_content = "Test content for presigned URL"
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(test_content)
            test_file_path = f.name
        
        try:
            object_name = "test-presigned.txt"
            self.minio_client.upload_file(self.test_bucket_name, object_name, test_file_path)
            self.test_objects_created.append((self.test_bucket_name, object_name))
            
            # Generate download presigned URL
            download_url = self.minio_client.generate_presigned_url(
                self.test_bucket_name, object_name, expires_in=3600
            )
            self.assertIsInstance(download_url, str)
            self.assertIn("localhost:9000", download_url)
            self.assertIn(self.test_bucket_name, download_url)
            self.assertIn(object_name, download_url)
            
            # Generate upload presigned URL
            upload_object_name = "test-upload-presigned.txt"
            upload_url = self.minio_client.generate_upload_presigned_url(
                self.test_bucket_name, upload_object_name, expires_in=3600
            )
            self.assertIsInstance(upload_url, str)
            self.assertIn("localhost:9000", upload_url)
            self.assertIn(self.test_bucket_name, upload_url)
            self.assertIn(upload_object_name, upload_url)
            
        finally:
            try:
                os.unlink(test_file_path)
            except:
                pass


if __name__ == '__main__':
    unittest.main()