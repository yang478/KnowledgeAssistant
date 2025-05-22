# -*- coding: utf-8 -*-
"""配置管理器 (ConfigManager) 的主实现文件。

包含 ConfigManager 类，该类封装了从不同来源（如文件、环境变量）
加载配置、合并配置以及提供统一接口供其他模块访问配置项等核心功能。
"""
import copy  # For deep merging
import json
import logging
import os

# Configure basic logging for the ConfigManager itself
# Applications using ConfigManager should configure logging more robustly.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ConfigManager:
    _instance = None
    _config = None
    _config_dir = None  # Directory where config files are located
    _base_config_filename = "config.json"  # Base config file name
    _env_var_map = {  # Mapping from config key path (dot notation) to environment variable
        "llm.api_key": "LLM_API_KEY",
        "llm.api_endpoint": "LLM_API_ENDPOINT",
        # Add other sensitive or environment-specific keys here
        # Example: "database.password": "DB_PASSWORD"
    }

    def __new__(cls, config_dir=None):
        """
        Ensures a single instance of ConfigManager.
        If config_dir is provided, it sets/updates the config directory and reloads configuration
        if the directory is different from the current one or if it's the first instantiation.
        """
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            if config_dir:
                cls._config_dir = os.path.abspath(config_dir)
                logger.info(
                    f"ConfigManager initializing. Config directory explicitly set to: {cls._config_dir}"
                )
            else:
                # Default: Use current working directory if no config_dir is specified.
                # This makes it easier to test and more aligned with typical CLI tool behavior.
                cls._config_dir = os.path.abspath(os.getcwd())
                logger.info(
                    f"ConfigManager initializing. No config_dir provided, using current working directory as default: {cls._config_dir}"
                )
            cls._instance._load_config()  # Load initial config
        elif config_dir:
            # Instance exists. If config_dir is provided, check if it's different.
            new_abs_config_dir = os.path.abspath(config_dir)
            if cls._config_dir != new_abs_config_dir:
                logger.warning(
                    f"ConfigManager already initialized with config directory {cls._config_dir}. "
                    f"Ignoring attempt to re-initialize with different directory {new_abs_config_dir}. "
                    "Use reload_config() to explicitly change settings and reload."
                )
                # DO NOT change cls._config_dir or call _load_config() here when instance exists.
            # If config_dir is the same or not provided when instance exists, just return instance.
        # If instance exists and no config_dir is provided, just return the instance.
        return cls._instance

    @classmethod
    def _get_config_path(cls, filename):
        """Constructs the full path to a config file in the configured directory."""
        if not cls._config_dir:
            # This should ideally not happen as __new__ sets it, but log an error if it does.
            logger.error(
                "Config directory (_config_dir) is not set. Cannot determine config path."
            )
            # Attempt fallback using current working directory
            cls._config_dir = os.path.abspath(os.getcwd())
            logger.warning(f"Attempting fallback config directory (using CWD): {cls._config_dir}")
            if not cls._config_dir:  # Still failed
                raise RuntimeError("Failed to determine configuration directory.")
        return os.path.join(cls._config_dir, filename)

    @staticmethod
    def _deep_merge(source, destination):
        """
        Deeply merges source dict into destination dict. Modifies destination in place.
        """
        for key, value in source.items():
            if isinstance(value, dict):
                # Get node or create one
                node = destination.setdefault(key, {})
                if isinstance(node, dict):
                    ConfigManager._deep_merge(value, node)
                else:
                    # If destination key exists but is not a dict, overwrite it (source takes precedence)
                    destination[key] = copy.deepcopy(value)
            elif isinstance(value, list):
                # For lists, source replaces destination list entirely
                destination[key] = copy.deepcopy(value)
            else:
                destination[key] = (
                    value  # Assign value (handles simple types, None, etc.)
                )
        return destination

    def _load_config(self):
        """Loads configuration from base file, environment-specific file, and merges them."""
        base_config = {}
        env_config = {}

        # 1. Load base config file
        base_path = self._get_config_path(self._base_config_filename)
        try:
            with open(base_path, "r", encoding="utf-8") as f:
                base_config = json.load(f)
            logger.info(f"Loaded base config from {base_path}")
        except FileNotFoundError:
            logger.warning(
                f"Base config file not found at {base_path}. Starting with empty base config."
            )
            base_config = {}
        except json.JSONDecodeError as e:
            logger.error(
                f"Could not decode JSON from {base_path}: {e}. Using empty base config."
            )
            base_config = {}
        except (IOError, OSError) as e: # Catch PermissionError and other IO/OS errors
            logger.error(
                f"Permission denied while trying to read config file {base_path}: {e}. Using empty base config."
            )
            base_config = {}
        except Exception as e:
            logger.error(
                f"An unexpected generic error occurred loading base config from {base_path}: {e}. Using empty base config.",
                exc_info=True, # Keep exc_info for truly unexpected errors
            )
            base_config = {}

        # 2. Load environment-specific config file if APP_ENV is set
        app_env = os.environ.get("APP_ENV")
        env_config_filename = None  # Initialize
        if app_env:
            env_config_filename = f"config.{app_env}.json"
            env_config_path = self._get_config_path(env_config_filename)
            try:
                with open(env_config_path, "r", encoding="utf-8") as f:
                    env_config = json.load(f)
                logger.info(
                    f"Loaded environment config from {env_config_path} for APP_ENV='{app_env}'"
                )
            except FileNotFoundError:
                logger.info(
                    f"Environment-specific config file not found at {env_config_path}. Using base/default config only for file loading."
                )
                env_config = {}
            except json.JSONDecodeError as e:
                logger.error(
                    f"Could not decode JSON from {env_config_path}: {e}. Ignoring environment-specific config file."
                )
                env_config = {}
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred loading environment config from {env_config_path}: {e}. Ignoring environment-specific config file.",
                    exc_info=True,
                )
                env_config = {}
        else:
            logger.info(
                "APP_ENV environment variable not set. No environment-specific config file loaded."
            )
            env_config = {}

        # 3. Merge configurations (environment overrides base, deep merge)
        # Start with a deep copy of base, then merge env_config into it
        merged_config = copy.deepcopy(base_config)
        self._deep_merge(env_config, merged_config)

        self.__class__._config = merged_config

        # Update _env_var_map if "ENV_VAR_MAP" is present in the loaded configuration
        if "ENV_VAR_MAP" in merged_config and isinstance(merged_config["ENV_VAR_MAP"], dict):
            # Decide on replacement or merge strategy. For now, let's assume replacement
            # as tests seem to imply providing the full map.
            # A more robust approach might merge with the class default or provide an option.
            self.__class__._env_var_map = merged_config["ENV_VAR_MAP"]
            logger.info(f"Updated _env_var_map from configuration file. New map: {self.__class__._env_var_map}")
        # else:
            # If not in config, retain the class-defined _env_var_map
            # logger.info(f"No 'ENV_VAR_MAP' found in loaded config, using class default: {self.__class__._env_var_map}")


        logger.info(
            f"Configuration loaded. APP_ENV='{app_env}'. Priority: Env Vars > Env File ('{env_config_filename}' if used) > Base File ('{self._base_config_filename}')."
        )

    def reload_config(self, config_dir=None, base_filename=None, app_env_override=None):
        """
        Reloads the configuration. Optionally allows changing the config directory,
        base filename, or overriding the APP_ENV for this load.

        WARNING: Modifying config_dir here affects the singleton state for all subsequent
        uses of ConfigManager. This is primarily intended for testing or specific
        dynamic scenarios and should be used with caution.
        """
        logger.info("Reloading configuration...")
        original_env = os.environ.get("APP_ENV")
        if app_env_override:
            os.environ["APP_ENV"] = app_env_override
            logger.info(
                f"Temporarily overriding APP_ENV to '{app_env_override}' for reload."
            )

        # Handle potential change in config directory (affects singleton state)
        if config_dir:
            new_config_dir = os.path.abspath(config_dir)
            if new_config_dir != self.__class__._config_dir:
                self.__class__._config_dir = new_config_dir
                logger.warning(
                    f"Configuration directory permanently changed for singleton instance to: {self.__class__._config_dir}"
                )
            else:
                logger.info(
                    f"Configuration directory remains: {self.__class__._config_dir}"
                )

        # Handle potential change in base filename (affects singleton state)
        if base_filename:
            if base_filename != self.__class__._base_config_filename:
                self.__class__._base_config_filename = base_filename
                logger.info(
                    f"Base configuration filename changed to: {self.__class__._base_config_filename}"
                )
            else:
                logger.info(
                    f"Base configuration filename remains: {self.__class__._base_config_filename}"
                )

        self._load_config()  # Perform the reload with potentially new settings

        # Restore original APP_ENV if it was overridden
        if app_env_override:
            if original_env is None:
                del os.environ["APP_ENV"]  # Remove if it didn't exist before
            else:
                os.environ["APP_ENV"] = original_env  # Restore original value
            logger.info(f"Restored APP_ENV to '{original_env}'.")

    def get_config(self, key, default_value=None):
        """
        Retrieves a configuration value, prioritizing environment variables mapped in _env_var_map,
        then looking in the loaded configuration using dot notation for nested keys.

        Args:
            key (str): The configuration key using dot notation (e.g., "llm.api_key").
            default_value: The value to return if the key is not found. Defaults to None.

        Returns:
            The configuration value if found, otherwise default_value.
        """
        # 1. Check environment variables first for mapped keys
        # The key provided to get_config() is the config key (e.g., "database.host")
        # We need to check if this key exists in our _env_var_map
        env_value = None
        found_in_env = False
        if self.__class__._env_var_map and key in self.__class__._env_var_map:
            env_var_name = self.__class__._env_var_map[key]
            env_value_str = os.environ.get(env_var_name)
            if env_value_str is not None:
                # Log the override attempt *before* conversion
                logger.info(
                    f"Configuration '{key}' overridden by environment variable '{env_var_name}' with value '{env_value_str}'."
                )
                # Attempt type conversion based on common patterns
                if env_value_str.lower() == 'true':
                    env_value = True
                elif env_value_str.lower() == 'false':
                    env_value = False
                else:
                    try:
                        # Try converting to int
                        env_value = int(env_value_str)
                    except ValueError:
                        try:
                            # Try converting to float
                            env_value = float(env_value_str)
                        except ValueError:
                            # Keep as string if other conversions fail
                            env_value = env_value_str
                found_in_env = True

        if found_in_env:
             return env_value # Return potentially type-converted value

        # 2. Handle empty key explicitly (before splitting)
        if key == "":
             logger.debug("Requested config with empty key string.")
             # If key is empty:
             # 1. If a default_value is provided, return it.
             # 2. Else, if config is loaded, return the whole config.
             # 3. Else (config not loaded, no default), log error and return None.
             if default_value is not None:
                 logger.debug(f"Returning default value ({default_value}) for empty key.")
                 return default_value
             elif self.__class__._config is not None:
                logger.debug("Empty key requested and no default, returning entire loaded configuration.")
                return self.__class__._config
             else:
                logger.error("Configuration is not loaded, empty key requested, and no default value provided. Returning None.")
                return None

        # 3. If not found in env vars or key not mapped, check loaded config
        if self.__class__._config is None:
            logger.warning(
                "Config accessed before initial load or after a load failure. Attempting reload."
            )
            self._load_config()
            if self.__class__._config is None:  # Still None after trying to load
                logger.error(
                    f"Configuration is not loaded. Cannot retrieve key '{key}'."
                )
                if default_value is not None:
                    return default_value
                else:
                    # Raising KeyError might be too disruptive; log error and return None or default.
                    # Let's return default_value (which is None if not provided).
                    logger.error(
                        f"Returning default value ({default_value}) for key '{key}' due to missing config."
                    )
                    return default_value

        # 3. Traverse the loaded config dictionary using dot notation
        keys = key.split(".")
        value = self.__class__._config
        current_key_path = []

        try:
            for k in keys:
                current_key_path.append(k)
                if isinstance(value, dict):
                    value = value[k]
                # Add handling for list indices if needed in the future:
                # elif isinstance(value, list) and k.isdigit():
                #     value = value[int(k)]
                else:
                    # Trying to access a key on a non-dictionary (or index a non-list)
                    raise KeyError(
                        f"Intermediate key '{'.'.join(current_key_path[:-1])}' does not contain object for key '{k}'"
                    )
            logger.debug(
                f"Retrieved config key '{key}' from loaded configuration files."
            )
            return value
        except (KeyError, IndexError, TypeError) as e:
            # KeyError if key not found, IndexError for list index, TypeError if trying to index non-dict/list
            logger.debug(
                f"Configuration key '{key}' not found in loaded files or structure mismatch ({e})."
            )
            if default_value is not None:
                logger.debug(
                    f"Returning default value ({default_value}) for key '{key}'."
                )
                return default_value
            else:
                # Instead of raising KeyError, log an error and return None.
                # Raising errors here can make application startup brittle if optional config is missing.
                # Log level changed to warning as this is a common scenario
                logger.warning(
                    f"Configuration key '{key}' not found and no default value provided. Returning None."
                )
                return None


# Example Usage (can be removed or kept for module-level testing)
if __name__ == "__main__":
    # Example: Assume project structure where config.json is in the root
    # and this script is in src/config_manager/
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # Create dummy config files for testing
    if not os.path.exists(project_root):
        os.makedirs(project_root)  # Should exist, but safeguard
    with open(os.path.join(project_root, "config.json"), "w") as f:
        json.dump(
            {
                "llm": {"default_model": "base-model"},
                "logging": {"level": "INFO"},
                "feature_flags": {"new_ui": False},
            },
            f,
            indent=2,
        )
    with open(os.path.join(project_root, "config.development.json"), "w") as f:
        json.dump(
            {"logging": {"level": "DEBUG"}, "database": {"url": "dev_db_url"}},
            f,
            indent=2,
        )

    # Set environment variables for testing
    os.environ["LLM_API_KEY"] = "env_key_123"
    os.environ["APP_ENV"] = "development"

    print("\n--- Initializing ConfigManager ---")
    config_manager = ConfigManager()  # Uses default path logic

    print("\n--- Testing Configuration Retrieval ---")
    # Test environment variable override
    api_key = config_manager.get_config("llm.api_key")
    print(f"LLM API Key (from env var LLM_API_KEY): {api_key}")

    # Test environment-specific config override (deep merge check)
    log_level = config_manager.get_config("logging.level", "WARNING")  # Default WARNING
    print(f"Log Level (from config.development.json): {log_level}")

    # Test base config value not overridden
    default_model = config_manager.get_config("llm.default_model")
    print(f"Default LLM Model (from config.json): {default_model}")

    # Test value only in env-specific config
    db_url = config_manager.get_config("database.url")
    print(f"DB URL (from config.development.json): {db_url}")

    # Test default value for non-existent key
    non_existent = config_manager.get_config("server.port", 8080)
    print(f"Server Port (default): {non_existent}")

    # Test key not found (should return None and log error)
    another_non_existent = config_manager.get_config("non.existent.key")
    print(f"Non-existent key (should be None): {another_non_existent}")

    # Test feature flag from base
    feature_flag = config_manager.get_config("feature_flags.new_ui")
    print(f"Feature Flag (from config.json): {feature_flag}")

    # Clean up dummy files and env vars
    # os.remove(os.path.join(project_root, 'config.json'))
    # os.remove(os.path.join(project_root, 'config.development.json'))
    # del os.environ['LLM_API_KEY']
    # del os.environ['APP_ENV']
    print("\n--- Test Complete ---")
