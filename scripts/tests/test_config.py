import os
import unittest
from pathlib import Path
from dynaconf import Dynaconf

# Define the path to the test configuration files
TESTS_DIR = Path(__file__).parent
TEST_CONFIG_TOML = TESTS_DIR / "config.toml"
TEST_DOTENV = TESTS_DIR / ".env"

class TestConfig(unittest.TestCase):

    def setUp(self):
        """Set up a fresh Dynaconf instance for each test."""
        # Clean up environment variables before each test
        if "MINIO_TUI_MINIO_ENDPOINT_URL" in os.environ:
            del os.environ["MINIO_TUI_MINIO_ENDPOINT_URL"]
        if "MINIO_TUI_MINIO_SECRET_KEY" in os.environ:
            del os.environ["MINIO_TUI_MINIO_SECRET_KEY"]

        self.settings = Dynaconf(
            settings_files=[str(TEST_CONFIG_TOML)],
            load_dotenv=True,
            dotenv_path=str(TEST_DOTENV),
            envvar_prefix="MINIO_TUI",
            environments=True,
            merge_enabled=True,
            default_env="default",
        )

    def test_load_from_toml(self):
        """Tests that configuration is loaded from the TOML file."""
        self.assertEqual(self.settings.minio.endpoint_url, "http://localhost:9000")
        self.assertEqual(self.settings.minio.access_key, "test_access_key")

    def test_load_from_dotenv(self):
        """Tests that configuration is loaded from the .env file."""
        self.assertEqual(self.settings.minio.secret_key, "secret_from_env")

    def test_load_from_env_override(self):
        """Tests that environment variables override other config files."""
        os.environ["MINIO_TUI_MINIO_ENDPOINT_URL"] = "http://override:9000"
        
        settings = Dynaconf(
            settings_files=[str(TEST_CONFIG_TOML)],
            load_dotenv=True,
            dotenv_path=str(TEST_DOTENV),
            envvar_prefix="MINIO_TUI",
            environments=True,
            merge_enabled=True,
            default_env="default",
        )
        
        self.assertEqual(settings.minio.endpoint_url, "http://override:9000")
        del os.environ["MINIO_TUI_MINIO_ENDPOINT_URL"]

if __name__ == "__main__":
    unittest.main()
