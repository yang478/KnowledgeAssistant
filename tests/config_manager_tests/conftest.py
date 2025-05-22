"""Shared fixtures for ConfigManager tests."""

import pytest
import json
import os
from unittest import mock
import sys

# Ensure the config_manager module can be imported
# Adjust path if conftest.py is in a subdirectory like tests/config_manager_tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from config_manager.config_manager import ConfigManager, logger

# Helper function to reset ConfigManager singleton for isolated tests
def reset_config_manager_singleton():
    """Resets the ConfigManager singleton instance and its state."""
    ConfigManager._instance = None
    ConfigManager._config_dir = None
    ConfigManager._config = None
    # ConfigManager._env_var_map = None # Let it use the class default
    ConfigManager._initialized_with_config_dir = None

@pytest.fixture(autouse=True)
def reset_singleton_before_each_test():
    """Fixture to automatically reset the ConfigManager singleton before each test."""
    reset_config_manager_singleton()

@pytest.fixture
def temp_config_dir(tmp_path):
    """Creates a temporary directory for config files."""
    config_dir = tmp_path / "config_test_dir"
    config_dir.mkdir()
    return config_dir

@pytest.fixture
def base_config_content():
    """Provides base configuration data."""
    return {
        "database": {
            "host": "localhost",
            "port": 5432,
            "user": "base_user"
        },
        "logging_level": "INFO",
        "feature_flags": {
            "new_dashboard": True,
            "alpha_feature": False
        },
        "service_url": "http://base.example.com"
    }

@pytest.fixture
def env_specific_config_content():
    """Provides environment-specific configuration data for overrides."""
    return {
        "database": {
            "host": "prod_host", # Override
            "port": 5433 # Override
            # user is not overridden, should remain "base_user"
        },
        "logging_level": "DEBUG", # Override
        "api_key": "env_specific_key_123", # New key
        "feature_flags": { # Nested override/merge
            "new_dashboard": False, # Override
            "beta_feature": True # New flag
        }
    }

@pytest.fixture
def create_base_config_file(temp_config_dir, base_config_content):
    """Creates a base config.json file in the temp_config_dir."""
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f:
        json.dump(base_config_content, f)
    return config_file_path

@pytest.fixture
def create_env_specific_config_file(temp_config_dir, env_specific_config_content):
    """Creates an environment-specific config file (e.g., config.test_env.json)."""
    env_name = "test_env"
    env_config_file_path = temp_config_dir / f"{os.path.splitext("config.json")[0]}.{env_name}.json"
    with open(env_config_file_path, 'w') as f:
        json.dump(env_specific_config_content, f)
    return env_config_file_path, env_name

@pytest.fixture
def create_invalid_json_file(temp_config_dir):
    """Creates a file with invalid JSON content."""
    invalid_file_path = temp_config_dir / "invalid_config.json"
    with open(invalid_file_path, 'w') as f:
        f.write("this is not valid json {")
    return invalid_file_path

@pytest.fixture
def env_var_map_config():
    """Config content specifically for testing environment variable overrides via _env_var_map."""
    return {
        "database": {
            "host": "db_host_from_file",
            "port": 1111,
            "password_ref": "ENV_DB_PASSWORD" 
        },
        "api": {
            "key": "api_key_from_file",
            "secret_ref": "ENV_API_SECRET"
        },
        "logging": {
            "level": "FILE_INFO"
        },
        "feature_x_enabled": False 
    }

@pytest.fixture
def create_env_var_map_config_file(temp_config_dir, env_var_map_config):
    """Creates a config file for testing _env_var_map."""
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f:
        json.dump(env_var_map_config, f)
    return config_file_path