import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
from pathlib import Path

# Add the 'scripts' directory to the Python path to allow importing 'minio_tui'
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from minio_tui.app import MinioTUI, CreateBucketScreen, UploadFileScreen, DownloadFileScreen, ConfirmDeleteScreen, ShowURLScreen, PresignURLScreen, UploadPresignURLScreen, RenameObjectScreen, CreateDirectoryScreen, FilePreviewScreen, get_syntax_language
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

    def test_get_object_tree_actions_no_bucket(self):
        """Test object tree actions when no bucket is selected."""
        # Mock tree widget with no current bucket
        mock_tree = MagicMock()
        mock_tree.cursor_node = MagicMock()
        
        with patch.object(self.app, 'query_one', return_value=mock_tree), \
             patch.object(self.app, 'current_bucket', None):
            
            actions = self.app._get_object_tree_actions()
            expected = {"create_directory", "upload_file", "upload_presign_url"}
            self.assertEqual(actions, expected)

    def test_get_object_tree_actions_file_selected(self):
        """Test object tree actions when a file is selected."""
        # Mock tree widget with file node selected
        mock_tree = MagicMock()
        mock_node = MagicMock()
        mock_node.data = "test-file.txt"  # File object (no trailing slash)
        mock_tree.cursor_node = mock_node
        
        with patch.object(self.app, 'query_one', return_value=mock_tree), \
             patch.object(self.app, 'current_bucket', "test-bucket"):
            
            actions = self.app._get_object_tree_actions()
            expected = {"download_file", "presign_url", "show_metadata", "preview_file", "rename_item", "object_lock_info", "set_retention", "toggle_legal_hold", "delete_item"}
            self.assertEqual(actions, expected)

    def test_get_object_tree_actions_directory_selected(self):
        """Test object tree actions when a directory is selected."""
        # Mock tree widget with directory node selected
        mock_tree = MagicMock()
        mock_node = MagicMock()
        mock_node.data = "test-folder/"  # Directory object (trailing slash)
        mock_tree.cursor_node = mock_node
        
        with patch.object(self.app, 'query_one', return_value=mock_tree), \
             patch.object(self.app, 'current_bucket', "test-bucket"):
            
            actions = self.app._get_object_tree_actions()
            expected = {"create_directory", "upload_file", "upload_presign_url", "delete_item"}
            self.assertEqual(actions, expected)

    def test_get_object_tree_actions_folder_node(self):
        """Test object tree actions when a folder node (no data) is selected."""
        # Mock tree widget with folder node selected (no data attribute)
        mock_tree = MagicMock()
        mock_node = MagicMock()
        mock_node.data = None  # Folder node without data
        mock_tree.cursor_node = mock_node
        
        with patch.object(self.app, 'query_one', return_value=mock_tree), \
             patch.object(self.app, 'current_bucket', "test-bucket"):
            
            actions = self.app._get_object_tree_actions()
            expected = {"create_directory", "upload_file", "upload_presign_url", "delete_item"}
            self.assertEqual(actions, expected)

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
        
        # Mock the input widget and buttons
        mock_input = MagicMock()
        mock_input.value = "10"
        mock_minutes_button = MagicMock()
        mock_minutes_button.id = "minutes"
        mock_hours_button = MagicMock()
        mock_hours_button.id = "hours"
        mock_days_button = MagicMock()
        mock_days_button.id = "days"
        mock_generate_button = MagicMock()
        mock_generate_button.id = "generate"

        def query_one_side_effect(selector):
            if selector == "#expiry_input":
                return mock_input
            return MagicMock()

        def query_side_effect(selector):
            if selector == "Button":
                return [mock_minutes_button, mock_hours_button, mock_days_button, mock_generate_button]
            return MagicMock()

        with patch.object(screen, 'query_one', side_effect=query_one_side_effect), \
             patch.object(screen, 'query', side_effect=query_side_effect), \
             patch.object(screen, 'dismiss') as mock_dismiss:

            # Test with default (minutes)
            event = MagicMock()
            event.button = mock_generate_button
            screen.on_button_pressed(event)
            mock_dismiss.assert_called_with(10)

            # Test with hours
            event.button = mock_hours_button
            screen.on_button_pressed(event)
            self.assertEqual(screen.time_unit, "hours")
            
            event.button = mock_generate_button
            screen.on_button_pressed(event)
            mock_dismiss.assert_called_with(10 * 60)

            # Test with days
            event.button = mock_days_button
            screen.on_button_pressed(event)
            self.assertEqual(screen.time_unit, "days")

            event.button = mock_generate_button
            screen.on_button_pressed(event)
            mock_dismiss.assert_called_with(10 * 60 * 24)

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

    def test_upload_presign_url_screen(self):
        """Test UploadPresignURLScreen returns correct data."""
        screen = UploadPresignURLScreen("uploads/")
        
        # Mock the input widgets
        mock_object_name = MagicMock()
        mock_object_name.value = "uploads/test-file.jpg"
        
        mock_content_type = MagicMock()
        mock_content_type.value = "image/jpeg"
        
        mock_expiry = MagicMock()
        mock_expiry.value = "2"  # 2 hours

        mock_hours_button = MagicMock()
        mock_hours_button.id = "hours"
        mock_generate_button = MagicMock()
        mock_generate_button.id = "generate"
        
        def mock_query_one(selector):
            if selector == "#object_name":
                return mock_object_name
            elif selector == "#content_type":
                return mock_content_type
            elif selector == "#expiry_input":
                return mock_expiry
            return MagicMock()

        def query_side_effect(selector):
            if selector == "Button":
                return [mock_hours_button, mock_generate_button]
            return MagicMock()

        with patch.object(screen, 'query_one', side_effect=mock_query_one), \
             patch.object(screen, 'query', side_effect=query_side_effect), \
             patch.object(screen, 'dismiss') as mock_dismiss:

            # Select hours
            event = MagicMock()
            event.button = mock_hours_button
            screen.on_button_pressed(event)
            self.assertEqual(screen.time_unit, "hours")

            # Generate
            event.button = mock_generate_button
            screen.on_button_pressed(event)

            mock_dismiss.assert_called_once_with({
                "object_name": "uploads/test-file.jpg",
                "content_type": "image/jpeg",
                "expiry_minutes": 120 # 2 hours
            })

    def test_upload_presign_url_screen_no_content_type(self):
        """Test UploadPresignURLScreen handles empty content type."""
        screen = UploadPresignURLScreen()
        
        # Mock the input widgets
        mock_object_name = MagicMock()
        mock_object_name.value = "test-file.txt"
        
        mock_content_type = MagicMock()
        mock_content_type.value = ""  # Empty content type
        
        mock_expiry = MagicMock()
        mock_expiry.value = "15"
        
        def mock_query_one(selector):
            if selector == "#object_name":
                return mock_object_name
            elif selector == "#content_type":
                return mock_content_type
            elif selector == "#expiry_input":
                return mock_expiry
        
        with patch.object(screen, 'query_one', side_effect=mock_query_one):
            # Mock button press event
            mock_button = MagicMock()
            mock_button.id = "generate"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            with patch.object(screen, 'dismiss') as mock_dismiss:
                screen.on_button_pressed(mock_event)
                mock_dismiss.assert_called_once_with({
                    "object_name": "test-file.txt",
                    "content_type": None,  # Should be None when empty
                    "expiry_minutes": 15
                })

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

    def test_file_preview_screen(self):
        """Test FilePreviewScreen displays content correctly."""
        test_content = "def hello():\n    print('Hello, World!')\n    return True"
        screen = FilePreviewScreen("test.py", test_content)
        
        # Test that the screen initializes with correct content and language
        self.assertEqual(screen.object_name, "test.py")
        self.assertEqual(screen.content, test_content)
        self.assertEqual(screen.language, "python")
        
        # Test plain text file
        plain_screen = FilePreviewScreen("readme.txt", "Plain text content")
        self.assertEqual(plain_screen.language, "")
        
        # Mock button press event for close
        mock_button = MagicMock()
        mock_button.id = "close"
        mock_event = MagicMock()
        mock_event.button = mock_button
        
        with patch.object(screen, 'dismiss') as mock_dismiss:
            screen.on_button_pressed(mock_event)
            mock_dismiss.assert_called_once()

    def test_is_text_file_detection(self):
        """Test text file detection logic."""
        app = MinioTUI(MagicMock())
        
        # Test common text file extensions
        self.assertTrue(app.is_text_file("test.txt"))
        self.assertTrue(app.is_text_file("script.py"))
        self.assertTrue(app.is_text_file("config.json"))
        self.assertTrue(app.is_text_file("README.md"))
        self.assertTrue(app.is_text_file("styles.css"))
        self.assertTrue(app.is_text_file("Dockerfile"))  # No extension
        
        # Test binary file extensions
        self.assertFalse(app.is_text_file("image.png"))
        self.assertFalse(app.is_text_file("video.mp4"))
        self.assertFalse(app.is_text_file("archive.zip"))
        self.assertFalse(app.is_text_file("binary.exe"))

    def test_syntax_language_detection(self):
        """Test syntax language detection for file previews."""
        # Test programming languages
        self.assertEqual(get_syntax_language("script.py"), "python")
        self.assertEqual(get_syntax_language("app.js"), "javascript")
        self.assertEqual(get_syntax_language("component.tsx"), "javascript")
        self.assertEqual(get_syntax_language("main.go"), "go")
        self.assertEqual(get_syntax_language("lib.rs"), "rust")
        self.assertEqual(get_syntax_language("Main.java"), "java")
        
        # Test web technologies
        self.assertEqual(get_syntax_language("index.html"), "html")
        self.assertEqual(get_syntax_language("styles.css"), "css")
        self.assertEqual(get_syntax_language("style.scss"), "css")
        self.assertEqual(get_syntax_language("data.xml"), "xml")
        
        # Test data formats
        self.assertEqual(get_syntax_language("config.json"), "json")
        self.assertEqual(get_syntax_language("docker-compose.yml"), "yaml")
        self.assertEqual(get_syntax_language("pyproject.toml"), "toml")
        
        # Test shell scripts
        self.assertEqual(get_syntax_language("script.sh"), "bash")
        self.assertEqual(get_syntax_language("install.bash"), "bash")
        
        # Test markdown
        self.assertEqual(get_syntax_language("README.md"), "markdown")
        self.assertEqual(get_syntax_language("README"), "markdown")  # Special case
        
        # Test unknown extensions
        self.assertEqual(get_syntax_language("binary.exe"), "")
        self.assertEqual(get_syntax_language("image.png"), "")
        self.assertEqual(get_syntax_language(""), "")


if __name__ == "__main__":
    unittest.main()