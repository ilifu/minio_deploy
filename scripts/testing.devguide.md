# Testing Guide

This guide documents the comprehensive testing strategy used in the MinIO TUI project, including patterns, practices, and lessons learned.

## Testing Philosophy

### Core Principles

1. **Test Pyramid**: Lots of unit tests, some integration tests, few end-to-end tests
2. **Test-Driven Development**: Tests guide design and catch regressions
3. **Mock External Dependencies**: Isolate units under test
4. **Realistic Test Data**: Use data that reflects real-world scenarios
5. **Comprehensive Coverage**: Test both happy paths and error conditions

### Test Categories

```
End-to-End Tests (5%)     # Full system integration (future)
     ↑
Integration Tests (5%)    # Real MinIO API tests (Docker-based)
     ↑  
Unit Tests (90%)         # Individual functions/methods (mocked)
```

**Current Implementation:**
- **Unit Tests (71)**: Fast, mocked dependencies, comprehensive coverage
- **Integration Tests (4)**: Real MinIO server via Docker, API validation
- **Dual Strategy**: Both approaches complement each other perfectly

## Test Structure

### Directory Organization

```
tests/
├── test_app.py              # UI component tests (unit)
├── test_app_actions.py      # Action and workflow tests (unit)
├── test_minio_client.py     # Business logic tests (unit)
├── test_simple_config.py    # Configuration tests (unit)
├── integration/             # Integration tests (real MinIO)
│   ├── __init__.py
│   └── test_minio_integration.py
├── test_config_integration.toml  # Integration test config
├── conftest.py              # Shared fixtures and utilities
└── fixtures/                # Test data files
    ├── sample.txt
    ├── large_file.bin
    └── test_config.toml
```

### Test Naming Conventions

```python
class TestMinioClient:
    def test_list_buckets_success(self):           # Happy path
    def test_list_buckets_no_credentials(self):    # Error condition
    def test_list_buckets_connection_error(self):  # Network error
    
    def test_upload_file_simple(self):             # Basic functionality
    def test_upload_file_with_progress(self):      # Advanced feature
    def test_upload_file_cancellation(self):       # Edge case
```

## Unit Testing Patterns

### 1. Mocking External Dependencies

**MinIO Client Tests:**
```python
import unittest
from unittest.mock import MagicMock, patch
import pytest

class TestMinioClient:
    def setup_method(self):
        """Setup run before each test method."""
        self.mock_s3_client = MagicMock()
        self.minio_client = MinioClient(client=self.mock_s3_client)
    
    def test_list_buckets_success(self):
        """Test successful bucket listing."""
        # Arrange
        self.mock_s3_client.list_buckets.return_value = {
            'Buckets': [
                {'Name': 'bucket1'},
                {'Name': 'bucket2'}
            ]
        }
        
        # Act
        result = self.minio_client.list_buckets()
        
        # Assert
        assert result == ['bucket1', 'bucket2']
        self.mock_s3_client.list_buckets.assert_called_once()
    
    def test_list_buckets_error_handling(self):
        """Test error handling for bucket listing."""
        from botocore.exceptions import ClientError
        
        # Arrange
        error = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'list_buckets'
        )
        self.mock_s3_client.list_buckets.side_effect = error
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            self.minio_client.list_buckets()
        
        assert "Access denied" in str(exc_info.value)
```

### 2. Testing with Temporary Files

```python
import tempfile
import os
from pathlib import Path

class TestFileOperations:
    def test_upload_file_success(self):
        """Test file upload with real file."""
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            test_content = "Hello, MinIO!"
            temp_file.write(test_content)
            temp_file_path = temp_file.name
        
        try:
            # Setup mock
            self.mock_s3_client.upload_file.return_value = None
            
            # Test upload
            self.minio_client.upload_file('test-bucket', 'test-object', temp_file_path)
            
            # Verify upload was called with correct parameters
            self.mock_s3_client.upload_file.assert_called_once_with(
                temp_file_path, 'test-bucket', 'test-object'
            )
        finally:
            # Cleanup
            os.unlink(temp_file_path)
    
    def test_get_object_content_binary_detection(self):
        """Test binary file detection."""
        # Test with binary content
        binary_content = b'\x00\x01\x02\x03\xff\xfe\xfd'
        
        self.mock_s3_client.get_object.return_value = {
            'Body': MagicMock(),
            'ContentLength': len(binary_content)
        }
        self.mock_s3_client.get_object.return_value['Body'].read.return_value = binary_content
        
        with pytest.raises(Exception) as exc_info:
            self.minio_client.get_object_content('test-bucket', 'binary-file')
        
        assert "binary data" in str(exc_info.value).lower()
```

### 3. Testing Progress Callbacks

```python
def test_upload_with_progress_callback(self):
    """Test that progress callbacks are called correctly."""
    # Track progress calls
    progress_calls = []
    
    def progress_callback(bytes_transferred):
        progress_calls.append(bytes_transferred)
    
    # Create test file
    test_content = b"A" * 1000  # 1KB file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(test_content)
        temp_file_path = temp_file.name
    
    try:
        # Mock successful upload
        self.mock_s3_client.upload_file.return_value = None
        
        # Test upload with progress
        self.minio_client.upload_file(
            'test-bucket', 
            'test-object', 
            temp_file_path,
            progress_callback=progress_callback
        )
        
        # Verify upload was called with callback
        call_args = self.mock_s3_client.upload_file.call_args
        assert 'Callback' in call_args.kwargs
        
        # Simulate progress callback
        callback = call_args.kwargs['Callback']
        callback(500)  # 50% progress
        callback(1000) # 100% progress
        
        # Verify progress was tracked
        assert progress_calls == [500, 1000]
        
    finally:
        os.unlink(temp_file_path)
```

## Integration Testing

### 1. Configuration Testing

```python
import tempfile
import os
from pathlib import Path

class TestSimpleConfig:
    def test_toml_and_env_integration(self):
        """Test TOML file with environment variable override."""
        # Create temporary TOML file
        toml_content = """
[minio]
endpoint_url = "http://localhost:9000"
access_key = "toml_key"
secret_key = "toml_secret"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name
        
        try:
            # Set environment variable to override TOML
            os.environ['MINIO_TUI_MINIO_ACCESS_KEY'] = 'env_override_key'
            
            # Load config
            config = Config(config_files=[toml_file])
            
            # Verify environment variable takes precedence
            assert config.get('minio.endpoint_url') == 'http://localhost:9000'  # From TOML
            assert config.get('minio.access_key') == 'env_override_key'          # From ENV
            assert config.get('minio.secret_key') == 'toml_secret'               # From TOML
            
        finally:
            os.unlink(toml_file)
            os.environ.pop('MINIO_TUI_MINIO_ACCESS_KEY', None)
```

### 2. UI Component Integration

```python
from textual.testing import run_pilot

class TestModalScreens:
    async def test_upload_file_screen_integration(self):
        """Test upload file screen workflow."""
        app = MinioTUI()
        
        async with run_pilot(app) as pilot:
            # Initialize app state
            app.current_bucket = "test-bucket"
            
            # Open upload screen
            await pilot.press("u")
            
            # Verify modal is shown
            upload_screen = app.screen
            assert isinstance(upload_screen, UploadFileScreen)
            
            # Fill in form
            await pilot.click("#file_path")
            await pilot.type("/path/to/test/file.txt")
            
            await pilot.click("#object_name")
            await pilot.type("uploads/file.txt")
            
            # Submit form
            await pilot.click("#upload")
            
            # Verify modal was dismissed
            assert app.screen != upload_screen
```

## Testing Complex Workflows

### 1. Testing Threaded Operations

```python
import threading
import time

class TestProgressOperations:
    def test_upload_with_cancellation(self):
        """Test upload cancellation workflow."""
        # Create cancel event
        cancel_event = threading.Event()
        
        # Track progress
        progress_calls = []
        def progress_callback(bytes_transferred):
            progress_calls.append(bytes_transferred)
            # Cancel after some progress
            if len(progress_calls) >= 2:
                cancel_event.set()
        
        # Create large test file
        large_content = b"A" * (1024 * 1024)  # 1MB
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(large_content)
            temp_file_path = temp_file.name
        
        try:
            # Test cancellation
            with pytest.raises(Exception) as exc_info:
                self.minio_client.upload_file(
                    'test-bucket',
                    'large-file',
                    temp_file_path,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event
                )
            
            assert "cancelled" in str(exc_info.value).lower()
            assert len(progress_calls) >= 2  # Some progress was made
            
        finally:
            os.unlink(temp_file_path)
```

### 2. Testing Error Recovery

```python
def test_multipart_upload_cleanup_on_error(self):
    """Test that failed multipart uploads are properly cleaned up."""
    # Mock multipart upload initialization
    self.mock_s3_client.create_multipart_upload.return_value = {
        'UploadId': 'test-upload-id'
    }
    
    # Mock upload part to fail after first part
    upload_part_calls = 0
    def upload_part_side_effect(*args, **kwargs):
        nonlocal upload_part_calls
        upload_part_calls += 1
        if upload_part_calls == 1:
            return {'ETag': 'test-etag-1'}
        else:
            raise ClientError(
                {'Error': {'Code': 'InternalError', 'Message': 'Server error'}},
                'upload_part'
            )
    
    self.mock_s3_client.upload_part.side_effect = upload_part_side_effect
    
    # Create large file to trigger multipart upload
    large_content = b"A" * (1024 * 1024 * 2)  # 2MB
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(large_content)
        temp_file_path = temp_file.name
    
    try:
        # Upload should fail and cleanup
        with pytest.raises(Exception):
            self.minio_client.upload_file('test-bucket', 'large-file', temp_file_path)
        
        # Verify cleanup was called
        self.mock_s3_client.abort_multipart_upload.assert_called_once_with(
            Bucket='test-bucket',
            Key='large-file',
            UploadId='test-upload-id'
        )
        
    finally:
        os.unlink(temp_file_path)
```

## Testing UI Components

### 1. Modal Screen Testing

```python
from textual.testing import run_pilot

class TestModalScreens:
    def test_create_bucket_screen_validation(self):
        """Test bucket creation form validation."""
        screen = CreateBucketScreen()
        
        # Test empty bucket name
        screen.query_one("#bucket_name").value = ""
        
        # Simulate create button press
        button_event = Button.Pressed(screen.query_one("#create"))
        screen.on_button_pressed(button_event)
        
        # Should not dismiss modal due to validation error
        assert screen.is_attached  # Modal still active
        
        # Test valid bucket name
        screen.query_one("#bucket_name").value = "valid-bucket-name"
        screen.on_button_pressed(button_event)
        
        # Should dismiss modal with data
        # (In real implementation, check dismiss was called with correct data)
    
    def test_file_preview_screen_syntax_detection(self):
        """Test syntax highlighting language detection."""
        # Test Python file
        assert get_syntax_language("script.py") == "python"
        assert get_syntax_language("app.py") == "python"
        
        # Test JavaScript
        assert get_syntax_language("script.js") == "javascript"
        assert get_syntax_language("app.jsx") == "javascript"
        
        # Test JSON
        assert get_syntax_language("config.json") == "json"
        assert get_syntax_language("package.json") == "json"
        
        # Test unknown extension
        assert get_syntax_language("unknown.xyz") == ""
        
        # Test no extension
        assert get_syntax_language("README") == "markdown"
        assert get_syntax_language("Dockerfile") == ""
```

### 2. Testing Tree Operations

```python
def test_object_tree_building(self):
    """Test hierarchical object tree construction."""
    # Sample objects with directory structure
    objects = [
        {'key': 'file1.txt', 'size': 100},
        {'key': 'dir1/file2.txt', 'size': 200},
        {'key': 'dir1/subdir/file3.txt', 'size': 300},
        {'key': 'dir2/file4.txt', 'size': 400},
    ]
    
    app = MinioTUI()
    app.update_object_tree(objects)
    
    tree = app.query_one("#objects_tree")
    
    # Verify tree structure
    root_children = list(tree.root.children)
    assert len(root_children) == 3  # file1.txt, dir1, dir2
    
    # Find directory nodes
    dir1_node = next(child for child in root_children if "dir1" in child.label)
    dir2_node = next(child for child in root_children if "dir2" in child.label)
    
    # Verify directory contents
    dir1_children = list(dir1_node.children)
    assert len(dir1_children) == 2  # file2.txt, subdir
    
    # Verify file data is preserved
    file1_node = next(child for child in root_children if "file1.txt" in child.label)
    assert file1_node.data == 'file1.txt'
```

## Performance Testing

### 1. Memory Usage Testing

```python
import psutil
import os

def test_large_object_list_memory_usage(self):
    """Test memory usage with large object lists."""
    # Generate large object list
    large_object_list = [
        {'key': f'object_{i}.txt', 'size': i * 1000}
        for i in range(10000)  # 10k objects
    ]
    
    # Measure memory before
    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss
    
    # Update tree with large list
    app = MinioTUI()
    app.update_object_tree(large_object_list)
    
    # Measure memory after
    memory_after = process.memory_info().rss
    memory_increase = memory_after - memory_before
    
    # Assert reasonable memory usage (less than 100MB for 10k objects)
    assert memory_increase < 100 * 1024 * 1024  # 100MB
    
    # Test memory cleanup
    app.clear_objects_tree()
    
    # Force garbage collection
    import gc
    gc.collect()
    
    # Memory should be released (allow some overhead)
    memory_final = process.memory_info().rss
    assert memory_final < memory_after
```

### 2. Response Time Testing

```python
import time

def test_object_list_performance(self):
    """Test object listing performance."""
    # Mock large response
    large_response = {
        'Contents': [
            {'Key': f'object_{i}.txt', 'Size': i * 100, 'LastModified': datetime.now()}
            for i in range(1000)
        ]
    }
    
    self.mock_s3_client.list_objects_v2.return_value = large_response
    
    # Measure execution time
    start_time = time.time()
    result = self.minio_client.list_objects_with_metadata('test-bucket')
    end_time = time.time()
    
    # Should complete within reasonable time
    execution_time = end_time - start_time
    assert execution_time < 1.0  # Less than 1 second for 1000 objects
    
    # Verify all objects processed
    assert len(result) == 1000
```

## Test Fixtures and Utilities

### 1. Shared Fixtures

```python
# conftest.py
import pytest
import tempfile
import os
from pathlib import Path

@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"Test content for file operations")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)

@pytest.fixture
def large_temp_file():
    """Create a large temporary file for testing."""
    content = b"A" * (1024 * 1024)  # 1MB
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(content)
        temp_path = f.name
    
    yield temp_path, len(content)
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)

@pytest.fixture
def mock_minio_client():
    """Create a MinIO client with mocked S3 client."""
    from unittest.mock import MagicMock
    mock_s3 = MagicMock()
    return MinioClient(client=mock_s3), mock_s3

@pytest.fixture
def sample_objects():
    """Sample object list for testing."""
    return [
        {'key': 'document.pdf', 'size': 1024, 'last_modified': datetime.now()},
        {'key': 'images/photo1.jpg', 'size': 2048, 'last_modified': datetime.now()},
        {'key': 'images/photo2.png', 'size': 1536, 'last_modified': datetime.now()},
        {'key': 'data/export.csv', 'size': 4096, 'last_modified': datetime.now()},
    ]
```

### 2. Test Utilities

```python
# test_utils.py
from contextlib import contextmanager
import threading
import time

@contextmanager
def timeout(seconds):
    """Context manager for testing timeouts."""
    def timeout_handler():
        raise TimeoutError(f"Test timed out after {seconds} seconds")
    
    timer = threading.Timer(seconds, timeout_handler)
    timer.start()
    try:
        yield
    finally:
        timer.cancel()

def wait_for_condition(condition_func, timeout=5, interval=0.1):
    """Wait for a condition to become true."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False

def assert_eventually(condition_func, timeout=5, message="Condition not met"):
    """Assert that a condition becomes true within timeout."""
    if not wait_for_condition(condition_func, timeout):
        raise AssertionError(message)

# Usage in tests
def test_async_operation():
    app = MinioTUI()
    app.start_background_operation()
    
    # Wait for operation to complete
    assert_eventually(
        lambda: app.operation_complete,
        timeout=10,
        message="Background operation did not complete"
    )
```

## Test Data Management

### 1. Test Data Generation

```python
def generate_test_objects(count=100, prefix="test/"):
    """Generate realistic test object data."""
    import random
    from datetime import datetime, timedelta
    
    file_types = ['.txt', '.pdf', '.jpg', '.png', '.csv', '.json', '.py', '.js']
    directories = ['documents/', 'images/', 'data/', 'scripts/', '']
    
    objects = []
    for i in range(count):
        directory = random.choice(directories)
        extension = random.choice(file_types)
        filename = f"file_{i:04d}{extension}"
        
        objects.append({
            'key': f"{prefix}{directory}{filename}",
            'size': random.randint(100, 10000),
            'last_modified': datetime.now() - timedelta(days=random.randint(0, 365)),
            'etag': f"etag_{i:04d}",
            'storage_class': random.choice(['STANDARD', 'REDUCED_REDUNDANCY'])
        })
    
    return objects
```

### 2. Test Configuration

```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --strict-config
    --cov=minio_tui
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90

markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    ui: marks tests as UI tests
```

## Continuous Integration

### 1. Test Pipeline

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .[dev]
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=minio_tui --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Test Maintenance

### 1. Test Health Monitoring

```python
# Detect flaky tests
def test_stability_check():
    """Run a test multiple times to check for flakiness."""
    results = []
    for _ in range(10):
        try:
            # Run the potentially flaky test
            result = potentially_flaky_operation()
            results.append(True)
        except Exception:
            results.append(False)
    
    # Should be stable (at least 90% success rate)
    success_rate = sum(results) / len(results)
    assert success_rate >= 0.9, f"Test is flaky: {success_rate:.2%} success rate"
```

### 2. Test Performance Tracking

```python
import time
import json
from pathlib import Path

def track_test_performance(test_name, duration):
    """Track test execution times."""
    perf_file = Path("test_performance.json")
    
    if perf_file.exists():
        with open(perf_file) as f:
            data = json.load(f)
    else:
        data = {}
    
    if test_name not in data:
        data[test_name] = []
    
    data[test_name].append(duration)
    
    # Keep only last 10 runs
    data[test_name] = data[test_name][-10:]
    
    with open(perf_file, 'w') as f:
        json.dump(data, f, indent=2)

# Decorator for automatic performance tracking
def track_performance(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            duration = time.time() - start_time
            track_test_performance(func.__name__, duration)
    return wrapper
```

## Testing Best Practices Summary

1. **Write Tests First**: Use TDD approach for new features
2. **Mock External Dependencies**: Isolate units under test
3. **Test Both Success and Failure**: Cover happy paths and error conditions
4. **Use Realistic Data**: Test with data that reflects real usage
5. **Keep Tests Fast**: Unit tests should run in milliseconds
6. **Make Tests Independent**: Each test should be able to run in isolation
7. **Use Clear Assertions**: Make test failures easy to understand
8. **Test the Interface**: Focus on testing public APIs, not implementation details
9. **Maintain Test Code**: Refactor tests when refactoring production code
10. **Monitor Test Health**: Track flaky tests and performance regressions

This comprehensive testing strategy ensures the MinIO TUI is reliable, maintainable, and performs well under various conditions.