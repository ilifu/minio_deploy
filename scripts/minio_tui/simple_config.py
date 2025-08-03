"""
Simple configuration management for MinIO TUI.
Supports TOML files and environment variables, with environment variables taking precedence.
"""

import os
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Simple configuration loader that supports TOML files and environment variables."""
    
    def __init__(self, config_files: Optional[list] = None, env_prefix: str = "MINIO_TUI"):
        self.env_prefix = env_prefix
        self.config_data = {}
        
        # Default config files to look for
        if config_files is None:
            cwd = Path.cwd()
            config_files = [
                cwd / "config.toml",
                cwd / "minio_tui.toml",
                Path.home() / ".config" / "minio_tui" / "config.toml"
            ]
        
        # Load configuration from TOML files
        for config_file in config_files:
            if isinstance(config_file, str):
                config_file = Path(config_file)
            
            if config_file.exists():
                try:
                    with open(config_file, "rb") as f:
                        toml_data = tomllib.load(f)
                        self._merge_config(toml_data)
                        break  # Use the first config file found
                except Exception as e:
                    print(f"Warning: Could not load config from {config_file}: {e}")
        
        # Load configuration from environment variables (these override TOML)
        self._load_env_vars()
    
    def _merge_config(self, new_config: Dict[str, Any]) -> None:
        """Merge new configuration data into existing config."""
        for key, value in new_config.items():
            if isinstance(value, dict) and key in self.config_data and isinstance(self.config_data[key], dict):
                self.config_data[key].update(value)
            else:
                self.config_data[key] = value
    
    def _load_env_vars(self) -> None:
        """Load configuration from environment variables."""
        for key, value in os.environ.items():
            if key.startswith(f"{self.env_prefix}_"):
                # Convert MINIO_TUI_MINIO_ENDPOINT_URL to minio.endpoint_url
                config_key = key[len(f"{self.env_prefix}_"):].lower()
                
                # Handle nested configuration (e.g., MINIO_ENDPOINT_URL -> minio.endpoint_url)
                parts = config_key.split("_")
                if len(parts) >= 2:
                    section = parts[0]
                    setting = "_".join(parts[1:])
                    
                    if section not in self.config_data:
                        self.config_data[section] = {}
                    
                    self.config_data[section][setting] = value
                else:
                    # Single-level config
                    self.config_data[config_key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key (e.g., 'minio.endpoint_url' or 'MINIO_ENDPOINT_URL')
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        # Handle both dotted notation and environment variable style
        if "." in key:
            section, setting = key.split(".", 1)
            return self.config_data.get(section, {}).get(setting, default)
        else:
            # Handle direct environment variable style (e.g., MINIO_ENDPOINT_URL)
            key_lower = key.lower()
            if "_" in key_lower:
                parts = key_lower.split("_")
                section = parts[0]
                setting = "_".join(parts[1:])
                return self.config_data.get(section, {}).get(setting, default)
            else:
                return self.config_data.get(key_lower, default)
    
    def get_minio_config(self) -> Dict[str, str]:
        """
        Get MinIO configuration with required keys.
        
        Returns:
            Dictionary with endpoint_url, access_key, secret_key
            
        Raises:
            ValueError: If required configuration is missing
        """
        minio_config = {}
        
        # Get required configuration
        endpoint_url = self.get("minio.endpoint_url") or self.get("MINIO_ENDPOINT_URL")
        access_key = self.get("minio.access_key") or self.get("MINIO_ACCESS_KEY")
        secret_key = self.get("minio.secret_key") or self.get("MINIO_SECRET_KEY")
        
        if not endpoint_url:
            raise ValueError("MinIO endpoint URL is required. Set it in config.toml [minio] section or MINIO_TUI_MINIO_ENDPOINT_URL environment variable.")
        
        if not access_key:
            raise ValueError("MinIO access key is required. Set it in config.toml [minio] section or MINIO_TUI_MINIO_ACCESS_KEY environment variable.")
        
        if not secret_key:
            raise ValueError("MinIO secret key is required. Set it in config.toml [minio] section or MINIO_TUI_MINIO_SECRET_KEY environment variable.")
        
        return {
            "endpoint_url": endpoint_url,
            "access_key": access_key,
            "secret_key": secret_key
        }


# Create a global configuration instance
settings = Config()