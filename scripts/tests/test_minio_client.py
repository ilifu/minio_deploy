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

if __name__ == "__main__":
    unittest.main()
