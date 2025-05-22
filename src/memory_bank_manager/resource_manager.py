# -*- coding: utf-8 -*-
"""
资源管理器 (ResourceManager) 负责处理与知识点相关的外部资源链接。
"""
from typing import Any, Dict, List, Optional

from src.monitoring_manager.monitoring_manager import MonitoringManager

from .db_utils import DBUtil


class ResourceManager:
    """管理资源链接的所有操作。"""

    def __init__(self, db_util: DBUtil, monitoring_manager: MonitoringManager):
        """
        初始化 ResourceManager。

        Args:
            db_util (DBUtil): 数据库工具实例。
            monitoring_manager (MonitoringManager): 监控管理器实例。
        """
        self.db_util = db_util
        self.monitoring_manager = monitoring_manager

    def add_resource_link(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        为知识点添加资源链接。
        输入: {
            "knowledge_point_id": "...", "url": "http://...",
            "description": "...", "resource_type": "article" (可选)
        }
        输出: {"status": "success", "link_id": new_link_id} 或 {"status": "error", "message": "..."}
        """
        kp_id = payload.get("knowledge_point_id")
        url = payload.get("url")

        if not kp_id or not url:
            return {
                "status": "error",
                "message": "knowledge_point_id and url are required.",
            }

        added_at = self.db_util.get_current_timestamp_iso()
        description = payload.get("description")
        resource_type = payload.get("resource_type")

        query = """
        INSERT INTO resource_links
        (knowledge_point_id, url, description, resource_type, added_at)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (kp_id, url, description, resource_type, added_at)

        # Similar to save_assessment_log, we need lastrowid
        if not self.db_util._db_connection:
             self.monitoring_manager.log_error("Database connection not available for adding resource link.")
             return {"status": "error", "message": "Database connection error."}

        cursor = None
        try:
            cursor = self.db_util._db_connection.cursor()
            cursor.execute(query, params)
            self.db_util._db_connection.commit()
            link_id = cursor.lastrowid
            self.monitoring_manager.log_info(
                f"Resource link added successfully for KP {kp_id}. Link ID: {link_id}"
            )
            return {"status": "success", "link_id": link_id}
        except Exception as e:
            self.monitoring_manager.log_error(
                f"Failed to add resource link for KP {kp_id}: {e}", exc_info=True
            )
            if self.db_util._db_connection:
                try:
                    self.db_util._db_connection.rollback()
                except Exception as rb_e:
                    self.monitoring_manager.log_error(f"Rollback failed: {rb_e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to add resource link: {e}",
            }
        finally:
            if cursor:
                cursor.close()

    def get_resource_links_for_kp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取特定知识点的所有资源链接。
        输入: {"knowledge_point_id": "..."}
        输出: {"status": "success", "data": [{...}, ...]} 或 {"status": "error", "message": "..."}
        """
        kp_id = payload.get("knowledge_point_id")
        if not kp_id:
            return {"status": "error", "message": "knowledge_point_id is required."}

        query = "SELECT * FROM resource_links WHERE knowledge_point_id = ? ORDER BY added_at DESC"
        links = self.db_util.execute_query(query, (kp_id,))

        if links is not None and isinstance(links, list):
            return {"status": "success", "data": links}
        elif links is None: # Query execution failed
            return {"status": "error", "message": f"Failed to retrieve resource links for KP {kp_id}."}
        else: # Empty list
            return {"status": "success", "data": []}

    def delete_resource_link(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        删除特定的资源链接。
        输入: {"link_id": ...}
        输出: {"status": "success"} 或 {"status": "error", "message": "..."}
        """
        link_id = payload.get("link_id")
        if not link_id:
            return {"status": "error", "message": "link_id is required."}

        query = "DELETE FROM resource_links WHERE link_id = ?"
        success = self.db_util.execute_query(query, (link_id,), is_write=True)

        if success:
            self.monitoring_manager.log_info(f"Resource link {link_id} deleted successfully.")
            return {"status": "success", "message": f"Resource link {link_id} deleted."}
        else:
            # Check if the link existed before claiming it failed to delete
            # For now, assume failure means it couldn't be deleted or didn't exist.
            self.monitoring_manager.log_warning(f"Failed to delete resource link {link_id}, it might not exist or a DB error occurred.")
            return {"status": "error", "message": f"Failed to delete resource link {link_id}."}