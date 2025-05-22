# -*- coding: utf-8 -*-
"""
数据库工具模块 (DBUtils)

提供与 SQLite 数据库交互的底层实用函数，包括连接管理、
查询执行、数据序列化/反序列化以及数据库初始化。
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from src.monitoring_manager.monitoring_manager import MonitoringManager


class DBUtil:
    """封装数据库操作的工具类。"""

    def __init__(self, db_path: str, monitoring_manager: MonitoringManager):
        """
        初始化 DBUtil。

        Args:
            db_path (str): 数据库文件的路径。
            monitoring_manager (MonitoringManager): 监控管理器实例。
        """
        self.db_path = db_path
        self.monitoring_manager = monitoring_manager
        self._db_connection: Optional[sqlite3.Connection] = None
        self._ensure_db_directory()
        self._connect_db()
        self._initialize_database()

    def _ensure_db_directory(self):
        """确保数据库文件所在的目录存在。"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
                self.monitoring_manager.log_info(
                    f"Created database directory: {db_dir}"
                )
            except OSError as e:
                self.monitoring_manager.log_error(
                    f"Failed to create database directory {db_dir}: {e}", exc_info=True
                )
                raise OSError(f"Failed to create database directory {db_dir}") from e

    def _connect_db(self):
        """建立数据库连接。失败时抛出 ConnectionError。"""
        if self._db_connection:
            self.close_connection()

        try:
            self._db_connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._db_connection.row_factory = sqlite3.Row
            self.monitoring_manager.log_info(
                f"Successfully connected to database: {self.db_path}"
            )
        except sqlite3.Error as e:
            self.monitoring_manager.log_error(
                f"Error connecting to database {self.db_path}: {e}", exc_info=True
            )
            self._db_connection = None
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    def _initialize_database(self):
        """检查并创建所需的数据库表（如果不存在）。失败时抛出 RuntimeError。"""
        if not self._db_connection:
            self.monitoring_manager.log_error(
                "Database connection not available for initialization."
            )
            raise ConnectionError("Cannot initialize database without a connection.")

        # 表创建语句
        create_knowledge_points_table = """
        CREATE TABLE IF NOT EXISTS knowledge_points (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT,
            status TEXT DEFAULT 'new' CHECK(status IN ('new', 'learning', 'mastered', 'archived')),
            dependencies TEXT, -- Store as JSON string
            priority INTEGER DEFAULT 3,
            created_at TEXT, -- ISO 8601 format
            last_reviewed TEXT, -- ISO 8601 format
            last_assessed_time TEXT, -- ISO 8601 format
            last_assessed_score REAL
        );
        """
        create_learning_context_table = """
        CREATE TABLE IF NOT EXISTS learning_context (
            session_id TEXT PRIMARY KEY,
            current_topics TEXT, -- Store as JSON string
            unresolved_questions TEXT, -- Store as JSON string of list of dicts
            session_goals TEXT,
            updated_at TEXT, -- ISO 8601 format
            mode_contexts TEXT -- JSON string to store context for different modes
        );
        """
        create_assessment_logs_table = """
        CREATE TABLE IF NOT EXISTS assessment_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            assessment_id TEXT NOT NULL,
            knowledge_point_id TEXT NOT NULL,
            question_id TEXT, 
            score REAL,
            is_correct INTEGER, 
            feedback TEXT,
            timestamp TEXT NOT NULL 
        );
        """
        create_generated_assessments_table = """
        CREATE TABLE IF NOT EXISTS generated_assessments (
            assessment_id TEXT PRIMARY KEY,
            assessment_type TEXT,
            difficulty TEXT,
            knowledge_point_ids TEXT, -- JSON string list
            questions TEXT, -- JSON string list of question objects
            generated_at TEXT -- ISO 8601 format
        );
        """
        create_resource_links_table = """
        CREATE TABLE IF NOT EXISTS resource_links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_point_id TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT,
            resource_type TEXT,
            added_at TEXT NOT NULL, 
            FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id) ON DELETE CASCADE
        );
        """
        create_knowledge_point_history_table = """
        CREATE TABLE IF NOT EXISTS knowledge_point_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_point_id TEXT NOT NULL,
            version_id TEXT NOT NULL, 
            change_type TEXT NOT NULL CHECK(change_type IN ('created', 'updated', 'archived', 'deleted')),
            changed_at TEXT NOT NULL, 
            snapshot_data TEXT 
        );
        """
        create_backup_metadata_table = """
        CREATE TABLE IF NOT EXISTS backup_metadata (
            backup_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            size_bytes INTEGER,
            status TEXT NOT NULL CHECK(status IN ('success', 'failed', 'pending')),
            trigger_event TEXT,
            path TEXT NOT NULL,
            message TEXT,
            duration_seconds REAL
        );
        """
        
        tables_to_create = [
            create_knowledge_points_table,
            create_learning_context_table,
            create_assessment_logs_table,
            create_generated_assessments_table,
            create_resource_links_table,
            create_knowledge_point_history_table,
            create_backup_metadata_table,
        ]

        cursor = None
        try:
            cursor = self._db_connection.cursor()
            for table_sql in tables_to_create:
                cursor.execute(table_sql)
            self._db_connection.commit()
            self.monitoring_manager.log_info(
                "Database tables checked/created successfully."
            )
        except sqlite3.Error as e:
            self.monitoring_manager.log_error(
                f"Error initializing database tables: {e}", exc_info=True
            )
            raise RuntimeError(f"Failed to initialize database tables: {e}") from e
        finally:
            if cursor:
                cursor.close()

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        fetch_one: bool = False,
        is_write: bool = False,
    ) -> Union[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], bool]:
        """
        执行数据库查询或命令。

        Args:
            query (str): SQL 查询语句。
            params (tuple, optional): 查询参数。
            fetch_one (bool, optional): 是否只获取一条记录。
            is_write (bool, optional): 是否是写入操作（需要 commit）。

        Returns:
            查询结果或操作成功状态。写入操作成功返回 True，失败返回 False。
            读取操作成功返回字典或字典列表，失败返回 None。
        """
        if not self._db_connection:
            self.monitoring_manager.log_error(
                "Cannot execute query: Database connection is not available."
            )
            try:
                self.monitoring_manager.log_warning(
                    "Attempting to reconnect to the database..."
                )
                self._connect_db()
                if not self._db_connection:
                    raise ConnectionError("Database reconnection failed.")
                self.monitoring_manager.log_info("Database reconnection successful.")
            except ConnectionError as ce:
                self.monitoring_manager.log_error(
                    f"Database reconnection failed: {ce}", exc_info=True
                )
                return False if is_write else None

        cursor = None
        try:
            cursor = self._db_connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if is_write:
                self._db_connection.commit()
                return True
            else:
                if fetch_one:
                    result = cursor.fetchone()
                    return dict(result) if result else None
                else:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
        except sqlite3.Error as e:
            self.monitoring_manager.log_error(
                f"Database error executing query '{query}' with params {params}: {e}",
                exc_info=True,
            )
            if is_write:
                try:
                    self._db_connection.rollback()
                    self.monitoring_manager.log_warning(
                        "Database transaction rolled back due to error."
                    )
                except sqlite3.Error as rb_e:
                    self.monitoring_manager.log_error(
                        f"Error during rollback: {rb_e}", exc_info=True
                    )
            return False if is_write else None
        finally:
            if cursor:
                cursor.close()

    def serialize(self, data: Any) -> Optional[str]:
        """安全地将 Python 对象（列表、字典）序列化为 JSON 字符串。"""
        if data is None:
            return None
        try:
            return json.dumps(data)
        except (TypeError, ValueError) as e:
            self.monitoring_manager.log_warning(
                f"Could not serialize data to JSON: {data}, Error: {e}"
            )
            return None

    def deserialize(self, text: Optional[str]) -> Any:
        """安全地将 JSON 字符串反序列化为 Python 对象。错误时返回 None。"""
        if text is None:
            return None
        try:
            return json.loads(text)
        except (TypeError, json.JSONDecodeError) as e:
            self.monitoring_manager.log_warning(
                f"Could not deserialize JSON string: {text}, Error: {e}"
            )
            return None
            
    def get_current_timestamp_iso(self) -> str:
        """返回当前的 UTC ISO 8601 格式时间戳。"""
        return datetime.utcnow().isoformat() + "Z"

    def close_connection(self):
        """关闭数据库连接。"""
        if self._db_connection:
            try:
                self._db_connection.close()
                self.monitoring_manager.log_info(
                    f"Database connection to {self.db_path} closed."
                )
            except sqlite3.Error as e:
                self.monitoring_manager.log_error(
                    f"Error closing database connection: {e}", exc_info=True
                )
            finally:
                self._db_connection = None

    def __del__(self):
        """确保在对象销毁时关闭连接。"""
        self.close_connection()