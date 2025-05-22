"""Unit tests for ConfigManager - Configuration Loading aspects."""

import pytest
import json
import os
from unittest import mock

# ConfigManager and CONFIG_FILE_NAME are expected to be available via conftest.py
# but importing them explicitly can make the code clearer.
# However, to avoid potential import issues if conftest isn't fully processed first
# by all test runners in all contexts, we'll rely on pytest to inject them.
from config_manager.config_manager import ConfigManager

# Note: Fixtures like temp_config_dir, create_base_config_file, etc.,
# are automatically discovered from tests/config_manager_tests/conftest.py

def test_load_base_config_file_successfully(temp_config_dir, create_base_config_file, base_config_content):
    """Test loading a single valid base config.json file."""
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("database.host") == base_config_content["database"]["host"]
    assert cm.get_config("logging_level") == base_config_content["logging_level"]
    assert cm.get_config("feature_flags.new_dashboard") == base_config_content["feature_flags"]["new_dashboard"]

def test_load_env_specific_config_override(temp_config_dir, create_base_config_file, create_env_specific_config_file, base_config_content, env_specific_config_content):
    """Test loading and merging an environment-specific config file."""
    _, env_name = create_env_specific_config_file
    with mock.patch.dict(os.environ, {"APP_ENV": env_name}):
        cm = ConfigManager(config_dir=str(temp_config_dir))

        # Overridden values
        assert cm.get_config("database.host") == env_specific_config_content["database"]["host"]
        assert cm.get_config("database.port") == env_specific_config_content["database"]["port"]
        assert cm.get_config("logging_level") == env_specific_config_content["logging_level"]
        assert cm.get_config("feature_flags.new_dashboard") == env_specific_config_content["feature_flags"]["new_dashboard"]

        # Value from base config (not in env-specific)
        assert cm.get_config("database.user") == base_config_content["database"]["user"]
        assert cm.get_config("service_url") == base_config_content["service_url"]
        assert cm.get_config("feature_flags.alpha_feature") == base_config_content["feature_flags"]["alpha_feature"]

        # Value only in env-specific config
        assert cm.get_config("api_key") == env_specific_config_content["api_key"]
        assert cm.get_config("feature_flags.beta_feature") == env_specific_config_content["feature_flags"]["beta_feature"]

def test_deep_merge_logic(temp_config_dir):
    """Test the _deep_merge utility directly and indirectly via config loading."""
    base = {"a": 1, "b": {"c": 2, "d": 3}, "e": [1,2]}
    override = {"b": {"c": 4, "f": 5}, "e": [3,4], "g": 6}
    expected = {"a": 1, "b": {"c": 4, "d": 3, "f": 5}, "e": [3,4], "g": 6}
    
    # Corrected: merge override into base, then check base
    target_dict = base.copy()
    ConfigManager._deep_merge(override.copy(), target_dict)
    assert target_dict == expected

    # Indirect test via file loading
    base_file = temp_config_dir / "base.json"
    # Env specific file should be config.{app_env}.json
    override_file = temp_config_dir / "config.override.json"

    with open(base_file, 'w') as f: json.dump(base, f)
    with open(override_file, 'w') as f: json.dump(override, f)

    with mock.patch.dict(os.environ, {"APP_ENV": "override"}):
        original_config_file_name = ConfigManager._base_config_filename
        # Temporarily change CONFIG_FILE_NAME for this specific test
        # This is a bit of a hack; ideally, ConfigManager would allow specifying the base name
        ConfigManager._base_config_filename = "base.json"
        try:
            cm = ConfigManager(config_dir=str(temp_config_dir))
            assert cm._config == expected
        finally:
            ConfigManager._base_config_filename = original_config_file_name # Reset

def test_missing_base_config_file_logs_warning(temp_config_dir, caplog):
    """Test that a missing base config.json logs a warning and results in empty config."""
    base_config_path = temp_config_dir / "config.json"
    if base_config_path.exists():
        os.remove(base_config_path)

    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm._config == {} 
    assert f"Base config file not found at {str(base_config_path)}" in caplog.text
    assert "warning" in caplog.text.lower() 

def test_missing_env_specific_config_file_no_warning(temp_config_dir, create_base_config_file, caplog):
    """Test that a missing env-specific config file does not log error/warning (it's optional)."""
    with mock.patch.dict(os.environ, {"APP_ENV": "non_existent_env"}):
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("logging_level") == "INFO" 
        env_specific_path_str = str(temp_config_dir / f"{os.path.splitext("config.json")[0]}.non_existent_env.json")
        assert f"Config file not found at {env_specific_path_str}" not in caplog.text

def test_invalid_json_in_base_config_logs_error(temp_config_dir, create_invalid_json_file, caplog):
    """Test that invalid JSON in base config.json logs an error."""
    os.rename(create_invalid_json_file, temp_config_dir / "config.json")
    
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm._config == {} 
    assert f"Could not decode JSON from {str(temp_config_dir / "config.json")}" in caplog.text
    assert "error" in caplog.text.lower()

def test_invalid_json_in_env_specific_config_logs_error(temp_config_dir, create_base_config_file, create_invalid_json_file, caplog):
    """Test that invalid JSON in an environment-specific file logs an error and doesn't corrupt base config."""
    env_name = "bad_json_env"
    env_specific_invalid_path = temp_config_dir / f"{os.path.splitext("config.json")[0]}.{env_name}.json"
    os.rename(create_invalid_json_file, env_specific_invalid_path)

    with mock.patch.dict(os.environ, {"APP_ENV": env_name}):
        cm = ConfigManager(config_dir=str(temp_config_dir))
        assert cm.get_config("logging_level") == "INFO" 
        assert f"Could not decode JSON from {str(env_specific_invalid_path)}" in caplog.text
        assert "error" in caplog.text.lower()
        assert cm.get_config("database.host") == "localhost"

def test_config_dir_default_to_project_root(tmp_path, caplog):
    """Test ConfigManager uses project root if config_dir is None or not provided."""
    project_root_config_path = tmp_path / "config.json"
    project_root_content = {"project_root_key": "project_root_value"}
    with open(project_root_config_path, 'w') as f:
        json.dump(project_root_content, f)

    with mock.patch('os.getcwd', return_value=str(tmp_path)):
        # Test with config_dir=None
        # Need to import reset_config_manager_singleton or call it via ConfigManager if static/class method
        # Assuming reset_singleton_before_each_test fixture in conftest handles this
        cm_none_dir = ConfigManager(config_dir=None)
        assert cm_none_dir.get_config("project_root_key") == "project_root_value"
        assert str(tmp_path) in cm_none_dir._config_dir 

        # Test with no config_dir argument
        # reset_config_manager_singleton() # Handled by autouse fixture
        cm_no_arg = ConfigManager()
        assert cm_no_arg.get_config("project_root_key") == "project_root_value"
        assert str(tmp_path) in cm_no_arg._config_dir

def test_empty_json_file_handling(temp_config_dir, caplog):
    """Test handling of an empty JSON file (e.g., "{}")."""
    empty_json_path = temp_config_dir / "config.json"
    with open(empty_json_path, 'w') as f:
        f.write("{}") 

    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm._config == {} 
    assert f"Could not decode JSON from {str(empty_json_path)}" not in caplog.text 

    # Test with a file containing only whitespace (should be invalid JSON)
    # reset_config_manager_singleton() # Handled by autouse fixture
    caplog.clear()
    # whitespace_json_path = temp_config_dir / "whitespace.json" # Not needed
    os.rename(empty_json_path, temp_config_dir / "old_config.json")
    base_config_path_for_whitespace = temp_config_dir / "config.json"
    with open(base_config_path_for_whitespace, 'w') as f:
        f.write("   \n  \t  ")
    
    # Get the ConfigManager instance. Since reset_singleton_before_each_test ran,
    # this ConfigManager() call will initialize and load the whitespace file.
    # No, this is incorrect. The *first* cm = ConfigManager() in this test method (line 143)
    # already initialized the singleton for temp_config_dir.
    # Subsequent ConfigManager(config_dir=str(temp_config_dir)) calls with the *same* dir
    # will NOT reload if the instance already exists and _config_dir matches.
    # We need to use the existing instance 'cm' (or get it again) and call reload_config.

    # Get the singleton instance (it was 'cm' from the first part of the test)
    # or create/get it if it were a different test structure.
    # Since 'cm' is already configured with temp_config_dir, we use it.
    # If 'cm' was not available, we'd do:
    # cm_instance_for_reload = ConfigManager(config_dir=str(temp_config_dir))
    # For this test, 'cm' is the instance we want to operate on.
    
    cm.reload_config() # Force reload of the new whitespace config.json

    assert cm._config == {}, "Config should be empty after reloading whitespace file"
    assert f"Could not decode JSON from {str(base_config_path_for_whitespace)}" in caplog.text, \
        f"Expected decode error log not found. Log content: {caplog.text}"
    assert "error" in caplog.text.lower()

@mock.patch('builtins.open', new_callable=mock.mock_open)
def test_file_permission_error_on_load(mock_open_func, temp_config_dir, caplog):
    """Test handling of permission error when trying to open a config file."""
    mock_open_func.side_effect = PermissionError("Permission denied to read file")
    
    cm = ConfigManager(config_dir=str(temp_config_dir))
    
    expected_config_path = str(temp_config_dir / "config.json")
    assert f"Permission denied while trying to read config file {expected_config_path}" in caplog.text
    assert "error" in caplog.text.lower()
    assert cm._config == {}

def test_config_path_resolution_non_existent_dir(caplog):
    """Test behavior when a non-existent config_dir is provided."""
    non_existent_dir = "/path/to/a/very/unlikely/dir_for_config_test_xyz123"
    if os.path.exists(non_existent_dir): # pragma: no cover
        pytest.skip("Skipping test as the non_existent_dir surprisingly exists.")

    cm = ConfigManager(config_dir=non_existent_dir)
    
    expected_base_path = os.path.join(non_existent_dir, "config.json")
    assert f"Base config file not found at {expected_base_path}" in caplog.text
    assert cm._config == {}