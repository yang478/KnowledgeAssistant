"""Unit tests for ConfigManager - Singleton and Reload aspects."""

import pytest
import os
import json
from unittest import mock

# ConfigManager, CONFIG_FILE_NAME are expected to be available via conftest.py
from config_manager.config_manager import ConfigManager

# Note: Fixtures like temp_config_dir, create_base_config_file, base_config_content,
# reset_config_manager_singleton (via autouse fixture)
# are automatically discovered from tests/config_manager_tests/conftest.py

def test_singleton_behavior(temp_config_dir, create_base_config_file):
    """Test that ConfigManager behaves as a singleton."""
    cm1 = ConfigManager(config_dir=str(temp_config_dir))
    cm2 = ConfigManager(config_dir=str(temp_config_dir)) # Should return the same instance
    assert cm1 is cm2
    cm1.get_config("database.host") # Access to ensure it's loaded
    
    # Attempting to re-initialize with a different dir should ideally log a warning
    # and return the existing instance.
    # Current ConfigManager._initialize_config_if_needed checks _initialized_with_config_dir
    with mock.patch.object(ConfigManager, '_load_config', wraps=cm1._load_config) as mock_load:
        # Create a dummy other_dir for the test
        other_dir_path = temp_config_dir / "other_dir"
        other_dir_path.mkdir()
        cm3 = ConfigManager(config_dir=str(other_dir_path)) 
        # If singleton is enforced strictly and init dir matters, this might be a new instance or error
        # Based on current ConfigManager logic: if already initialized, it returns the existing one.
        # And _initialize_config_if_needed has a check for _initialized_with_config_dir
        # If config_dir is different, it WILL re-initialize if _instance is None or _config_dir doesn't match.
        # However, the singleton pattern means `ConfigManager()` call itself returns the same _instance.
        # The re-initialization logic is *within* `_initialize_config_if_needed`.
        # Let's test the scenario where it's called again with a *different* directory *after* first init.
        # The `reset_singleton_before_each_test` ensures `_instance` is None initially.
        # `cm1` initializes it. `cm2` gets the same.
        # `cm3` with a different dir:
        #   - `ConfigManager()` returns `cm1` (the singleton instance).
        #   - `cm1._initialize_config_if_needed(str(other_dir_path))` is called.
        #   - Inside, `if self._initialized_with_config_dir is not None and self._initialized_with_config_dir != config_dir_to_use:`
        #     This condition will be true. It logs a warning and *does not* reload.
        assert cm3 is cm1 # Should still be the same instance
        mock_load.assert_not_called() # Should not reload if already initialized and dir mismatches (logs warning)

    # To get a new instance, singleton must be reset
    # This is handled by the autouse fixture for subsequent tests, but for clarity here:
    from .conftest import reset_config_manager_singleton # Access helper from current directory's conftest
    reset_config_manager_singleton()
    cm_new = ConfigManager(config_dir=str(temp_config_dir))
    assert cm_new is not cm1 # After reset, it's a new instance

def test_reload_config_functionality(temp_config_dir, create_base_config_file, base_config_content):
    """Test the reload_config method."""
    cm = ConfigManager(config_dir=str(temp_config_dir))
    assert cm.get_config("logging_level") == "INFO"

    # Modify the config file on disk
    modified_content = base_config_content.copy()
    modified_content["logging_level"] = "SUPER_DEBUG"
    modified_content["new_key_after_reload"] = "found_me"
    
    config_file_path = temp_config_dir / "config.json"
    with open(config_file_path, 'w') as f:
        json.dump(modified_content, f)

    # ConfigManager should still have old config until reloaded
    assert cm.get_config("logging_level") == "INFO"
    assert cm.get_config("new_key_after_reload") is None

    cm.reload_config()
    assert cm.get_config("logging_level") == "SUPER_DEBUG"
    assert cm.get_config("new_key_after_reload") == "found_me"

def test_reload_config_when_config_dir_was_not_set_at_init(tmp_path):
    """Test reload_config when ConfigManager was initialized without a config_dir (using project root)."""
    project_root_config_path = tmp_path / "config.json"
    initial_content = {"initial_val": "first"}
    with open(project_root_config_path, 'w') as f: json.dump(initial_content, f)

    with mock.patch('os.getcwd', return_value=str(tmp_path)):
        cm = ConfigManager() # Initializes with project root
        assert cm.get_config("initial_val") == "first"

        modified_content = {"initial_val": "second", "reloaded_val": "yes"}
        with open(project_root_config_path, 'w') as f: json.dump(modified_content, f)
        
        cm.reload_config()
        assert cm.get_config("initial_val") == "second"
        assert cm.get_config("reloaded_val") == "yes"