import sys
from .app import MinioTUI
from .minio_client import MinioClient

def main():
    """The main entry point for the application."""
    try:
        minio_client = MinioClient()
        app = MinioTUI(minio_client=minio_client)
        app.run()
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
