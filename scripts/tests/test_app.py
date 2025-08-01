import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
from pathlib import Path

# Add the 'scripts' directory to the Python path to allow importing 'minio_tui'
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from minio_tui.app import MinioTUI, CreateBucketScreen, UploadFileScreen, DownloadFileScreen, ConfirmDeleteScreen, ShowURLScreen, PresignURLScreen, RenameObjectScreen, CreateDirectoryScreen
from minio_tui.minio_client import MinioClient


class TestMinioTUI(unittest.TestCase):

    def setUp(self):
        """Set up a mock MinIO client and TUI app for testing."""
        self.mock_minio_client = MagicMock(spec=MinioClient)
        self.app = MinioTUI(minio_client=self.mock_minio_client)

    def test_app_initialization(self):
        """Test that the app initializes correctly."""
        self.assertEqual(self.app.minio_client, self.mock_minio_client)
        self.assertIsNone(self.app.current_bucket)

    def test_check_action_system_actions(self):
        """Test that system actions are always allowed."""
        # Mock the focused property to return None (no focused widget)
        with patch.object(type(self.app), 'focused', new_callable=lambda: property(lambda self: None)):
            # Test without any focused widget (should default to allow all)
            self.assertTrue(self.app.check_action("toggle_dark", {}))
            self.assertTrue(self.app.check_action("quit", {}))
            
            # Test navigation actions are always allowed
            self.assertTrue(self.app.check_action("focus_next", {}))
            self.assertTrue(self.app.check_action("focus_previous", {}))

    def test_update_bucket_table_logic(self):
        """Test bucket table update logic without UI dependencies."""
        # Mock the widgets that would be queried
        mock_buckets_table = MagicMock()
        mock_bucket_status = MagicMock()
        
        with patch.object(self.app, 'query_one') as mock_query, \
             patch.object(self.app, 'show_objects') as mock_show_objects:
            # Setup mock to return our mocked widgets
            def mock_query_one(selector):
                if selector == "#buckets_table":
                    return mock_buckets_table
                elif selector == "#bucket_status":
                    return mock_bucket_status
                else:
                    raise ValueError(f"Unexpected selector: {selector}")
            
            mock_query.side_effect = mock_query_one
            
            # Test data
            bucket_data = [("bucket1", 5), ("bucket2", 10)]
            
            # Call the method
            self.app.update_bucket_table(bucket_data)
            
            # Verify table operations
            mock_buckets_table.clear.assert_called_once_with(columns=True)
            mock_buckets_table.add_columns.assert_called_once_with("Name", "Object Count")
            mock_buckets_table.add_rows.assert_called_once_with([["bucket1", "5"], ["bucket2", "10"]])
            
            # Verify status update
            mock_bucket_status.update.assert_called_once_with("2 buckets found.")
            
            # Verify that show_objects was called with the first bucket
            mock_show_objects.assert_called_once_with("bucket1")

    def test_update_object_tree(self):
        """Test that the object tree updates correctly."""
        # Mock the tree widget and status
        mock_tree = MagicMock()
        mock_root = MagicMock()
        mock_tree.root = mock_root
        mock_object_status = MagicMock()
        
        with patch.object(self.app, 'query_one') as mock_query:
            def mock_query_one(selector):
                if selector == "#objects_tree":
                    return mock_tree
                elif selector == "#object_status":
                    return mock_object_status
                else:
                    raise ValueError(f"Unexpected selector: {selector}")
            
            mock_query.side_effect = mock_query_one
            
            # Test with simple objects
            objects = ["file1.txt", "folder/file2.txt", "folder/subfolder/file3.txt"]
            
            # Call the method
            self.app.update_object_tree(objects)
            
            # Verify tree operations
            mock_root.expand.assert_called_once()
            mock_object_status.update.assert_called_once_with("3 objects found.")


class TestModalScreens(unittest.TestCase):
    """Test modal screen components."""

    def test_create_bucket_screen_submit(self):
        """Test CreateBucketScreen returns correct value on submit."""
        screen = CreateBucketScreen()
        
        # Mock the input widgets
        mock_bucket_input = MagicMock()
        mock_bucket_input.value = "new-bucket"
        mock_retention_input = MagicMock()
        mock_retention_input.value = ""
        
        def mock_query_one(selector):
            if selector == "#bucket_name_input":
                return mock_bucket_input
            elif selector == "#retention_days_input":
                return mock_retention_input
            else:
                return MagicMock()
        
        with patch.object(screen, 'query_one', side_effect=mock_query_one):
            # Mock button press event
            mock_button = MagicMock()
            mock_button.id = "create"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                expected_result = {
                    'name': 'new-bucket',
                    'object_lock_enabled': False,
                    'default_retention_days': None,
                    'default_retention_mode': 'GOVERNANCE'
                }
                mock_dismiss.assert_called_once_with(expected_result)

    def test_create_bucket_screen_cancel(self):
        """Test CreateBucketScreen returns None on cancel."""
        screen = CreateBucketScreen()
        
        # Mock button press event
        mock_button = MagicMock()
        mock_button.id = "cancel"
        mock_event = MagicMock()
        mock_event.button = mock_button
        
        with patch.object(screen, 'dismiss') as mock_dismiss:
            screen.on_button_pressed(mock_event)
            mock_dismiss.assert_called_once_with(None)

    def test_upload_file_screen_submit(self):
        """Test UploadFileScreen returns correct values on submit."""
        screen = UploadFileScreen()
        
        # Mock the input widgets
        mock_file_input = MagicMock()
        mock_file_input.value = "/path/to/file.txt"
        mock_object_input = MagicMock()
        mock_object_input.value = "custom-name.txt"
        
        with patch.object(screen, 'query_one') as mock_query:
            mock_query.side_effect = lambda selector: {
                "#file_path_input": mock_file_input,
                "#object_name_input": mock_object_input
            }[selector]
            
            # Mock button press event
            mock_button = MagicMock()
            mock_button.id = "upload"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                mock_dismiss.assert_called_once_with(("/path/to/file.txt", "custom-name.txt"))

    def test_confirm_delete_screen(self):
        """Test ConfirmDeleteScreen returns correct confirmation."""
        screen = ConfirmDeleteScreen("test-item")
        
        # Test delete confirmation
        mock_button = MagicMock()
        mock_button.id = "delete"
        mock_event = MagicMock()
        mock_event.button = mock_button
        
        with patch.object(screen, 'dismiss') as mock_dismiss:
            screen.on_button_pressed(mock_event)
            mock_dismiss.assert_called_once_with(True)

        # Test cancel
        mock_button.id = "cancel"
        with patch.object(screen, 'dismiss') as mock_dismiss:
            screen.on_button_pressed(mock_event)
            mock_dismiss.assert_called_once_with(False)

    def test_presign_url_screen(self):
        """Test PresignURLScreen returns correct expiration time."""
        screen = PresignURLScreen()
        
        # Mock the input widget
        mock_input = MagicMock()
        mock_input.value = "30"  # 30 minutes
        
        with patch.object(screen, 'query_one', return_value=mock_input):
            # Mock button press event
            mock_button = MagicMock()
            mock_button.id = "generate"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                mock_dismiss.assert_called_once_with(30)

    def test_presign_url_screen_invalid_input(self):
        """Test PresignURLScreen handles invalid input gracefully."""
        screen = PresignURLScreen()
        
        # Mock the input widget with invalid value
        mock_input = MagicMock()
        mock_input.value = "invalid"
        
        with patch.object(screen, 'query_one', return_value=mock_input):
            # Mock button press event
            mock_button = MagicMock()
            mock_button.id = "generate"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                # Should default to 15 minutes
                mock_dismiss.assert_called_once_with(15)

    def test_rename_object_screen_submit(self):
        """Test RenameObjectScreen returns new name on submit."""
        screen = RenameObjectScreen("old-name.txt")
        
        # Mock the input widget
        mock_input = MagicMock()
        mock_input.value = "new-name.txt"
        
        with patch.object(screen, 'query_one', return_value=mock_input):
            # Mock button press event for rename
            mock_button = MagicMock()
            mock_button.id = "rename"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                mock_dismiss.assert_called_once_with("new-name.txt")

    def test_rename_object_screen_cancel(self):
        """Test RenameObjectScreen returns None on cancel."""
        screen = RenameObjectScreen("old-name.txt")
        
        # Mock button press event for cancel
        mock_button = MagicMock()
        mock_button.id = "cancel"
        mock_event = MagicMock()
        mock_event.button = mock_button
        
        with patch.object(screen, 'dismiss') as mock_dismiss:
            screen.on_button_pressed(mock_event)
            mock_dismiss.assert_called_once_with(None)

    def test_rename_object_screen_same_name(self):
        """Test RenameObjectScreen returns None when name unchanged."""
        screen = RenameObjectScreen("test-name.txt")
        
        # Mock the input widget with same name
        mock_input = MagicMock()
        mock_input.value = "test-name.txt"  # Same as original
        
        with patch.object(screen, 'query_one', return_value=mock_input):
            # Mock button press event for rename
            mock_button = MagicMock()
            mock_button.id = "rename"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                mock_dismiss.assert_called_once_with(None)

    def test_create_directory_screen_submit(self):
        """Test CreateDirectoryScreen returns directory name with slash."""
        screen = CreateDirectoryScreen()
        
        # Mock the input widget
        mock_input = MagicMock()
        mock_input.value = "test-folder"
        
        with patch.object(screen, 'query_one', return_value=mock_input):
            # Mock button press event for create
            mock_button = MagicMock()
            mock_button.id = "create"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                mock_dismiss.assert_called_once_with("test-folder/")

    def test_create_directory_screen_with_slash(self):
        """Test CreateDirectoryScreen handles names that already end with slash."""
        screen = CreateDirectoryScreen()
        
        # Mock the input widget with trailing slash
        mock_input = MagicMock()
        mock_input.value = "test-folder/"
        
        with patch.object(screen, 'query_one', return_value=mock_input):
            # Mock button press event for create
            mock_button = MagicMock()
            mock_button.id = "create"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                # Should still end with single slash
                mock_dismiss.assert_called_once_with("test-folder/")

    def test_create_directory_screen_cancel(self):
        """Test CreateDirectoryScreen returns None on cancel."""
        screen = CreateDirectoryScreen()
        
        # Mock button press event for cancel
        mock_button = MagicMock()
        mock_button.id = "cancel"
        mock_event = MagicMock()
        mock_event.button = mock_button
        
        with patch.object(screen, 'dismiss') as mock_dismiss:
            screen.on_button_pressed(mock_event)
            mock_dismiss.assert_called_once_with(None)

    def test_create_directory_screen_empty_name(self):
        """Test CreateDirectoryScreen returns None for empty name."""
        screen = CreateDirectoryScreen()
        
        # Mock the input widget with empty value
        mock_input = MagicMock()
        mock_input.value = ""
        
        with patch.object(screen, 'query_one', return_value=mock_input):
            # Mock button press event for create
            mock_button = MagicMock()
            mock_button.id = "create"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                mock_dismiss.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()