# -*- coding: utf-8 -*-
"""模式控制器 (ModeController) 的主实现文件。

包含 ModeController 类，该类作为核心协调器，负责接收用户请求、
识别用户意图、管理和切换不同的学习模式（规划、学习、评估、复习），
并将请求路由到相应的模式模块进行处理。
"""
from typing import Any, Dict, Optional

from src.assessor_module.assessor_module import AssessorModule

# Import dependent modules and managers
from src.config_manager.config_manager import ConfigManager
from src.learner_module.learner_module import LearnerModule
from src.llm_interface.llm_interface import LLMInterface
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import MonitoringManager
from src.planner_module.planner_module import PlannerModule
from src.reviewer_module.reviewer_module import ReviewerModule
from src.update_manager.update_manager import UpdateManager


class ModeController:
    def __init__(
        self,
        config_manager: ConfigManager,
        monitoring_manager: MonitoringManager,
        memory_bank_manager: MemoryBankManager,
        llm_interface: LLMInterface,
        update_manager: UpdateManager,
    ):
        """
        Initializes the ModeController with all necessary manager dependencies.
        """
        self.config_manager = config_manager
        self.monitoring_manager = monitoring_manager
        self.memory_bank_manager = memory_bank_manager
        self.llm_interface = llm_interface
        self.update_manager = update_manager

        # Load default mode from config or set a fallback
        self.current_mode = self.config_manager.get_config(
            "mode_controller.default_mode", "learn"
        )
        self.monitoring_manager.log_info(
            f"ModeController initialized. Default mode set to: {self.current_mode}"
        )

        # Initialize mode modules with their specific dependencies
        self.planner_module = PlannerModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
        )
        self.learner_module = LearnerModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
            update_manager=self.update_manager,
        )
        self.assessor_module = AssessorModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
            update_manager=self.update_manager,
        )
        self.reviewer_module = ReviewerModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
        )

        self._mode_map: Dict[str, Any] = {
            "plan": self.planner_module,
            "learn": self.learner_module,
            "assess": self.assessor_module,
            "review": self.reviewer_module,
        }
        # Ensure the initial current_mode is valid
        if self.current_mode not in self._mode_map:
            self.monitoring_manager.log_warning(
                f"Initial default_mode '{self.current_mode}' from config is not a registered mode. Falling back to 'learn'."
            )
            self.current_mode = "learn"

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives requests from the API Gateway, determines/switches mode,
        and routes the request to the active mode module.

        Args:
            request: A dictionary containing the request details, e.g.,
                     {"session_id": "...", "user_input": "...", "current_mode": "..."}

        Returns:
            A dictionary containing the response from the active mode module, e.g.,
            {"session_id": "...", "response": {...}, "new_mode": "...", "timestamp": "..."}
        """
        session_id = request.get("session_id", "N/A")
        user_input = request.get("user_input", "")
        suggested_mode = request.get("current_mode")
        timestamp = request.get("timestamp", "")

        self.monitoring_manager.log_info(
            f"[{session_id}] Received request: {user_input[:50]}..."
        )

        target_mode = self._determine_mode(user_input, suggested_mode, session_id)

        if target_mode != self.current_mode:
            self._switch_mode(target_mode, session_id)

        response = self._route_request_to_mode(request)

        response["new_mode"] = self.current_mode
        response["session_id"] = session_id
        response["timestamp"] = timestamp

        self.monitoring_manager.log_info(
            f"[{session_id}] Request processed. New mode: {self.current_mode}"
        )
        return response

    def _determine_mode(
        self, user_input: str, suggested_mode: Optional[str], session_id: str
    ) -> str:
        """
        Determines the target mode based on user input, suggested mode, and configuration.
        """
        # Highest priority: explicit suggestion from the request
        if suggested_mode and suggested_mode in self._mode_map:
            self.monitoring_manager.log_info(
                f"[{session_id}] Mode determined by suggested_mode: {suggested_mode}"
            )
            return suggested_mode
        
        intent_rules = self.config_manager.get_config(
            "mode_controller.intent_recognition.rules", []
        )
        llm_intent_config = self.config_manager.get_config(
            "mode_controller.intent_recognition.llm"
        )

        if intent_rules:
            for rule in intent_rules:
                keywords = rule.get("keywords", [])
                mode = rule.get("mode")
                if any(keyword.lower() in user_input.lower() for keyword in keywords):
                    if mode in self._mode_map:
                        self.monitoring_manager.log_info(
                            f"[{session_id}] Mode determined by rule: {mode} (keywords: {keywords})"
                        )
                        return mode
                    else:
                        self.monitoring_manager.log_warning(
                            f"[{session_id}] Rule matched mode '{mode}' but it's not a registered mode."
                        )

        if llm_intent_config and llm_intent_config.get("enabled", False):
            prompt_template = llm_intent_config.get("prompt_template")
            if prompt_template:
                try:
                    prompt = prompt_template.format(
                        user_input=user_input, current_mode=self.current_mode
                    )
                    llm_determined_mode_response = self.llm_interface.generate_text(
                        prompt=prompt,
                        session_id=session_id,
                    )
                    llm_determined_mode = ""
                    if (
                        isinstance(llm_determined_mode_response, dict)
                        and llm_determined_mode_response.get("status") == "success"
                    ):
                        llm_determined_mode = (
                            llm_determined_mode_response.get("text", "").strip().lower()
                        )
                    elif isinstance(
                        llm_determined_mode_response, str
                    ):
                        llm_determined_mode = (
                            llm_determined_mode_response.strip().lower()
                        )

                    if llm_determined_mode in self._mode_map:
                        self.monitoring_manager.log_info(
                            f"[{session_id}] Mode determined by LLM: {llm_determined_mode}"
                        )
                        return llm_determined_mode
                    else:
                        self.monitoring_manager.log_warning(
                            f"[{session_id}] LLM returned invalid or unmatchable mode: '{llm_determined_mode}'. Falling back."
                        )
                except Exception as e:
                    self.monitoring_manager.log_error(
                        f"[{session_id}] Error during LLM intent recognition: {e}",
                        exc_info=True,
                    )
            else:
                self.monitoring_manager.log_warning(
                    f"[{session_id}] LLM intent recognition enabled but no prompt_template found in config."
                )

        # If no other determination, try to stay in current valid mode or use fallback
        default_fallback_mode = self.config_manager.get_config(
            "mode_controller.default_fallback_mode", "learn"
        )
        if self.current_mode in self._mode_map:
            self.monitoring_manager.log_info(
                f"[{session_id}] No specific intent matched. Staying in current mode: {self.current_mode}"
            )
            return self.current_mode

        self.monitoring_manager.log_info(
            f"[{session_id}] No specific intent matched and current mode invalid. Falling back to default: {default_fallback_mode}"
        )
        return (
            default_fallback_mode
            if default_fallback_mode in self._mode_map
            else "learn"
        )

    def _switch_mode(self, target_mode: str, session_id: str):
        """
        Switches the current mode to the target mode.
        Includes logging and state saving/loading logic.
        """
        if target_mode not in self._mode_map:
            self.monitoring_manager.log_error(
                f"[{session_id}] Attempted to switch to invalid or unregistered mode: {target_mode}"
            )
            return

        old_mode_name = self.current_mode
        old_mode_module = self._mode_map.get(old_mode_name)

        if old_mode_module and hasattr(old_mode_module, "get_mode_context"):
            try:
                context_to_save = old_mode_module.get_mode_context()
                if context_to_save is not None:
                    # Using a structured payload for save_learning_context
                    # The key for mode-specific context will be distinct.
                    mode_context_payload = {
                        "session_id": session_id,
                        "data_type": "mode_context",
                        "mode_name": old_mode_name,
                        "context": context_to_save,
                    }
                    # We'll use a session_id combined with mode name for the actual storage key
                    # if MemoryBankManager's save_learning_context doesn't directly support nested structures for session_id.
                    # For now, assuming save_learning_context can handle a payload that includes mode name.
                    # A more robust way might be to have a dedicated save_mode_session_data in MemoryBankManager.
                    # Let's use a simpler approach: store it under a specific key within the session's learning_context.

                    existing_session_context_resp = (
                        self.memory_bank_manager.get_learning_context(
                            {"session_id": session_id}
                        )
                    )
                    session_context_data = {}
                    if (
                        existing_session_context_resp["status"] == "success"
                        and existing_session_context_resp["data"]
                    ):
                        session_context_data = existing_session_context_resp["data"]

                    # Store the mode context under a specific key, e.g., "mode_contexts" -> "planner_context"
                    if "mode_contexts" not in session_context_data:
                        session_context_data["mode_contexts"] = {}
                    session_context_data["mode_contexts"][
                        old_mode_name
                    ] = context_to_save

                    # Ensure session_id is in the payload for save_learning_context
                    session_context_data["session_id"] = session_id

                    save_response = self.memory_bank_manager.save_learning_context(
                        session_context_data
                    )

                    if save_response.get("status") == "success":
                        self.monitoring_manager.log_info(
                            f"[{session_id}] Context for mode '{old_mode_name}' saved successfully."
                        )
                    else:
                        self.monitoring_manager.log_error(
                            f"[{session_id}] Failed to save context for mode '{old_mode_name}': {save_response.get('message')}"
                        )
            except Exception as e:
                self.monitoring_manager.log_error(
                    f"[{session_id}] Error calling get_mode_context for '{old_mode_name}': {e}",
                    exc_info=True,
                )

        self.monitoring_manager.log_info(
            f"[{session_id}] Switching mode from {old_mode_name} to {target_mode}"
        )
        self.current_mode = target_mode
        new_mode_module = self._mode_map.get(target_mode)

        if new_mode_module and hasattr(new_mode_module, "load_mode_context"):
            try:
                session_context_resp = self.memory_bank_manager.get_learning_context(
                    {"session_id": session_id}
                )
                if (
                    session_context_resp["status"] == "success"
                    and session_context_resp["data"]
                ):
                    session_data = session_context_resp["data"]
                    mode_contexts = session_data.get("mode_contexts", {})
                    context_to_load = mode_contexts.get(target_mode)

                    if context_to_load is not None:
                        new_mode_module.load_mode_context(context_to_load)
                        self.monitoring_manager.log_info(
                            f"[{session_id}] Context for mode '{target_mode}' loaded successfully."
                        )
                    else:
                        self.monitoring_manager.log_info(
                            f"[{session_id}] No saved context found for mode '{target_mode}'."
                        )
                else:
                    self.monitoring_manager.log_info(
                        f"[{session_id}] No general learning context found for session to load '{target_mode}' context from."
                    )
            except Exception as e:
                self.monitoring_manager.log_error(
                    f"[{session_id}] Error calling load_mode_context for '{target_mode}': {e}",
                    exc_info=True,
                )

    def _route_request_to_mode(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the request to the currently active mode module.
        """
        active_module = self._mode_map.get(self.current_mode)
        session_id = request.get("session_id", "N/A")
        request_type = request.get("request_type")
        payload = request.get("payload", {})

        if not active_module:
            default_fallback_mode = self.config_manager.get_config(
                "mode_controller.default_fallback_mode", "learn"
            )
            self.monitoring_manager.log_error(
                f"[{session_id}] No active module for current mode: {self.current_mode}. Attempting fallback to '{default_fallback_mode}'."
            )

            if default_fallback_mode in self._mode_map:
                self._switch_mode(default_fallback_mode, session_id)
                active_module = self._mode_map.get(self.current_mode)
                if not active_module:
                    self.monitoring_manager.log_error( # Changed from log_critical
                        f"[{session_id}] Fallback mode '{self.current_mode}' also has no module. Config error."
                    )
                    return {
                        "status": "error",
                        "message": f"Critical: Invalid mode: {self.current_mode}, fallback failed.",
                    }
            else:
                self.monitoring_manager.log_error( # Changed from log_critical
                    f"[{session_id}] Configured fallback mode '{default_fallback_mode}' is not registered. Critical config error."
                )
                return {
                    "status": "error",
                    "message": f"Critical: Fallback mode '{default_fallback_mode}' invalid.",
                }

        if not request_type:
            self.monitoring_manager.log_error(
                f"[{session_id}] Missing 'request_type' for mode {self.current_mode}."
            )
            return {
                "status": "error",
                "message": "Internal routing error: Missing 'request_type'.",
            }

        try:
            self.monitoring_manager.log_info(
                f"[{session_id}] Routing to {self.current_mode}.handle_request (type: {request_type})"
            )
            response = active_module.handle_request(session_id, request_type, payload)
            return response
        except AttributeError as ae:
            if "handle_request" in str(ae).lower():
                self.monitoring_manager.log_error(
                    f"[{session_id}] Module {self.current_mode} lacks 'handle_request'.",
                    exc_info=True,
                )
                return {
                    "status": "error",
                    "message": f"Config error: Handler not found for {self.current_mode}",
                }
            else:
                self.monitoring_manager.log_warning(
                    f"[{session_id}] Attribute error in {self.current_mode} (optional context method?): {ae}",
                    exc_info=True,
                )
                return {
                    "status": "error",
                    "message": f"Attribute error in {self.current_mode}: {str(ae)}",
                }
        except Exception as e:
            self.monitoring_manager.log_error(
                f"[{session_id}] Error in {self.current_mode}.handle_request: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Error in {self.current_mode}: {str(e)}",
            }
