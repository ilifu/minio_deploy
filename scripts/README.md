# MinIO TUI

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

The application can be configured using a `config.toml` file, a `.env` file, or environment variables. The application will look for these files in the directory where it is run.

**`config.toml` example:**

```toml
[minio]
endpoint_url = "https://your-minio-server.com"
access_key = "your-access-key"
secret_key = "your-secret-key"
```

**.env example:**
```
MINIO_TUI_MINIO_ENDPOINT_URL="https://your-minio-server.com"
MINIO_TUI_MINIO_ACCESS_KEY="your-access-key"
MINIO_TUI_MINIO_SECRET_KEY="your-secret-key"
```

**Environment variables:**

The application can also be configured using environment variables with the prefix `MINIO_TUI_`. For example:
- `MINIO_TUI_MINIO_ENDPOINT_URL`
- `MINIO_TUI_MINIO_ACCESS_KEY`
- `MINIO_TUI_MINIO_SECRET_KEY`

All three configuration values are required for the application to run.

## Usage

Once installed, you can run the application using the following command:

```bash
minio-tui
```

## Interface

The TUI features a two-panel layout:

- **Left Panel**: Bucket list with object counts
- **Right Panel**: Object tree view showing folder hierarchy

Use **Tab** to switch between panels. The status bar at the bottom shows context-sensitive keybindings.

## Keybindings

### Bucket Panel (Left)
- `c` - Create new bucket
- `x` - Delete selected bucket
- `d` - Toggle dark mode
- `q` - Quit application

### Object Panel (Right)
- `u` - Upload file to current bucket
- `l` - Download selected object
- `p` - Generate presigned URL for selected object
- `m` - View object metadata
- `x` - Delete selected object
- `d` - Toggle dark mode
- `q` - Quit application

## Features

- **Bucket Management**: Create and delete buckets
- **Object Operations**: Upload, download, and delete objects
- **Object Metadata**: View file sizes, modification dates, and content types
- **Search & Filter**: Real-time search filtering of objects by name
- **Presigned URLs**: Generate time-limited URLs (configurable expiration, default 15 minutes) 
- **Smart File Types**: Automatic content type detection based on file extensions
- **Context Menus**: Different keybindings available based on current focus
- **Real-time Updates**: Object counts and listings update automatically
