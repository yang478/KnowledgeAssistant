"""Unit tests for ConfigManager - Get Config Value aspects."""

import pytest
from unittest import mock

# ConfigManager, logger are expected to be available via conftest.py
from config_manager.config_manager import ConfigManager, logger

# Note: Fixtures like temp_config_dir, create_base_config_file, base_config_content
# are automatically discovered from tests/config_manager_tests/conftest.py


def test_get_config_existing_top_level_key(temp_config_dir, create_base_config_file, base_config_content):
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("logging_level") == base_config_content["logging_level"]

def test_get_config_existing_nested_key(temp_config_dir, create_base_config_file, base_config_content):
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("database.host") == base_config_content["database"]["host"]
    assert cm.get_config("feature_flags.new_dashboard") == base_config_content["feature_flags"]["new_dashboard"]

def test_get_config_non_existent_key_no_default(temp_config_dir, create_base_config_file):
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("this_key_does_not_exist") is None
    assert cm.get_config("database.this_nested_key_does_not_exist") is None

def test_get_config_non_existent_key_with_default(temp_config_dir, create_base_config_file):
    cm = ConfigManager(config_dir=str(temp_config_dir))
    default_value = "my_default"
    assert cm.get_config("this_key_does_not_exist", default_value) == default_value
    assert cm.get_config("database.this_nested_key_does_not_exist", default_value) == default_value

def test_get_config_key_points_to_dict_no_default(temp_config_dir, create_base_config_file, base_config_content):
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("database") == base_config_content["database"]

def test_get_config_key_points_to_dict_with_default_ignored(temp_config_dir, create_base_config_file, base_config_content):
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("database", default_value="should_be_ignored") == base_config_content["database"]

def test_get_config_with_empty_key_string(temp_config_dir, create_base_config_file):
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("", "default_for_empty") == "default_for_empty"
    # Current implementation of _get_value_by_path might return entire config for empty string
    # Let's check the actual behavior based on implementation.
    # If key is '', _get_value_by_path returns current_level (which is self._config)
    assert cm.get_config("") == cm._config


def test_security_sensitive_info_not_logged_on_get_config(temp_config_dir, create_base_config_file, caplog):
    """Ensure get_config itself doesn't log the values being retrieved (unless in debug for missing keys)."""
    logger.setLevel("INFO") # Set to INFO to catch unwanted logs
    cm = ConfigManager(config_dir=str(temp_config_dir))
    
    # Get a known sensitive-like key
    cm.get_config("database.host") 
    # Get a non-existent key with default
    cm.get_config("non_existent_secret", "default_secret_val")

    # Check caplog for any logs containing the actual values "localhost" or "default_secret_val"
    # from the get_config calls themselves.
    # Note: ConfigManager logs overrides during load, which is fine. This test is about `get_config`.
    for record in caplog.records:
        # Allow logs from _load_config_files or _apply_env_overrides or _initialize_config_if_needed
        if record.funcName not in ['_load_config_files', '_apply_env_overrides', '_initialize_config_if_needed']:
            assert "localhost" not in record.message.lower()
            assert "default_secret_val" not in record.message.lower()
            # A missing key might log the key name and default, which is acceptable at DEBUG
            if record.levelname == "DEBUG": # pragma: no cover
                assert "non_existent_secret" in record.message # Key name is fine
            else: # At INFO or higher, should not log details of get_config calls
                assert "non_existent_secret" not in record.message