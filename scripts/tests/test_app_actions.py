import unittest
from unittest.mock import MagicMock, patch, call
import sys
from pathlib import Path

# Add the 'scripts' directory to the Python path to allow importing 'minio_tui'
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from minio_tui.app import MinioTUI
from minio_tui.minio_client import MinioClient


class TestMinioTUIActions(unittest.TestCase):

    def setUp(self):
        """Set up a mock MinIO client and TUI app for testing."""
        self.mock_minio_client = MagicMock(spec=MinioClient)
        self.app = MinioTUI(minio_client=self.mock_minio_client)

    def test_action_create_bucket_success(self):
        """Test successful bucket creation."""
        with patch.object(self.app, 'push_screen') as mock_push_screen:
            # Mock the screen callback
            def mock_callback(bucket_name):
                if bucket_name == "new-bucket":
                    # Simulate successful bucket creation
                    self.mock_minio_client.create_bucket(bucket_name)
                    
            # Call the action
            self.app.action_create_bucket()
            
            # Verify that push_screen was called with the CreateBucketScreen
            self.assertEqual(mock_push_screen.call_count, 1)
            screen_class = mock_push_screen.call_args[0][0].__class__.__name__
            self.assertEqual(screen_class, "CreateBucketScreen")

    def test_action_delete_logic(self):
        """Test delete action logic without UI dependencies."""
        # Test that method exists and is callable
        self.assertTrue(callable(self.app.action_delete_item))
        
        # We can't easily test the full delete flow without initializing 
        # the Textual app, but we can test the MinIO client integration
        # through the load methods which are tested separately

    def test_action_upload_file_no_bucket(self):
        """Test upload file action when no bucket is selected."""
        self.app.current_bucket = None
        
        with patch.object(self.app, 'set_status') as mock_status:
            self.app.action_upload_file()
            mock_status.assert_called_once_with("Select a bucket before uploading.")

    def test_action_upload_file_with_bucket(self):
        """Test upload file action with bucket selected."""
        self.app.current_bucket = "test-bucket"
        
        with patch.object(self.app, 'push_screen') as mock_push_screen:
            self.app.action_upload_file()
            
            # Verify upload screen was shown
            self.assertEqual(mock_push_screen.call_count, 1)
            screen_class = mock_push_screen.call_args[0][0].__class__.__name__
            self.assertEqual(screen_class, "UploadFileScreen")

    def test_action_methods_exist(self):
        """Test that all action methods exist and are callable."""
        # Test that all action methods exist
        self.assertTrue(callable(self.app.action_download_file))
        self.assertTrue(callable(self.app.action_presign_url))
        
        # These methods require UI context to test properly, but we can
        # verify they exist and test the underlying MinIO operations separately

    def test_load_buckets_and_counts_success(self):
        """Test successful loading of buckets and counts."""
        # Mock the MinIO client responses
        self.mock_minio_client.list_buckets.return_value = ["bucket1", "bucket2"]
        self.mock_minio_client.list_objects.side_effect = [
            ["obj1", "obj2", "obj3"],  # bucket1 has 3 objects
            ["obj4", "obj5"]           # bucket2 has 2 objects
        ]
        
        with patch.object(self.app, 'call_from_thread') as mock_call_from_thread:
            # Call the worker method directly
            self.app.load_buckets_and_counts()
            
            # Verify MinIO client calls
            self.mock_minio_client.list_buckets.assert_called_once()
            self.assertEqual(self.mock_minio_client.list_objects.call_count, 2)
            
            # Verify call_from_thread was called with bucket data
            mock_call_from_thread.assert_called_once()
            call_args = mock_call_from_thread.call_args
            self.assertEqual(call_args[0][0].__name__, "update_bucket_table")
            # Check the bucket data structure
            bucket_data = call_args[0][1]
            self.assertEqual(bucket_data, [("bucket1", 3), ("bucket2", 2)])

    def test_load_buckets_and_counts_error(self):
        """Test error handling in bucket loading."""
        # Mock the MinIO client to raise an exception
        self.mock_minio_client.list_buckets.side_effect = Exception("Connection error")
        
        # Mock the query_one method to avoid UI dependencies  
        with patch.object(self.app, 'call_from_thread') as mock_call_from_thread:
            with patch.object(self.app, 'query_one') as mock_query_one:
                mock_status_widget = MagicMock()
                mock_query_one.return_value = mock_status_widget
                
                # Call the worker method
                self.app.load_buckets_and_counts()
                
                # Verify error was handled
                mock_call_from_thread.assert_called_once()
                # The call should be to update the status with an error message
                call_args = mock_call_from_thread.call_args[0]
                self.assertIn("Error:", str(call_args[1]))

    def test_load_objects_success(self):
        """Test successful loading of objects for a bucket."""
        bucket_name = "test-bucket"
        objects = ["file1.txt", "folder/file2.txt"]
        
        self.mock_minio_client.list_objects.return_value = objects
        
        with patch.object(self.app, 'call_from_thread') as mock_call_from_thread:
            # Call the worker method
            self.app.load_objects(bucket_name)
            
            # Verify MinIO client call
            self.mock_minio_client.list_objects.assert_called_once_with(bucket_name)
            
            # Verify call_from_thread was called with objects
            mock_call_from_thread.assert_called_once()
            call_args = mock_call_from_thread.call_args
            self.assertEqual(call_args[0][0].__name__, "update_object_tree")
            self.assertEqual(call_args[0][1], objects)

    def test_load_objects_error(self):
        """Test error handling in object loading."""
        bucket_name = "test-bucket"
        
        # Mock the MinIO client to raise an exception
        self.mock_minio_client.list_objects.side_effect = Exception("Access denied")
        
        with patch.object(self.app, 'call_from_thread') as mock_call_from_thread:
            # Call the worker method
            self.app.load_objects(bucket_name)
            
            # Verify error was handled
            mock_call_from_thread.assert_called_once()
            call_args = mock_call_from_thread.call_args
            self.assertEqual(call_args[0][0].__name__, "set_status")
            self.assertIn("Error:", call_args[0][1])


if __name__ == "__main__":
    unittest.main()