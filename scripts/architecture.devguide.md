# Architecture & Design Guide

This guide documents the architectural decisions, design patterns, and overall structure of the MinIO TUI project.

## Project Overview

The MinIO TUI is a terminal-based user interface for interacting with MinIO object storage. It provides a dual-panel file manager-like interface with comprehensive S3 operations support.

## Architecture Principles

### 1. Separation of Concerns

The codebase is structured around clear separation of responsibilities:

```
minio_tui/
├── app.py              # UI logic, event handling, user interactions
├── minio_client.py     # MinIO/S3 API wrapper and business logic
├── simple_config.py    # Configuration management
├── app.css            # All styling and layout
└── run.py             # Application entry point
```

**Key Benefits:**
- UI logic is separate from business logic
- API interactions are abstracted behind a clean interface
- Configuration is centralized and flexible
- Styling is externalized for easy customization

### 2. Event-Driven Architecture

The application follows Textual's event-driven model:

```python
# Events flow from user actions to handlers to business logic
User Input → Event → Handler → Business Logic → UI Update

# Example flow:
Key Press 'u' → key_u() → action_upload_file() → MinioClient.upload_file() → UI Update
```

### 3. Modal-Based UI Pattern

Complex operations use modal screens for user input:

```python
# Pattern: Action → Modal → Business Logic → Result
self.action_upload_file()
  ↓
self.push_screen(UploadFileScreen())
  ↓
user_input_collected
  ↓
self.minio_client.upload_file()
  ↓
self.update_ui_with_result()
```

## Core Components

### 1. Main Application (app.py)

**Responsibilities:**
- UI layout and widget management
- Event handling and routing
- Modal screen management
- Progress tracking and threading
- State management (current bucket, focused widget, etc.)

**Key Classes:**
```python
class MinioTUI(App):
    """Main application class."""
    
    # Core UI management
    def compose(self) -> ComposeResult
    def on_mount(self) -> None
    
    # Event handlers
    def key_*(self) -> None          # Key press handlers
    def action_*(self) -> None       # Action handlers
    def on_*_pressed(self) -> None   # Button handlers
    
    # Business logic coordination
    def show_objects(bucket_name)
    def update_bucket_table()
    def _start_upload_with_progress()
```

**Modal Screens:**
- `CreateBucketScreen` - Bucket creation with Object Lock options
- `UploadFileScreen` - File upload configuration
- `DownloadFileScreen` - Download destination selection
- `ProgressScreen` - Progress tracking with cancellation
- `MetadataScreen` - Object metadata display
- `FilePreviewScreen` - Syntax-highlighted file preview
- And others for various operations

### 2. MinIO Client (minio_client.py)

**Responsibilities:**
- S3 API abstraction
- Error handling and translation
- Progress tracking implementation
- Object Lock operations
- File content detection and validation

**Key Methods:**
```python
class MinioClient:
    # Core S3 operations
    def list_buckets()
    def create_bucket(object_lock_enabled=False)
    def list_objects_with_metadata()
    
    # File operations with progress
    def upload_file(progress_callback=None, cancel_event=None)
    def download_file(progress_callback=None, cancel_event=None)
    
    # Object Lock (WORM) support
    def set_object_retention()
    def set_object_legal_hold()
    
    # Content operations
    def get_object_content()  # For previews
    def generate_presigned_url()
```

### 3. Configuration Management (simple_config.py)

**Design Philosophy:**
- Simple over complex (replaced Dynaconf with custom solution)
- Environment variables take precedence over files
- Clear error messages for missing configuration
- Multiple file location support

```python
class Config:
    # Configuration sources (in priority order):
    # 1. Environment variables (MINIO_TUI_*)
    # 2. config.toml in current directory
    # 3. minio_tui.toml in current directory
    # 4. ~/.config/minio_tui/config.toml
```

## Design Patterns

### 1. Factory Pattern (Client Creation)

```python
# MinioClient can be created with real or mock S3 client
class MinioClient:
    def __init__(self, client=None):
        if client:
            self.client = client  # Dependency injection for testing
        else:
            self.client = boto3.client(...)  # Production client
```

### 2. Observer Pattern (Progress Tracking)

```python
# Progress callbacks allow UI to observe operation progress
def upload_with_progress(file_path, progress_callback):
    for chunk in file_chunks:
        upload_chunk(chunk)
        progress_callback(bytes_uploaded)  # Notify observer
```

### 3. Command Pattern (Actions)

```python
# Actions encapsulate operations and can be triggered multiple ways
def action_upload_file(self):
    """Can be called from key press, button click, or programmatically."""
    # Implementation here
    
# Keybinding
BINDINGS = [("u", "upload_file", "Upload")]

# Button
Button("Upload", id="upload", action="upload_file")
```

### 4. State Machine (UI Context)

```python
# UI behavior changes based on current focus/context
def get_current_context(self):
    if self.focused.id == "buckets_table":
        return "bucket_context"
    elif self.focused.id == "objects_tree":
        return "object_context"
    return "app_context"

# Context-sensitive keybindings
def update_footer_for_context(self, context):
    if context == "bucket_context":
        self.footer.text = "c: Create | x: Delete | Tab: Switch"
    elif context == "object_context":
        self.footer.text = "u: Upload | l: Download | v: Preview"
```

### 5. Template Method (Modal Screens)

```python
# Base modal pattern
class BaseModalScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Container(classes="modal-container"):
            yield self.create_title()
            yield from self.create_content()
            yield self.create_buttons()
    
    def create_title(self): ...      # Override in subclasses
    def create_content(self): ...    # Override in subclasses
    def create_buttons(self): ...    # Override in subclasses
```

## Threading Architecture

### 1. Thread Safety Strategy

```python
# Main thread: UI updates only
# Worker threads: Long-running operations (upload/download)
# Communication: call_from_thread() for thread-safe UI updates

def worker_function():
    try:
        # Long operation
        result = self.minio_client.upload_file(...)
        # Thread-safe UI update
        self.call_from_thread(self.handle_success, result)
    except Exception as e:
        # Thread-safe error handling
        self.call_from_thread(self.handle_error, str(e))
```

### 2. Cancellation Pattern

```python
# Cooperative cancellation using threading.Event
class ProgressScreen(ModalScreen):
    def __init__(self):
        self.cancel_event = threading.Event()
    
    def cancel(self):
        self.cancel_event.set()  # Signal worker to stop

# Worker checks cancellation periodically
def upload_worker():
    for chunk in file_chunks:
        if cancel_event.is_set():
            cleanup_and_exit()
        upload_chunk(chunk)
```

## Error Handling Strategy

### 1. Layered Error Handling

```python
# Layer 1: boto3 exceptions
try:
    self.client.upload_file(...)
except ClientError as e:
    # Convert to application exceptions
    raise Exception(f"Upload failed: {e}")

# Layer 2: Application exceptions
try:
    self.minio_client.upload_file(...)
except Exception as e:
    # Handle in UI layer
    self.set_status(f"Error: {e}")

# Layer 3: UI error display
def set_status(self, message):
    self.query_one("#status").update(message)
```

### 2. User-Friendly Error Messages

```python
def translate_s3_error(self, error_code):
    """Convert S3 error codes to user-friendly messages."""
    error_mapping = {
        'NoSuchBucket': "Bucket does not exist",
        'AccessDenied': "Permission denied - check your credentials",
        'BucketAlreadyExists': "Bucket name is already taken",
        'InvalidBucketName': "Bucket name contains invalid characters",
    }
    return error_mapping.get(error_code, f"Unknown error: {error_code}")
```

## Testing Strategy

### 1. Test Pyramid

```
                /\
               /  \
              /Unit\     # Fast, isolated, comprehensive
             /Tests\
            /______\
           /        \
          /Integration\ # Medium speed, real components
         /   Tests    \
        /____________/
       /              \
      /   End-to-End   \ # Slow, full system, critical paths
     /     Tests       \
    /_________________/
```

### 2. Testing Patterns

**Unit Tests:**
```python
# Mock external dependencies
class TestMinioClient:
    def setup_method(self):
        self.mock_s3_client = MagicMock()
        self.minio_client = MinioClient(client=self.mock_s3_client)
    
    def test_list_buckets(self):
        # Test business logic without S3 dependency
        self.mock_s3_client.list_buckets.return_value = {...}
        result = self.minio_client.list_buckets()
        assert result == expected_result
```

**Integration Tests:**
```python
# Test with real MinIO server
@pytest.fixture
def real_minio_client():
    return MinioClient(
        endpoint_url='http://localhost:9000',
        access_key='testkey',
        secret_key='testsecret'
    )

def test_upload_download_cycle(real_minio_client):
    # Test actual S3 operations
    real_minio_client.create_bucket('test-bucket')
    real_minio_client.upload_file(...)
    real_minio_client.download_file(...)
```

**UI Tests:**
```python
# Test UI interactions with Textual's test framework
async def test_upload_workflow():
    app = MinioTUI()
    async with app.run_test() as pilot:
        await pilot.press("u")  # Upload key
        await pilot.click("#upload_button")
        # Assert expected UI state
```

## Performance Considerations

### 1. Lazy Loading

```python
# Load data only when needed
def show_objects(self, bucket_name):
    """Load objects only when bucket is selected."""
    if bucket_name != self.current_bucket:
        self.run_worker(self.load_objects, bucket_name, thread=True)
```

### 2. Chunked Processing

```python
# Process large files in chunks to avoid memory issues
def upload_large_file(self, file_path):
    chunk_size = 64 * 1024  # 64KB chunks
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            process_chunk(chunk)
```

### 3. Connection Pooling

```python
# Configure boto3 for better performance
config = Config(
    max_pool_connections=50,
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)
```

## Security Considerations

### 1. Credential Management

```python
# Never log or display credentials
def __init__(self, access_key, secret_key):
    self.access_key = access_key
    self.secret_key = secret_key
    
def __repr__(self):
    return f"MinioClient(endpoint={self.endpoint_url})"  # No credentials

# Use environment variables for credentials
config = {
    'access_key': os.getenv('MINIO_ACCESS_KEY'),
    'secret_key': os.getenv('MINIO_SECRET_KEY'),  # Never hardcode
}
```

### 2. Input Validation

```python
def validate_bucket_name(self, name):
    """Validate bucket name according to S3 rules."""
    if not name or len(name) < 3 or len(name) > 63:
        return False
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', name):
        return False
    return True
```

### 3. Path Safety

```python
def safe_file_path(self, user_input):
    """Ensure file paths are safe."""
    # Resolve path to prevent directory traversal
    path = os.path.abspath(user_input)
    
    # Ensure path is within allowed directories
    if not path.startswith('/allowed/directory/'):
        raise ValueError("Path not allowed")
    
    return path
```

## Scalability Patterns

### 1. Pagination Support

```python
def list_objects_paginated(self, bucket_name, max_keys=1000):
    """Handle large object lists with pagination."""
    paginator = self.client.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket=bucket_name, MaxKeys=max_keys):
        yield from page.get('Contents', [])
```

### 2. Connection Management

```python
# Singleton pattern for client management
class ClientManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

## Extension Points

### 1. Plugin Architecture

```python
# Design for extensibility
class OperationHandler:
    def handle_upload(self, *args): ...
    def handle_download(self, *args): ...

class S3OperationHandler(OperationHandler):
    # S3-specific implementation
    pass

class MinioOperationHandler(OperationHandler):
    # MinIO-specific implementation
    pass
```

### 2. Configuration Extensions

```python
# Support for additional config sources
class ConfigLoader:
    def load(self):
        sources = [
            EnvironmentConfig(),
            TOMLConfig(),
            YAMLConfig(),  # Easy to add new sources
            JSONConfig(),
        ]
        return merge_configs(sources)
```

## Deployment Considerations

### 1. Packaging

```python
# pyproject.toml configuration
[project]
name = "minio-tui"
dependencies = [
    "textual[syntax]",  # Include syntax highlighting
    "boto3",           # Minimal dependencies
]

[project.scripts]
minio-tui = "minio_tui.run:main"  # Entry point
```

### 2. Configuration Distribution

```
~/.config/minio_tui/
├── config.toml          # User configuration
├── themes/              # Custom themes
└── keybindings.toml     # Custom keybindings
```

## Future Architecture Considerations

### 1. Multi-Backend Support

```python
# Abstract storage interface
class StorageBackend:
    def list_buckets(self): ...
    def upload_file(self): ...

class S3Backend(StorageBackend): ...
class MinioBackend(StorageBackend): ...
class GoogleCloudBackend(StorageBackend): ...
```

### 2. Plugin System

```python
# Plugin discovery and loading
class PluginManager:
    def load_plugins(self):
        for plugin_path in discover_plugins():
            plugin = import_plugin(plugin_path)
            self.register_plugin(plugin)
```

### 3. Distributed Operations

```python
# Support for multiple MinIO clusters
class ClusterManager:
    def __init__(self):
        self.clusters = {
            'primary': MinioClient(...),
            'backup': MinioClient(...),
        }
    
    def replicate_upload(self, file_path):
        for cluster_name, client in self.clusters.items():
            client.upload_file(file_path)
```

This architecture provides a solid foundation for a maintainable, extensible, and robust object storage management tool while keeping the codebase clean and understandable.