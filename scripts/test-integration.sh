#!/bin/bash

# Integration test runner for MinIO TUI
# This script starts a MinIO Docker container and runs integration tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🐳 Starting MinIO test server..."

# Start MinIO container
docker compose -f docker-compose.test.yml up -d

# Wait for MinIO to be ready
echo "⏳ Waiting for MinIO to be ready..."
timeout=60
counter=0

while ! curl -f http://localhost:9000/minio/health/live >/dev/null 2>&1; do
    sleep 1
    counter=$((counter + 1))
    if [ $counter -ge $timeout ]; then
        echo "❌ MinIO failed to start within $timeout seconds"
        docker compose -f docker-compose.test.yml logs minio-test
        docker compose -f docker-compose.test.yml down
        exit 1
    fi
done

echo "✅ MinIO is ready!"

# Run integration tests
echo "🧪 Running integration tests..."
python -m pytest tests/integration/ -v

# Store exit code
EXIT_CODE=$?

# Clean up
echo "🧹 Cleaning up..."
docker compose -f docker-compose.test.yml down -v

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All integration tests passed!"
else
    echo "❌ Some integration tests failed!"
fi

exit $EXIT_CODE