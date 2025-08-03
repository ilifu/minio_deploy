import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add the 'scripts' directory to the Python path to allow importing 'minio_tui'
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from minio_tui.minio_client import MinioClient

class TestMinioClient(unittest.TestCase):

    def setUp(self):
        """Set up a mock boto3 client and our MinioClient."""
        self.mock_boto3_client = MagicMock()
        self.minio_client = MinioClient(client=self.mock_boto3_client)

    def test_list_buckets(self):
        """Tests that list_buckets calls the correct boto3 method."""
        # Set up the mock to return a specific value
        self.mock_boto3_client.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket1"},
                {"Name": "bucket2"},
            ]
        }

        # Call the method we are testing
        buckets = self.minio_client.list_buckets()

        # Assert that the mock was called correctly
        self.mock_boto3_client.list_buckets.assert_called_once()
        # Assert that the method returned the correct value
        self.assertEqual(buckets, ["bucket1", "bucket2"])

    def test_create_bucket(self):
        """Tests that create_bucket calls the correct boto3 method."""
        self.minio_client.create_bucket("new-bucket")
        self.mock_boto3_client.create_bucket.assert_called_once_with(Bucket="new-bucket")

    def test_create_bucket_with_object_lock(self):
        """Tests that create_bucket with Object Lock calls the correct boto3 methods."""
        self.minio_client.create_bucket("lock-bucket", object_lock_enabled=True, default_retention_days=30, default_retention_mode="GOVERNANCE")
        
        # Verify create_bucket was called with Object Lock enabled
        self.mock_boto3_client.create_bucket.assert_called_once_with(
            Bucket="lock-bucket",
            ObjectLockEnabledForBucket=True
        )
        
        # Verify put_object_lock_configuration was called for default retention
        self.mock_boto3_client.put_object_lock_configuration.assert_called_once_with(
            Bucket="lock-bucket",
            ObjectLockConfiguration={
                'ObjectLockEnabled': 'Enabled',
                'Rule': {
                    'DefaultRetention': {
                        'Mode': 'GOVERNANCE',
                        'Days': 30
                    }
                }
            }
        )

    def test_delete_bucket(self):
        """Tests that delete_bucket calls the correct boto3 method."""
        self.minio_client.delete_bucket("bucket-to-delete")
        self.mock_boto3_client.delete_bucket.assert_called_once_with(Bucket="bucket-to-delete")

    def test_list_objects(self):
        """Tests that list_objects calls the correct boto3 method."""
        self.mock_boto3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "object1"},
                {"Key": "object2"},
            ]
        }
        objects = self.minio_client.list_objects("my-bucket")
        self.mock_boto3_client.list_objects_v2.assert_called_once_with(Bucket="my-bucket")
        self.assertEqual(objects, ["object1", "object2"])

    def test_upload_file(self):
        """Tests that upload_file calls the correct boto3 method."""
        self.minio_client.upload_file("my-bucket", "my-object", "/path/to/file")
        self.mock_boto3_client.upload_file.assert_called_once_with("/path/to/file", "my-bucket", "my-object")

    def test_download_file(self):
        """Tests that download_file calls the correct boto3 method."""
        self.minio_client.download_file("my-bucket", "my-object", "/path/to/save")
        self.mock_boto3_client.download_file.assert_called_once_with("my-bucket", "my-object", "/path/to/save")

    def test_generate_presigned_url(self):
        """Tests that generate_presigned_url calls the correct boto3 method."""
        self.mock_boto3_client.generate_presigned_url.return_value = "http://presigned-url"
        url = self.minio_client.generate_presigned_url("my-bucket", "my-object")
        self.mock_boto3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "my-object"},
            ExpiresIn=3600,
        )
        self.assertEqual(url, "http://presigned-url")

    def test_delete_object(self):
        """Tests that delete_object calls the correct boto3 method."""
        self.minio_client.delete_object("my-bucket", "my-object")
        self.mock_boto3_client.delete_object.assert_called_once_with(Bucket="my-bucket", Key="my-object")

    def test_list_objects_with_metadata(self):
        """Tests that list_objects_with_metadata returns formatted object data."""
        from datetime import datetime
        
        self.mock_boto3_client.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "file1.txt",
                    "Size": 1024,
                    "LastModified": datetime(2023, 1, 1, 12, 0),
                    "ETag": '"abc123"',
                    "StorageClass": "STANDARD"
                },
                {
                    "Key": "file2.jpg",
                    "Size": 2048,
                    "LastModified": datetime(2023, 1, 2, 14, 30),
                    "ETag": '"def456"'
                }
            ]
        }
        
        objects = self.minio_client.list_objects_with_metadata("my-bucket")
        
        self.mock_boto3_client.list_objects_v2.assert_called_once_with(Bucket="my-bucket")
        self.assertEqual(len(objects), 2)
        
        # Check first object
        self.assertEqual(objects[0]["key"], "file1.txt")
        self.assertEqual(objects[0]["size"], 1024)
        self.assertEqual(objects[0]["storage_class"], "STANDARD")
        
        # Check second object (should default storage class)
        self.assertEqual(objects[1]["key"], "file2.jpg")
        self.assertEqual(objects[1]["size"], 2048)
        self.assertEqual(objects[1]["storage_class"], "STANDARD")

    def test_get_object_metadata(self):
        """Tests that get_object_metadata calls head_object and formats response."""
        from datetime import datetime
        
        self.mock_boto3_client.head_object.return_value = {
            "ContentLength": 5120,
            "LastModified": datetime(2023, 1, 1, 10, 0),
            "ContentType": "text/plain",
            "ETag": '"xyz789"',
            "StorageClass": "STANDARD",
            "Metadata": {"custom": "value"}
        }
        
        metadata = self.minio_client.get_object_metadata("my-bucket", "my-object")
        
        self.mock_boto3_client.head_object.assert_called_once_with(Bucket="my-bucket", Key="my-object")
        self.assertEqual(metadata["size"], 5120)
        self.assertEqual(metadata["content_type"], "text/plain")
        self.assertEqual(metadata["etag"], "xyz789")
        self.assertEqual(metadata["storage_class"], "STANDARD")
        self.assertEqual(metadata["metadata"], {"custom": "value"})

    def test_rename_object(self):
        """Tests that rename_object calls copy_object and delete_object."""
        self.minio_client.rename_object("my-bucket", "old-name.txt", "new-name.txt")
        
        # Verify copy_object was called
        self.mock_boto3_client.copy_object.assert_called_once_with(
            CopySource={"Bucket": "my-bucket", "Key": "old-name.txt"},
            Bucket="my-bucket",
            Key="new-name.txt"
        )
        
        # Verify delete_object was called  
        self.mock_boto3_client.delete_object.assert_called_with(Bucket="my-bucket", Key="old-name.txt")

    def test_create_directory(self):
        """Tests that create_directory uploads an empty object with trailing slash."""
        self.minio_client.create_directory("my-bucket", "test-folder")
        
        # Verify put_object was called with correct parameters
        self.mock_boto3_client.put_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="test-folder/",
            Body=b''
        )

    def test_create_directory_with_slash(self):
        """Tests that create_directory handles names that already end with slash."""
        self.minio_client.create_directory("my-bucket", "test-folder/")
        
        # Verify put_object was called with correct parameters
        self.mock_boto3_client.put_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="test-folder/",
            Body=b''
        )

    def test_delete_directory_empty(self):
        """Tests that delete_directory removes empty directory."""
        # Mock list_objects_v2 to return only the directory marker
        self.mock_boto3_client.list_objects_v2.return_value = {
            'Contents': [{'Key': 'test-folder/'}]
        }
        
        self.minio_client.delete_directory("my-bucket", "test-folder")
        
        # Verify list_objects_v2 was called to check if directory is empty
        self.mock_boto3_client.list_objects_v2.assert_called_once_with(
            Bucket="my-bucket",
            Prefix="test-folder/",
            MaxKeys=2
        )
        
        # Verify delete_object was called
        self.mock_boto3_client.delete_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="test-folder/"
        )

    def test_delete_directory_not_empty(self):
        """Tests that delete_directory raises error for non-empty directory."""
        # Mock list_objects_v2 to return directory marker and another object
        self.mock_boto3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'test-folder/'},
                {'Key': 'test-folder/file.txt'}
            ]
        }
        
        with self.assertRaises(Exception) as context:
            self.minio_client.delete_directory("my-bucket", "test-folder")
        
        self.assertIn("is not empty", str(context.exception))
        
        # Verify delete_object was NOT called
        self.mock_boto3_client.delete_object.assert_not_called()

    def test_set_object_retention(self):
        """Tests that set_object_retention calls put_object_retention."""
        from datetime import datetime
        retain_until = datetime(2024, 12, 31, 23, 59, 59)
        
        self.minio_client.set_object_retention("my-bucket", "my-object", retain_until, "COMPLIANCE")
        
        self.mock_boto3_client.put_object_retention.assert_called_once_with(
            Bucket="my-bucket",
            Key="my-object",
            Retention={
                'Mode': 'COMPLIANCE',
                'RetainUntilDate': retain_until
            }
        )

    def test_get_object_retention(self):
        """Tests that get_object_retention calls get_object_retention."""
        from datetime import datetime
        
        self.mock_boto3_client.get_object_retention.return_value = {
            'Retention': {
                'Mode': 'GOVERNANCE',
                'RetainUntilDate': datetime(2024, 12, 31)
            }
        }
        
        result = self.minio_client.get_object_retention("my-bucket", "my-object")
        
        self.mock_boto3_client.get_object_retention.assert_called_once_with(
            Bucket="my-bucket",
            Key="my-object"
        )
        self.assertEqual(result['Mode'], 'GOVERNANCE')

    def test_set_object_legal_hold(self):
        """Tests that set_object_legal_hold calls put_object_legal_hold."""
        self.minio_client.set_object_legal_hold("my-bucket", "my-object", "ON")
        
        self.mock_boto3_client.put_object_legal_hold.assert_called_once_with(
            Bucket="my-bucket",
            Key="my-object",
            LegalHold={'Status': 'ON'}
        )

    def test_get_object_legal_hold(self):
        """Tests that get_object_legal_hold calls get_object_legal_hold."""
        self.mock_boto3_client.get_object_legal_hold.return_value = {
            'LegalHold': {'Status': 'ON'}
        }
        
        result = self.minio_client.get_object_legal_hold("my-bucket", "my-object")
        
        self.mock_boto3_client.get_object_legal_hold.assert_called_once_with(
            Bucket="my-bucket",
            Key="my-object"
        )
        self.assertEqual(result['Status'], 'ON')

    def test_get_object_content_success(self):
        """Tests that get_object_content fetches and decodes text content."""
        # Mock get_object_metadata to return small file size
        with patch.object(self.minio_client, 'get_object_metadata') as mock_metadata:
            mock_metadata.return_value = {'size': 100}
            
            # Mock the get_object call
            mock_body = MagicMock()
            mock_body.read.return_value = b"Hello, World!\nThis is test content."
            self.mock_boto3_client.get_object.return_value = {
                'Body': mock_body
            }
            
            content = self.minio_client.get_object_content("my-bucket", "test.txt")
            
            # Verify get_object was called
            self.mock_boto3_client.get_object.assert_called_once_with(
                Bucket="my-bucket",
                Key="test.txt"
            )
            
            # Verify content is decoded correctly
            self.assertEqual(content, "Hello, World!\nThis is test content.")

    def test_get_object_content_too_large(self):
        """Tests that get_object_content rejects files that are too large."""
        # Mock get_object_metadata to return large file size
        with patch.object(self.minio_client, 'get_object_metadata') as mock_metadata:
            mock_metadata.return_value = {'size': 50 * 1024}  # 50KB
            
            with self.assertRaises(Exception) as context:
                self.minio_client.get_object_content("my-bucket", "large-file.txt")
            
            self.assertIn("too large for preview", str(context.exception))

    def test_get_object_content_binary_file(self):
        """Tests that get_object_content rejects binary content."""
        # Mock get_object_metadata to return small file size
        with patch.object(self.minio_client, 'get_object_metadata') as mock_metadata:
            mock_metadata.return_value = {'size': 100}
            
            # Mock the get_object call with binary content containing null bytes
            mock_body = MagicMock()
            # Use content with null bytes (common binary indicator)
            mock_body.read.return_value = b"Some text\x00with null bytes\x00"
            self.mock_boto3_client.get_object.return_value = {
                'Body': mock_body
            }
            
            with self.assertRaises(Exception) as context:
                self.minio_client.get_object_content("my-bucket", "binary.dat")
            
            self.assertIn("binary data", str(context.exception))

if __name__ == "__main__":
    unittest.main()
