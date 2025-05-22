# -*- coding: utf-8 -*-
"""
评估数据管理器 (AssessmentDataManager) 负责处理与评估和测验相关的数据。
"""
import uuid
from typing import Any, Dict, List, Optional

from src.monitoring_manager.monitoring_manager import MonitoringManager

from .db_utils import DBUtil


class AssessmentDataManager:
    """管理评估数据的所有操作。"""

    def __init__(self, db_util: DBUtil, monitoring_manager: MonitoringManager):
        """
        初始化 AssessmentDataManager。

        Args:
            db_util (DBUtil): 数据库工具实例。
            monitoring_manager (MonitoringManager): 监控管理器实例。
        """
        self.db_util = db_util
        self.monitoring_manager = monitoring_manager

    def save_assessment_log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存评估日志条目。
        输入: {
            "session_id": "...", "assessment_id": "...", "knowledge_point_id": "...",
            "question_id": "...", "score": 0.0-1.0, "is_correct": True/False,
            "feedback": "...", "timestamp": "YYYY-MM-DDTHH:MM:SSZ" (可选, 否则自动生成)
        }
        输出: {"status": "success", "log_id": new_log_id} 或 {"status": "error", "message": "..."}
        """
        session_id = payload.get("session_id")
        assessment_id = payload.get("assessment_id")
        kp_id = payload.get("knowledge_point_id")
        # question_id is optional
        # score is optional
        # is_correct is optional
        # feedback is optional

        if not session_id or not assessment_id or not kp_id:
            return {
                "status": "error",
                "message": "session_id, assessment_id, and knowledge_point_id are required.",
            }

        timestamp = payload.get("timestamp", self.db_util.get_current_timestamp_iso())

        query = """
        INSERT INTO assessment_logs
        (session_id, assessment_id, knowledge_point_id, question_id, score, is_correct, feedback, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            session_id,
            assessment_id,
            kp_id,
            payload.get("question_id"),
            payload.get("score"),
            payload.get("is_correct"), # Store as 1 or 0 if boolean
            payload.get("feedback"),
            timestamp,
        )

        # The execute_query for write operations returns True on success, False on failure.
        # We need to get the last inserted row ID if successful.
        # This requires a slightly different handling than a simple True/False.

        if not self.db_util._db_connection: # Accessing protected member for check
             self.monitoring_manager.log_error("Database connection not available for saving assessment log.")
             return {"status": "error", "message": "Database connection error."}

        cursor = None
        try:
            # It's generally not good practice to access protected members (_db_connection)
            # of another class. db_util should provide a method to get a cursor or
            # handle the entire transaction for `lastrowid`.
            # For now, proceeding with current structure for expediency.
            cursor = self.db_util._db_connection.cursor()
            cursor.execute(query, params)
            self.db_util._db_connection.commit()
            log_id = cursor.lastrowid
            self.monitoring_manager.log_info(
                f"Assessment log saved successfully for assessment {assessment_id}, KP {kp_id}. Log ID: {log_id}"
            )
            return {"status": "success", "log_id": log_id}
        except Exception as e:
            self.monitoring_manager.log_error(
                f"Failed to save assessment log for assessment {assessment_id}, KP {kp_id}: {e}",
                exc_info=True
            )
            if self.db_util._db_connection:
                try:
                    self.db_util._db_connection.rollback()
                except Exception as rb_e:
                    self.monitoring_manager.log_error(f"Rollback failed: {rb_e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to save assessment log: {e}",
            }
        finally:
            if cursor:
                cursor.close()

    def save_generated_assessment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存生成的评估（问题集）。
        输入: {
            "assessment_id": "..." (可选, 否则自动生成),
            "assessment_type": "multiple_choice", "difficulty": "medium",
            "knowledge_point_ids": ["kp_1", "kp_2"],
            "questions": [{"question_text": "...", "options": [], "answer": ...}, ...],
            "generated_at": "YYYY-MM-DDTHH:MM:SSZ" (可选, 否则自动生成)
        }
        输出: {"status": "success", "assessment_id": "..."} 或 {"status": "error", "message": "..."}
        """
        assessment_id = payload.get("assessment_id", str(uuid.uuid4()))
        kp_ids_json = self.db_util.serialize(payload.get("knowledge_point_ids", []))
        questions_json = self.db_util.serialize(payload.get("questions", []))
        generated_at = payload.get(
            "generated_at", self.db_util.get_current_timestamp_iso()
        )

        if not payload.get("assessment_type") or not questions_json:
            return {"status": "error", "message": "assessment_type and questions are required."}


        query = """
        INSERT OR REPLACE INTO generated_assessments
        (assessment_id, assessment_type, difficulty, knowledge_point_ids, questions, generated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            assessment_id,
            payload.get("assessment_type"),
            payload.get("difficulty"),
            kp_ids_json,
            questions_json,
            generated_at,
        )

        success = self.db_util.execute_query(query, params, is_write=True)

        if success:
            self.monitoring_manager.log_info(
                f"Generated assessment {assessment_id} saved successfully."
            )
            return {"status": "success", "assessment_id": assessment_id}
        else:
            return {
                "status": "error",
                "message": f"Failed to save generated assessment {assessment_id}.",
            }

    def get_generated_assessment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取先前保存的生成的评估。
        输入: {"assessment_id": "..."}
        输出: {"status": "success", "data": {...}} 或 {"status": "error", "message": "..."}
        """
        assessment_id = payload.get("assessment_id")
        if not assessment_id:
            return {"status": "error", "message": "assessment_id is required"}

        query = "SELECT * FROM generated_assessments WHERE assessment_id = ?"
        assessment_data = self.db_util.execute_query(
            query, (assessment_id,), fetch_one=True
        )

        if assessment_data and isinstance(assessment_data, dict):
            assessment_data["knowledge_point_ids"] = self.db_util.deserialize(
                assessment_data.get("knowledge_point_ids")
            )
            assessment_data["questions"] = self.db_util.deserialize(
                assessment_data.get("questions")
            )
            return {"status": "success", "data": assessment_data}
        elif assessment_data is None:
            return {
                "status": "not_found",
                "message": f"Generated assessment with id {assessment_id} not found.",
            }
        else:
            self.monitoring_manager.log_error(
                f"Unexpected data type from db_util.execute_query for assessment_id {assessment_id}: {type(assessment_data)}"
            )
            return {
                 "status": "error",
                 "message": f"Error retrieving generated assessment {assessment_id}.",
            }


    def get_assessment_log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取特定评估或知识点的评估日志。
        输入: {"assessment_id": "...", "knowledge_point_id": "..." (可选)}
        输出: {"status": "success", "data": [{...}, ...]} 或 {"status": "error", "message": "..."}
        """
        assessment_id = payload.get("assessment_id")
        kp_id = payload.get("knowledge_point_id") # Optional

        if not assessment_id:
            return {"status": "error", "message": "assessment_id is required."}

        query_conditions = ["assessment_id = ?"]
        params: List[Any] = [assessment_id]

        if kp_id:
            query_conditions.append("knowledge_point_id = ?")
            params.append(kp_id)
        
        query = f"SELECT * FROM assessment_logs WHERE {' AND '.join(query_conditions)} ORDER BY timestamp DESC"
        
        log_data = self.db_util.execute_query(query, tuple(params))

        if log_data is not None and isinstance(log_data, list):
            return {"status": "success", "data": log_data}
        elif log_data is None: # Query execution failed
            return {"status": "error", "message": "Failed to retrieve assessment logs."}
        else: # Empty list if no logs found
            return {"status": "success", "data": []}
