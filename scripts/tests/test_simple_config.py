import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import sys
from pathlib import Path

# Add the 'scripts' directory to the Python path to allow importing 'minio_tui'
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from minio_tui.simple_config import Config


class TestSimpleConfig(unittest.TestCase):

    def setUp(self):
        """Clean up environment variables before each test."""
        for key in list(os.environ.keys()):
            if key.startswith("MINIO_TUI_"):
                del os.environ[key]

    def test_load_from_toml_file(self):
        """Test loading configuration from a TOML file."""
        # Create a temporary TOML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
[minio]
endpoint_url = "http://localhost:9000"
access_key = "test_access_key"
secret_key = "test_secret_key"
""")
            toml_file = f.name

        try:
            config = Config(config_files=[toml_file])
            
            self.assertEqual(config.get("minio.endpoint_url"), "http://localhost:9000")
            self.assertEqual(config.get("minio.access_key"), "test_access_key")
            self.assertEqual(config.get("minio.secret_key"), "test_secret_key")
            
            # Test get_minio_config method
            minio_config = config.get_minio_config()
            self.assertEqual(minio_config["endpoint_url"], "http://localhost:9000")
            self.assertEqual(minio_config["access_key"], "test_access_key")
            self.assertEqual(minio_config["secret_key"], "test_secret_key")
            
        finally:
            os.unlink(toml_file)

    def test_load_from_environment_variables(self):
        """Test loading configuration from environment variables."""
        os.environ["MINIO_TUI_MINIO_ENDPOINT_URL"] = "http://env:9000"
        os.environ["MINIO_TUI_MINIO_ACCESS_KEY"] = "env_access_key"
        os.environ["MINIO_TUI_MINIO_SECRET_KEY"] = "env_secret_key"
        
        config = Config(config_files=[])  # No TOML files
        
        self.assertEqual(config.get("minio.endpoint_url"), "http://env:9000")
        self.assertEqual(config.get("minio.access_key"), "env_access_key")
        self.assertEqual(config.get("minio.secret_key"), "env_secret_key")
        
        # Test get_minio_config method
        minio_config = config.get_minio_config()
        self.assertEqual(minio_config["endpoint_url"], "http://env:9000")
        self.assertEqual(minio_config["access_key"], "env_access_key")
        self.assertEqual(minio_config["secret_key"], "env_secret_key")

    def test_environment_variables_override_toml(self):
        """Test that environment variables override TOML file values."""
        # Create a temporary TOML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
[minio]
endpoint_url = "http://localhost:9000"
access_key = "toml_access_key"
secret_key = "toml_secret_key"
""")
            toml_file = f.name

        try:
            # Set environment variable that should override TOML
            os.environ["MINIO_TUI_MINIO_ACCESS_KEY"] = "env_override_key"
            
            config = Config(config_files=[toml_file])
            
            # TOML values should be used where no env var is set
            self.assertEqual(config.get("minio.endpoint_url"), "http://localhost:9000")
            self.assertEqual(config.get("minio.secret_key"), "toml_secret_key")
            
            # Environment variable should override TOML
            self.assertEqual(config.get("minio.access_key"), "env_override_key")
            
        finally:
            os.unlink(toml_file)

    def test_missing_configuration_error(self):
        """Test that missing required configuration raises an error."""
        config = Config(config_files=[])  # No config files, no env vars
        
        with self.assertRaises(ValueError) as context:
            config.get_minio_config()
        
        self.assertIn("endpoint URL is required", str(context.exception))

    def test_alternative_key_formats(self):
        """Test different ways of accessing configuration keys."""
        os.environ["MINIO_TUI_MINIO_ENDPOINT_URL"] = "http://test:9000"
        
        config = Config(config_files=[])
        
        # Both dotted notation and env var style should work
        self.assertEqual(config.get("minio.endpoint_url"), "http://test:9000")
        self.assertEqual(config.get("MINIO_ENDPOINT_URL"), "http://test:9000")

    def test_get_with_default_value(self):
        """Test getting configuration with default values."""
        config = Config(config_files=[])
        
        # Should return default when key doesn't exist
        self.assertEqual(config.get("nonexistent.key", "default_value"), "default_value")
        self.assertIsNone(config.get("nonexistent.key"))

    def test_nonexistent_toml_file_ignored(self):
        """Test that nonexistent TOML files are ignored gracefully."""
        # This should not raise an error
        config = Config(config_files=["/nonexistent/path/config.toml"])
        
        # Should return None for missing keys
        self.assertIsNone(config.get("minio.endpoint_url"))


if __name__ == "__main__":
    unittest.main()