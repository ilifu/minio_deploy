<div align="center">
  <img src="assets/minow-logo.png" alt="minow logo" width="200"/>
</div>

# minow

A Textual TUI for interacting with a MinIO instance. Features a dual-panel interface with bucket management on the left and object browsing on the right, plus context-sensitive keybindings.

## Installation

1.  **Navigate to the `scripts` directory:**

    ```bash
    cd scripts
    ```

2.  **Install the application:**

    You can install the application using `pip`. It is recommended to do this in a virtual environment.

    ```bash
    pip install .
    ```

## Configuration

The application can be configured using a `config.toml` file or environment variables. Environment variables take precedence over TOML file settings.

**`config.toml` example:**

```toml
[minio]
endpoint_url = "https://your-minio-server.com"
access_key = "your-access-key"
secret_key = "your-secret-key"
```

The application will look for config files in this order:
1. `config.toml` in the current directory
2. `minio_tui.toml` in the current directory  
3. `~/.config/minio_tui/config.toml` in your home directory

**Environment variables:**

You can also configure the application using environment variables with the prefix `MINIO_TUI_`:
- `MINIO_TUI_MINIO_ENDPOINT_URL`
- `MINIO_TUI_MINIO_ACCESS_KEY`
- `MINIO_TUI_MINIO_SECRET_KEY`

**Example:**
```bash
export MINIO_TUI_MINIO_ENDPOINT_URL="https://your-minio-server.com"
export MINIO_TUI_MINIO_ACCESS_KEY="your-access-key"
export MINIO_TUI_MINIO_SECRET_KEY="your-secret-key"
minow
```

All three configuration values are required for the application to run.

## Usage

Once installed, you can run the application using the following command:

```bash
minow
```

To view the comprehensive manual page after installation:

```bash
man minow
```

## Interface

The TUI features a two-panel layout:

- **Left Panel**: Bucket list with object counts
- **Right Panel**: Object tree view showing folder hierarchy

Use **Tab** to switch between panels. The status bar at the bottom shows context-sensitive keybindings.

## Keybindings

### General
- `h` - Show comprehensive help screen with all keybindings
- `d` - Toggle dark mode
- `q` - Quit application
- `Tab` - Switch between panels

### Bucket Panel (Left)
- `c` - Create new bucket
- `x` - Delete selected bucket
- `P` - Generate upload URL (others can upload to this bucket)

### Object Panel (Right)
- `f` - Create new directory/folder
- `u` - Upload file to current bucket
- `l` - Download selected object
- `p` - Generate presigned URL for selected object
- `P` - Generate upload URL (others can upload to this path)
- `m` - View object metadata
- `v` - Preview text files (small files only)
- `r` - Rename selected object
- `o` - View Object Lock information
- `t` - Set retention period (Object Lock)
- `H` - Toggle legal hold (Object Lock)
- `x` - Delete selected object/directory (directories must be empty)

## Features

- **Bucket Management**: Create and delete buckets with optional Object Lock configuration
- **Directory Management**: Create and delete directories (empty directories only)
- **Object Operations**: Upload, download, rename, and delete objects with progress tracking
- **Smart Path Prepopulation**: Upload and directory creation modals auto-populate with current path
- **Object Metadata**: View file sizes, modification dates, and content types
- **Object Lock Support**: Set retention periods and legal holds for WORM compliance
- **Search & Filter**: Real-time search filtering of objects by name
- **Presigned URLs**: Generate time-limited download URLs and upload URLs (configurable expiration, default 15 minutes) 
- **Smart File Types**: Automatic content type detection based on file extensions
- **File Type Icons**: Visual file type indicators with support for 40+ file types (🐍 Python, 🖼️ Images, 📄 Documents, etc.)
- **File Preview**: Large modal preview of small text files (≤10KB) with syntax highlighting for 15+ languages (Python, JavaScript, JSON, YAML, etc.)
- **Context-Aware Keybindings**: Footer dynamically shows only relevant actions based on current selection (files vs directories vs buckets)
- **Comprehensive Help System**: Built-in help screen (`h` key) with all keybindings and detailed man page documentation
- **Real-time Updates**: Object counts and listings update automatically
- **Enhanced UI/UX**: Clean tree view without leaf arrows, responsive footer that updates as you navigate

**Notes:** 
- Bucket renaming is not supported by S3/MinIO - buckets are immutable once created
- Object Lock must be enabled at bucket creation time - it cannot be enabled later
- Object Lock provides WORM (Write Once Read Many) compliance with retention periods and legal holds

## Testing

The project includes comprehensive testing with both unit tests (mocked) and integration tests (real MinIO):

### Quick Testing
```bash
# Run unit tests (fast, <1 second)
python -m pytest tests/ -v

# Run integration tests (with Docker MinIO, ~30 seconds)
./test-integration.sh
```

### Testing Strategy
- **Unit Tests** (`tests/test_*.py`) - Fast feedback with mocked dependencies (71 tests)
- **Integration Tests** (`tests/integration/`) - Real MinIO API validation (4 tests)
- **Dual approach** ensures both fast development feedback and real-world compatibility

See `TESTING.md` for detailed testing documentation.

## Contributors

- **Dane Kennedy** - Original concept and project initiation
- **Claude (Anthropic)** - Core development, architecture design, comprehensive testing, and feature implementation

This project was developed through an extensive collaboration, with Claude contributing significantly to the codebase architecture, implementing advanced features like progress bars with cancellation, syntax-highlighted file previews, Object Lock support, comprehensive testing suite (75+ tests), Docker-based integration testing, and creating detailed development guides. The clean separation of concerns, robust error handling, and professional UI/UX design were all developed through this collaborative process.
