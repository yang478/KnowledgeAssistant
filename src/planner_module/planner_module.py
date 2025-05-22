# -*- coding: utf-8 -*-
"""规划模块 (PlannerModule) 的主实现文件。

包含 PlannerModule 类，该类封装了学习计划的制定与管理功能，
包括分析用户目标、从记忆库获取知识点和进度信息、
应用规划策略生成学习步骤、以及分析当前学习进度。
"""
import json
from typing import Any, Dict, Optional

from src.config_manager.config_manager import ConfigManager
from src.llm_interface.llm_interface import LLMInterface
# 导入依赖模块（假设这些模块已经存在或将要实现）
# 导入依赖模块
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import \
    MonitoringManager  # Import MonitoringManager


class PlannerModule:
    def __init__(self,
                 memory_bank_manager: MemoryBankManager,
                 llm_interface: LLMInterface,
                 config_manager: ConfigManager,
                 monitoring_manager: MonitoringManager): # Add monitoring_manager
        self.memory_bank_manager = memory_bank_manager
        self.llm_interface = llm_interface
        self.config_manager = config_manager
        self.monitoring_manager = monitoring_manager # Store monitoring_manager
        self.monitoring_manager.log_info("PlannerModule initialized.")

    def handle_request(self, session_id: str, request_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一处理来自 ModeController 的请求。

        Args:
            session_id: 当前会话 ID。
            request_type: 请求类型 (e.g., "generate_plan")。
            payload: 请求的具体数据。

        Returns:
            包含处理结果的字典。
        """
        if request_type == "generate_plan":
            return self._generate_plan(session_id, payload)
        # elif request_type == "analyze_progress":
        #     # return self._analyze_progress(session_id, payload)
        #     pass
        else:
            self.monitoring_manager.log_warning(
                f"Unsupported request type received: {request_type}",
                {"session_id": session_id, "request_type": request_type}
            )
            return {
                "status": "error",
                "message": f"Unsupported request type for PlannerModule: {request_type}"
            }

    def generate_study_plan(self, session_id: str, user_input: str, current_mode_name: str) -> Dict[str, Any]:
        """
        Public method to generate a study plan, called by ModeController.

        Args:
            session_id: Current session ID.
            user_input: The user's input, typically representing their goal.
            current_mode_name: The current mode name (passed by ModeController, unused here directly but good for consistency).

        Returns:
            A dictionary containing the study plan or an error.
        """
        self.monitoring_manager.log_info(
            f"PlannerModule.generate_study_plan called for session {session_id}",
            context={"user_input": user_input, "current_mode_name": current_mode_name}
        )
        payload = {
            "goal": user_input,
            # Add other potential parameters extracted from user_input or mode_name if needed
            # e.g., timeframe, specific KPs
        }
        return self._generate_plan(session_id, payload)

    def _generate_plan(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据用户目标和当前学习状态生成学习计划 (内部辅助方法)。
        参考 developer_handbook/03_PlannerModule.md

        Args:
            session_id: 当前会话 ID。
            payload: 包含 goal, timeframe, knowledge_point_ids, replan 等信息的请求数据字典。

        Returns:
            包含学习计划详情的字典。
        """
        self.monitoring_manager.log_info(f"Generating plan for session {session_id}", payload)
        goal = payload.get("goal")
        # timeframe = payload.get("timeframe") # Currently unused for logic, but could be for summary
        # target_kp_ids = payload.get("knowledge_point_ids") # Currently unused filter
        # replan = payload.get("replan", False) # Currently unused

        # --- 1. 获取所需数据 ---
        # 获取所有知识点 (包含状态、依赖等)
        kp_response = self.memory_bank_manager.process_request(
            "get_all_kps", # Changed from get_all_syllabus_topics
            {}
        )
        if kp_response.get("status") != "success":
            error_msg = f"Failed to retrieve knowledge points from MemoryBankManager: {kp_response.get('message', 'Unknown error')}"
            self.monitoring_manager.log_error(error_msg, {"session_id": session_id})
            return {"status": "error", "message": error_msg}
        all_kps_dict = {kp['id']: kp for kp in kp_response.get("data", []) if kp.get('id')}
        if not all_kps_dict:
            self.monitoring_manager.log_warning("No knowledge points found to generate plan.", {"session_id": session_id})
            return {"status": "success", "data": {"plan_id": f"plan_{session_id}_empty", "steps": [], "summary": "知识库为空，无法生成计划。"}}

        # 获取评估历史 (假设接口存在)
        assessment_log_response = self.memory_bank_manager.process_request(
            "get_al", # Changed from get_assessment_log
            {"session_id": session_id} # Or maybe filter by user_id if available
        )
        assessment_log = {}
        if assessment_log_response.get("status") == "success":
            # 假设返回格式为 {kp_id: [{"timestamp": ..., "score": ..., "passed": ...}]}
            assessment_log = assessment_log_response.get("data", {})
            self.monitoring_manager.log_debug(f"Retrieved assessment log for {len(assessment_log)} KPs.", {"session_id": session_id})
        else:
            self.monitoring_manager.log_warning(
                f"Failed to retrieve assessment log: {assessment_log_response.get('message', 'Unknown error')}. Proceeding without it.",
                {"session_id": session_id}
            )

        # 获取规划配置
        config = {
            "strategy": self.config_manager.get_config("planner.strategy", "default"),
            "priority_weights": self.config_manager.get_config("planner.priority.weights", {
                "status_learning": 5, "status_not_started": 3, "status_mastered": -5, # Base weights by status
                "recent_fail": 10, "recent_pass": -2, # Assessment impact
                "dependency_unmet": -100, # Strong penalty if prerequisites not met
                "importance": 1 # Weight for KP's inherent importance (if exists)
            }),
            "time_estimates": self.config_manager.get_config("planner.time_estimates", {
                "learn_default": "1h", "review_default": "30m", "practice_default": "45m", "assess_default": "15m"
            }),
            "mastery_threshold": self.config_manager.get_config("planner.mastery_threshold", 0.8) # Example threshold
        }
        self.monitoring_manager.log_debug(f"Using planning config: {config['strategy']}", {"session_id": session_id})

        # --- 2. (可选) LLM 分析目标 ---
        # TODO: Implement goal analysis if needed

        # --- 3. 计算优先级、确定动作、估算时间 ---
        processed_kps = []
        for kp_id, kp_data in all_kps_dict.items():
            # 检查依赖是否满足 (基于当前批次中其他KP的状态)
            dependencies_met = self._check_dependencies(kp_data, all_kps_dict, config["mastery_threshold"])

            priority = self._calculate_priority(kp_data, assessment_log.get(kp_id, []), config, dependencies_met)
            action = self._determine_action(kp_data, assessment_log.get(kp_id, []), config["mastery_threshold"])
            estimated_time = self._estimate_time(kp_data, action, config["time_estimates"])

            processed_kps.append({
                "knowledge_point_id": kp_id,
                "title": kp_data.get("title", "Untitled"),
                "action": action,
                "estimated_time": estimated_time,
                "priority": priority,
                "status": kp_data.get("status", "not_started"), # Use 'status' or 'mastery_level'
                "dependencies": kp_data.get("dependencies", []), # Keep dependencies for sorting
                "dependencies_met": dependencies_met
            })

        # --- 4. 排序和过滤步骤 ---
        # 优先处理依赖未满足但优先级高的（可能指示需要先学依赖），然后按优先级降序
        # 过滤掉优先级极低的（例如已掌握且近期评估通过）
        # 简单的排序：优先处理依赖满足的，然后按优先级降序
        sorted_steps = sorted(
            [kp for kp in processed_kps if kp["priority"] > -50], # Filter out very low priority items
            key=lambda x: (not x["dependencies_met"], -x["priority"]) # Sort by unmet dependencies first (False < True), then by descending priority
        )

        # --- 5. 生成摘要 ---
        # TODO: Improve summary generation, potentially using LLM
        step_titles = [step['title'] for step in sorted_steps[:5]] # Show first 5 titles
        summary = f"为您生成的学习计划包含 {len(sorted_steps)} 个步骤。"
        if goal:
            summary += f" 目标是 '{goal}'。"
        if step_titles:
            summary += f" 建议首先关注: {', '.join(step_titles)}..."

        # --- 6. 返回结果 ---
        plan_id = f"plan_{session_id}_{hash(json.dumps(sorted_steps))}" # More stable ID based on content
        response_data = {
            "plan_id": plan_id,
            "steps": sorted_steps, # Return the sorted and filtered steps
            "summary": summary
        }
        self.monitoring_manager.log_info(f"Generated plan {plan_id} with {len(sorted_steps)} steps.", {"session_id": session_id})

        # --- 7. (可选) 保存计划 ---
        # self.memory_bank_manager.process_request({"operation": "save_plan", "payload": response_data})

        return {
            "status": "success",
            "data": response_data
        }

    def _check_dependencies(self, kp_data: Dict, all_kps: Dict, mastery_threshold: float) -> bool:
        """检查知识点的依赖是否都已满足"""
        dependencies = kp_data.get("dependencies", [])
        if not dependencies:
            return True
        for dep_id in dependencies:
            dep_kp = all_kps.get(dep_id)
            # 如果依赖项不存在或未达到掌握阈值，则认为依赖未满足
            # TODO: Refine status check - use 'mastery_level' if available
            if not dep_kp or dep_kp.get("status") != "mastered":
                 # Or check: dep_kp.get("mastery_level", 0) < mastery_threshold
                return False
        return True

    def _calculate_priority(self, kp_data: Dict, kp_assessment_log: list, config: Dict, dependencies_met: bool) -> int:
        """计算知识点的动态优先级"""
        weights = config["priority_weights"]
        base_priority = kp_data.get("priority", 3) # Use inherent priority if available
        importance_weight = weights.get("importance", 1)
        priority = base_priority * importance_weight

        status = kp_data.get("status", "not_started")
        # TODO: Use mastery_level if available: mastery = kp_data.get("mastery_level", 0)

        # 依赖惩罚
        if not dependencies_met:
            priority += weights.get("dependency_unmet", -100)
            # If dependencies are not met, significantly lower priority unless it's the *next* thing to learn
            # Maybe return early if penalty is huge?
            if weights.get("dependency_unmet", -100) <= -100:
                 return priority # Don't calculate further if blocked by dependencies

        # 状态权重
        if status == "learning":
            priority += weights.get("status_learning", 5)
        elif status == "not_started":
            priority += weights.get("status_not_started", 3)
        elif status == "mastered":
            priority += weights.get("status_mastered", -5)

        # 评估历史影响 (检查最近一次评估)
        if kp_assessment_log:
            last_assessment = sorted(kp_assessment_log, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
            if last_assessment.get("passed") is False: # Explicitly check for False
                priority += weights.get("recent_fail", 10)
            elif last_assessment.get("passed") is True:
                priority += weights.get("recent_pass", -2)

        # TODO: Add recency factor (last_reviewed_at) if available

        return int(priority) # Return integer priority

    def _determine_action(self, kp_data: Dict, kp_assessment_log: list, mastery_threshold: float) -> str:
        """根据状态和评估历史确定建议动作"""
        status = kp_data.get("status", "not_started")
        # TODO: Use mastery_level if available: mastery = kp_data.get("mastery_level", 0)

        last_assessment_passed = None
        if kp_assessment_log:
            last_assessment = sorted(kp_assessment_log, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
            last_assessment_passed = last_assessment.get("passed")

        if status == "not_started":
            return "学习"
        elif status == "learning":
            if last_assessment_passed is False:
                return "复习" # Failed assessment while learning -> Review
            elif last_assessment_passed is True:
                return "练习" # Passed assessment while learning -> Practice
            else:
                return "复习" # Still learning, no recent assessment -> Review/Continue Learning
        elif status == "mastered":
             # TODO: Add recency check - if mastered long ago, suggest review/assess
            if last_assessment_passed is False:
                 return "复习" # Mastered but failed recent assessment? -> Review needed
            else:
                 return "评估" # Mastered, maybe assess again or practice advanced topics
        else: # Unknown status
            return "学习"

    def _estimate_time(self, kp_data: Dict, action: str, time_estimates: Dict) -> str:
        """估算完成动作所需的时间"""
        # TODO: Could be more sophisticated based on kp_data complexity, type etc.
        action_lower = action.lower()
        if f"{action_lower}_default" in time_estimates:
            return time_estimates[f"{action_lower}_default"]
        elif "learn_default" in time_estimates: # Fallback to learn time
             return time_estimates["learn_default"]
        else:
            return "未知" # Default fallback

    # 实际中可能还需要其他方法，如 _analyze_progress, _manage_syllabus 等
    # def _analyze_progress(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    #     pass
    #
    # def _manage_syllabus(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    #     pass

    def get_mode_context(self) -> Optional[Dict[str, Any]]:
        """
        Gathers context from the PlannerModule that might be useful to save.
        For PlannerModule, this might include the last generated plan ID or summary.
        """
        # Example: return {"last_plan_id": self.last_plan_id, "last_plan_summary": self.last_plan_summary}
        # For now, returning None as no specific state is being tracked for saving.
        self.monitoring_manager.log_info("PlannerModule.get_mode_context called.")
        return None

    def load_mode_context(self, context_data: Dict[str, Any]) -> None:
        """
        Loads context into the PlannerModule.
        """
        # Example: self.last_plan_id = context_data.get("last_plan_id")
        self.monitoring_manager.log_info(f"PlannerModule.load_mode_context called with data: {context_data}")
        # For now, no specific state to load.
        pass
