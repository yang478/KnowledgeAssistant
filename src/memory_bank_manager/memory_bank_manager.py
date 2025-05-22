# -*- coding: utf-8 -*-
"""
MemoryBankManager Facade 类，统一处理所有与记忆库相关的操作请求。
"""
import os # For __main__ example path checking
from typing import Any, Dict, Optional

from src.config_manager.config_manager import ConfigManager
from src.monitoring_manager.monitoring_manager import MonitoringManager

from .assessment_data_manager import AssessmentDataManager
from .backup_manager import BackupManager
from .db_utils import DBUtil
from .knowledge_point_manager import KnowledgePointManager
from .learning_context_manager import LearningContextManager
from .resource_manager import ResourceManager


class MemoryBankManager:
    """
    MemoryBankManager Facade 类。
    提供一个统一的接口来访问记忆库的各种功能。
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        config_manager: Optional[ConfigManager] = None,
        monitoring_manager: Optional[MonitoringManager] = None,
    ):
        """
        初始化 MemoryBankManager Facade。

        Args:
            db_path (Optional[str]): SQLite 数据库文件的路径。
                                     如果为 None，则从 ConfigManager 获取。
            config_manager (Optional[ConfigManager]): 配置管理器实例。
                                                    如果为 None，则会创建一个新的实例。
            monitoring_manager (Optional[MonitoringManager]): 监控管理器实例。
                                                        如果为 None，则会创建一个新的实例。
        """
        if config_manager is None:
            self.config_manager = ConfigManager()
            # Ensure default config is loaded if not already
            if not self.config_manager.get_config():
                 self.config_manager.load_config() # Load default if not loaded
        else:
            self.config_manager = config_manager

        if monitoring_manager is None:
            self.monitoring_manager = MonitoringManager(
                config_manager=self.config_manager
            )
        else:
            self.monitoring_manager = monitoring_manager

        if db_path is None:
            db_settings = self.config_manager.get_config("DATABASE_SETTINGS") # Changed get_setting to get_config
            if not db_settings or not isinstance(db_settings, dict) or not db_settings.get("db_path"):
                # Use log_error as log_critical is not defined in MonitoringManager
                self.monitoring_manager.log_error("Database path not found in configuration.", context={"DATABASE_SETTINGS": db_settings})
                raise ValueError("Database path must be provided or configured in DATABASE_SETTINGS.")
            self.db_path = db_settings["db_path"]
        else:
            self.db_path = db_path
        
        self.monitoring_manager.log_info(f"MemoryBankManager initializing with DB path: {self.db_path}")

        self.db_util = DBUtil(db_path=self.db_path, monitoring_manager=self.monitoring_manager)
        # DBUtil's __init__ method now handles its own initialization using _initialize_database.
        # The logic for finding schema.sql and calling init_db here is no longer needed.

        self.knowledge_point_manager = KnowledgePointManager(
            db_util=self.db_util, monitoring_manager=self.monitoring_manager
        )
        self.learning_context_manager = LearningContextManager(
            db_util=self.db_util, monitoring_manager=self.monitoring_manager
        )
        self.assessment_data_manager = AssessmentDataManager(
            db_util=self.db_util, monitoring_manager=self.monitoring_manager
        )
        self.resource_manager = ResourceManager(
            db_util=self.db_util, monitoring_manager=self.monitoring_manager
        )
        self.backup_manager = BackupManager(
            db_util=self.db_util,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
        )
        
        self.operation_mapping = {
            # KnowledgePointManager operations
            "create_kp": self.knowledge_point_manager.save_knowledge_point, # Corrected: Was create_knowledge_point
            "get_kp": self.knowledge_point_manager.get_knowledge_point,
            "update_kp": self.knowledge_point_manager.update_knowledge_point,
            "delete_kp": self.knowledge_point_manager.delete_knowledge_point,
            "search_kps": self.knowledge_point_manager.search_knowledge_points,
            "get_all_kps": self.knowledge_point_manager.get_all_syllabus_topics, # Corrected: Was get_all_knowledge_points, maps to get_all_syllabus_topics
            # "get_related_kps": self.knowledge_point_manager.get_related_knowledge_points, # Method does not exist in KPM
            # "add_kp_relation": self.knowledge_point_manager.add_knowledge_point_relation, # Method does not exist in KPM
            # "remove_kp_relation": self.knowledge_point_manager.remove_knowledge_point_relation, # Method does not exist in KPM
            "get_kp_history": self.knowledge_point_manager.get_historical_version, # Corrected: Was get_knowledge_point_history, maps to get_historical_version
            # "get_kps_by_tags": self.knowledge_point_manager.get_knowledge_points_by_tags, # Method does not exist in KPM
            # "get_kps_by_status": self.knowledge_point_manager.get_knowledge_points_by_status, # Method does not exist in KPM
            # "get_kps_for_review": self.knowledge_point_manager.get_knowledge_points_for_review, # Method does not exist in KPM
            # "batch_update_kps_status": self.knowledge_point_manager.batch_update_kps_status, # Method does not exist in KPM
            # "get_kp_dependencies": self.knowledge_point_manager.get_knowledge_point_dependencies, # Method does not exist in KPM
            # "get_kp_dependents": self.knowledge_point_manager.get_knowledge_point_dependents, # Method does not exist in KPM
            # "get_all_tags": self.knowledge_point_manager.get_all_tags, # Method does not exist in KPM
            # "get_all_categories": self.knowledge_point_manager.get_all_categories, # Method does not exist in KPM

            # LearningContextManager operations
            "get_lc": self.learning_context_manager.get_learning_context,
            "save_lc": self.learning_context_manager.save_learning_context,
            "update_progress": self.learning_context_manager.update_progress,
            "get_reviewable_kps": self.learning_context_manager.get_reviewable_knowledge_points,

            # AssessmentDataManager operations
            "save_al": self.assessment_data_manager.save_assessment_log,
            "save_ga": self.assessment_data_manager.save_generated_assessment,
            "get_ga": self.assessment_data_manager.get_generated_assessment,
            "get_al": self.assessment_data_manager.get_assessment_log,

            # ResourceManager operations
            "add_rl": self.resource_manager.add_resource_link,
            "get_rls_for_kp": self.resource_manager.get_resource_links_for_kp,
            "delete_rl": self.resource_manager.delete_resource_link,

            # BackupManager operations
            "rec_bm": self.backup_manager.record_backup_metadata,
            "get_last_bi": self.backup_manager.get_last_backup_info,
            "perform_backup": self.backup_manager.perform_backup,
        }
        self.monitoring_manager.log_info("MemoryBankManager initialized successfully with all sub-managers.")


    def process_request(self, operation: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理传入的请求，将其路由到适当的管理器和方法。

        Args:
            operation (str): 要执行的操作的名称 (例如, "create_kp", "get_lc")。
            payload (Optional[Dict[str, Any]]): 操作所需的参数。默认为 None。

        Returns:
            Dict[str, Any]: 操作的结果。
                           通常是 {"status": "success", "data": ...} 或
                           {"status": "error", "message": "..."}。
        """
        if payload is None:
            payload = {} # Ensure payload is always a dict

        self.monitoring_manager.log_info(f"Processing request for operation: {operation} with payload: {payload}")
        
        handler_method = self.operation_mapping.get(operation)

        if handler_method:
            try:
                result = handler_method(payload) # All mapped methods should accept a payload dict
                self.monitoring_manager.log_info(
                    f"Operation {operation} completed with status: {result.get('status')}"
                )
                return result
            except Exception as e:
                self.monitoring_manager.log_error(
                    f"Error during operation {operation} with payload {payload}: {e}", exc_info=True
                )
                return {"status": "error", "message": f"An unexpected error occurred processing {operation}: {str(e)}"}
        else:
            self.monitoring_manager.log_warning(f"Unknown operation requested: {operation}")
            return {"status": "error", "message": f"Unknown operation: {operation}"}

    def close_db_connection(self):
        """关闭数据库连接。"""
        self.db_util.close_connection()
        self.monitoring_manager.log_info("MemoryBankManager: Database connection closed.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_db_connection()

# Example Usage (for testing or direct script execution):
if __name__ == "__main__":
    _config_file_path = "config.json" 
    _config = ConfigManager(config_file_path=_config_file_path)
    
    # Example: Check if essential settings are present, otherwise create default config
    db_settings = _config.get_config("DATABASE_SETTINGS", {})
    backup_settings = _config.get_config("BACKUP_SETTINGS", {})
    
    if not db_settings.get("db_path") or not backup_settings.get("backup_directory"):
        print(f"Config file '{_config_file_path}' not found or incomplete. Creating a default one for example.")
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        default_schema_path = os.path.join(current_dir, "schema.sql")
        default_db_path = os.path.join(current_dir, "memory_bank_main_example.db") # Place example DB in src folder
        default_backup_dir = os.path.join(current_dir, "backups_main_example/")

        # Create schema file if it doesn't exist (simplified version)
        if not os.path.exists(default_schema_path):
             try:
                 with open(default_schema_path, "w") as sf:
                     # Simplified schema for example
                     sf.write("""
CREATE TABLE IF NOT EXISTS knowledge_points (id TEXT PRIMARY KEY, title TEXT);
CREATE TABLE IF NOT EXISTS app_metadata ( key TEXT PRIMARY KEY, value TEXT );
INSERT OR IGNORE INTO app_metadata (key, value) VALUES ('db_version', '1.1');
                     """)
                 print(f"Created default schema file at {default_schema_path}")
             except IOError as e:
                 print(f"Could not create default schema file: {e}")

        _config.config = {
            "LOGGING_SETTINGS": {"log_level": "INFO", "log_file": "memory_bank.log", "log_to_console": True},
            "DATABASE_SETTINGS": {"db_path": default_db_path, "schema_file": default_schema_path},
            "BACKUP_SETTINGS": {"backup_directory": default_backup_dir, "max_backups": 5},
            "LLM_SETTINGS": {"provider": "ollama", "model": "mistral"},
            "APP_SETTINGS": {"default_mode": "learner"}
        }
        try:
            _config.save_config() 
            print(f"Saved default config to '{_config_file_path}' for example.")
        except Exception as e:
            print(f"Could not save default config for example: {e}")

    monitor = MonitoringManager(config_manager=_config)
    
    try:
        with MemoryBankManager(config_manager=_config, monitoring_manager=monitor) as mbm:
            monitor.log_info("MemoryBankManager instance created for __main__ example.")
            kp_payload = {
                "title": "Test KP Main", "content": "Content for main test.", "category": "Main Test",
                "tags": ["main", "example"], "status": "new", "priority": 1
            }
            create_result = mbm.process_request("create_kp", kp_payload)
            monitor.log_info(f"Create KP result: {create_result}")

            if create_result.get("status") == "success":
                kp_id = create_result.get("kp_id")
                get_result = mbm.process_request("get_kp", {"id": kp_id})
                monitor.log_info(f"Get KP result: {get_result}")

            backup_result = mbm.process_request("perform_backup", {"trigger_event": "manual_example_main"})
            monitor.log_info(f"Perform Backup result: {backup_result}")
            
            last_backup_info = mbm.process_request("get_last_bi") 
            monitor.log_info(f"Last Backup Info: {last_backup_info}")
            
            all_kps = mbm.process_request("get_all_kps")
            monitor.log_info(f"All KPs: {len(all_kps.get('data',[]))} found.")

    except ValueError as ve:
        monitor.log_critical(f"Initialization error in __main__ example: {ve}", exc_info=True) # Changed to critical
    except Exception as e:
        monitor.log_critical(f"An error occurred in the __main__ example: {e}", exc_info=True) # Changed to critical
