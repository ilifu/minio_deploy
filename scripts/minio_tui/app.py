from functools import partial
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Input, Static, Button, Tree
from textual.widgets.tree import TreeNode
from datetime import datetime
from textual.widgets.data_table import RowDoesNotExist
from textual.screen import ModalScreen
from textual.events import Focus
from .minio_client import MinioClient

# --- Modal Screens ---

class CreateBucketScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Create New Bucket", classes="modal-title")
            yield Input(placeholder="Enter bucket name", id="bucket_name_input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            value = self.query_one("#bucket_name_input").value
            self.dismiss(value)
        else:
            self.dismiss(None)

class UploadFileScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Upload File", classes="modal-title")
            yield Input(placeholder="Local file path", id="file_path_input")
            yield Input(placeholder="Object name (optional)", id="object_name_input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Upload", variant="primary", id="upload")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "upload":
            file_path = self.query_one("#file_path_input").value
            object_name = self.query_one("#object_name_input").value
            self.dismiss((file_path, object_name))
        else:
            self.dismiss(None)

class DownloadFileScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Download File", classes="modal-title")
            yield Input(placeholder="Local save path", id="file_path_input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Download", variant="primary", id="download")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download":
            value = self.query_one("#file_path_input").value
            self.dismiss(value)
        else:
            self.dismiss(None)

class ConfirmDeleteScreen(ModalScreen):
    def __init__(self, item_to_delete: str, **kwargs):
        super().__init__(**kwargs)
        self.item_to_delete = item_to_delete

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static(f"Permanently delete '{self.item_to_delete}'?", classes="modal-title")
            with Horizontal(classes="modal-buttons"):
                yield Button("Delete", variant="error", id="delete")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "delete")

class PresignURLScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Generate Presigned URL", classes="modal-title")
            yield Input(placeholder="Expiration time in minutes (default: 15)", id="expiry_input", value="15")
            with Horizontal(classes="modal-buttons"):
                yield Button("Generate", variant="primary", id="generate")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "generate":
            expiry_str = self.query_one("#expiry_input").value
            try:
                expiry_minutes = int(expiry_str) if expiry_str else 15
                self.dismiss(expiry_minutes)
            except ValueError:
                self.dismiss(15)  # Default to 15 minutes if invalid input
        else:
            self.dismiss(None)

class ShowURLScreen(ModalScreen):
    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Presigned URL", classes="modal-title")
            yield Input(value=self.url, id="url_input")
            yield Static("Select all text (Ctrl+A) and copy (Ctrl+C)", classes="help-text")
            yield Button("Close", id="close")

    def on_mount(self) -> None:
        # Focus the input and select all text
        url_input = self.query_one("#url_input")
        url_input.focus()
        url_input.select_all()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

class MetadataScreen(ModalScreen):
    def __init__(self, object_name: str, metadata: dict, **kwargs):
        super().__init__(**kwargs)
        self.object_name = object_name
        self.metadata = metadata

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static(f"Metadata: {self.object_name}", classes="modal-title")
            
            # Create metadata display
            metadata_text = []
            metadata_text.append(f"Size: {format_size(self.metadata.get('size', 0))}")
            
            if self.metadata.get('last_modified'):
                metadata_text.append(f"Modified: {format_date(self.metadata['last_modified'])}")
            
            metadata_text.append(f"Content Type: {self.metadata.get('content_type', 'unknown')}")
            metadata_text.append(f"Storage Class: {self.metadata.get('storage_class', 'STANDARD')}")
            
            if self.metadata.get('etag'):
                metadata_text.append(f"ETag: {self.metadata['etag']}")
            
            # Show custom metadata if any
            custom_metadata = self.metadata.get('metadata', {})
            if custom_metadata:
                metadata_text.append("\nCustom Metadata:")
                for key, value in custom_metadata.items():
                    metadata_text.append(f"  {key}: {value}")
            
            yield Static("\n".join(metadata_text), id="metadata_content")
            yield Button("Close", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# --- Main App ---

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

def format_date(date_obj):
    """Format datetime object for display."""
    if date_obj is None:
        return "Unknown"
    
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime("%Y-%m-%d %H:%M")
    return str(date_obj)

class MinioTUI(App):
    CSS_PATH = "app.css"

    # Define all possible bindings - visibility controlled by check_action
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("c", "create_bucket", "Create Bucket"),
        ("u", "upload_file", "Upload"),
        ("l", "download_file", "Download"),
        ("p", "presign_url", "Get URL"),
        ("m", "show_metadata", "Metadata"),
        ("x", "delete_item", "Delete"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, minio_client: MinioClient, **kwargs):
        super().__init__(**kwargs)
        self.minio_client = minio_client
        self.current_bucket = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="buckets_panel"):
                yield DataTable(id="buckets_table", cursor_type="row")
                yield Static(id="bucket_status", classes="status-bar")
            with Vertical(id="objects_panel"):
                yield Tree(id="objects_tree", label="Select a bucket")
                yield Static(id="object_status", classes="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        # The BINDINGS class variable handles the initial state.
        self.query_one("#buckets_table").focus()
        self.run_worker(self.load_buckets_and_counts, thread=True)

    def on_focus(self, event: Focus) -> None:
        """Update footer when focus changes."""
        # Force footer to refresh to show current context bindings
        footer = self.query_one(Footer)
        footer.refresh()

    def check_action(self, action: str, parameters) -> bool | None:
        """Control which actions are available based on current focus."""
        focused = self.focused
        
        # Always allow navigation and system actions
        system_actions = {"toggle_dark", "quit", "focus_next", "focus_previous", "app.focus_next", "app.focus_previous"}
        if action in system_actions:
            return True
        
        # Get available actions based on focus
        if focused and focused.id == "buckets_table":
            # Bucket context actions
            allowed_actions = {"create_bucket", "delete_item"}
        elif focused and focused.id == "objects_tree":
            # Object context actions
            allowed_actions = {"upload_file", "download_file", "presign_url", "show_metadata", "delete_item"}
        else:
            # Default: allow all actions
            return True
        
        return action in allowed_actions

    def load_buckets_and_counts(self):
        """
        Worker to fetch all buckets and the number of objects in each.
        """
        try:
            buckets = self.minio_client.list_buckets()
            bucket_data = []
            for bucket_name in buckets:
                objects = self.minio_client.list_objects(bucket_name)
                bucket_data.append((bucket_name, len(objects)))
            self.call_from_thread(self.update_bucket_table, bucket_data)
        except Exception as e:
            # Post error to the correct status bar
            self.call_from_thread(self.query_one("#bucket_status").update, f"Error: {e}")

    def update_bucket_table(self, bucket_data: list[tuple[str, int]]):
        """
        Update the bucket table with names and object counts.
        """
        buckets_table = self.query_one("#buckets_table")
        buckets_table.clear(columns=True)
        buckets_table.add_columns("Name", "Object Count")
        
        rows = [
            [name, str(count)] for name, count in bucket_data
        ]
        
        if rows:
            buckets_table.add_rows(rows)
            # --- FIX: Automatically load the first bucket's objects ---
            first_bucket_name = rows[0][0]
            self.show_objects(first_bucket_name)
            self.current_bucket = first_bucket_name

        self.query_one("#bucket_status").update(f"{len(bucket_data)} buckets found.")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        """
        Handles the event when a user highlights a bucket with the cursor.
        """
        if event.control.id == "buckets_table":
            try:
                bucket_name = event.data_table.get_row_at(event.cursor_row)[0]
                # Avoid reloading if the same bucket is highlighted
                if bucket_name != self.current_bucket:
                    self.current_bucket = bucket_name
                    self.show_objects(bucket_name)
            except (IndexError, RowDoesNotExist):
                self.current_bucket = None
                self.clear_objects_tree()

    def show_objects(self, bucket_name: str):
        tree = self.query_one("#objects_tree")
        tree.label = bucket_name
        tree.reset(bucket_name)
        
        self.query_one("#object_status").update("Loading...")
        # Use functools.partial to create a worker with the argument pre-filled
        worker = partial(self.load_objects, bucket_name)
        self.run_worker(worker, thread=True)

    def load_objects(self, bucket_name: str):
        """Worker to load objects for a given bucket."""
        try:
            objects = self.minio_client.list_objects(bucket_name)
            self.call_from_thread(self.update_object_tree, objects)
        except Exception as e:
            self.call_from_thread(self.set_status, f"Error: {e}")

    def update_object_tree(self, objects: list[str]):
        tree = self.query_one("#objects_tree")
        nodes = {"": tree.root}

        for obj_path in sorted(objects):
            if not obj_path:
                continue

            parent_path = ""
            path_parts = [part for part in obj_path.split('/') if part]

            for i, part in enumerate(path_parts):
                current_path = "/".join(path_parts[:i + 1])
                
                if current_path not in nodes:
                    parent_node = nodes.get(parent_path, tree.root)
                    
                    is_file = (i == len(path_parts) - 1) and not obj_path.endswith('/')
                    
                    new_node = parent_node.add(
                        part,
                        data=obj_path if is_file else None
                    )
                    nodes[current_path] = new_node
                
                parent_path = current_path

        tree.root.expand()
        self.query_one("#object_status").update(f"{len(objects)} objects found.")

    def clear_objects_tree(self):
        self.query_one("#objects_tree").clear()
        self.query_one("#object_status").update("")

    def set_status(self, message: str):
        self.query_one("#object_status").update(message)

    def action_create_bucket(self):
        def on_submit(bucket_name: str):
            if bucket_name:
                try:
                    self.minio_client.create_bucket(bucket_name)
                    self.query_one("#bucket_status").update(f"Bucket '{bucket_name}' created.")
                    # Refresh the bucket list
                    self.run_worker(self.load_buckets_and_counts, thread=True)
                except Exception as e:
                    self.set_status(f"Error: {e}")
        self.push_screen(CreateBucketScreen(), on_submit)

    def action_delete_item(self):
        focused = self.focused
        if isinstance(focused, DataTable) and focused.id == "buckets_table":
            try:
                item_name = focused.get_row_at(focused.cursor_row)[0]
                def on_confirm_bucket(confirmed: bool):
                    if confirmed:
                        try:
                            self.minio_client.delete_bucket(item_name)
                            self.query_one("#bucket_status").update(f"Bucket '{item_name}' deleted.")
                            self.clear_objects_tree()
                            self.run_worker(self.load_buckets_and_counts, thread=True)
                        except Exception as e:
                            self.set_status(f"Error: {e}")
                self.push_screen(ConfirmDeleteScreen(f"bucket '{item_name}'"), on_confirm_bucket)
            except (IndexError, RowDoesNotExist):
                return
        elif isinstance(focused, Tree) and focused.id == "objects_tree":
            node = focused.cursor_node
            if node and node.data:
                item_name = node.data
                def on_confirm_object(confirmed: bool):
                    if confirmed:
                        try:
                            self.minio_client.delete_object(self.current_bucket, item_name)
                            self.set_status(f"Object '{item_name}' deleted.")
                            self.show_objects(self.current_bucket)
                        except Exception as e:
                            self.set_status(f"Error: {e}")
                self.push_screen(ConfirmDeleteScreen(f"object '{item_name}'"), on_confirm_object)

    def action_upload_file(self):
        if not self.current_bucket:
            self.set_status("Select a bucket before uploading.")
            return
        def on_submit(data):
            if data:
                file_path, object_name = data
                if not object_name:
                    object_name = file_path.split("/")[-1]
                try:
                    self.minio_client.upload_file(self.current_bucket, object_name, file_path)
                    self.set_status(f"File '{file_path}' uploaded.")
                    self.show_objects(self.current_bucket)
                except Exception as e:
                    self.set_status(f"Error: {e}")
        self.push_screen(UploadFileScreen(), on_submit)

    def action_download_file(self):
        if self.focused.id != "objects_tree" or not self.current_bucket:
            self.set_status("Select an object to download.")
            return
        node = self.query_one("#objects_tree").cursor_node
        if not node or not node.data:
            return
        object_name = node.data
        def on_submit(file_path: str):
            if file_path:
                try:
                    self.minio_client.download_file(self.current_bucket, object_name, file_path)
                    self.set_status(f"File '{object_name}' downloaded to '{file_path}'.")
                except Exception as e:
                    self.set_status(f"Error: {e}")
        self.push_screen(DownloadFileScreen(), on_submit)

    def action_presign_url(self):
        if self.focused.id != "objects_tree" or not self.current_bucket:
            self.set_status("Select an object to get a URL.")
            return
        node = self.query_one("#objects_tree").cursor_node
        if not node or not node.data:
            return
        
        object_name = node.data
        
        def on_expiry_submit(expiry_minutes):
            if expiry_minutes is not None:
                try:
                    # Convert minutes to seconds for the API
                    expiry_seconds = expiry_minutes * 60
                    url = self.minio_client.generate_presigned_url(self.current_bucket, object_name, expires_in=expiry_seconds)
                    self.push_screen(ShowURLScreen(url))
                except Exception as e:
                    self.set_status(f"Error: {e}")
        
        self.push_screen(PresignURLScreen(), on_expiry_submit)

    def action_show_metadata(self):
        """Show metadata for the selected object."""
        if self.focused.id != "objects_tree" or not self.current_bucket:
            self.set_status("Select an object to view metadata.")
            return
        node = self.query_one("#objects_tree").cursor_node
        if not node or not node.data:
            return
        
        object_name = node.data
        
        # Run metadata fetch in a worker thread
        def fetch_metadata():
            try:
                metadata = self.minio_client.get_object_metadata(self.current_bucket, object_name)
                self.call_from_thread(self.show_metadata_modal, object_name, metadata)
            except Exception as e:
                self.call_from_thread(self.set_status, f"Error fetching metadata: {e}")
        
        self.run_worker(fetch_metadata, thread=True)
        self.set_status("Fetching metadata...")

    def show_metadata_modal(self, object_name: str, metadata: dict):
        """Show the metadata modal with the fetched data."""
        self.push_screen(MetadataScreen(object_name, metadata))

if __name__ == "__main__":
    pass

