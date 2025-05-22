"""Unit tests for ConfigManager - Environment Variable Override aspects."""

import pytest
import os
import json
from unittest import mock

# ConfigManager, CONFIG_FILE_NAME, logger, and fixtures like temp_config_dir,
# create_env_var_map_config_file, env_var_map_config, base_config_content,
# reset_config_manager_singleton (via autouse fixture)
# are expected to be available via conftest.py
from config_manager.config_manager import ConfigManager, logger


def test_env_variable_override_simple_string(temp_config_dir, env_var_map_config):
    """Test direct override of a config value by an environment variable."""
    env_map_in_config = {"logging.level": "MY_APP_LOG_LEVEL"}
    # Use the env_var_map_config fixture and add ENV_VAR_MAP to it
    current_config_content = env_var_map_config.copy() # Get a mutable copy from fixture
    current_config_content["ENV_VAR_MAP"] = env_map_in_config
    
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f:
        json.dump(current_config_content, f)

    with mock.patch.dict(os.environ, {"MY_APP_LOG_LEVEL": "ENV_DEBUG"}):
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("logging.level") == "ENV_DEBUG"
        assert cm.get_config("database.host") == env_var_map_config["database"]["host"] # Not overridden

def test_env_variable_override_nested_key(temp_config_dir): # ConfigManager and CONFIG_FILE_NAME were already removed here by previous partial apply
    """Test override of a nested config value by an environment variable."""
    env_map_in_config = {"database.host": "DB_HOST_FROM_ENV", "database.port": "DB_PORT_FROM_ENV"}
    config_content = {
        "database": {"host": "file_host", "port": 1234, "user": "file_user"},
        "ENV_VAR_MAP": env_map_in_config
    }
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f: json.dump(config_content, f)

    with mock.patch.dict(os.environ, {"DB_HOST_FROM_ENV": "env_db_host", "DB_PORT_FROM_ENV": "5678"}):
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("database.host") == "env_db_host"
        assert cm.get_config("database.port") == 5678 # Should be converted to int
        assert cm.get_config("database.user") == "file_user"

def test_env_variable_override_boolean_conversion(temp_config_dir): # ConfigManager and CONFIG_FILE_NAME were already removed
    """Test boolean conversion for environment variables (e.g., "true", "false")."""
    env_map_in_config = {"feature_x_enabled": "FEATURE_X_ACTIVE"}
    config_content = {
        "feature_x_enabled": False, 
        "ENV_VAR_MAP": env_map_in_config
    }
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f: json.dump(config_content, f)

    test_cases = {
        "true": True, "True": True,
        "false": False, "False": False,
        "not_a_bool": "not_a_bool" # Stays string
    }
    # reset_config_manager_singleton is autouse, so it runs before each iteration implicitly if test func is re-entered
    # However, parameterizing the test is cleaner if possible.
    # For simplicity here, we'll rely on the autouse fixture and separate with blocks.

    with mock.patch.dict(os.environ, {"FEATURE_X_ACTIVE": "true"}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("feature_x_enabled") is True
    
    with mock.patch.dict(os.environ, {"FEATURE_X_ACTIVE": "False"}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("feature_x_enabled") is False

    with mock.patch.dict(os.environ, {"FEATURE_X_ACTIVE": "not_a_bool"}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("feature_x_enabled") == "not_a_bool"


def test_env_variable_override_integer_conversion(temp_config_dir): # ConfigManager and CONFIG_FILE_NAME were already removed
    """Test integer conversion for environment variables."""
    env_map_in_config = {"resources.worker_threads": "WORKER_COUNT"}
    config_content = {
        "resources": {"worker_threads": 2}, 
        "ENV_VAR_MAP": env_map_in_config
    }
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f: json.dump(config_content, f)

    with mock.patch.dict(os.environ, {"WORKER_COUNT": "10"}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("resources.worker_threads") == 10
    
    with mock.patch.dict(os.environ, {"WORKER_COUNT": "not_an_int"}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("resources.worker_threads") == "not_an_int"

    with mock.patch.dict(os.environ, {"WORKER_COUNT": ""}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("resources.worker_threads") == ""


def test_env_variable_not_in_map_is_ignored(temp_config_dir, env_var_map_config): # ConfigManager and CONFIG_FILE_NAME were already removed
    """Test that environment variables not in _env_var_map are ignored."""
    env_map_in_config = {"logging.level": "MY_APP_LOG_LEVEL"}
    current_config_content = env_var_map_config.copy()
    current_config_content["ENV_VAR_MAP"] = env_map_in_config
    
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f:
        json.dump(current_config_content, f)

    with mock.patch.dict(os.environ, {
        "MY_APP_LOG_LEVEL": "ENV_TRACE", 
        "UNRELATED_ENV_VAR": "should_be_ignored"
    }):
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("logging.level") == "ENV_TRACE"
        assert cm.get_config("UNRELATED_ENV_VAR") is None 
        assert cm.get_config("database.host") == env_var_map_config["database"]["host"]


def test_empty_env_var_map_in_config(temp_config_dir, create_base_config_file, base_config_content): # ConfigManager and CONFIG_FILE_NAME were already removed
    """Test behavior when ENV_VAR_MAP in config is empty or not present."""
    config_file_path = temp_config_dir / "config.json" # create_base_config_file uses this

    # Case 1: ENV_VAR_MAP is empty in config
    config_with_empty_map = base_config_content.copy()
    config_with_empty_map["ENV_VAR_MAP"] = {}
    
    with open(config_file_path, 'w') as f: json.dump(config_with_empty_map, f)

    with mock.patch.dict(os.environ, {"SOME_ENV_VAR": "some_value"}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("logging_level") == base_config_content["logging_level"]

    # Case 2: ENV_VAR_MAP key is not present (base_config_content does not have it)
    with open(config_file_path, 'w') as f: json.dump(base_config_content, f) # Recreate base
    with mock.patch.dict(os.environ, {"APP_LOGGING_LEVEL": "ENV_VAL"}):
        # reset_config_manager_singleton() # Handled by autouse
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("logging_level") == base_config_content["logging_level"]


def test_special_characters_in_env_var_values(temp_config_dir): # ConfigManager and CONFIG_FILE_NAME were already removed
    """Test that special characters in environment variable values are handled as strings."""
    env_map_in_config = {"service_details.connection_string": "SPECIAL_VAL_ENV"}
    config_content = {
        "service_details": {"connection_string": "file_default_conn_str"},
        "ENV_VAR_MAP": env_map_in_config
    }
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f: json.dump(config_content, f)

    special_value = "user:pass@host:port/db?opt=1&flag=true#frag"
    with mock.patch.dict(os.environ, {"SPECIAL_VAL_ENV": special_value}):
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("service_details.connection_string") == special_value

def test_logging_of_env_var_overrides(temp_config_dir, caplog): # ConfigManager, CONFIG_FILE_NAME, logger were already removed/handled
    """Test that successful environment variable overrides are logged at INFO level."""
    from config_manager.config_manager import logger # Import logger directly if needed
    logger.setLevel("INFO")
    env_map_in_config = {"logging.level": "LOG_LEVEL_VIA_ENV"}
    config_content = {
        "logging": {"level": "FILE_DEFAULT"},
        "ENV_VAR_MAP": env_map_in_config
    }
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f: json.dump(config_content, f)

    with mock.patch.dict(os.environ, {"LOG_LEVEL_VIA_ENV": "ENV_OVERRIDE_DEBUG"}):
        cm = ConfigManager(config_dir=str(temp_config_dir))
        cm.get_config("logging.level") # Ensure the config is accessed to trigger logging
        
    expected_log_msg = "Configuration 'logging.level' overridden by environment variable 'LOG_LEVEL_VIA_ENV' with value 'ENV_OVERRIDE_DEBUG'."
    assert expected_log_msg in caplog.text
    assert any(record.levelname == "INFO" and expected_log_msg in record.message for record in caplog.records)