# -*- coding: utf-8 -*-
"""复习模块 (ReviewerModule) 的主实现文件。

包含 ReviewerModule 类，该类封装了与知识复习相关的功能，
包括根据复习策略（如间隔重复）生成复习建议、
从记忆库获取知识点内容、以及提供格式化的复习材料。
"""
import datetime
import math
# src/reviewer_module/reviewer_module.py
from typing import Any, Dict, List, Optional

from src.config_manager.config_manager import ConfigManager
from src.llm_interface.llm_interface import LLMInterface
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import MonitoringManager


class ReviewerModule:
    """
    Handles review logic, suggesting content based on forgetting curves,
    assessment results, etc., and providing review materials.
    """
    def __init__(self,
                 memory_bank_manager: MemoryBankManager,
                 llm_interface: LLMInterface,
                 config_manager: ConfigManager,
                 monitoring_manager: MonitoringManager):
        """
        Initializes the ReviewerModule.

        Args:
            memory_bank_manager: Instance of MemoryBankManager.
            llm_interface: Instance of LLMInterface.
            config_manager: Instance of ConfigManager.
            monitoring_manager: Instance of MonitoringManager.
        """
        self.memory_bank_manager = memory_bank_manager
        self.llm_interface = llm_interface
        self.config_manager = config_manager
        self.monitoring_manager = monitoring_manager

        self.review_config = self._load_review_config()
        self.monitoring_manager.log_info("ReviewerModule initialized.")

    def _load_review_config(self) -> Dict:
        """Loads review strategy configurations from ConfigManager."""
        self.monitoring_manager.log_debug("Loading review config.", context={"module": "ReviewerModule"}) # Changed to log_debug
        default_config = {
            "default_strategy": "weighted_sum_v1",
            "max_suggestions": 5,
            "llm_summary_prompt_template": "Provide a concise review summary for the topic: {title}\nContent:\n{content}",
            "llm_questions_prompt_template": "Generate 2-3 key review questions for the topic: {title}\nContent:\n{content}",
            "llm": {
                "summary_max_tokens": 150,
                "questions_max_tokens": 100
            },
            "defaults": {
                "assessment_score_if_missing": 100,
                "time_decay_penalty_factor_on_error": 0.5
            },
            "strategies": {
                "weighted_sum_v1": {
                    "weights": {
                        "time_since_last_review": 0.4,
                        "assessment_performance": 0.3,
                        "knowledge_point_priority": 0.2,
                        "status_learning": 0.1
                    },
                    "status_boosts": {
                        "learning": 1.0,
                        "review": 0.8
                    },
                    "mastered_recent_review_dampening_factor": 0.5,
                    "ebbinghaus_half_life_days": 2,
                    "max_time_decay_score": 1.0,
                    "assessment_score_normalization_factor": 100.0
                }
            }
        }
        # Attempt to load from ConfigManager, fall back to defaults if not found or error
        try:
            config_from_file = self.config_manager.get_config("reviewer_module")
            if not config_from_file: # If 'reviewer_module' key doesn't exist or is empty
                self.monitoring_manager.log_warning("Reviewer module config not found in ConfigManager, using defaults.", context={"module": "ReviewerModule"})
                return default_config
            
            # Deep merge: config_from_file overrides defaults
            # Start with a deep copy of defaults to avoid modifying the original default_config dict
            import copy
            merged_config = copy.deepcopy(default_config)
            
            def _deep_merge_dicts(target, source):
                for key, value in source.items():
                    if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                        _deep_merge_dicts(target[key], value)
                    else:
                        # Source overrides target for non-dicts or if target key is not a dict,
                        # or if target does not have the key.
                        target[key] = copy.deepcopy(value) if isinstance(value, (dict, list)) else value

            _deep_merge_dicts(merged_config, config_from_file) # Merge loaded config into the default_config copy
            
            return merged_config
        except Exception as e:
            self.monitoring_manager.log_error(f"Error loading reviewer_module config: {e}. Using defaults.", context={"module": "ReviewerModule"}, exc_info=True)
            return default_config

    def handle_request(self, session_id: str, request_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一处理来自 ModeController 的复习请求。

        Args:
            session_id: 当前会话 ID。
            request_type: 请求类型 (e.g., "get_suggestions", "provide_material")。
            payload: 请求的具体数据。

        Returns:
            包含处理结果的字典。
        """
        self.monitoring_manager.log_info(f"Processing review request: {request_type}", context={"module": "ReviewerModule", "session_id": session_id})
        if request_type == "get_suggestions":
            max_items = payload.get("max_items", self.review_config.get("max_suggestions", 5))
            return self._get_review_suggestions(session_id, max_items)
        elif request_type == "provide_material":
            knowledge_point_id = payload.get("knowledge_point_id")
            if not knowledge_point_id:
                self.monitoring_manager.log("warning", "knowledge_point_id missing in provide_material request.", {"module": "ReviewerModule", "session_id": session_id})
                return {"status": "error", "message": "knowledge_point_id is required for provide_material."}
            return self._provide_review_material(session_id, knowledge_point_id)
        else:
            self.monitoring_manager.log("warning", f"Unsupported review request type: {request_type}", {"module": "ReviewerModule", "session_id": session_id})
            return {"status": "error", "message": f"Unsupported review request type: {request_type}"}

    def _get_review_suggestions(self, session_id: str, max_items: int) -> Dict[str, Any]:
        """
        Generates a list of knowledge points recommended for review (internal method).

        Args:
            session_id: The session ID.
            max_items: Maximum number of suggestions to return.

        Returns:
            A dictionary containing the list of suggestions.
        """
        self.monitoring_manager.log_debug(f"Getting review suggestions for session {session_id}, max_items={max_items}", context={"module": "ReviewerModule"})
        try:
            # 1. Get all relevant knowledge points from MemoryBankManager
            # Using get_all_syllabus_topics as per developer_handbook
            mbm_response_kps = self.memory_bank_manager.process_request({"operation": "get_all_syllabus_topics"})
            
            if mbm_response_kps["status"] != "success":
                self.monitoring_manager.log_error(f"Failed to get syllabus topics from MBM: {mbm_response_kps.get('message')}", context={"module": "ReviewerModule", "session_id": session_id})
                return {"status": "error", "message": f"Failed to get syllabus topics: {mbm_response_kps.get('message', 'Unknown error')}"}

            all_kps = mbm_response_kps.get("data", [])
            if not isinstance(all_kps, list): # Ensure data is a list
                all_kps = all_kps.get("topics", []) if isinstance(all_kps, dict) else []

            self.monitoring_manager.log_debug(f"Received {len(all_kps)} KPs from MBM.", context={"module": "ReviewerModule", "session_id": session_id})

            # Optionally, get assessment log for more detailed performance data
            # mbm_response_assessments = self.memory_bank_manager.process_request({"operation": "get_assessment_log", "payload": {"session_id": session_id}})
            # assessment_log = mbm_response_assessments.get("data", []) if mbm_response_assessments["status"] == "success" else []
            # For simplicity, we'll rely on last_assessed_score from KP data for now.

            suggestions_with_priority = []
            current_time_utc = datetime.datetime.now(datetime.timezone.utc)
            
            strategy_name = self.review_config.get("default_strategy", "weighted_sum_v1")
            strategy_params = self.review_config.get("strategies", {}).get(strategy_name, {})
            weights = strategy_params.get("weights", {})
            
            time_weight = weights.get("time_since_last_review", 0.4)
            assessment_weight = weights.get("assessment_performance", 0.3)
            kp_priority_weight = weights.get("knowledge_point_priority", 0.2)
            status_learning_weight = weights.get("status_learning", 0.1)
            
            ebbinghaus_half_life_days = strategy_params.get("ebbinghaus_half_life_days", 2)
            max_time_decay_score = strategy_params.get("max_time_decay_score", 1.0)
            assessment_norm_factor = strategy_params.get("assessment_score_normalization_factor", 100.0)

            # Get default values from config
            default_values_config = self.review_config.get("defaults", {})
            default_assessment_score = default_values_config.get("assessment_score_if_missing", 100)
            time_decay_penalty_factor = default_values_config.get("time_decay_penalty_factor_on_error", 0.5)

            # Get status boosts and dampening factor from strategy_params
            status_boosts_config = strategy_params.get("status_boosts", {})
            learning_boost_val = status_boosts_config.get("learning", 1.0)
            review_boost_val = status_boosts_config.get("review", 0.8)
            mastered_dampening_factor = strategy_params.get("mastered_recent_review_dampening_factor", 0.5)

            for kp in all_kps:
                kp_id = kp.get("id")
                title = kp.get("title", "Untitled Knowledge Point")
                status = kp.get("status", "not_started") # Default to not_started if missing
                last_reviewed_str = kp.get("last_reviewed_at") or kp.get("last_reviewed") # Accommodate different field names
                
                # Use 'updated_at' or 'created_at' if 'last_reviewed_at' is missing for new items
                if not last_reviewed_str:
                    last_reviewed_str = kp.get("updated_at") or kp.get("created_at")

                last_assessed_score = kp.get("last_assessment_score")
                if last_assessed_score is None:
                    last_assessed_score = kp.get("last_assessed_score", default_assessment_score)

                kp_inherent_priority = kp.get("priority", 0.5) # Assume medium priority (0.0 to 1.0 scale)

                # a. Time since last review (Ebbinghaus-like decay)
                time_decay_score = 0
                if last_reviewed_str:
                    try:
                        # Ensure last_reviewed_time is offset-aware (UTC)
                        last_reviewed_time = datetime.datetime.fromisoformat(last_reviewed_str.replace('Z', '+00:00'))
                        if last_reviewed_time.tzinfo is None:
                            last_reviewed_time = last_reviewed_time.replace(tzinfo=datetime.timezone.utc)
                        
                        days_since_review = (current_time_utc - last_reviewed_time).total_seconds() / (24 * 3600)
                        # Ebbinghaus formula: P = e^(-t/S), where P is retention, t is time, S is memory strength (related to half-life)
                        # We want higher score for lower retention (i.e. longer time or weaker memory)
                        # Score = 1 - P. For simplicity, using a scaled version.
                        # Or simpler: score = min(1, days_since_review / (ebbinghaus_half_life_days * 2)) # Linear increase up to a point
                        # Using a common forgetting curve model: R = exp(-k*t) where k = ln(2)/half_life
                        # Forgetting_score = 1 - R
                        if days_since_review > 0 and ebbinghaus_half_life_days > 0:
                            k = math.log(2) / ebbinghaus_half_life_days
                            retention_probability = math.exp(-k * days_since_review)
                            time_decay_score = max(0, min(max_time_decay_score, (1 - retention_probability) * max_time_decay_score))
                        elif days_since_review <= 0: # Reviewed today or in future (data error?)
                             time_decay_score = 0
                        else: # Very old, max score
                            time_decay_score = max_time_decay_score

                    except ValueError:
                        self.monitoring_manager.log_warning(f"Invalid last_reviewed format for KP {kp_id}: {last_reviewed_str}", context={"module": "ReviewerModule"})
                        time_decay_score = max_time_decay_score * time_decay_penalty_factor
                else: # Never reviewed, high priority
                    time_decay_score = max_time_decay_score

                # b. Assessment performance
                assessment_performance_score = 0
                if last_assessed_score is not None and assessment_norm_factor > 0:
                    # Score 0-100, lower is worse. We want higher review priority for lower scores.
                    assessment_performance_score = max(0, min(1, (assessment_norm_factor - last_assessed_score) / assessment_norm_factor))
                
                # c. Knowledge point inherent priority (0.0 to 1.0)
                kp_priority_score = max(0, min(1, kp_inherent_priority))

                # d. Status boost for 'learning'
                status_learning_boost = 0
                if status == 'learning':
                    status_learning_boost = learning_boost_val
                elif status == 'review':
                    status_learning_boost = review_boost_val

                # Combine scores using configured weights
                final_priority_score = (
                    (time_decay_score * time_weight) +
                    (assessment_performance_score * assessment_weight) +
                    (kp_priority_score * kp_priority_weight) +
                    (status_learning_boost * status_learning_weight)
                )
                
                # Filter out already mastered and recently reviewed items unless score is very high due to other factors
                if status == 'mastered' and time_decay_score < (max_time_decay_score * 0.3): # if mastered and reviewed relatively recently
                    final_priority_score *= mastered_dampening_factor

                reason_parts = []
                if time_decay_score > 0.7 * max_time_decay_score : reason_parts.append("long time since last review")
                if assessment_performance_score > 0.7 : reason_parts.append(f"low assessment score ({last_assessed_score})")
                if kp_priority_score > 0.7 : reason_parts.append("high inherent priority")
                if status_learning_boost > 0 : reason_parts.append(f"status is '{status}'")
                reason = ", ".join(reason_parts) if reason_parts else "General review recommended"


                suggestions_with_priority.append({
                    "knowledge_point_id": kp_id,
                    "title": title,
                    "reason": reason,
                    "priority_score": round(final_priority_score, 4),
                    "status": status,
                    "last_reviewed": last_reviewed_str,
                    # "last_assessed_time": kp.get("last_assessed_time"), # If available
                    "last_assessed_score": last_assessed_score,
                    "debug_scores": { # For easier debugging
                        "time_decay": round(time_decay_score,3),
                        "assessment_perf": round(assessment_performance_score,3),
                        "kp_inherent_prio": round(kp_priority_score,3),
                        "status_boost": round(status_learning_boost,3)
                    }
                })

            # 3. Sort KPs by priority score (descending)
            suggestions_with_priority.sort(key=lambda x: x['priority_score'], reverse=True)

            # 4. Select top 'max_items' KPs and format output
            final_suggestions = []
            for item in suggestions_with_priority[:max_items]:
                final_suggestions.append({
                    "knowledge_point_id": item["knowledge_point_id"],
                    "title": item["title"],
                    "reason": item["reason"],
                    "priority_score": item["priority_score"],
                    "status": item["status"],
                    "last_reviewed": item["last_reviewed"]
                    # "debug_scores": item["debug_scores"] # Optionally include for API response
                })
 
            self.monitoring_manager.log_info(f"Generated {len(final_suggestions)} review suggestions.", context={"module": "ReviewerModule", "session_id": session_id, "count": len(final_suggestions)})
            return {
                "status": "success",
                "data": {"suggestions": final_suggestions},
                "message": "Review suggestions generated successfully."
            }
        except Exception as e:
            self.monitoring_manager.log_error(f"Error getting review suggestions: {e}", context={"module": "ReviewerModule", "session_id": session_id}, exc_info=True)
            return {"status": "error", "message": f"An unexpected error occurred while generating review suggestions: {str(e)}"}

    def _provide_review_material(self, session_id: str, knowledge_point_id: str) -> Dict[str, Any]:
        """
        Provides review material for a specific knowledge point (internal method).
        Fetches KP content, related resources, and optionally generates summaries/questions via LLM.
        """
        self.monitoring_manager.log_debug(f"Providing review material for KP: {knowledge_point_id}", context={"module": "ReviewerModule", "session_id": session_id})
        try:
            # 1. Get knowledge point details from MemoryBankManager
            kp_details_response = self.memory_bank_manager.process_request({
                "operation": "get_knowledge_point",
                "payload": {"knowledge_point_id": knowledge_point_id}
            })

            if kp_details_response['status'] != 'success' or not kp_details_response.get('data'):
                self.monitoring_manager.log("warning", f"Knowledge point {knowledge_point_id} not found or error fetching.", {"module": "ReviewerModule", "session_id": session_id, "response": kp_details_response})
                return {"status": "error", "message": f"Knowledge point {knowledge_point_id} not found or error fetching: {kp_details_response.get('message', 'Unknown MBM error')}"}
            
            kp_data = kp_details_response['data']
            title = kp_data.get("title", "N/A")
            content = kp_data.get("content", "") # Main content of the KP

            # 2. Get related notes or resources from MemoryBankManager
            # Assuming an operation like 'get_related_resources' exists or can be added
            # For now, let's assume 'resource_links' might be part of kp_data or fetched separately
            related_resources = kp_data.get("resource_links", []) # Example
            # If not directly in kp_data, you might call:
            # related_res_response = self.memory_bank_manager.process_request({
            #     "operation": "get_resource_links_for_kp", "payload": {"knowledge_point_id": knowledge_point_id}
            # })
            # if related_res_response['status'] == 'success':
            #     related_resources.extend(related_res_response.get('data', []))


            # 3. (Optional) Use LLMInterface to generate a summary or key questions
            llm_summary = ""
            llm_key_questions = []
            
            summary_prompt_template = self.review_config.get("llm_summary_prompt_template")
            questions_prompt_template = self.review_config.get("llm_questions_prompt_template")
            
            llm_config = self.review_config.get("llm", {})
            summary_max_tokens = llm_config.get("summary_max_tokens", 150)
            questions_max_tokens = llm_config.get("questions_max_tokens", 100)

            if self.llm_interface and summary_prompt_template and content:
                try:
                    summary_prompt = summary_prompt_template.format(title=title, content=content[:2000])
                    llm_response_summary = self.llm_interface.generate_text({"prompt": summary_prompt, "max_tokens": summary_max_tokens})
                    if llm_response_summary['status'] == 'success' and llm_response_summary['data'].get('text'):
                        llm_summary = llm_response_summary['data']['text'].strip()
                    else:
                        self.monitoring_manager.log_warning(f"LLM summary generation failed for KP {knowledge_point_id}.", context={"module": "ReviewerModule", "llm_error": llm_response_summary.get('message')})
                except Exception as llm_e:
                    self.monitoring_manager.log_error(f"LLM summary generation exception for KP {knowledge_point_id}: {llm_e}", context={"module": "ReviewerModule"}, exc_info=True)
            
            if self.llm_interface and questions_prompt_template and content:
                try:
                    questions_prompt = questions_prompt_template.format(title=title, content=content[:2000])
                    llm_response_questions = self.llm_interface.generate_text({"prompt": questions_prompt, "max_tokens": questions_max_tokens})
                    if llm_response_questions['status'] == 'success' and llm_response_questions['data'].get('text'):
                        # Assuming questions are returned one per line or similar parsable format
                        raw_questions = llm_response_questions['data']['text'].strip()
                        llm_key_questions = [q.strip() for q in raw_questions.split('\n') if q.strip()]
                    else:
                        self.monitoring_manager.log_warning(f"LLM key questions generation failed for KP {knowledge_point_id}.", context={"module": "ReviewerModule", "llm_error": llm_response_questions.get('message')})
                except Exception as llm_e:
                    self.monitoring_manager.log_error(f"LLM key questions generation exception for KP {knowledge_point_id}: {llm_e}", context={"module": "ReviewerModule"}, exc_info=True)

            # Determine final content to show: LLM summary if available, else original content
            display_content = llm_summary if llm_summary else content

            response_data = {
                "type": "review_material",
                "knowledge_point_id": knowledge_point_id,
                "title": title,
                "content": display_content,
                "original_content_available": bool(content and llm_summary), # Flag if original is different from summary
                "key_questions": llm_key_questions,
                "related_resources": related_resources, # This should be a list of dicts e.g. {"title": "Link Name", "url": "http://..."}
                "suggested_actions": ["Mark as Reviewed", "Test Me on This", "Show Original Content"] # Example actions
            }
 
            self.monitoring_manager.log_info(f"Provided review material for KP: {knowledge_point_id}", context={"module": "ReviewerModule", "session_id": session_id})
            return {
                "status": "success",
                "response": response_data,
                "message": "Review material provided successfully."
            }
        except Exception as e:
            self.monitoring_manager.log_error(f"Error providing review material for KP {knowledge_point_id}: {e}", context={"module": "ReviewerModule", "session_id": session_id}, exc_info=True)
            return {"status": "error", "message": f"An unexpected error occurred while providing review material: {str(e)}"}

    def get_mode_context(self) -> Optional[Dict[str, Any]]:
        """
        Gathers context from the ReviewerModule.
        This might include the last set of review suggestions or user preferences.
        """
        # Example: return {"last_suggestions": self.last_suggestions_cache}
        self.monitoring_manager.log_info("ReviewerModule.get_mode_context called.", context={"module": "ReviewerModule"})
        return None # Placeholder

    def load_mode_context(self, context_data: Dict[str, Any]) -> None:
        """
        Loads context into the ReviewerModule.
        """
        # Example: self.last_suggestions_cache = context_data.get("last_suggestions")
        self.monitoring_manager.log_info(f"ReviewerModule.load_mode_context called with data: {context_data}", context={"module": "ReviewerModule"})
        pass # Placeholder
