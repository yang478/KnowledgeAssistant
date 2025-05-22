# -*- coding: utf-8 -*-
"""
知识点管理器 (KnowledgePointManager) 负责处理与知识点相关的业务逻辑，
包括 CRUD 操作、历史记录、导入导出以及搜索功能。
"""
import uuid
from typing import Any, Dict, List, Optional

from src.monitoring_manager.monitoring_manager import MonitoringManager

from .db_utils import DBUtil


class KnowledgePointManager:
    """管理知识点的所有操作。"""

    def __init__(self, db_util: DBUtil, monitoring_manager: MonitoringManager):
        """
        初始化 KnowledgePointManager。

        Args:
            db_util (DBUtil): 数据库工具实例。
            monitoring_manager (MonitoringManager): 监控管理器实例。
        """
        self.db_util = db_util
        self.monitoring_manager = monitoring_manager

    def _log_knowledge_point_history(
        self,
        knowledge_point_id: str,
        change_type: str,
        snapshot_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        记录知识点变更到历史表。
        对于 'created' 或 'updated'，snapshot_data 应为变更后的状态。
        对于 'archived' 或 'deleted'，snapshot_data 应为变更前的状态。
        """
        if not knowledge_point_id or not change_type:
            self.monitoring_manager.log_warning(
                f"Skipping history log: knowledge_point_id or change_type missing. KP_ID: {knowledge_point_id}, Change: {change_type}"
            )
            return False

        now_iso = self.db_util.get_current_timestamp_iso()
        version_id = now_iso  # 使用时间戳作为版本ID

        final_snapshot_data = snapshot_data
        # 如果 'updated' 或 'created' 时未提供快照，尝试获取当前状态
        if change_type in ["created", "updated"] and snapshot_data is None:
            kp_details_response = self.get_knowledge_point(
                {"knowledge_point_id": knowledge_point_id}
            )
            if kp_details_response["status"] == "success":
                final_snapshot_data = kp_details_response["data"]
            else:
                self.monitoring_manager.log_warning(
                    f"Could not fetch current KP data for history snapshot (KP_ID: {knowledge_point_id}). Logging history without full snapshot."
                )

        snapshot_json = self.db_util.serialize(final_snapshot_data)

        query = """
        INSERT INTO knowledge_point_history
        (knowledge_point_id, version_id, change_type, changed_at, snapshot_data)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (knowledge_point_id, version_id, change_type, now_iso, snapshot_json)

        success = self.db_util.execute_query(query, params, is_write=True)
        if success:
            self.monitoring_manager.log_info(
                f"Logged history for KP_ID {knowledge_point_id}: type='{change_type}', version='{version_id}'."
            )
        else:
            self.monitoring_manager.log_error(
                f"Failed to log history for KP_ID {knowledge_point_id}, type='{change_type}'."
            )
        return success

    def get_knowledge_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        从数据库获取知识点。
        输入: {"knowledge_point_id": "..."}
        输出: {"status": "success", "data": {...}} 或 {"status": "error", "message": "..."}
        """
        kp_id = payload.get("knowledge_point_id")
        if not kp_id:
            return {"status": "error", "message": "knowledge_point_id is required"}

        query = "SELECT * FROM knowledge_points WHERE id = ?"
        db_data = self.db_util.execute_query(query, (kp_id,), fetch_one=True)

        if db_data and isinstance(db_data, dict):
            db_data["dependencies"] = self.db_util.deserialize(
                db_data.get("dependencies")
            )
            return {"status": "success", "data": db_data}
        elif db_data is None: # Explicitly check for None if execute_query can return it for not found
             self.monitoring_manager.log_warning(
                f"Knowledge point with id {kp_id} not found."
            )
             return {
                "status": "not_found",
                "message": f"Knowledge point with id {kp_id} not found",
                "data": None,
            }
        else: # Handle unexpected return type from db_util
            self.monitoring_manager.log_error(
                f"Unexpected data type from db_util.execute_query for KP_ID {kp_id}: {type(db_data)}"
            )
            return {
                "status": "error",
                "message": f"Error retrieving knowledge point {kp_id}.",
                "data": None,
            }

    def save_knowledge_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        向数据库插入或更新知识点 (Upsert)。
        输入: 知识点字典，至少包含 'id' 和 'title'。
        输出: {"status": "success"} 或 {"status": "error", "message": "..."}
        """
        kp_data = payload
        kp_id = kp_data.get("id")
        title = kp_data.get("title")

        if not kp_id: # Generate new ID if not provided
            kp_id = str(uuid.uuid4())
            kp_data["id"] = kp_id # Add to payload for history logging
            self.monitoring_manager.log_info(f"No ID provided for knowledge point, generated new ID: {kp_id}")
        
        if not title:
            return {
                "status": "error",
                "message": "Knowledge point 'title' is required",
            }

        existing_kp_resp = self.get_knowledge_point({"knowledge_point_id": kp_id})
        is_creation = existing_kp_resp["status"] == "not_found"
        change_type = "created" if is_creation else "updated"

        now_iso = self.db_util.get_current_timestamp_iso()
        created_at = kp_data.get("created_at")
        if is_creation and not created_at:
            created_at = now_iso
        elif not is_creation and not created_at and existing_kp_resp["status"] == "success" and isinstance(existing_kp_resp["data"], dict) :
            created_at = existing_kp_resp["data"].get("created_at", now_iso)
        elif not created_at: # Fallback if existing_kp_resp failed or data is not dict
            created_at = now_iso


        dependencies_json = self.db_util.serialize(kp_data.get("dependencies", []))

        query = """
        INSERT OR REPLACE INTO knowledge_points
        (id, title, content, status, dependencies, priority, created_at, last_reviewed, last_assessed_time, last_assessed_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            kp_id,
            title,
            kp_data.get("content"),
            kp_data.get("status", "new"),
            dependencies_json,
            kp_data.get("priority", 3),
            created_at,
            kp_data.get("last_reviewed"),
            kp_data.get("last_assessed_time"),
            kp_data.get("last_assessed_score"),
        )

        success = self.db_util.execute_query(query, params, is_write=True)

        if success:
            self.monitoring_manager.log_info(
                f"Knowledge point {kp_id} saved successfully (change: {change_type})."
            )
            # Fetch the full KP data after save for accurate snapshot
            saved_kp_data_resp = self.get_knowledge_point({"knowledge_point_id": kp_id})
            snapshot_to_log = kp_data # Fallback to input if fetch fails
            if saved_kp_data_resp["status"] == "success" and isinstance(saved_kp_data_resp["data"], dict):
                snapshot_to_log = saved_kp_data_resp["data"]
            
            self._log_knowledge_point_history(
                kp_id, change_type, snapshot_data=snapshot_to_log
            )
            return {
                "status": "success",
                "message": f"Knowledge point {kp_id} saved successfully.",
                "data": {"id": kp_id} # Return the ID
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to save knowledge point {kp_id}.",
            }

    def update_knowledge_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新现有知识点。
        输入: {"knowledge_point_id": "...", "update_data": {"title": "new title", ...}}
        输出: {"status": "success"} 或 {"status": "error", "message": "..."}
        """
        kp_id = payload.get("knowledge_point_id")
        update_data = payload.get("update_data")

        if not kp_id or not update_data or not isinstance(update_data, dict):
            return {
                "status": "error",
                "message": "knowledge_point_id and update_data (dictionary) are required.",
            }

        existing_kp_resp = self.get_knowledge_point({"knowledge_point_id": kp_id})
        if existing_kp_resp["status"] != "success":
            return existing_kp_resp # Return not_found or error from get_knowledge_point

        # Prepare fields for SQL SET clause
        set_clauses = []
        params = []
        valid_fields = [
            "title",
            "content",
            "status",
            "dependencies",
            "priority",
            "last_reviewed",
            "last_assessed_time",
            "last_assessed_score",
        ]

        for field, value in update_data.items():
            if field in valid_fields:
                set_clauses.append(f"{field} = ?")
                if field == "dependencies":
                    params.append(self.db_util.serialize(value))
                else:
                    params.append(value)
            elif field == "id": # ID cannot be updated here
                self.monitoring_manager.log_warning(f"Attempted to update 'id' for KP {kp_id}, which is not allowed.")
            # created_at should not be updated after creation

        if not set_clauses:
            return {"status": "error", "message": "No valid fields provided for update."}

        params.append(kp_id)  # For WHERE clause
        query = f"UPDATE knowledge_points SET {', '.join(set_clauses)} WHERE id = ?"

        success = self.db_util.execute_query(query, tuple(params), is_write=True)

        if success:
            self.monitoring_manager.log_info(
                f"Knowledge point {kp_id} updated successfully."
            )
            # Log history after successful update
            updated_kp_data_resp = self.get_knowledge_point({"knowledge_point_id": kp_id})
            snapshot_to_log = update_data # Fallback
            if updated_kp_data_resp["status"] == "success" and isinstance(updated_kp_data_resp["data"], dict):
                snapshot_to_log = updated_kp_data_resp["data"]

            self._log_knowledge_point_history(
                kp_id, "updated", snapshot_data=snapshot_to_log
            )
            return {"status": "success", "message": f"Knowledge point {kp_id} updated."}
        else:
            return {
                "status": "error",
                "message": f"Failed to update knowledge point {kp_id}.",
            }

    def delete_knowledge_point(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        从数据库删除（或归档）知识点。
        实际操作是将其状态更新为 'archived'。
        输入: {"knowledge_point_id": "..."}
        输出: {"status": "success"} 或 {"status": "error", "message": "..."}
        """
        kp_id = payload.get("knowledge_point_id")
        if not kp_id:
            return {"status": "error", "message": "knowledge_point_id is required"}

        # Get current state for history snapshot BEFORE archiving
        kp_before_archive_resp = self.get_knowledge_point({"knowledge_point_id": kp_id})
        if kp_before_archive_resp["status"] != "success":
            return kp_before_archive_resp # KP not found or other error

        # For true deletion:
        # query = "DELETE FROM knowledge_points WHERE id = ?"
        # success = self.db_util.execute_query(query, (kp_id,), is_write=True)
        
        # For archiving:
        query = "UPDATE knowledge_points SET status = ? WHERE id = ?"
        params = ("archived", kp_id)
        success = self.db_util.execute_query(query, params, is_write=True)

        if success:
            self.monitoring_manager.log_info(
                f"Knowledge point {kp_id} archived successfully."
            )
            self._log_knowledge_point_history(
                kp_id, "archived", snapshot_data=kp_before_archive_resp.get("data")
            )
            return {"status": "success", "message": f"Knowledge point {kp_id} archived."}
        else:
            return {
                "status": "error",
                "message": f"Failed to archive knowledge point {kp_id}.",
            }

    def get_all_syllabus_topics(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        获取所有知识点作为教学大纲主题（通常包含id, title, status, dependencies, priority）。
        输出: {"status": "success", "data": [{...}, ...]} 或 {"status": "error", "message": "..."}
        """
        # payload is not used for now, but kept for interface consistency
        query = "SELECT id, title, content, status, dependencies, priority, created_at, last_reviewed, last_assessed_time, last_assessed_score FROM knowledge_points WHERE status != 'archived' ORDER BY priority DESC, title ASC"
        results = self.db_util.execute_query(query)

        if results is not None and isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    item["dependencies"] = self.db_util.deserialize(
                        item.get("dependencies")
                    )
            return {"status": "success", "data": results}
        elif results is None: # Query failed
             return {"status": "error", "message": "Failed to retrieve syllabus topics."}
        else: # Should be an empty list if no topics found but query was successful
            return {"status": "success", "data": []}


    def get_historical_version(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取知识点的特定历史版本。
        输入: {"knowledge_point_id": "...", "version_id": "..." (timestamp)}
        输出: {"status": "success", "data": {...}} 或 {"status": "error", "message": "..."}
        """
        kp_id = payload.get("knowledge_point_id")
        version_id = payload.get("version_id")

        if not kp_id or not version_id:
            return {
                "status": "error",
                "message": "knowledge_point_id and version_id are required.",
            }

        query = "SELECT * FROM knowledge_point_history WHERE knowledge_point_id = ? AND version_id = ?"
        history_data = self.db_util.execute_query(
            query, (kp_id, version_id), fetch_one=True
        )

        if history_data and isinstance(history_data, dict):
            history_data["snapshot_data"] = self.db_util.deserialize(
                history_data.get("snapshot_data")
            )
            return {"status": "success", "data": history_data}
        else:
            return {
                "status": "not_found",
                "message": f"Historical version {version_id} for KP {kp_id} not found.",
            }

    def search_knowledge_points(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据关键词搜索知识点 (标题和内容)。
        输入: {"query": "search term", "status_filter": ["new", "learning"], "limit": 10}
        输出: {"status": "success", "data": [{...}, ...]} 或 {"status": "error", "message": "..."}
        """
        search_query = payload.get("query")
        status_filter = payload.get("status_filter") # Optional list of statuses
        limit = payload.get("limit", 10) # Default limit

        if not search_query:
            return {"status": "error", "message": "Search query is required."}

        base_sql = "SELECT id, title, content, status, priority, last_reviewed FROM knowledge_points WHERE (title LIKE ? OR content LIKE ?)"
        params: List[Any] = [f"%{search_query}%", f"%{search_query}%"]

        if status_filter and isinstance(status_filter, list) and len(status_filter) > 0:
            placeholders = ','.join('?' for _ in status_filter)
            base_sql += f" AND status IN ({placeholders})"
            params.extend(status_filter)
        else:
            # Default to not searching archived KPs if no filter is provided
            base_sql += " AND status != 'archived'"


        base_sql += " ORDER BY priority DESC, last_reviewed DESC LIMIT ?"
        params.append(limit)

        results = self.db_util.execute_query(base_sql, tuple(params))

        if results is not None and isinstance(results, list):
            # No deserialization needed for these fields typically
            return {"status": "success", "data": results}
        elif results is None:
            return {"status": "error", "message": "Error during knowledge point search."}
        else: # Empty list if no results
            return {"status": "success", "data": []}

    def import_from_markdown(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 Markdown 内容导入知识点。
        输入: {"markdown_content": "...", "default_status": "new"}
        输出: {"status": "success", "data": {"imported_count": N, "failed_count": M, "errors": [...]}}
        """
        markdown_content = payload.get("markdown_content")
        default_status = payload.get("default_status", "new")

        if not markdown_content:
            return {"status": "error", "message": "markdown_content is required."}

        imported_count = 0
        failed_count = 0
        errors = []
        
        # Basic parsing: assumes "## Title" for KP title and subsequent lines as content
        # More sophisticated parsing might be needed for complex Markdown.
        current_title = None
        current_content_lines: List[str] = []

        for line in markdown_content.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("## "):
                if current_title and current_content_lines:
                    # Save previous KP
                    kp_id = str(uuid.uuid4())
                    content = "\n".join(current_content_lines).strip()
                    save_payload = {
                        "id": kp_id,
                        "title": current_title,
                        "content": content,
                        "status": default_status,
                        "dependencies": [], # Default to no dependencies
                        "priority": 3, # Default priority
                        "created_at": self.db_util.get_current_timestamp_iso()
                    }
                    save_result = self.save_knowledge_point(save_payload)
                    if save_result["status"] == "success":
                        imported_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"Failed to save '{current_title}': {save_result.get('message')}")
                
                current_title = line_stripped[3:].strip()
                current_content_lines = []
            elif current_title: # Only add content if a title is active
                current_content_lines.append(line)
        
        # Save the last KP if any
        if current_title and current_content_lines:
            kp_id = str(uuid.uuid4())
            content = "\n".join(current_content_lines).strip()
            save_payload = {
                "id": kp_id,
                "title": current_title,
                "content": content,
                "status": default_status,
                "dependencies": [],
                "priority": 3,
                "created_at": self.db_util.get_current_timestamp_iso()
            }
            save_result = self.save_knowledge_point(save_payload)
            if save_result["status"] == "success":
                imported_count += 1
            else:
                failed_count += 1
                errors.append(f"Failed to save '{current_title}': {save_result.get('message')}")

        return {
            "status": "success",
            "data": {
                "imported_count": imported_count,
                "failed_count": failed_count,
                "errors": errors,
            },
        }

    def export_to_markdown(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        将所有（或特定状态的）知识点导出为 Markdown 格式。
        输入 (可选): {"status_filter": ["learning", "mastered"]}
        输出: {"status": "success", "data": {"markdown_content": "..."}}
        """
        status_filter = payload.get("status_filter") if payload else None
        
        query = "SELECT title, content, status FROM knowledge_points"
        params: List[Any] = []

        if status_filter and isinstance(status_filter, list) and len(status_filter) > 0:
            placeholders = ','.join('?' for _ in status_filter)
            query += f" WHERE status IN ({placeholders})"
            params.extend(status_filter)
        else:
            query += " WHERE status != 'archived'" # Default: exclude archived

        query += " ORDER BY title ASC"
        
        kps_data = self.db_util.execute_query(query, tuple(params))

        if kps_data is None: # Error in query execution
            return {"status": "error", "message": "Failed to retrieve knowledge points for export."}

        markdown_lines: List[str] = []
        if isinstance(kps_data, list):
            for kp in kps_data:
                if isinstance(kp, dict):
                    markdown_lines.append(f"## {kp.get('title', 'Untitled')}")
                    markdown_lines.append(f"Status: {kp.get('status', 'unknown')}")
                    markdown_lines.append("\n" + kp.get('content', '') + "\n")
        
        return {
            "status": "success",
            "data": {"markdown_content": "\n".join(markdown_lines)},
        }
