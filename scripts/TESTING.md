# Testing Guide

This project includes both unit tests (with mocks) and integration tests (with real MinIO).

## Unit Tests (Fast, Mocked)

Run the existing unit tests for fast feedback:

```bash
# Run all unit tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_minio_client.py -v
python -m pytest tests/test_app.py -v
python -m pytest tests/test_simple_config.py -v
```

## Integration Tests (Real MinIO)

Integration tests run against a real MinIO server using Docker. These tests verify actual API behavior, authentication, and data serialization.

### Prerequisites

- Docker and Docker Compose installed
- Ports 9000 and 9001 available on localhost

### Running Integration Tests

```bash
# Run integration tests (automatically starts/stops MinIO Docker container)
./test-integration.sh
```

This script will:
1. Start a MinIO Docker container with test credentials
2. Wait for MinIO to be ready
3. Run all integration tests
4. Clean up the container

### Manual Testing with Docker MinIO

If you want to manually test against the Docker MinIO instance:

```bash
# Start MinIO container
docker compose -f docker-compose.test.yml up -d

# MinIO will be available at:
# - API: http://localhost:9000
# - Console: http://localhost:9001
# - Credentials: testuser / testpass123

# Configure MinIO TUI to use test server
export MINIO_TUI_MINIO_ENDPOINT_URL="http://localhost:9000"
export MINIO_TUI_MINIO_ACCESS_KEY="testuser"
export MINIO_TUI_MINIO_SECRET_KEY="testpass123"

# Run MinIO TUI
minio-tui

# Stop container when done
docker compose -f docker-compose.test.yml down -v
```

### Integration Test Structure

Integration tests are located in `tests/integration/` and extend `MinIOIntegrationTest`:

- **Automatic setup/teardown** - Containers managed automatically
- **Real API calls** - No mocking, actual MinIO responses
- **Cleanup** - Test buckets and objects automatically cleaned up
- **Skip if unavailable** - Tests skip gracefully if MinIO isn't running

### Test Categories

1. **Unit Tests** (`tests/test_*.py`)
   - Fast execution (~1 second)
   - Mocked dependencies
   - Edge case testing
   - Always run in CI/CD

2. **Integration Tests** (`tests/integration/test_*.py`)
   - Real MinIO API calls
   - Authentication testing
   - Data serialization verification
   - Run before releases

## Best Practices

- **Run unit tests frequently** during development
- **Run integration tests** before committing major changes
- **Add integration tests** for new MinIO API features
- **Keep integration tests isolated** - each test cleans up after itself

## Troubleshooting

### Docker Issues
```bash
# Check if MinIO container is running
docker ps

# View MinIO logs
docker compose -f docker-compose.test.yml logs minio-test

# Reset everything
docker compose -f docker-compose.test.yml down -v
docker system prune -f
```

### Port Conflicts
If ports 9000/9001 are in use, modify `docker-compose.test.yml` to use different ports and update the test configuration accordingly.

### Network Issues
Ensure Docker can access localhost ports and that no firewall is blocking the connections.