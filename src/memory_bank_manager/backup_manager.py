# -*- coding: utf-8 -*-
"""
备份管理器 (BackupManager) 负责处理与数据库备份相关的元数据。
"""
import os
import shutil # For actual backup operations if extended
import uuid
from datetime import datetime # For calculating duration
from typing import Any, Dict, Optional

from src.config_manager.config_manager import ConfigManager
from src.monitoring_manager.monitoring_manager import MonitoringManager

from .db_utils import DBUtil


class BackupManager:
    """管理备份元数据的所有操作。"""

    def __init__(
        self,
        db_util: DBUtil,
        config_manager: ConfigManager,
        monitoring_manager: MonitoringManager,
    ):
        """
        初始化 BackupManager。

        Args:
            db_util (DBUtil): 数据库工具实例。
            config_manager (ConfigManager): 配置管理器实例。
            monitoring_manager (MonitoringManager): 监控管理器实例。
        """
        self.db_util = db_util
        self.config_manager = config_manager
        self.monitoring_manager = monitoring_manager

    def record_backup_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        记录备份操作的元数据。
        输入: {
            "backup_id": "..." (可选, 否则自动生成),
            "timestamp": "YYYY-MM-DDTHH:MM:SSZ" (可选),
            "size_bytes": ..., "status": "success/failed/pending",
            "trigger_event": "manual/scheduled", "path": "/path/to/backup.db",
            "message": "...", "duration_seconds": ...
        }
        输出: {"status": "success", "backup_id": "..."} 或 {"status": "error", "message": "..."}
        """
        backup_id = payload.get("backup_id", str(uuid.uuid4()))
        timestamp = payload.get("timestamp", self.db_util.get_current_timestamp_iso())
        status = payload.get("status")
        path = payload.get("path")

        if not status or not path:
            return {"status": "error", "message": "status and path are required."}
        
        if status not in ["success", "failed", "pending"]:
            return {"status": "error", "message": "Invalid status value. Must be one of 'success', 'failed', 'pending'."}

        query = """
        INSERT INTO backup_metadata
        (backup_id, timestamp, size_bytes, status, trigger_event, path, message, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            backup_id,
            timestamp,
            payload.get("size_bytes"),
            status,
            payload.get("trigger_event"),
            path,
            payload.get("message"),
            payload.get("duration_seconds"),
        )

        success = self.db_util.execute_query(query, params, is_write=True)

        if success:
            self.monitoring_manager.log_info(
                f"Backup metadata recorded for ID {backup_id}, status: {status}."
            )
            return {"status": "success", "backup_id": backup_id}
        else:
            return {
                "status": "error",
                "message": f"Failed to record backup metadata for ID {backup_id}.",
            }

    def get_last_backup_info(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取最新的成功备份信息。
        输出: {"status": "success", "data": {...}} 或 {"status": "not_found"} 或 {"status": "error"}
        """
        # payload is not used for now, but kept for interface consistency
        query = "SELECT * FROM backup_metadata WHERE status = 'success' ORDER BY timestamp DESC LIMIT 1"
        backup_info = self.db_util.execute_query(query, fetch_one=True)

        if backup_info and isinstance(backup_info, dict):
            return {"status": "success", "data": backup_info}
        
        # Check if the query itself failed or if simply no successful backups exist
        # A more robust way would be for execute_query to distinguish between "no rows" and "query error"
        # For now, we assume if backup_info is None, it could be either.
        # Let's try to count successful backups to be more specific.
        count_query = "SELECT COUNT(*) as count FROM backup_metadata WHERE status = 'success'"
        count_result = self.db_util.execute_query(count_query, fetch_one=True)

        if count_result and isinstance(count_result, dict) and count_result.get("count", 0) == 0:
            return {"status": "not_found", "message": "No successful backups found."}
        elif backup_info is None: # Indicates a potential query error if count wasn't 0 or count_result was None
             self.monitoring_manager.log_error("Failed to retrieve last backup information or count of backups.")
             return {"status": "error", "message": "Failed to retrieve last backup information."}
        else: # Should not be reached if backup_info was a dict, but as a fallback
            self.monitoring_manager.log_warning("get_last_backup_info returned unexpected data.")
            return {"status": "not_found", "message": "No successful backup information available or error."}
def perform_backup(self, trigger_event: str = "manual") -> Dict[str, Any]:
        """
        实际执行数据库备份操作，并记录元数据。
        注意: 此方法会直接操作文件系统。

        Args:
            trigger_event (str): 触发备份的事件 ("manual" 或 "scheduled").

        Returns:
            Dict[str, Any]: 包含备份操作结果的字典。
        """
        backup_id = str(uuid.uuid4())
        start_time_dt = datetime.now() # For duration calculation
        start_time_iso = self.db_util.convert_datetime_to_iso(start_time_dt)

        db_path = self.db_util.db_path
        # Ensure db_path is a string and not None
        if not db_path or not isinstance(db_path, str):
            self.monitoring_manager.log_error(f"Database path is not configured or invalid: {db_path}")
            return {"status": "error", "message": "Database path not configured."}

        backup_config = self.config_manager.get_setting("BACKUP_SETTINGS")
        if not backup_config or not isinstance(backup_config, dict) or not backup_config.get("backup_directory"):
            self.monitoring_manager.log_error("Backup directory not configured in BACKUP_SETTINGS.")
            return {"status": "error", "message": "Backup directory not configured."}
        
        backup_dir = backup_config["backup_directory"]
        
        if not os.path.exists(db_path):
            self.monitoring_manager.log_error(f"Database file not found at {db_path} for backup.")
            return {"status": "error", "message": f"Database file not found at {db_path}."}

        try:
            os.makedirs(backup_dir, exist_ok=True)
            backup_filename = f"backup_{self.db_util.convert_datetime_to_filename_safe(start_time_dt)}_{backup_id}.db"
            backup_file_path = os.path.join(backup_dir, backup_filename)

            # Perform the actual backup (copying the file)
            shutil.copy2(db_path, backup_file_path)
            self.monitoring_manager.log_info(f"Database backup created: {backup_file_path}")

            # Get backup size
            size_bytes = os.path.getsize(backup_file_path)
            end_time_dt = datetime.now()
            duration_seconds = (end_time_dt - start_time_dt).total_seconds()

            metadata_payload = {
                "backup_id": backup_id,
                "timestamp": start_time_iso, # Use start time as the backup timestamp
                "size_bytes": size_bytes,
                "status": "success",
                "trigger_event": trigger_event,
                "path": backup_file_path,
                "message": "Backup completed successfully.",
                "duration_seconds": round(duration_seconds, 2)
            }
            self.record_backup_metadata(metadata_payload)
            return {"status": "success", "backup_id": backup_id, "path": backup_file_path}

        except Exception as e:
            self.monitoring_manager.log_error(f"Backup failed: {e}", exc_info=True)
            end_time_dt = datetime.now()
            duration_seconds = (end_time_dt - start_time_dt).total_seconds()
            
            # Try to record failed backup attempt
            metadata_payload = {
                "backup_id": backup_id,
                "timestamp": start_time_iso,
                "status": "failed",
                "trigger_event": trigger_event,
                "path": db_path, # Path might be the original if copy failed early
                "message": f"Backup failed: {str(e)}",
                "duration_seconds": round(duration_seconds, 2)
            }
            self.record_backup_metadata(metadata_payload)
            return {"status": "error", "message": f"Backup failed: {e}"}