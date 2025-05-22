# -*- coding: utf-8 -*-
"""
学习上下文管理器 (LearningContextManager) 负责处理与用户学习会话相关的上下文信息。
"""
from typing import Any, Dict, Optional

from src.monitoring_manager.monitoring_manager import MonitoringManager

from .db_utils import DBUtil


class LearningContextManager:
    """管理学习上下文的所有操作。"""

    def __init__(self, db_util: DBUtil, monitoring_manager: MonitoringManager):
        """
        初始化 LearningContextManager。

        Args:
            db_util (DBUtil): 数据库工具实例。
            monitoring_manager (MonitoringManager): 监控管理器实例。
        """
        self.db_util = db_util
        self.monitoring_manager = monitoring_manager

    def get_learning_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        从数据库获取当前学习上下文。
        输入: {"session_id": "..."}
        输出: {"status": "success", "data": {...}} 或 {"status": "error", "message": "..."}
        """
        session_id = payload.get("session_id")
        if not session_id:
            return {"status": "error", "message": "session_id is required"}

        query = "SELECT * FROM learning_context WHERE session_id = ?"
        context_data = self.db_util.execute_query(query, (session_id,), fetch_one=True)

        if context_data and isinstance(context_data, dict):
            context_data["current_topics"] = self.db_util.deserialize(
                context_data.get("current_topics")
            )
            context_data["unresolved_questions"] = self.db_util.deserialize(
                context_data.get("unresolved_questions")
            )
            context_data["mode_contexts"] = self.db_util.deserialize(
                context_data.get("mode_contexts")
            )
            return {"status": "success", "data": context_data}
        elif context_data is None:
            self.monitoring_manager.log_info(
                f"Learning context for session_id {session_id} not found. Returning default."
            )
            # Return a default empty context structure if not found
            default_context = {
                "session_id": session_id,
                "current_topics": [],
                "unresolved_questions": [],
                "session_goals": "",
                "updated_at": self.db_util.get_current_timestamp_iso(),
                "mode_contexts": {}
            }
            return {"status": "success", "data": default_context, "message": "Context not found, returned default."}
        else:
            self.monitoring_manager.log_error(
                f"Unexpected data type from db_util.execute_query for session_id {session_id}: {type(context_data)}"
            )
            return {
                "status": "error",
                "message": f"Error retrieving learning context for session {session_id}.",
            }

    def save_learning_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        向数据库插入或更新学习上下文。
        输入: 学习上下文的字典，至少包含 'session_id'。
              例如: {"session_id": "...", "current_topics": [...], ...}
        输出: {"status": "success"} 或 {"status": "error", "message": "..."}
        """
        context_data = payload
        session_id = context_data.get("session_id")

        if not session_id:
            return {"status": "error", "message": "session_id is required"}

        now_iso = self.db_util.get_current_timestamp_iso()
        current_topics_json = self.db_util.serialize(
            context_data.get("current_topics", [])
        )
        unresolved_questions_json = self.db_util.serialize(
            context_data.get("unresolved_questions", [])
        )
        mode_contexts_json = self.db_util.serialize(
            context_data.get("mode_contexts", {})
        )


        query = """
        INSERT OR REPLACE INTO learning_context
        (session_id, current_topics, unresolved_questions, session_goals, updated_at, mode_contexts)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            session_id,
            current_topics_json,
            unresolved_questions_json,
            context_data.get("session_goals", ""),
            now_iso, # Always update 'updated_at'
            mode_contexts_json,
        )

        success = self.db_util.execute_query(query, params, is_write=True)

        if success:
            self.monitoring_manager.log_info(
                f"Learning context for session {session_id} saved successfully."
            )
            return {
                "status": "success",
                "message": f"Learning context for session {session_id} saved.",
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to save learning context for session {session_id}.",
            }

    def update_progress(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新特定知识点的学习进度（例如，状态、上次复习时间）。
        这是对 KnowledgePointManager.update_knowledge_point 的一个特定封装，
        专注于与学习进度相关的字段。

        输入: {
            "knowledge_point_id": "...",
            "status": "learning",  // optional
            "last_reviewed": "YYYY-MM-DDTHH:MM:SSZ", // optional
            "last_assessed_time": "YYYY-MM-DDTHH:MM:SSZ", // optional
            "last_assessed_score": 0.8 // optional
        }
        输出: {"status": "success"} 或 {"status": "error", "message": "..."}
        """
        kp_id = payload.get("knowledge_point_id")
        if not kp_id:
            return {"status": "error", "message": "knowledge_point_id is required for updating progress."}

        update_data = {}
        if "status" in payload:
            update_data["status"] = payload["status"]
        if "last_reviewed" in payload:
            update_data["last_reviewed"] = payload["last_reviewed"]
        if "last_assessed_time" in payload:
            update_data["last_assessed_time"] = payload["last_assessed_time"]
        if "last_assessed_score" in payload:
            update_data["last_assessed_score"] = payload["last_assessed_score"]
        
        if not update_data:
            return {"status": "error", "message": "No progress fields provided to update."}

        # This method might be better placed in KnowledgePointManager or
        # this manager should call KnowledgePointManager.update_knowledge_point
        # For now, directly updating for simplicity as per original structure.
        
        set_clauses = [f"{field} = ?" for field in update_data.keys()]
        params = list(update_data.values())
        params.append(kp_id)

        query = f"UPDATE knowledge_points SET {', '.join(set_clauses)} WHERE id = ?"
        
        success = self.db_util.execute_query(query, tuple(params), is_write=True)

        if success:
            self.monitoring_manager.log_info(f"Progress for KP {kp_id} updated: {update_data}")
            # Consider logging history for these changes via KnowledgePointManager
            # For now, direct update as per original structure.
            # self.knowledge_point_manager._log_knowledge_point_history(kp_id, "updated", snapshot_data=update_data)
            return {"status": "success", "message": f"Progress for KP {kp_id} updated."}
        else:
            return {"status": "error", "message": f"Failed to update progress for KP {kp_id}."}

    def get_reviewable_knowledge_points(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取需要复习的知识点列表。
        可以根据上次复习时间、状态等进行筛选。
        输入: {"max_points": 10, "min_priority": 2, "status_filter": ["learning"]}
        输出: {"status": "success", "data": [{...}, ...]} 或 {"status": "error", "message": "..."}
        """
        max_points = payload.get("max_points", 10)
        min_priority = payload.get("min_priority", 1) # Default to include all priorities
        status_filter = payload.get("status_filter", ["learning", "new"]) # Default statuses

        query = """
        SELECT id, title, status, priority, last_reviewed, last_assessed_score
        FROM knowledge_points
        WHERE status IN ({}) AND priority >= ?
        ORDER BY last_reviewed ASC, priority DESC
        LIMIT ?
        """.format(','.join('?' for _ in status_filter)) # Prepare placeholders for status_filter

        params = list(status_filter)
        params.extend([min_priority, max_points])
        
        results = self.db_util.execute_query(query, tuple(params))

        if results is not None and isinstance(results, list):
            return {"status": "success", "data": results}
        elif results is None:
            return {"status": "error", "message": "Failed to retrieve reviewable knowledge points."}
        else: # Empty list
            return {"status": "success", "data": []}