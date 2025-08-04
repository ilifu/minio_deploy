import os
import threading
from functools import partial
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import Header, Footer, DataTable, Input, Static, Button, Tree, ProgressBar, Label, TextArea
from textual.widgets.tree import TreeNode
from datetime import datetime
from textual.widgets.data_table import RowDoesNotExist
from textual.screen import ModalScreen
from textual.events import Focus
from .minio_client import MinioClient

# --- Modal Screens ---

class HelpScreen(ModalScreen):
    """Help screen showing all available keybindings and their descriptions."""
    
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container help-screen"):
            yield Static("minow - Help", classes="modal-title")
            
            # Use TextArea for better scrollbar handling
            yield TextArea(
                self._get_help_content(), 
                read_only=True,
                show_line_numbers=False,
                classes="help-content"
            )
            
            with Horizontal(classes="modal-buttons"):
                yield Button("Close", variant="primary", id="close")
    
    def _get_help_content(self) -> str:
        """Generate comprehensive help content with all keybindings."""
        help_text = """
minow provides a dual-panel interface for managing S3-compatible object storage.

🔹 GENERAL NAVIGATION
  Tab                   Switch between panels (buckets ↔ objects)
  ↑/↓ or j/k           Navigate within panels
  Enter                 Select/expand items
  Esc                   Cancel operations or close modals

🔹 SYSTEM ACTIONS
  h                     Show this help screen
  d                     Toggle dark/light mode
  q                     Quit application

🔹 BUCKET OPERATIONS (Left Panel)
  c                     Create new bucket (with optional Object Lock)
  x                     Delete selected bucket (with confirmation)
  P                     Generate upload URL for bucket

🔹 OBJECT OPERATIONS (Right Panel)
  u                     Upload file (with progress bar)
  l                     Download selected object (with progress bar)
  p                     Generate presigned download URL
  P                     Generate presigned upload URL
  m                     View object metadata (size, dates, content type)
  v                     Preview text files (with syntax highlighting)
  r                     Rename selected object
  x                     Delete selected object/directory

🔹 DIRECTORY OPERATIONS
  f                     Create new directory/folder
  x                     Delete empty directory

🔹 OBJECT LOCK (WORM Compliance)
  o                     View Object Lock information
  t                     Set retention period (GOVERNANCE/COMPLIANCE)
  H                     Toggle legal hold (ON/OFF)

🔹 SEARCH & FILTERING
  Type in search box    Filter objects by name (real-time)
  Esc in search box     Clear search filter

🔹 FEATURES
  • Progress bars with cancellation support (Esc during transfer)
  • File type icons (🐍 Python, 📄 Documents, 🖼️ Images, etc.)
  • Syntax highlighting for 15+ programming languages
  • Smart path completion for uploads and directory creation
  • Context-aware keybindings (only relevant actions shown)
  • Real-time object counts and status updates
  • WORM compliance with Object Lock support
  • Presigned URLs for secure sharing and uploads

🔹 CONFIGURATION
  Configuration can be provided via:
  • config.toml in current directory
  • minio_tui.toml in current directory
  • ~/.config/minio_tui/config.toml
  • Environment variables (MINIO_TUI_MINIO_*)

  Required settings:
  [minio]
  endpoint_url = "https://your-minio-server.com"
  access_key = "your-access-key"
  secret_key = "your-secret-key"

🔹 NOTES
  • Bucket renaming is not supported (S3/MinIO limitation)
  • Object Lock must be enabled at bucket creation time
  • Directory deletion requires directories to be empty
  • Binary files cannot be previewed (text files only)
  • File size limits apply to preview (≤10KB for text files)
"""
        return help_text.strip()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss()

class CreateBucketScreen(ModalScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.object_lock_enabled = False
        self.default_retention_days = None
        self.default_retention_mode = "GOVERNANCE"

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Create New Bucket", classes="modal-title")
            yield Input(placeholder="Enter bucket name", id="bucket_name_input")
            
            yield Static("Object Lock Settings (cannot be changed after creation):", classes="help-text")
            with Horizontal():
                yield Button("Enable Object Lock", variant="success", id="enable_lock")
                yield Button("No Object Lock", variant="default", id="no_lock")
            
            yield Static("", id="lock_status")
            
            # Retention settings (initially hidden)
            yield Static("Default Retention (optional):", id="retention_label", classes="help-text")
            yield Input(placeholder="Days (e.g., 30)", id="retention_days_input")
            with Horizontal():
                yield Button("Governance", variant="primary", id="governance")
                yield Button("Compliance", variant="error", id="compliance")
            yield Static("", id="retention_mode_status")
            
            with Horizontal(classes="modal-buttons"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        # Initially hide retention settings
        self.hide_retention_settings()

    def hide_retention_settings(self):
        """Hide retention-related widgets."""
        self.query_one("#retention_label").display = False
        self.query_one("#retention_days_input").display = False
        for button in self.query("#governance, #compliance"):
            button.display = False
        self.query_one("#retention_mode_status").display = False

    def show_retention_settings(self):
        """Show retention-related widgets."""
        self.query_one("#retention_label").display = True
        self.query_one("#retention_days_input").display = True
        for button in self.query("#governance, #compliance"):
            button.display = True
        self.query_one("#retention_mode_status").display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "enable_lock":
            self.object_lock_enabled = True
            self.query_one("#lock_status").update("✓ Object Lock will be enabled")
            self.show_retention_settings()
            
        elif event.button.id == "no_lock":
            self.object_lock_enabled = False
            self.query_one("#lock_status").update("○ Object Lock disabled")
            self.hide_retention_settings()
            self.default_retention_days = None
            
        elif event.button.id == "governance":
            self.default_retention_mode = "GOVERNANCE"
            self.query_one("#retention_mode_status").update("Mode: GOVERNANCE (can be overridden)")
            
        elif event.button.id == "compliance":
            self.default_retention_mode = "COMPLIANCE"
            self.query_one("#retention_mode_status").update("Mode: COMPLIANCE (cannot be overridden)")
            
        elif event.button.id == "create":
            bucket_name = self.query_one("#bucket_name_input").value.strip()
            if bucket_name:
                # Get retention days if Object Lock is enabled
                if self.object_lock_enabled:
                    retention_days_str = self.query_one("#retention_days_input").value.strip()
                    if retention_days_str:
                        try:
                            self.default_retention_days = int(retention_days_str)
                        except ValueError:
                            self.default_retention_days = None
                
                result = {
                    'name': bucket_name,
                    'object_lock_enabled': self.object_lock_enabled,
                    'default_retention_days': self.default_retention_days,
                    'default_retention_mode': self.default_retention_mode
                }
                self.dismiss(result)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

class UploadFileScreen(ModalScreen):
    def __init__(self, initial_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self.initial_path = initial_path

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Upload File", classes="modal-title")
            if self.initial_path:
                yield Static(f"Uploading to: {self.initial_path}", classes="help-text")
            yield Input(placeholder="Local file path", id="file_path_input")
            yield Input(placeholder="Object name (optional)", id="object_name_input", value=self.initial_path)
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.time_unit = "minutes"  # Default time unit

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Generate Presigned URL", classes="modal-title")
            yield Input(placeholder="Expiration time (default: 15)", id="expiry_input", value="15")
            
            yield Static("Time Unit:", classes="help-text")
            with Horizontal():
                yield Button("Minutes", variant="primary", id="minutes")
                yield Button("Hours", id="hours")
                yield Button("Days", id="days")

            with Horizontal(classes="modal-buttons"):
                yield Button("Generate", variant="primary", id="generate")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ["minutes", "hours", "days"]:
            self.time_unit = event.button.id
            # Update button variants to show selection
            for button in self.query("Button"):
                if button.id in ["minutes", "hours", "days"]:
                    button.variant = "primary" if button.id == self.time_unit else "default"

        elif event.button.id == "generate":
            expiry_str = self.query_one("#expiry_input").value
            try:
                expiry_value = int(expiry_str) if expiry_str else 15
                
                # Calculate expiry in minutes based on selected unit
                if self.time_unit == "hours":
                    expiry_minutes = expiry_value * 60
                elif self.time_unit == "days":
                    expiry_minutes = expiry_value * 60 * 24
                else: # minutes
                    expiry_minutes = expiry_value
                    
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


class UploadPresignURLScreen(ModalScreen):
    def __init__(self, current_path=""):
        super().__init__()
        self.current_path = current_path
        self.time_unit = "minutes"

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Generate Upload URL", classes="modal-title")
            yield Input(
                placeholder="Object name/path",
                id="object_name",
                value=self.current_path
            )
            yield Input(
                placeholder="Content type (optional, e.g., image/jpeg)",
                id="content_type"
            )
            yield Input(
                placeholder="Expiration time (default: 15)",
                id="expiry_input",
                value="15"
            )
            
            yield Static("Time Unit:", classes="help-text")
            with Horizontal():
                yield Button("Minutes", variant="primary", id="minutes")
                yield Button("Hours", id="hours")
                yield Button("Days", id="days")

            yield Static("Others can use this URL to upload files directly", classes="help-text")
            with Horizontal(classes="modal-buttons"):
                yield Button("Generate", variant="primary", id="generate")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ["minutes", "hours", "days"]:
            self.time_unit = event.button.id
            # Update button variants to show selection
            for button in self.query("Button"):
                if button.id in ["minutes", "hours", "days"]:
                    button.variant = "primary" if button.id == self.time_unit else "default"

        elif event.button.id == "generate":
            object_name = self.query_one("#object_name").value.strip()
            content_type = self.query_one("#content_type").value.strip()
            expiry_str = self.query_one("#expiry_input").value.strip()

            if not object_name:
                # Could add error display here
                return

            try:
                expiry_value = int(expiry_str) if expiry_str else 15
                
                # Calculate expiry in minutes based on selected unit
                if self.time_unit == "hours":
                    expiry_minutes = expiry_value * 60
                elif self.time_unit == "days":
                    expiry_minutes = expiry_value * 60 * 24
                else: # minutes
                    expiry_minutes = expiry_value

                self.dismiss({
                    "object_name": object_name,
                    "content_type": content_type if content_type else None,
                    "expiry_minutes": expiry_minutes
                })
            except ValueError:
                self.dismiss({
                    "object_name": object_name,
                    "content_type": content_type if content_type else None,
                    "expiry_minutes": 15  # Default to 15 minutes if invalid input
                })
        else:
            self.dismiss(None)


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

class RenameObjectScreen(ModalScreen):
    def __init__(self, current_name: str, **kwargs):
        super().__init__(**kwargs)
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Rename Object", classes="modal-title")
            yield Static(f"Current name: {self.current_name}", classes="help-text")
            yield Input(placeholder="Enter new object name", id="new_name_input", value=self.current_name)
            with Horizontal(classes="modal-buttons"):
                yield Button("Rename", variant="primary", id="rename")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rename":
            new_name = self.query_one("#new_name_input").value.strip()
            if new_name and new_name != self.current_name:
                self.dismiss(new_name)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

class CreateDirectoryScreen(ModalScreen):
    def __init__(self, initial_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self.initial_path = initial_path

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Create Directory", classes="modal-title")
            if self.initial_path:
                yield Static(f"Creating in: {self.initial_path}", classes="help-text")
            yield Static("Directory names should not contain trailing slashes", classes="help-text")
            yield Input(placeholder="Enter directory name", id="directory_name_input", value=self.initial_path)
            with Horizontal(classes="modal-buttons"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            directory_name = self.query_one("#directory_name_input").value.strip()
            if directory_name:
                # Ensure it ends with / for S3 directory convention
                if not directory_name.endswith('/'):
                    directory_name += '/'
                self.dismiss(directory_name)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

class SetRetentionScreen(ModalScreen):
    def __init__(self, object_name: str, **kwargs):
        super().__init__(**kwargs)
        self.object_name = object_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static(f"Set Retention: {self.object_name}", classes="modal-title")
            yield Static("Set object retention period (Object Lock)", classes="help-text")
            yield Input(placeholder="Days to retain (e.g., 30)", id="days_input")
            yield Static("Retention Mode:", classes="help-text")
            with Horizontal():
                yield Button("Governance", variant="primary", id="governance")
                yield Button("Compliance", variant="error", id="compliance")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id in ["governance", "compliance"]:
            days_str = self.query_one("#days_input").value.strip()
            if days_str:
                try:
                    days = int(days_str)
                    mode = event.button.id.upper()
                    self.dismiss((days, mode))
                except ValueError:
                    self.dismiss(None)
            else:
                self.dismiss(None)

class LegalHoldScreen(ModalScreen):
    def __init__(self, object_name: str, current_status: str = "OFF", **kwargs):
        super().__init__(**kwargs)
        self.object_name = object_name
        self.current_status = current_status

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static(f"Legal Hold: {self.object_name}", classes="modal-title")
            yield Static(f"Current status: {self.current_status}", classes="help-text")
            yield Static("Legal hold prevents object deletion until removed", classes="help-text")
            with Horizontal(classes="modal-buttons"):
                if self.current_status == "OFF":
                    yield Button("Enable Hold", variant="error", id="enable")
                else:
                    yield Button("Remove Hold", variant="primary", id="disable")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "enable":
            self.dismiss("ON")
        elif event.button.id == "disable":
            self.dismiss("OFF")
        else:
            self.dismiss(None)

class ObjectLockInfoScreen(ModalScreen):
    def __init__(self, object_name: str, retention_info: dict, legal_hold_info: dict, **kwargs):
        super().__init__(**kwargs)
        self.object_name = object_name
        self.retention_info = retention_info
        self.legal_hold_info = legal_hold_info

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static(f"Object Lock Status: {self.object_name}", classes="modal-title")
            
            # Retention information
            if self.retention_info:
                mode = self.retention_info.get('Mode', 'None')
                retain_until = self.retention_info.get('RetainUntilDate', 'Not set')
                if hasattr(retain_until, 'strftime'):
                    retain_until = retain_until.strftime("%Y-%m-%d %H:%M:%S")
                retention_text = f"Retention: {mode} until {retain_until}"
            else:
                retention_text = "Retention: Not set"
            
            yield Static(retention_text, id="retention_info")
            
            # Legal hold information
            legal_status = self.legal_hold_info.get('Status', 'OFF')
            yield Static(f"Legal Hold: {legal_status}", id="legal_hold_info")
            
            yield Button("Close", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

class FilePreviewScreen(ModalScreen):
    def __init__(self, object_name: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.object_name = object_name
        self.content = content
        self.language = get_syntax_language(object_name)

    def compose(self) -> ComposeResult:
        with Vertical(classes="preview-modal-container"):
            # Show file name with language info
            title_text = f"File Preview: {self.object_name}"
            if self.language:
                title_text += f" ({self.language})"
            yield Static(title_text, classes="modal-title")
            
            # Content preview with syntax highlighting
            from textual.widgets import TextArea
            content_widget = TextArea(
                self.content,
                read_only=True,
                language=self.language if self.language else None,
                show_line_numbers=True,
                id="preview_content"
            )
            content_widget.cursor_blink = False
            yield content_widget
            
            # Show file statistics
            lines_count = self.content.count('\n') + 1
            bytes_count = len(self.content.encode('utf-8'))
            stats_text = f"Size: {bytes_count} bytes | Lines: {lines_count}"
            if self.language:
                stats_text += f" | Language: {self.language.title()}"
            yield Static(stats_text, classes="help-text")
            yield Button("Close", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class ProgressScreen(ModalScreen):
    """Modal screen to show upload/download progress with cancel option."""
    
    def __init__(self, operation_type: str, filename: str, total_size: int = 0):
        super().__init__()
        self.operation_type = operation_type  # "upload" or "download"
        self.filename = filename
        self.total_size = total_size
        self.bytes_transferred = 0
        self.cancelled = False
        self.cancel_event = threading.Event()  # Threading event for cancellation
        
    def compose(self) -> ComposeResult:
        with Container(id="progress_container"):
            yield Label(f"{self.operation_type.title()}ing: {self.filename}", id="progress_title")
            if self.total_size > 0:
                yield Label(f"Size: {format_size(self.total_size)}", id="progress_size")
            yield ProgressBar(total=100, id="progress_bar")
            yield Label("0%", id="progress_percentage")
            yield Label(f"0 / {format_size(self.total_size) if self.total_size > 0 else '??'}", id="progress_bytes")
            with Horizontal():
                yield Button("Cancel", variant="error", id="cancel_button")
    
    def on_mount(self) -> None:
        pass  # Styling is handled by CSS
        
    def update_progress(self, bytes_transferred: int) -> None:
        """Update the progress bar with new transfer information."""
        if self.cancelled:
            return
            
        self.bytes_transferred = bytes_transferred
        
        # Update progress bar
        if self.total_size > 0:
            percentage = int((bytes_transferred / self.total_size) * 100)
            self.query_one("#progress_bar").update(progress=percentage)
            self.query_one("#progress_percentage").update(f"{percentage}%")
        else:
            # For unknown size, show a pulsing animation or just bytes
            self.query_one("#progress_percentage").update("...")
        
        # Update byte counter
        if self.total_size > 0:
            self.query_one("#progress_bytes").update(f"{format_size(bytes_transferred)} / {format_size(self.total_size)}")
        else:
            self.query_one("#progress_bytes").update(f"{format_size(bytes_transferred)}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_button":
            self.cancelled = True
            self.cancel_event.set()  # Signal cancellation to worker thread
            self.query_one("#cancel_button").disabled = True
            self.query_one("#cancel_button").label = "Cancelling..."
            # Note: dismiss will be called by the worker thread


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

def get_syntax_language(filename: str) -> str:
    """Get the appropriate syntax highlighting language for a file based on its extension."""
    if not filename:
        return ""
    
    # Get the file extension (case insensitive)
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    # Special handling for files without extensions
    if not ext:
        filename_lower = filename.lower()
        if filename_lower in ['dockerfile', 'containerfile']:
            return ""  # No Docker language support yet
        elif filename_lower in ['makefile', 'gnumakefile']:
            return ""  # No Makefile language support yet
        elif filename_lower.startswith('readme'):
            return "markdown"
        return ""
    
    # Map file extensions to TextArea supported languages
    language_map = {
        # Python
        'py': 'python', 'pyw': 'python',
        
        # JavaScript/TypeScript
        'js': 'javascript', 'jsx': 'javascript', 'ts': 'javascript', 'tsx': 'javascript',
        
        # Web technologies
        'html': 'html', 'htm': 'html', 'xhtml': 'html',
        'css': 'css', 'scss': 'css', 'sass': 'css', 'less': 'css',
        'xml': 'xml', 'xsl': 'xml', 'xsd': 'xml', 'svg': 'xml',
        
        # Data formats
        'json': 'json', 'jsonl': 'json',
        'yaml': 'yaml', 'yml': 'yaml',
        'toml': 'toml',
        
        # Programming languages
        'java': 'java', 'class': 'java',
        'go': 'go',
        'rs': 'rust',
        'sql': 'sql',
        
        # Shell scripting
        'sh': 'bash', 'bash': 'bash', 'zsh': 'bash', 'fish': 'bash',
        
        # Markdown
        'md': 'markdown', 'markdown': 'markdown', 'mdown': 'markdown',
        'rst': 'markdown',  # Close enough for basic highlighting
        
        # Regex (for some config files)
        'gitignore': 'regex', 'ignore': 'regex',
    }
    
    return language_map.get(ext, "")

def get_file_icon(filename: str) -> str:
    """Get an appropriate icon for a file based on its extension."""
    if not filename or filename.endswith('/'):
        return "📁"  # Directory
    
    # Get the file extension (case insensitive)
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    # Icon mapping for common file types
    icon_map = {
        # Images
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'bmp': '🖼️', 
        'svg': '🖼️', 'webp': '🖼️', 'ico': '🖼️', 'tiff': '🖼️',
        
        # Documents
        'pdf': '📄', 'doc': '📄', 'docx': '📄', 'txt': '📄', 'rtf': '📄',
        'md': '📝', 'markdown': '📝',
        
        # Spreadsheets
        'xls': '📊', 'xlsx': '📊', 'csv': '📊', 'ods': '📊',
        
        # Presentations
        'ppt': '📈', 'pptx': '📈', 'odp': '📈',
        
        # Archives
        'zip': '🗜️', 'rar': '🗜️', 'tar': '🗜️', 'gz': '🗜️', '7z': '🗜️',
        'bz2': '🗜️', 'xz': '🗜️',
        
        # Code files
        'py': '🐍', 'js': '🟨', 'ts': '🔷', 'html': '🌐', 'css': '🎨',
        'java': '☕', 'cpp': '⚙️', 'c': '⚙️', 'h': '⚙️', 'hpp': '⚙️',
        'php': '🐘', 'rb': '💎', 'go': '🐹', 'rs': '🦀', 'sh': '📜',
        'sql': '🗃️', 'json': '📋', 'xml': '📋', 'yaml': '📋', 'yml': '📋',
        
        # Media
        'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬', 'mov': '🎬', 'wmv': '🎬',
        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵', 'aac': '🎵', 'ogg': '🎵',
        
        # Config/System
        'conf': '⚙️', 'config': '⚙️', 'ini': '⚙️', 'toml': '⚙️',
        'env': '🔧', 'log': '📊',
        
        # Executables
        'exe': '⚡', 'msi': '⚡', 'deb': '📦', 'rpm': '📦', 'dmg': '📦',
        'app': '📱', 'apk': '📱',
    }
    
    return icon_map.get(ext, '📄')  # Default to document icon

def extract_filename_from_label(label: str) -> str:
    """Extract the actual filename from a tree node label that may contain an icon."""
    # Tree node labels now have format: "icon filename" 
    # We need to extract just the filename part
    label_str = str(label)
    
    # Split by space and take everything after the first part (which should be the icon)
    parts = label_str.split(' ', 1)
    if len(parts) > 1:
        return parts[1]  # Return the filename part
    else:
        return label_str  # Fallback to the whole string if no space found

class MinioTUI(App):
    CSS_PATH = "app.css"
    TITLE = "minow"

    # Define all possible bindings - visibility controlled by check_action
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("c", "create_bucket", "Create Bucket"),
        ("f", "create_directory", "New Folder"),
        ("u", "upload_file", "Upload"),
        ("l", "download_file", "Download"),
        ("p", "presign_url", "Get URL"),
        ("P", "upload_presign_url", "Upload URL"),
        ("m", "show_metadata", "Metadata"),
        ("v", "preview_file", "Preview"),
        ("r", "rename_item", "Rename"),
        ("o", "object_lock_info", "Lock Info"),
        ("t", "set_retention", "Set Retention"),
        ("H", "toggle_legal_hold", "Legal Hold"),
        ("x", "delete_item", "Delete"),
        ("h", "show_help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, minio_client: MinioClient, **kwargs):
        super().__init__(**kwargs)
        self.minio_client = minio_client
        self.current_bucket = None
        self.all_objects = []  # Store all objects for filtering
        self.search_filter = ""  # Current search filter

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="buckets_panel"):
                yield DataTable(id="buckets_table", cursor_type="row")
                yield Static(id="bucket_status", classes="status-bar")
            with Vertical(id="objects_panel"):
                yield Input(placeholder="Search objects...", id="search_input")
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
        self.refresh_bindings()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Update footer when tree cursor moves."""
        if event.control.id == "objects_tree":
            # Force the app to re-evaluate its bindings when tree cursor moves
            self.call_after_refresh(self.refresh_bindings)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search_input":
            self.search_filter = event.value.lower()
            if self.all_objects and self.current_bucket:
                self.update_object_tree(self.all_objects)

    def check_action(self, action: str, parameters) -> bool | None:
        """Control which actions are available based on current focus and selection."""
        focused = self.focused
        
        # Always allow navigation and system actions
        system_actions = {"toggle_dark", "quit", "show_help", "focus_next", "focus_previous", "app.focus_next", "app.focus_previous"}
        if action in system_actions:
            return True
        
        # Get available actions based on focus
        if focused and focused.id == "buckets_table":
            # Bucket context actions
            allowed_actions = {"create_bucket", "delete_item", "upload_presign_url"}
        elif focused and focused.id == "objects_tree":
            # Object context actions - more refined based on selection
            allowed_actions = self._get_object_tree_actions()
        elif focused and focused.id == "search_input":
            # Search input context - allow upload and directory creation
            allowed_actions = {"create_directory", "upload_file", "upload_presign_url"}
        else:
            # Default: allow all actions
            return True
        
        return action in allowed_actions

    def _get_object_tree_actions(self) -> set[str]:
        """Get context-specific actions for objects tree based on current selection."""
        try:
            tree = self.query_one("#objects_tree")
            node = tree.cursor_node
            
            if not node or not self.current_bucket:
                # No selection or no bucket - only allow basic actions
                return {"create_directory", "upload_file", "upload_presign_url"}
            
            # Check if we're on a file (has data) or directory/empty space
            if node.data:
                # We're on a file object
                is_directory = node.data.endswith('/')
                if is_directory:
                    # Directory selected - upload/create actions + directory-specific actions
                    return {"create_directory", "upload_file", "upload_presign_url", "delete_item"}
                else:
                    # File selected - file-specific actions
                    return {"download_file", "presign_url", "show_metadata", "preview_file", "rename_item", "object_lock_info", "set_retention", "toggle_legal_hold", "delete_item"}
            else:
                # Directory node without data (folder in tree) or root - upload/create actions
                return {"create_directory", "upload_file", "upload_presign_url", "delete_item"}
                
        except Exception:
            # Fallback to basic actions if anything goes wrong
            return {"create_directory", "upload_file", "upload_presign_url"}

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
            self.call_from_thread(self.store_and_update_objects, objects)
        except Exception as e:
            self.call_from_thread(self.set_status, f"Error: {e}")

    def store_and_update_objects(self, objects: list[str]):
        """Store all objects and update the tree view."""
        self.all_objects = objects
        self.update_object_tree(objects)

    def update_object_tree(self, objects: list[str]):
        tree = self.query_one("#objects_tree")
        tree.clear()
        nodes = {"": tree.root}

        # Filter objects based on search filter
        if self.search_filter:
            filtered_objects = [obj for obj in objects if self.search_filter in obj.lower()]
        else:
            filtered_objects = objects

        for obj_path in sorted(filtered_objects):
            if not obj_path:
                continue

            parent_path = ""
            path_parts = [part for part in obj_path.split('/') if part]

            for i, part in enumerate(path_parts):
                current_path = "/".join(path_parts[:i + 1])
                
                if current_path not in nodes:
                    parent_node = nodes.get(parent_path, tree.root)
                    
                    is_file = (i == len(path_parts) - 1) and not obj_path.endswith('/')
                    
                    # Get appropriate icon and create display label
                    if is_file:
                        icon = get_file_icon(part)
                        display_label = f"{icon} {part}"
                    else:
                        icon = get_file_icon('')  # Directory icon
                        display_label = f"{icon} {part}"
                    
                    new_node = parent_node.add(
                        display_label,
                        data=obj_path if is_file else None
                    )
                    
                    # Disable expand arrow for leaf nodes (files)
                    if is_file:
                        new_node.allow_expand = False
                    
                    nodes[current_path] = new_node
                
                parent_path = current_path

        tree.root.expand()
        
        # Update status message
        if self.search_filter:
            total_objects = len(self.all_objects) if self.all_objects else len(objects)
            filtered_count = len(filtered_objects)
            self.query_one("#object_status").update(f"{filtered_count}/{total_objects} objects (filtered)")
        else:
            self.query_one("#object_status").update(f"{len(filtered_objects)} objects found.")

    def clear_objects_tree(self):
        self.query_one("#objects_tree").clear()
        self.query_one("#object_status").update("")
        self.query_one("#search_input").value = ""
        self.all_objects = []
        self.search_filter = ""

    def set_status(self, message: str):
        self.query_one("#object_status").update(message)

    def get_current_path(self):
        """Get the current path based on the selected tree node."""
        try:
            focused = self.focused
            if not focused or focused.id != "objects_tree":
                return ""
            
            node = focused.cursor_node
            if not node:
                return ""
            
            # If the node has data, it's a file - get its directory
            if node.data:
                path = node.data
                # If it's a directory marker, return it as is
                if path.endswith('/'):
                    return path
                # If it's a file, return its directory
                parts = path.split('/')
                if len(parts) > 1:
                    return '/'.join(parts[:-1]) + '/'
                return ""
            
            # If the node doesn't have data, it's a folder node - construct path from tree
            path_parts = []
            current = node
            while current and current != focused.root:
                path_parts.insert(0, extract_filename_from_label(current.label))
                current = current.parent
            
            if path_parts:
                return '/'.join(path_parts) + '/'
            return ""
        except Exception:
            # Handle cases where app is not fully initialized (e.g., in tests)
            return ""

    def action_create_bucket(self):
        def on_submit(bucket_config):
            if bucket_config:
                bucket_name = bucket_config['name']
                object_lock_enabled = bucket_config['object_lock_enabled']
                default_retention_days = bucket_config['default_retention_days']
                default_retention_mode = bucket_config['default_retention_mode']
                
                try:
                    self.minio_client.create_bucket(
                        bucket_name=bucket_name,
                        object_lock_enabled=object_lock_enabled,
                        default_retention_days=default_retention_days,
                        default_retention_mode=default_retention_mode
                    )
                    
                    # Create status message
                    status_msg = f"Bucket '{bucket_name}' created"
                    if object_lock_enabled:
                        status_msg += " with Object Lock enabled"
                        if default_retention_days:
                            status_msg += f" (default: {default_retention_days} days {default_retention_mode})"
                    status_msg += "."
                    
                    self.query_one("#bucket_status").update(status_msg)
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
                is_directory = item_name.endswith('/')
                item_type = "directory" if is_directory else "object"
                
                def on_confirm_object(confirmed: bool):
                    if confirmed:
                        try:
                            if is_directory:
                                self.minio_client.delete_directory(self.current_bucket, item_name)
                                self.set_status(f"Directory '{item_name}' deleted.")
                            else:
                                self.minio_client.delete_object(self.current_bucket, item_name)
                                self.set_status(f"Object '{item_name}' deleted.")
                            self.show_objects(self.current_bucket)
                        except Exception as e:
                            self.set_status(f"Error: {e}")
                self.push_screen(ConfirmDeleteScreen(f"{item_type} '{item_name}'"), on_confirm_object)
            elif node and not node.data:
                # This is a directory node without data (folder in tree)
                # We need to construct the directory path
                path_parts = []
                current = node
                while current and current != focused.root:
                    path_parts.insert(0, extract_filename_from_label(current.label))
                    current = current.parent
                
                if path_parts:
                    directory_path = "/".join(path_parts) + "/"
                    def on_confirm_directory(confirmed: bool):
                        if confirmed:
                            try:
                                self.minio_client.delete_directory(self.current_bucket, directory_path)
                                self.set_status(f"Directory '{directory_path}' deleted.")
                                self.show_objects(self.current_bucket)
                            except Exception as e:
                                self.set_status(f"Error: {e}")
                    self.push_screen(ConfirmDeleteScreen(f"directory '{directory_path}'"), on_confirm_directory)

    def action_upload_file(self):
        if not self.current_bucket:
            self.set_status("Select a bucket before uploading.")
            return
        
        # Get current path for smart prepopulation
        current_path = self.get_current_path()
        
        def on_submit(data):
            if data:
                file_path, object_name = data
                if not object_name:
                    # If no object name provided, use just the filename
                    object_name = file_path.split("/")[-1]
                elif object_name and not object_name.endswith('/'):
                    # If object_name doesn't end with /, it might be a rename
                    # Keep it as is - user might want to rename the file
                    pass
                
                # If object_name ends with /, append the original filename
                if object_name.endswith('/'):
                    object_name += file_path.split("/")[-1]
                
                # Get file size for progress tracking
                try:
                    file_size = os.path.getsize(file_path)
                except OSError:
                    file_size = 0
                
                # Create progress screen
                filename = file_path.split("/")[-1]
                progress_screen = ProgressScreen("upload", filename, file_size)
                
                def on_progress_result(result):
                    if result and result.get("cancelled"):
                        self.set_status("Upload cancelled.")
                    else:
                        # Upload completed successfully
                        self.set_status(f"File '{file_path}' uploaded as '{object_name}'.")
                        self.show_objects(self.current_bucket)
                
                # Start upload with progress tracking
                self.push_screen(progress_screen, on_progress_result)
                self._start_upload_with_progress(file_path, object_name, progress_screen)
                
        self.push_screen(UploadFileScreen(current_path), on_submit)
    
    def _start_upload_with_progress(self, file_path: str, object_name: str, progress_screen: ProgressScreen):
        """Start upload operation in a separate thread with progress updates."""
        def progress_callback(bytes_transferred: int):
            # Update progress from worker thread
            if not progress_screen.cancelled:
                self.call_from_thread(progress_screen.update_progress, bytes_transferred)
        
        def upload_worker():
            try:
                self.minio_client.upload_file(
                    self.current_bucket, 
                    object_name, 
                    file_path, 
                    progress_callback=progress_callback,
                    cancel_event=progress_screen.cancel_event
                )
                # Upload completed successfully
                if not progress_screen.cancelled:
                    self.call_from_thread(progress_screen.dismiss, None)
            except Exception as e:
                # Upload failed or cancelled
                if "cancelled" in str(e).lower():
                    self.call_from_thread(progress_screen.dismiss, {"cancelled": True})
                    self.call_from_thread(self.set_status, "Upload cancelled.")
                else:
                    self.call_from_thread(progress_screen.dismiss, {"error": str(e)})
                    self.call_from_thread(self.set_status, f"Upload error: {e}")
        
        # Start upload in background thread
        upload_thread = threading.Thread(target=upload_worker, daemon=True)
        upload_thread.start()

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
                # Get object size for progress tracking
                try:
                    metadata = self.minio_client.get_object_metadata(self.current_bucket, object_name)
                    file_size = metadata.get('size', 0)
                except Exception:
                    file_size = 0
                
                # Create progress screen
                filename = object_name.split("/")[-1]
                progress_screen = ProgressScreen("download", filename, file_size)
                
                def on_progress_result(result):
                    if result and result.get("cancelled"):
                        self.set_status("Download cancelled.")
                    else:
                        # Download completed successfully
                        self.set_status(f"File '{object_name}' downloaded to '{file_path}'.")
                
                # Start download with progress tracking
                self.push_screen(progress_screen, on_progress_result)
                self._start_download_with_progress(object_name, file_path, progress_screen)
                
        self.push_screen(DownloadFileScreen(), on_submit)
    
    def _start_download_with_progress(self, object_name: str, file_path: str, progress_screen: ProgressScreen):
        """Start download operation in a separate thread with progress updates."""
        def progress_callback(bytes_transferred: int):
            # Update progress from worker thread
            if not progress_screen.cancelled:
                self.call_from_thread(progress_screen.update_progress, bytes_transferred)
        
        def download_worker():
            try:
                self.minio_client.download_file(
                    self.current_bucket, 
                    object_name, 
                    file_path, 
                    progress_callback=progress_callback,
                    cancel_event=progress_screen.cancel_event
                )
                # Download completed successfully
                if not progress_screen.cancelled:
                    self.call_from_thread(progress_screen.dismiss, None)
            except Exception as e:
                # Download failed or cancelled
                if "cancelled" in str(e).lower():
                    self.call_from_thread(progress_screen.dismiss, {"cancelled": True})
                    self.call_from_thread(self.set_status, "Download cancelled.")
                else:
                    self.call_from_thread(progress_screen.dismiss, {"error": str(e)})
                    self.call_from_thread(self.set_status, f"Download error: {e}")
        
        # Start download in background thread
        download_thread = threading.Thread(target=download_worker, daemon=True)
        download_thread.start()

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

    def action_upload_presign_url(self):
        if not self.current_bucket:
            self.set_status("Select a bucket before generating upload URL.")
            return
        
        # Get current path for smart prepopulation
        current_path = self.get_current_path()
        
        def on_upload_url_submit(data):
            if data:
                object_name = data["object_name"]
                content_type = data["content_type"]
                expiry_minutes = data["expiry_minutes"]
                
                try:
                    # Convert minutes to seconds for the API
                    expiry_seconds = expiry_minutes * 60
                    url = self.minio_client.generate_upload_presigned_url(
                        self.current_bucket, 
                        object_name, 
                        expires_in=expiry_seconds,
                        content_type=content_type
                    )
                    self.push_screen(ShowURLScreen(url))
                except Exception as e:
                    self.set_status(f"Error: {e}")
        
        self.push_screen(UploadPresignURLScreen(current_path), on_upload_url_submit)

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

    def action_preview_file(self):
        """Preview the content of the selected file."""
        if self.focused.id != "objects_tree" or not self.current_bucket:
            self.set_status("Select a file to preview.")
            return
        
        node = self.query_one("#objects_tree").cursor_node
        if not node or not node.data:
            self.set_status("Select a file to preview.")
            return
        
        object_name = node.data
        
        # Check if it's a directory
        if object_name.endswith('/'):
            self.set_status("Cannot preview directories.")
            return
        
        # Check if file type is suitable for text preview
        if not self.is_text_file(object_name):
            self.set_status("File type not suitable for text preview.")
            return
        
        # Run content fetch in a worker thread
        def fetch_content():
            try:
                content = self.minio_client.get_object_content(self.current_bucket, object_name)
                self.call_from_thread(self.show_preview_modal, object_name, content)
            except Exception as e:
                self.call_from_thread(self.set_status, f"Error fetching file content: {e}")
        
        self.run_worker(fetch_content, thread=True)
        self.set_status("Loading file preview...")

    def is_text_file(self, filename: str) -> bool:
        """Check if a file is likely to be a text file based on its extension."""
        if not filename:
            return False
            
        # Get the file extension (case insensitive)
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Common text file extensions
        text_extensions = {
            'txt', 'md', 'markdown', 'rst', 'log', 'cfg', 'conf', 'config', 'ini',
            'json', 'xml', 'yaml', 'yml', 'toml', 'csv', 'tsv',
            'py', 'js', 'ts', 'html', 'htm', 'css', 'scss', 'sass', 'less',
            'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'php', 'rb', 'go', 'rs',
            'sh', 'bash', 'zsh', 'fish', 'ps1', 'bat', 'cmd',
            'sql', 'gitignore', 'env', 'dockerfile', 'makefile',
            'readme', 'license', 'changelog', 'authors', 'contributors'
        }
        
        return ext in text_extensions or not ext  # Files without extension might be text

    def show_preview_modal(self, object_name: str, content: str):
        """Show the file preview modal with the fetched content."""
        self.push_screen(FilePreviewScreen(object_name, content))

    def action_rename_item(self):
        """Rename the selected object (buckets cannot be renamed in S3/MinIO)."""
        focused = self.focused
        if focused and focused.id == "objects_tree" and self.current_bucket:
            node = focused.cursor_node
            if not node or not node.data:
                self.set_status("Select an object to rename.")
                return
            
            object_name = node.data
            
            def on_rename_submit(new_name):
                if new_name:
                    try:
                        self.minio_client.rename_object(self.current_bucket, object_name, new_name)
                        self.set_status(f"Object renamed from '{object_name}' to '{new_name}'.")
                        self.show_objects(self.current_bucket)  # Refresh the list
                    except Exception as e:
                        self.set_status(f"Error renaming object: {e}")
            
            self.push_screen(RenameObjectScreen(object_name), on_rename_submit)
        elif focused and focused.id == "buckets_table":
            self.set_status("Bucket renaming is not supported by S3/MinIO.")

    def action_create_directory(self):
        """Create a new directory in the current bucket."""
        if not self.current_bucket:
            self.set_status("Select a bucket before creating a directory.")
            return
        
        # Get current path for smart prepopulation
        current_path = self.get_current_path()
        
        def on_submit(directory_name):
            if directory_name:
                try:
                    self.minio_client.create_directory(self.current_bucket, directory_name)
                    self.set_status(f"Directory '{directory_name}' created.")
                    self.show_objects(self.current_bucket)  # Refresh the list
                except Exception as e:
                    self.set_status(f"Error creating directory: {e}")
        
        self.push_screen(CreateDirectoryScreen(current_path), on_submit)

    def action_object_lock_info(self):
        """Show Object Lock information for the selected object."""
        if self.focused.id != "objects_tree" or not self.current_bucket:
            self.set_status("Select an object to view lock info.")
            return
        node = self.query_one("#objects_tree").cursor_node
        if not node or not node.data:
            self.set_status("Select an object to view lock info.")
            return
        
        object_name = node.data
        
        def fetch_lock_info():
            try:
                retention_info = self.minio_client.get_object_retention(self.current_bucket, object_name)
                legal_hold_info = self.minio_client.get_object_legal_hold(self.current_bucket, object_name)
                self.call_from_thread(self.show_lock_info_modal, object_name, retention_info, legal_hold_info)
            except Exception as e:
                self.call_from_thread(self.set_status, f"Error fetching lock info: {e}")
        
        self.run_worker(fetch_lock_info, thread=True)
        self.set_status("Fetching Object Lock info...")

    def show_lock_info_modal(self, object_name: str, retention_info: dict, legal_hold_info: dict):
        """Show the Object Lock info modal with fetched data."""
        self.push_screen(ObjectLockInfoScreen(object_name, retention_info, legal_hold_info))

    def action_set_retention(self):
        """Set retention period for the selected object."""
        if self.focused.id != "objects_tree" or not self.current_bucket:
            self.set_status("Select an object to set retention.")
            return
        node = self.query_one("#objects_tree").cursor_node
        if not node or not node.data:
            self.set_status("Select an object to set retention.")
            return
        
        object_name = node.data
        
        def on_retention_submit(data):
            if data:
                days, mode = data
                from datetime import datetime, timedelta
                retain_until = datetime.utcnow() + timedelta(days=days)
                
                try:
                    self.minio_client.set_object_retention(self.current_bucket, object_name, retain_until, mode)
                    self.set_status(f"Retention set: {mode} for {days} days on '{object_name}'.")
                except Exception as e:
                    self.set_status(f"Error setting retention: {e}")
        
        self.push_screen(SetRetentionScreen(object_name), on_retention_submit)

    def action_toggle_legal_hold(self):
        """Toggle legal hold for the selected object."""
        if self.focused.id != "objects_tree" or not self.current_bucket:
            self.set_status("Select an object to toggle legal hold.")
            return
        node = self.query_one("#objects_tree").cursor_node
        if not node or not node.data:
            self.set_status("Select an object to toggle legal hold.")
            return
        
        object_name = node.data
        
        def fetch_current_status_and_show_modal():
            try:
                legal_hold_info = self.minio_client.get_object_legal_hold(self.current_bucket, object_name)
                current_status = legal_hold_info.get('Status', 'OFF')
                self.call_from_thread(self.show_legal_hold_modal, object_name, current_status)
            except Exception as e:
                self.call_from_thread(self.set_status, f"Error fetching legal hold status: {e}")
        
        def on_legal_hold_submit(new_status):
            if new_status:
                try:
                    self.minio_client.set_object_legal_hold(self.current_bucket, object_name, new_status)
                    status_text = "enabled" if new_status == "ON" else "disabled"
                    self.set_status(f"Legal hold {status_text} for '{object_name}'.")
                except Exception as e:
                    self.set_status(f"Error setting legal hold: {e}")
        
        self.legal_hold_callback = on_legal_hold_submit
        self.run_worker(fetch_current_status_and_show_modal, thread=True)

    def show_legal_hold_modal(self, object_name: str, current_status: str):
        """Show the legal hold modal with current status."""
        self.push_screen(LegalHoldScreen(object_name, current_status), self.legal_hold_callback)
    
    def action_show_help(self):
        """Show the help screen with all keybindings and descriptions."""
        self.push_screen(HelpScreen())

if __name__ == "__main__":
    pass

