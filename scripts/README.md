# MinIO TUI

A Textual TUI for interacting with a MinIO instance.

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
endpoint_url = "http://localhost:9000"
access_key = "minioadmin"
secret_key = "minioadmin"
```

**.env example:**
```
MINIO_TUI_MINIO_SECRET_KEY="your_secret_key"
```

**Environment variables:**

The application can also be configured using environment variables with the prefix `MINIO_TUI_`. For example, to set the endpoint URL, you can use `MINIO_TUI_MINIO_ENDPOINT_URL`.

## Usage

Once installed, you can run the application using the following command:

```bash
minio-tui
```
