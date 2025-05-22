# -*- coding: utf-8 -*-
"""更新与同步管理器 (UpdateManager) 的主实现文件。

包含 UpdateManager 类，该类封装了系统后台更新、数据同步（未来）
和自动备份等功能。它响应系统事件或定时调度，执行数据持久化、
一致性维护和版本管理等任务。
"""
import datetime
# src/update_manager/update_manager.py
import os
import shutil
import threading
import time
from typing import Any, Dict, Optional

from src.config_manager.config_manager import ConfigManager
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import MonitoringManager


class UpdateManager:
    """
    Handles background updates, data synchronization (future), and automatic backups.
    Listens to events and triggers actions based on configuration.
    """
    def __init__(self,
                 memory_bank_manager: MemoryBankManager,
                 config_manager: ConfigManager,
                 monitoring_manager: MonitoringManager):
        """
        Initializes the UpdateManager.

        Args:
            memory_bank_manager: Instance of MemoryBankManager.
            config_manager: Instance of ConfigManager.
            monitoring_manager: Instance of MonitoringManager.
        """
        self.memory_bank_manager = memory_bank_manager
        self.config_manager = config_manager
        self.monitoring_manager = monitoring_manager

        self.backup_config = self._load_backup_config()
        self.sync_config = self._load_sync_config() # For future use

        self.scheduler_thread = None
        self.stop_scheduler_event = threading.Event()

        if self.backup_config.get("enabled") and self.backup_config.get("automatic_scheduling_enabled"):
            self.start_scheduler()

        self.monitoring_manager.log_info("UpdateManager initialized.", context={"module": "UpdateManager"})

    def _load_backup_config(self) -> Dict:
        """Loads backup strategy configurations."""
        self.monitoring_manager.log_debug("Loading backup config.", context={"module": "UpdateManager"}) # Changed to log_debug
        return self.config_manager.get_config("backup", default_value={
            "enabled": self.config_manager.get_config("backup.enabled", False),
            "automatic_scheduling_enabled": self.config_manager.get_config("backup.automatic_scheduling_enabled", False),
            "strategy": self.config_manager.get_config("backup.strategy", "file_copy"),
            "frequency_hours": self.config_manager.get_config("backup.frequency_hours", 24),
            "target_directory": self.config_manager.get_config("backup.target_directory", "./backups"),
            "retention_count": self.config_manager.get_config("backup.retention_count", 5),
            "source_db_path": self.config_manager.get_config("backup.source_db_path", self.memory_bank_manager.db_path)
        })

    def _load_sync_config(self) -> Dict:
        """Loads data synchronization configurations (for future use)."""
        self.monitoring_manager.log_debug("Loading sync config.", context={"module": "UpdateManager"}) # Changed to log_debug
        # Placeholder
        return self.config_manager.get_config("sync", default_value={"enabled": False})

    def trigger_backup(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Triggers a data backup based on the event and configuration.
        This method now initiates the backup asynchronously.

        Args:
            event: The event triggering the backup (e.g., "manual_trigger", "auto_schedule").
            payload: Optional context for the event.

        Returns:
            A dictionary indicating the status of the backup initiation.
        """
        self.monitoring_manager.log_info(f"Backup trigger received. Event: {event}", context={"module": "UpdateManager", "payload": payload})

        if not self.backup_config.get("enabled", False):
            self.monitoring_manager.log_info("Backup is disabled in configuration.", context={"module": "UpdateManager"})
            return {"status": "skipped", "message": "Backup is disabled."}

        if event == "auto_schedule":
            last_backup_response = self.memory_bank_manager.get_last_backup_info()
            if last_backup_response and last_backup_response["status"] == "success":
                last_backup_data = last_backup_response["data"]
                if last_backup_data and last_backup_data.get("timestamp"):
                    try:
                        last_backup_time = datetime.datetime.fromisoformat(last_backup_data["timestamp"].replace("Z", "+00:00"))
                        frequency_hours = self.backup_config.get("frequency_hours", 24)
                        if datetime.datetime.now(datetime.timezone.utc) - last_backup_time < datetime.timedelta(hours=frequency_hours):
                            self.monitoring_manager.log_info("Backup skipped due to frequency policy.", context={"module": "UpdateManager", "last_backup_time": last_backup_data["timestamp"]})
                            return {"status": "skipped", "message": "Backup interval not yet reached."}
                    except ValueError:
                        self.monitoring_manager.log_warning(f"Invalid last backup time format from MBM: {last_backup_data.get('timestamp')}. Proceeding with backup.", context={"module": "UpdateManager"})
                else:
                    self.monitoring_manager.log_info("No valid timestamp for last successful backup found, proceeding with backup.", context={"module": "UpdateManager"})
            elif last_backup_response and last_backup_response["status"] == "not_found":
                 self.monitoring_manager.log_info("No previous successful backup metadata found, proceeding with backup.", context={"module": "UpdateManager"})
            elif last_backup_response and last_backup_response["status"] == "error":
                self.monitoring_manager.log_warning("Could not retrieve last backup info from MBM. Proceeding with backup.", context={"module": "UpdateManager"})


        strategy = self.backup_config.get("strategy", "file_copy")
        
        if strategy == "file_copy":
            # Pass event and payload to the async backup process
            return self._perform_file_copy_backup(trigger_event=event, trigger_payload=payload)
        # TODO: Implement other strategies like db_dump or cloud backup
        # elif strategy == "db_dump":
        #     return self._perform_db_dump_backup(trigger_event=event, trigger_payload=payload)
        else:
            self.monitoring_manager.log_error(f"Backup strategy '{strategy}' not implemented.", context={"module": "UpdateManager"})
            return {"status": "error", "message": f"Backup strategy '{strategy}' not implemented."}


    def _execute_file_copy_backup_async(self, source_path: str, target_dir: str, backup_filename: str, target_path: str, trigger_event: str, trigger_payload: Optional[Dict[str, Any]]):
        """Handles the actual file copy and metadata recording in a separate thread."""
        start_time = time.time()
        backup_status = "pending"
        error_message = None
        backup_size = None

        try:
            self.monitoring_manager.log_debug(f"Async: Copying {source_path} to {target_path}", context={"module": "UpdateManager"})
            shutil.copy2(source_path, target_path) # copy2 preserves metadata
            backup_size = os.path.getsize(target_path)
            backup_status = "success"
            self.monitoring_manager.log_info(f"Async: Database file copied to {target_path}", context={"module": "UpdateManager"})
            self._cleanup_old_backups()

        except Exception as e:
            backup_status = "failed"
            error_message = str(e)
            self.monitoring_manager.log_exception(f"Async: Backup to {target_path} failed: {e}", context={"module": "UpdateManager"}, exc_info=True)
        
        duration_seconds = time.time() - start_time
        
        metadata = {
            "backup_id": backup_filename,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "size_bytes": backup_size,
            "status": backup_status,
            "trigger_event": trigger_event,
            "path": target_path,
            "message": error_message if error_message else "Backup completed." if backup_status == "success" else "Backup process finished.",
            "duration_seconds": round(duration_seconds, 2)
        }
        if trigger_payload and trigger_payload.get("trigger_reason"): # Add reason if available
            metadata["message"] = f"Reason: {trigger_payload.get('trigger_reason')}. {metadata['message']}"

        record_result = self.memory_bank_manager.process_request(operation="rec_bm", payload=metadata)
        if record_result["status"] != "success":
            self.monitoring_manager.log_error(f"Failed to record backup metadata for {backup_filename}: {record_result.get('message')}", context={"module": "UpdateManager"})


    def _perform_file_copy_backup(self, trigger_event: str, trigger_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Initiates backup by copying the SQLite database file asynchronously.
        """
        source_path = self.backup_config.get("source_db_path")
        target_dir = self.backup_config.get("target_directory", "./backups")

        if not source_path:
            self.monitoring_manager.log_error("Source DB path not configured for backup.", context={"module": "UpdateManager"})
            return {"status": "error", "message": "Source database path not configured."}
        
        if not os.path.exists(source_path):
            self.monitoring_manager.log_error(f"Source database file not found: {source_path}", context={"module": "UpdateManager"})
            return {"status": "error", "message": f"Source database file not found: {source_path}"}

        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            self.monitoring_manager.log_exception(f"Failed to create backup directory {target_dir}: {e}", context={"module": "UpdateManager"}, exc_info=True)
            return {"status": "error", "message": f"Failed to create backup directory: {e}"}

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.basename(source_path)
        backup_filename = f"{os.path.splitext(base_name)[0]}_backup_{timestamp_str}{os.path.splitext(base_name)[1]}"
        target_path = os.path.join(target_dir, backup_filename)

        try:
            backup_thread = threading.Thread(
                target=self._execute_file_copy_backup_async,
                args=(source_path, target_dir, backup_filename, target_path, trigger_event, trigger_payload),
                daemon=True
            )
            backup_thread.start()
            self.monitoring_manager.log_info(f"Backup thread started for {backup_filename}.", context={"module": "UpdateManager"})
            return {"status": "pending", "backup_id": backup_filename, "message": "Backup process initiated asynchronously."}
        except Exception as e:
            self.monitoring_manager.log_exception(f"Failed to start backup thread: {e}", context={"module": "UpdateManager"}, exc_info=True)
            return {"status": "error", "message": f"Failed to start backup thread: {e}"}

    def _cleanup_old_backups(self):
        """Removes old backup files based on retention policy."""
        target_dir = self.backup_config.get("target_directory", "./backups")
        retention_count = self.backup_config.get("retention_count", 5)

        if not os.path.isdir(target_dir) or retention_count <= 0:
            return

        try:
            self.monitoring_manager.log_debug(f"Cleaning up old backups in {target_dir}, retaining {retention_count}", context={"module": "UpdateManager"})
            # List files matching the expected backup pattern (adjust if needed)
            backup_files = sorted(
                [f for f in os.listdir(target_dir) if f.endswith(os.path.splitext(self.backup_config.get("source_db_path", ".db"))[1]) and "_backup_" in f],
                key=lambda f: os.path.getmtime(os.path.join(target_dir, f))
            )

            files_to_delete = backup_files[:-retention_count] # Keep the latest 'retention_count' files

            for filename in files_to_delete:
                file_path = os.path.join(target_dir, filename)
                os.remove(file_path)
                self.monitoring_manager.log_info(f"Deleted old backup file: {file_path}", context={"module": "UpdateManager"})
        except Exception as e:
            self.monitoring_manager.log_exception(f"Error during backup cleanup: {e}", context={"module": "UpdateManager"}, exc_info=True)

    def _scheduler_loop(self):
        """Main loop for the automatic backup scheduler thread."""
        self.monitoring_manager.log_info("Backup scheduler thread started.", context={"module": "UpdateManager"})
        frequency_seconds = self.backup_config.get("frequency_hours", 24) * 3600
        while not self.stop_scheduler_event.is_set():
            try:
                self.monitoring_manager.log_info("Scheduler checking for backup.", context={"module": "UpdateManager"})
                # Pass a specific payload for scheduled backups
                self.trigger_backup(event="auto_schedule", payload={"trigger_reason": "automatic_scheduler"})
            except Exception as e:
                self.monitoring_manager.log_exception(f"Error in scheduler loop: {e}", context={"module": "UpdateManager"}, exc_info=True)
            
            # Wait for the next interval or until stop event is set
            # Check more frequently to allow faster shutdown if needed
            wait_interval = min(frequency_seconds, 60) # Check every minute or frequency_seconds
            remaining_wait = frequency_seconds
            while remaining_wait > 0 and not self.stop_scheduler_event.is_set():
                actual_wait = min(wait_interval, remaining_wait)
                self.stop_scheduler_event.wait(actual_wait)
                remaining_wait -= actual_wait
                
        self.monitoring_manager.log_info("Backup scheduler thread stopped.", context={"module": "UpdateManager"})

    def start_scheduler(self):
        """Starts the automatic backup scheduler thread if not already running."""
        if not self.backup_config.get("enabled") or not self.backup_config.get("automatic_scheduling_enabled"):
            self.monitoring_manager.log_info("Automatic backup scheduling is disabled in configuration.", context={"module": "UpdateManager"})
            return

        if self.scheduler_thread is None or not self.scheduler_thread.is_alive():
            self.stop_scheduler_event.clear()
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()
            self.monitoring_manager.log_info("Automatic backup scheduler initiated.", context={"module": "UpdateManager"})
        else:
            self.monitoring_manager.log_info("Automatic backup scheduler is already running.", context={"module": "UpdateManager"})

    def stop_scheduler(self):
        """Stops the automatic backup scheduler thread."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.monitoring_manager.log_info("Stopping automatic backup scheduler...", context={"module": "UpdateManager"})
            self.stop_scheduler_event.set()
            self.scheduler_thread.join(timeout=10) # Wait for thread to finish
            if self.scheduler_thread.is_alive():
                self.monitoring_manager.log_warning("Scheduler thread did not stop in time.", context={"module": "UpdateManager"})
            else:
                self.monitoring_manager.log_info("Scheduler thread successfully stopped.")
            self.scheduler_thread = None
        else:
            self.monitoring_manager.log_info("Scheduler thread is not running or already stopped.", context={"module": "UpdateManager"})
    # --- Future Methods ---
    # def trigger_sync(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    #     """Triggers data synchronization (placeholder)."""
    #     self.monitoring_manager.log("info", "Sync triggered (not implemented).", {"module": "UpdateManager"})
    #     if not self.sync_config.get("enabled", False):
    #         return {"status": "skipped", "message": "Sync is disabled."}
    #     # TODO: Implement sync logic
    #     return {"status": "not_implemented", "message": "Sync feature not yet implemented."}
