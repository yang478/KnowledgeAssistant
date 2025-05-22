# -*- coding: utf-8 -*-
"""学习模块 (LearnerModule) 的主实现文件。

包含 LearnerModule 类，该类封装了处理用户学习请求（如提问、请求解释）、
与 LLM 交互、管理学习上下文等核心功能。
"""
import ast
import json
import re  # Added for sanitization
from datetime import datetime, timezone # Added for timestamping context updates
from typing import Optional, Dict, Any

from src.config_manager.config_manager import ConfigManager
from src.llm_interface.llm_interface import LLMInterface
# Import necessary dependencies
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import MonitoringManager
from src.update_manager.update_manager import UpdateManager


class LearnerModule:
    def __init__(self, memory_bank_manager: MemoryBankManager, llm_interface: LLMInterface,
                 config_manager: ConfigManager, monitoring_manager: MonitoringManager,
                 update_manager: UpdateManager):
        """
        Initializes the LearnerModule with its dependencies.

        Args:
            memory_bank_manager: An instance of MemoryBankManager.
            llm_interface: An instance of LLMInterface.
            config_manager: An instance of ConfigManager.
            monitoring_manager: An instance of MonitoringManager.
            update_manager: An instance of UpdateManager.
        """
        self.memory_bank_manager = memory_bank_manager
        self.llm_interface = llm_interface
        self.config_manager = config_manager
        self.monitoring_manager = monitoring_manager
        self.update_manager = update_manager
        self.monitoring_manager.log_info("LearnerModule initialized.")

    def handle_request(self, session_id: str, request_type: str, payload: dict) -> dict:
        """
        统一处理来自 ModeController 的学习请求。

        Args:
            session_id: 当前会话 ID。
            request_type: 请求类型 (e.g., "ask_question", "explain_topic", "next_step")。
            payload: 请求的具体数据。

        Returns:
            一个包含处理结果的字典。
        """
        # Basic validation
        if not session_id or not request_type:
            self.monitoring_manager.log_error("Invalid request: missing session_id or request_type.", {"payload": payload})
            return {
                "status": "error",
                "response": {"type": "error", "content": "Invalid request: missing session_id or request_type."},
                "context_updated": False
            }

        self.monitoring_manager.log_info(f"Handling request type: {request_type}", {"session_id": session_id})

        try:
            # 1. Get current learning context from MemoryBankManager
            context_request = {"operation": "get_learning_context", "payload": {"session_id": session_id}}
            context_response = self.memory_bank_manager.process_request(context_request)

            # Handle cases where context might not be found (e.g., new session)
            if context_response.get("status") == "not_found":
                 self.monitoring_manager.log_info(f"Learning context not found for session {session_id}, creating default.", {"session_id": session_id})
                 learning_context = {"session_id": session_id, "current_topics": [], "unresolved_questions": [], "session_goals": None}
                 # Optionally save the new default context immediately
                 # save_req = {"operation": "save_learning_context", "payload": learning_context}
                 # self.memory_bank_manager.process_request(save_req)
            elif context_response.get("status") != "success":
                error_msg = f"Failed to get learning context: {context_response.get('message', 'Unknown error')}"
                self.monitoring_manager.log_error(error_msg, {"session_id": session_id})
                return {"status": "error", "response": {"type": "error", "content": error_msg}, "context_updated": False}
            else:
                learning_context = context_response.get("data", {})

            # 2. Build LLM prompt
            llm_prompt = self._build_llm_prompt(request_type, payload, learning_context)
            if llm_prompt is None: # Handle error during prompt building (e.g., KP fetch failed)
                 # Error already logged in _build_llm_prompt
                 return {"status": "error", "response": {"type": "error", "content": "Failed to build LLM prompt."}, "context_updated": False}

            # 3. Call LLMInterface
            # Get model config from ConfigManager based on request_type or context
            llm_config_key = f"learner.llm_config.{request_type}"
            default_llm_config_key = "learner.llm_config.default"
            llm_model_config = self.config_manager.get_config(llm_config_key, self.config_manager.get_config(default_llm_config_key, {}))

            llm_request = {"prompt": llm_prompt, "model_config": llm_model_config}
            self.monitoring_manager.log_debug(f"Sending prompt to LLM (first 200 chars): {llm_prompt[:200]}...", {"session_id": session_id, "model_config": llm_model_config})
            llm_response = self.llm_interface.generate_text(llm_request)

            if llm_response.get("status") != "success":
                error_msg = f"LLM request failed: {llm_response.get('message', 'Unknown error')}"
                self.monitoring_manager.log_error(error_msg, {"session_id": session_id})
                return {"status": "error", "response": {"type": "error", "content": error_msg}, "context_updated": False}

            llm_output = llm_response.get("data", {}).get("text", "")
            if not llm_output:
                 self.monitoring_manager.log_warning("LLM returned empty output.", {"session_id": session_id})
                 # Return specific message instead of error?
                 return {
                     "status": "success", # Or maybe "warning"?
                     "response": {"type": "info", "content": "I received an empty response, could you please rephrase?"},
                     "context_updated": False
                 }

            # 4. Parse LLM output
            response_content, follow_up_questions = self._parse_llm_output(request_type, llm_output)

            # 5. Update learning context in MemoryBankManager
            context_updated = self._update_learning_context(
                session_id=session_id,
                request_type=request_type,
                request_payload=payload,
                llm_response_content=response_content,
                follow_up_questions=follow_up_questions,
                current_context=learning_context
            )

            # 6. Call UpdateManager if needed
            if context_updated and request_type in ["explain_topic", "provide_example"]:
                topic_id = payload.get("topic_id")
                if topic_id:
                    update_payload = {
                        "session_id": session_id,
                        "topic_id": topic_id,
                        "reason": f"Learner completed interaction with topic: {topic_id}"
                    }
                    self.monitoring_manager.log_info(
                        f"Triggering backup after learner interaction with topic {topic_id}.",
                        {"session_id": session_id, "request_type": request_type}
                    )
                    self.update_manager.trigger_backup(event="learner_topic_interaction_completed", payload=update_payload)

            # 7. Construct final response
            response_data = {
                "type": self._determine_response_type(request_type),
                "content": response_content,
                "follow_up_questions": follow_up_questions
            }

            self.monitoring_manager.log_info(f"Request type {request_type} processed successfully.", {"session_id": session_id})
            return {
                "status": "success",
                "response": response_data,
                "context_updated": context_updated
            }

        except Exception as e:
            self.monitoring_manager.log_error(f"Unhandled exception in LearnerModule.handle_request: {e}", {"session_id": session_id}, exc_info=True)
            return {
                "status": "error",
                "response": {"type": "error", "content": f"An internal server error occurred in LearnerModule."},
                "context_updated": False
            }

    def _sanitize_input(self, text: str) -> str:
        """
        Basic sanitization to remove potentially harmful characters or sequences.
        """
        if not isinstance(text, str):
            return ""
        sanitized = re.sub(r'[^\w\s.,!?-]', '', text, flags=re.UNICODE)
        max_len = self.config_manager.get_config("learner.sanitize.max_input_length", 500)
        return sanitized[:max_len]

    def _build_llm_prompt(self, request_type: str, payload: dict, learning_context: dict) -> str | None:
        """
        Builds the prompt for the LLM based on request type, payload, context, and config templates.
        Returns the prompt string or None if an error occurs.
        """
        # Get prompt template from ConfigManager
        template_key = f"learner.prompt_templates.{request_type}"
        default_template_key = "learner.prompt_templates.default"
        prompt_template = self.config_manager.get_config(template_key, self.config_manager.get_config(default_template_key, ""))

        if not prompt_template:
            self.monitoring_manager.log_error(f"Prompt template not found for request type '{request_type}' or default.", {"template_key": template_key})
            return None

        try:
            # Prepare context string (handle potential serialization issues)
            context_str = json.dumps(learning_context, indent=2, ensure_ascii=False)
        except TypeError:
            context_str = "{Error serializing context}"
            self.monitoring_manager.log_warning("Could not serialize learning context for prompt.", {"context": learning_context})

        # Prepare specific inputs based on request type
        prompt_inputs = {
            "learning_context": context_str,
            "user_input": "",
            "topic_id": "",
            "topic_title": "",
            "topic_content": "",
            "request_type": request_type,
        }

        if request_type == "ask_question":
            raw_question = payload.get("text", "")
            prompt_inputs["user_input"] = self._sanitize_input(raw_question)
            # TODO: Fetch relevant KPs based on question and add to prompt_inputs

        elif request_type == "explain_topic" or request_type == "provide_example":
            topic_id = payload.get("topic_id")
            if not topic_id:
                 self.monitoring_manager.log_error(f"Missing topic_id in {request_type} request payload.", {"payload": payload})
                 return None

            # Fetch topic content from MemoryBankManager
            kp_request = {"operation": "get_knowledge_point", "payload": {"knowledge_point_id": topic_id}}
            kp_response = self.memory_bank_manager.process_request(kp_request)

            if kp_response.get("status") == "success" and kp_response.get("data"):
                prompt_inputs["topic_id"] = topic_id
                prompt_inputs["topic_title"] = kp_response["data"].get("title", topic_id)
                prompt_inputs["topic_content"] = kp_response["data"].get("content", "No content available.")
                prompt_inputs["user_input"] = f"Explain topic: {prompt_inputs['topic_title']}" if request_type == "explain_topic" else f"Provide example for topic: {prompt_inputs['topic_title']}"
            else:
                error_msg = f"Failed to retrieve content for topic {topic_id} for {request_type}: {kp_response.get('message', 'Unknown error')}"
                self.monitoring_manager.log_error(error_msg, {"topic_id": topic_id})
                return None # Cannot build prompt if topic content fails

        elif request_type == "next_step":
             prompt_inputs["user_input"] = "Suggest the next learning step."
             # TODO: Fetch progress/status data to inform suggestion and add to prompt_inputs

        else:
            # Add the missing details dictionary as the second argument
            self.monitoring_manager.log_warning(f"Building prompt for unknown request type: {request_type}", {"request_type": request_type})
            prompt_inputs["user_input"] = f"Unknown request: {request_type}"

        # Build the prompt using the template and inputs
        try:
            # Basic f-string formatting (can be replaced with more robust templating if needed)
            prompt = prompt_template.format(**prompt_inputs)
        except KeyError as e:
            self.monitoring_manager.log_error(f"Missing key in prompt template '{template_key}': {e}", {"inputs": prompt_inputs})
            return None
        except Exception as e:
             self.monitoring_manager.log_error(f"Error formatting prompt template '{template_key}': {e}", {"inputs": prompt_inputs}, exc_info=True)
             return None

        # Add standard instruction for follow-up questions (could also be part of the template)
        follow_up_instruction = self.config_manager.get_config("learner.prompt_templates.follow_up_instruction",
                                                               "\n\nAlso, suggest 2-3 relevant follow-up questions the user might have, formatted as a JSON list string on a new line starting with 'Follow-up questions: '.")
        prompt += follow_up_instruction

        return prompt

    def _parse_llm_output(self, request_type, llm_output: str):
        """
        Parses the LLM output string to extract the main content and follow-up questions.
        """
        if not llm_output:
            return "", []

        lines = llm_output.strip().split('\n')
        content_lines = []
        follow_up_questions = []
        follow_up_line_prefix = "Follow-up questions:"

        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line.startswith(follow_up_line_prefix):
                content_lines = lines[:i] # Lines before this are content
                q_list_str = stripped_line[len(follow_up_line_prefix):].strip()
                try:
                    parsed_q = json.loads(q_list_str)
                    if isinstance(parsed_q, list):
                        follow_up_questions = parsed_q
                    else:
                         self.monitoring_manager.log_warning("Parsed follow-up questions is not a list.", {"parsed": parsed_q})
                except json.JSONDecodeError:
                    if q_list_str.startswith('[') and q_list_str.endswith(']'):
                        try:
                            parsed_q = ast.literal_eval(q_list_str)
                            if isinstance(parsed_q, list):
                                follow_up_questions = parsed_q
                            else:
                                self.monitoring_manager.log_warning("literal_eval parsed follow-up questions is not a list.", {"parsed": parsed_q})
                        except (ValueError, SyntaxError, TypeError) as e:
                            self.monitoring_manager.log_warning(f"Failed to parse follow-up questions using literal_eval: {e}", {"line": line})
                    else:
                         self.monitoring_manager.log_warning("Follow-up questions line does not look like a JSON or Python list.", {"line": line})
                break # Stop processing lines after finding the follow-up line
        else: # If loop completes without break (no follow-up line found)
            content_lines = lines

        # Join content lines, stripping extra whitespace
        content = "\n".join(line.strip() for line in content_lines).strip()

        # Basic validation/cleaning of parsed questions
        follow_up_questions = [str(q) for q in follow_up_questions if isinstance(q, (str, int, float))]

        return content, follow_up_questions

    def _determine_response_type(self, request_type):
        """Determines the response type based on the request type."""
        if request_type == "ask_question" or request_type == "explain_topic":
            return "explanation"
        elif request_type == "next_step":
            return "suggestion"
        else:
            return "info" # Default type

    def _update_learning_context(self, session_id: str, request_type: str, request_payload: dict,
                                 llm_response_content: str, follow_up_questions: list,
                                 current_context: dict) -> bool:
        """
        Updates the learning context in the Memory Bank after an interaction.

        Args:
            session_id: The current session ID.
            request_type: The type of the user request.
            request_payload: The payload of the user request.
            llm_response_content: The main content generated by the LLM.
            follow_up_questions: Suggested follow-up questions from the LLM.
            current_context: The learning context before this interaction.

        Returns:
            True if the context was updated successfully, False otherwise.
        """
        updated_context = current_context.copy() # Start with the existing context

        # Add structured interaction log entry
        interaction_log = updated_context.get("interaction_history", [])
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"

        log_entry = {
            "timestamp": timestamp,
            "request_type": request_type,
            "user_input": None,
            "topic_id": None,
            "llm_response": llm_response_content,
            "follow_up_questions": follow_up_questions,
            "related_topics": [], # TODO: Extract related topics if possible
            "unresolved": False # TODO: Add logic to mark if question seems unresolved
        }

        if request_type == "ask_question":
            log_entry["user_input"] = request_payload.get("text")
        elif request_type == "explain_topic" or request_type == "provide_example":
            log_entry["topic_id"] = request_payload.get("topic_id")
            log_entry["user_input"] = f"{request_type}: {log_entry['topic_id']}"
        elif request_type == "next_step":
            log_entry["user_input"] = "Request next step"

        interaction_log.append(log_entry)
        updated_context["interaction_history"] = interaction_log[-self.config_manager.get_config("learner.context.history_limit", 10):] # Limit history size

        # Update other context fields (example)
        updated_context["last_interaction_timestamp"] = timestamp
        if request_type == "explain_topic" or request_type == "provide_example":
             current_topics = updated_context.get("current_topics", [])
             topic_id = request_payload.get("topic_id")
             if topic_id and topic_id not in current_topics:
                 current_topics.append(topic_id)
                 updated_context["current_topics"] = current_topics

        # TODO: Refine logic for managing unresolved_questions based on interaction/response

        # Save the updated context
        # Using 'save_learning_context' assuming it performs an upsert.
        # Documented in decisionLog.md if this assumption holds.
        update_context_request = {
            "operation": "save_learning_context",
            "payload": updated_context
        }
        self.monitoring_manager.log_debug("Updating learning context in MBM.", {"session_id": session_id})
        update_context_response = self.memory_bank_manager.process_request(update_context_request)

        if update_context_response.get("status") == "success":
            self.monitoring_manager.log_info("Learning context updated successfully.", {"session_id": session_id})
            return True
        else:
            self.monitoring_manager.log_warning(
                f"Failed to update learning context: {update_context_response.get('message', 'Unknown error')}",
                {"session_id": session_id}
            )
            return False

    def get_mode_context(self) -> Optional[Dict[str, Any]]:
        """
        Gathers context from the LearnerModule that might be useful to save.
        This could include recent interaction history or current topics.
        """
        # This is a simplified example. In a real scenario, you'd fetch the actual
        # learning_context for the current session if it's stored within the module instance,
        # or decide what specific parts of the module's state are relevant.
        # For now, as context is primarily managed via MBM per interaction,
        # this might return specific transient state if any.
        # self.monitoring_manager.log_info("LearnerModule.get_mode_context called.")
        # # Example: if self.current_session_context:
        # # return {"interaction_history": self.current_session_context.get("interaction_history", [])[-5:]} # last 5 interactions
        # return {"message": "LearnerModule context placeholder, actual context is managed per interaction via MBM."}
        pass

    def load_mode_context(self, context_data: Dict[str, Any]) -> None:
        """
        Loads context into the LearnerModule.
        This might involve setting up internal state based on the provided context.
        """
        # self.monitoring_manager.log_info(f"LearnerModule.load_mode_context called with data: {context_data}")
        # # Example: self.current_session_context = context_data # Or merge specific fields
        # # For now, no specific state to load directly into the module instance this way,
        # # as context is loaded from MBM at the beginning of each handle_request.
        pass
