import unittest
from unittest.mock import MagicMock
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

if __name__ == "__main__":
    unittest.main()
