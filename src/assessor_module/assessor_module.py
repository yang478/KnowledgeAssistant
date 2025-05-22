# -*- coding: utf-8 -*-
"""评估模块 (AssessorModule) 的主实现文件。

包含 AssessorModule 类，该类封装了生成评估问题、
提交和评估答案、记录评估日志以及更新知识点掌握程度等核心功能。
"""
import datetime  # For timestamps
import json
import traceback  # For detailed error logging
import uuid  # For generating unique IDs
from typing import Any, Dict, List, Optional

from src.config_manager.config_manager import ConfigManager
from src.llm_interface.llm_interface import LLMInterface
# Import dependencies
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import MonitoringManager
from src.update_manager.update_manager import UpdateManager


class AssessorModule:
    """
    评估模块 (AssessorModule)
    Handles assessment logic: generating questions, evaluating answers, logging results.
    """
    def __init__(self, memory_bank_manager: MemoryBankManager, llm_interface: LLMInterface,
                 config_manager: ConfigManager, monitoring_manager: MonitoringManager,
                 update_manager: UpdateManager):
        """
        Initializes the AssessorModule.
        """
        self.memory_bank_manager = memory_bank_manager
        self.llm_interface = llm_interface
        self.config_manager = config_manager
        self.monitoring_manager = monitoring_manager
        self.update_manager = update_manager
        
        # Load default assessor configurations
        self.default_question_type = self.config_manager.get_config("assessor.default_question_type", "multiple_choice")
        self.difficulty_levels = self.config_manager.get_config("assessor.difficulty_levels", {"easy": {}, "medium": {}, "hard": {}})
        self.generation_prompts = self.config_manager.get_config("assessor.prompts.generate_question", {})
        self.evaluation_prompts = self.config_manager.get_config("assessor.prompts.evaluate_answer", {})
        self.llm_gen_config = self.config_manager.get_config("assessor.llm_config.generation", {})
        self.llm_eval_config = self.config_manager.get_config("assessor.llm_config.evaluation", {})
        self.generation_strategies = self.config_manager.get_config("assessor.generation_strategies", {})
        self.evaluation_strategies = self.config_manager.get_config("assessor.evaluation_strategies", {})
        self.scoring_rubrics = self.config_manager.get_config("assessor.scoring_rubrics", {})

        self.monitoring_manager.log_info("AssessorModule initialized with configurations.")

    def handle_request(self, session_id: str, request_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles assessment-related requests from the ModeController.
        """
        self.monitoring_manager.log_info(f"Handling request type: {request_type}", {"session_id": session_id})
        try:
            if request_type == "generate_assessment":
                knowledge_point_ids = payload.get("knowledge_point_ids", [])
                assessment_type = payload.get("assessment_type", self.default_question_type)
                difficulty = payload.get("difficulty", "medium")
                count = payload.get("count") # Optional: number of questions

                if not knowledge_point_ids:
                     self.monitoring_manager.log_warning("generate_assessment request missing knowledge_point_ids.", {"session_id": session_id})
                     return {"status": "error", "message": "knowledge_point_ids are required to generate an assessment."}
                return self._generate_assessment(session_id, knowledge_point_ids, assessment_type, difficulty, count)

            elif request_type == "submit_assessment":
                assessment_id = payload.get("assessment_id")
                answers = payload.get("answers") # Can be None or empty list
                if not assessment_id or answers is None: # Check for None specifically
                    self.monitoring_manager.log_error("submit_assessment request missing assessment_id or answers.", {"session_id": session_id})
                    return {"status": "error", "message": "assessment_id and answers list are required for submit_assessment."}
                return self._submit_assessment(session_id, assessment_id, answers)

            else:
                self.monitoring_manager.log_warning(f"Unsupported request type received: {request_type}", {"session_id": session_id})
                return {"status": "error", "message": f"Unsupported request type for AssessorModule: {request_type}"}

        except Exception as e:
            self.monitoring_manager.log_error(f"Unhandled exception in AssessorModule.handle_request: {e}", {"session_id": session_id}, exc_info=True)
            return {"status": "error", "message": "An internal server error occurred in AssessorModule."}


    def _generate_assessment(self, session_id: str, knowledge_point_ids: List[str], assessment_type: str, difficulty: str, count: int = None) -> Dict[str, Any]:
        """
        Generates assessment questions based on specified knowledge points.
        Can use question banks or LLM based on configuration.
        """
        self.monitoring_manager.log_info(
            f"Generating assessment for session: {session_id}",
            {"kp_ids": knowledge_point_ids, "type": assessment_type, "difficulty": difficulty, "count": count}
        )

        # Attempt to generate questions from a question bank first, if configured
        # This is a placeholder for more sophisticated bank logic
        strategy_config = self.generation_strategies.get(assessment_type, {})
        use_bank = strategy_config.get("use_question_bank", False)
        
        generated_questions_from_bank = []
        if use_bank:
            self.monitoring_manager.log_info(f"Attempting to use question bank for assessment type: {assessment_type}", {"session_id": session_id})
            # Placeholder: Actual logic to fetch from MemoryBankManager based on kp_ids, type, difficulty, count
            # Example: bank_request = {"operation": "get_questions_from_bank", "payload": {"knowledge_point_ids": knowledge_point_ids, "type": assessment_type, "difficulty": difficulty, "count": count}}
            # bank_response = self.memory_bank_manager.process_request(bank_request)
            # if bank_response.get("status") == "success" and bank_response.get("data"):
            #    generated_questions_from_bank = bank_response["data"]
            #    self.monitoring_manager.log_info(f"Retrieved {len(generated_questions_from_bank)} questions from bank.", {"session_id": session_id})
            pass # Implement actual bank retrieval logic here

        # If bank generation is not used, or fails to produce enough questions, fall back to LLM or supplement
        # For simplicity, this example will proceed to LLM if bank is not used or yields nothing.
        # A more complex version might try to supplement bank questions with LLM-generated ones.

        if generated_questions_from_bank: # Basic check, could be more nuanced (e.g. if count is met)
            # If bank questions are sufficient, format and return them
            # This part needs to ensure bank questions have question_id, knowledge_point_id etc.
            # For now, let's assume if bank is used, it's the sole source for this simplified example.
            # This logic would need to be fleshed out considerably.
            # For this task, we will focus on LLM path and ConfigManager integration.
            pass


        # 1. Fetch content for requested knowledge points (still needed for LLM fallback/generation)
        knowledge_points_content = ""
        retrieved_kps_info = [] # Store basic info for prompt context
        for kp_id in knowledge_point_ids:
            mbm_request = {"operation": "get_knowledge_point", "payload": {"knowledge_point_id": kp_id}}
            kp_response = self.memory_bank_manager.process_request(mbm_request)
            if kp_response.get("status") == "success" and kp_response.get("data"):
                kp_data = kp_response["data"]
                retrieved_kps_info.append({"id": kp_data.get('id'), "title": kp_data.get('title')})
                knowledge_points_content += f"## Knowledge Point ID: {kp_data.get('id', 'N/A')}\n"
                knowledge_points_content += f"Title: {kp_data.get('title', 'N/A')}\n"
                knowledge_points_content += f"Content:\n{kp_data.get('content', 'N/A')}\n\n"
            else:
                error_msg = kp_response.get('message', 'Unknown error')
                self.monitoring_manager.log_warning(
                    f"Could not retrieve content for knowledge point {kp_id}: {error_msg}",
                    {"session_id": session_id, "knowledge_point_id": kp_id}
                )

        if not knowledge_points_content:
            self.monitoring_manager.log_error(
                "Failed to retrieve content for any requested knowledge points.",
                {"session_id": session_id, "knowledge_point_ids": knowledge_point_ids}
            )
            return {"status": "error", "message": "Failed to retrieve content for any requested knowledge points."}

        # 2. Build prompt and call LLMInterface
        prompt_template = self.generation_prompts.get(assessment_type, self.generation_prompts.get("default"))
        if not prompt_template:
            self.monitoring_manager.log_error(f"No suitable generation prompt template found for type '{assessment_type}' or default.", {"session_id": session_id})
            return {"status": "error", "message": f"Missing prompt template for assessment type '{assessment_type}'."}

        prompt_params = {
            "knowledge_points_content": knowledge_points_content,
            "assessment_type": assessment_type,
            "difficulty": difficulty,
            "count": count or "a few" # Adjust if count is None
        }
        try:
            prompt = prompt_template.format(**prompt_params)
        except KeyError as e:
            self.monitoring_manager.log_error(f"Missing parameter in prompt template for generation: {e}", {"session_id": session_id, "template_name": assessment_type})
            return {"status": "error", "message": f"Prompt template formatting error: missing key {e}."}
        
        llm_config_to_use = self.llm_gen_config.get(assessment_type, self.llm_gen_config.get("default", {}))

        llm_request = {"prompt": prompt, "model_config": llm_config_to_use}
        self.monitoring_manager.log_debug("Sending prompt to LLM for question generation.", {"session_id": session_id, "prompt_length": len(prompt)})
        llm_response = self.llm_interface.generate_text(llm_request)

        if llm_response.get("status") != "success":
            error_msg = f"LLM call failed during question generation: {llm_response.get('message', 'Unknown error')}"
            self.monitoring_manager.log_error(error_msg, {"session_id": session_id})
            return {"status": "error", "message": error_msg}

        # 3. Parse and validate LLM response
        try:
            llm_output_text = llm_response["data"]["text"]
            # Attempt to clean potential markdown code blocks
            if llm_output_text.strip().startswith("```json"):
                llm_output_text = llm_output_text.strip()[7:-3].strip() # Remove ```json ... ```
            elif llm_output_text.strip().startswith("```"):
                 llm_output_text = llm_output_text.strip()[3:-3].strip() # Remove ``` ... ```

            questions_data = json.loads(llm_output_text)
            if not isinstance(questions_data, list):
                 raise ValueError("LLM did not return a valid JSON list for questions.")

            processed_questions = []
            valid_kp_ids = {kp['id'] for kp in retrieved_kps_info} # Set of valid IDs based on retrieved content
            for i, q in enumerate(questions_data):
                if not isinstance(q, dict) or "knowledge_point_id" not in q or "text" not in q:
                     self.monitoring_manager.log_warning(f"Skipping invalid question structure from LLM: {q}", {"session_id": session_id})
                     continue
                # Ensure the KP ID from the question corresponds to one requested/retrieved
                if q["knowledge_point_id"] not in valid_kp_ids:
                     self.monitoring_manager.log_warning(f"Skipping question with mismatched/invalid knowledge_point_id '{q['knowledge_point_id']}' from LLM.", {"session_id": session_id, "question_data": q})
                     continue

                # Generate a unique ID for each valid question
                q["question_id"] = f"q_{uuid.uuid4()}"
                processed_questions.append(q)

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            error_msg = f"Failed to parse questions JSON from LLM response: {e}"
            self.monitoring_manager.log_error(error_msg, {"session_id": session_id, "llm_response": llm_response.get("data", {}).get("text")}, exc_info=True)
            return {"status": "error", "message": error_msg}

        if not processed_questions:
             self.monitoring_manager.log_warning("LLM returned no valid questions after parsing.", {"session_id": session_id})
             return {"status": "error", "message": "LLM returned no valid questions."}

        # 4. Construct and return the assessment structure
        assessment_id = f"assess_{uuid.uuid4()}"
        self.monitoring_manager.log_info(f"Generated assessment {assessment_id} with {len(processed_questions)} questions.")

        # Save the generated assessment to MemoryBankManager
        save_assessment_payload = {
            "assessment_id": assessment_id,
            "questions": processed_questions,
            "assessment_type": assessment_type,
            "difficulty": difficulty,
            "knowledge_point_ids": knowledge_point_ids, # Store original KP IDs for context
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        }
        # Assuming a new MBM operation 'save_generated_assessment'
        mbm_save_request = {"operation": "save_generated_assessment", "payload": save_assessment_payload}
        save_response = self.memory_bank_manager.process_request(mbm_save_request)

        if save_response.get("status") != "success":
            self.monitoring_manager.log_error(
                f"Failed to save generated assessment {assessment_id} to MemoryBankManager: {save_response.get('message', 'Unknown error')}",
                {"session_id": session_id, "assessment_id": assessment_id}
            )
            # Depending on requirements, we might return an error here or just log and continue
            # For now, let's return an error if saving fails, as submission will likely fail too.
            return {"status": "error", "message": f"Failed to save generated assessment: {save_response.get('message', 'Unknown error')}"}

        return {
            "status": "success",
            "data": {
                "assessment_id": assessment_id,
                "questions": processed_questions
            }
        }

    def _submit_assessment(self, session_id: str, assessment_id: str, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Submits assessment answers, evaluates them, logs results, and triggers updates.
        """
        self.monitoring_manager.log_info(
            f"Submitting assessment for session: {session_id}",
            {"assessment_id": assessment_id, "num_answers": len(answers)}
        )

        if not answers: # Handle empty answers list gracefully
             self.monitoring_manager.log_info("Received submission with empty answers list.", {"session_id": session_id, "assessment_id": assessment_id})
             return {
                 "status": "success",
                 "data": {"results": [], "overall_score": 0, "mastery_updates": []},
                 "message": "Assessment submitted with no answers."
             }

        # Retrieve the original assessment questions from MemoryBankManager
        # Assuming a new MBM operation 'get_generated_assessment'
        mbm_get_request = {"operation": "get_generated_assessment", "payload": {"assessment_id": assessment_id}}
        get_assessment_response = self.memory_bank_manager.process_request(mbm_get_request)

        if get_assessment_response.get("status") != "success" or not get_assessment_response.get("data"):
            self.monitoring_manager.log_error(
                f"Failed to retrieve original assessment {assessment_id} from MemoryBankManager: {get_assessment_response.get('message', 'Not found or error')}",
                {"session_id": session_id, "assessment_id": assessment_id}
            )
            return {"status": "error", "message": f"Original assessment {assessment_id} not found or could not be retrieved."}

        original_assessment_data = get_assessment_response["data"]
        original_questions = {q["question_id"]: q for q in original_assessment_data.get("questions", [])}

        if not original_questions:
            self.monitoring_manager.log_error(
                f"Retrieved assessment {assessment_id} contains no questions.",
                {"session_id": session_id, "assessment_id": assessment_id}
            )
            return {"status": "error", "message": f"Original assessment {assessment_id} is invalid (contains no questions)."}

        evaluation_results = []
        mastery_updates = []
        overall_score_sum = 0
        processed_answers = 0

        for answer_item in answers:
            question_id = answer_item.get("question_id")
            user_answer = answer_item.get("answer")

            if not question_id or user_answer is None:
                self.monitoring_manager.log_warning("Skipping invalid answer item (missing question_id or answer).", {"answer_item": answer_item, "session_id": session_id})
                continue

            processed_answers += 1

            original_question_data = original_questions.get(question_id)
            if not original_question_data:
                self.monitoring_manager.log_warning(
                    f"Question ID {question_id} from answer not found in original assessment {assessment_id}. Skipping.",
                    {"session_id": session_id, "assessment_id": assessment_id, "question_id": question_id}
                )
                continue

            knowledge_point_id = original_question_data.get("knowledge_point_id")
            question_text = original_question_data.get("text", "N/A") # Get original question text

            if not knowledge_point_id:
                 self.monitoring_manager.log_warning(
                    f"Original question {question_id} in assessment {assessment_id} is missing knowledge_point_id. Skipping.",
                    {"session_id": session_id, "assessment_id": assessment_id, "question_id": question_id}
                )
                 continue


            score = 0
            correct = False
            feedback = "Evaluation could not be performed."
            new_mastery_status = "learning" # Default status
            evaluated_by_direct_comparison = False # Flag to track if direct comparison was done

            question_type = original_question_data.get("type", "unknown")
            eval_strategy_config = self.evaluation_strategies.get(question_type, {})
            use_direct_comparison = eval_strategy_config.get("direct_comparison", False)
            
            # Attempt direct comparison for objective questions if configured
            if use_direct_comparison and "correct_answer" in original_question_data:
                correct_answer_expected = original_question_data["correct_answer"]
                # Simple comparison, can be made more robust (e.g. case-insensitivity, trimming whitespace)
                if str(user_answer).strip() == str(correct_answer_expected).strip():
                    correct = True
                    score = 100 # Or use a score from scoring_rubrics
                    feedback = self.scoring_rubrics.get(question_type, {}).get("correct_feedback", "Correct.")
                    # Determine new_mastery_status based on rubrics if available
                    new_mastery_status = self.scoring_rubrics.get(question_type, {}).get("mastery_on_correct", "mastered")
                else:
                    correct = False
                    score = 0 # Or use a score from scoring_rubrics
                    feedback = self.scoring_rubrics.get(question_type, {}).get("incorrect_feedback", "Incorrect.")
                    new_mastery_status = self.scoring_rubrics.get(question_type, {}).get("mastery_on_incorrect", "learning")
                
                self.monitoring_manager.log_info(f"Directly evaluated question {question_id} of type {question_type}. Correct: {correct}", {"session_id": session_id})
                evaluated_by_direct_comparison = True
            
            if not evaluated_by_direct_comparison:
                # Fallback to LLM-based evaluation
                eval_prompt_template = self.evaluation_prompts.get(question_type, self.evaluation_prompts.get("default"))
                if not eval_prompt_template:
                    self.monitoring_manager.log_error(f"No suitable evaluation prompt template found for type '{question_type}' or default.", {"session_id": session_id})
                    feedback = "Evaluation failed: Missing prompt template."
                    # Skip to appending results with error feedback
                else:
                    prompt_params = {
                        "knowledge_point_id": knowledge_point_id,
                        "question_id": question_id,
                        "original_question": question_text,
                        "user_answer": user_answer,
                        "options": original_question_data.get("options") # Pass options if available
                    }
                    try:
                        eval_prompt = eval_prompt_template.format(**prompt_params)
                    except KeyError as e:
                        self.monitoring_manager.log_error(f"Missing parameter in prompt template for evaluation: {e}", {"session_id": session_id, "template_name": question_type})
                        feedback = f"Evaluation failed: Prompt template error (missing {e})."
                        # Skip to appending results
                    else:
                        llm_eval_config_to_use = self.llm_eval_config.get(question_type, self.llm_eval_config.get("default", {}))
                        llm_request = {"prompt": eval_prompt, "model_config": llm_eval_config_to_use}
                        self.monitoring_manager.log_debug(f"Sending prompt to LLM for answer evaluation: QID {question_id}", {"session_id": session_id, "prompt_length": len(eval_prompt)})
                        llm_response = self.llm_interface.generate_text(llm_request)

                        if llm_response.get("status") == "success" and llm_response.get("data"):
                            try:
                                llm_output_text = llm_response["data"]["text"]
                                # Clean potential markdown
                                if llm_output_text.strip().startswith("```json"):
                                    llm_output_text = llm_output_text.strip()[7:-3].strip()
                                elif llm_output_text.strip().startswith("```"):
                                    llm_output_text = llm_output_text.strip()[3:-3].strip()

                                eval_data = json.loads(llm_output_text)
                                score = eval_data.get("score", 0)
                                correct = eval_data.get("correct", False)
                                feedback = eval_data.get("feedback", "No feedback provided.")
                                new_mastery_status = eval_data.get("new_mastery_status", "learning") # Default if missing

                            except (json.JSONDecodeError, ValueError, TypeError) as e:
                                feedback = "Evaluation failed: Could not parse LLM response."
                                self.monitoring_manager.log_warning(
                                    f"Failed to parse LLM evaluation response for question {question_id}: {e}",
                                    {"session_id": session_id, "assessment_id": assessment_id, "llm_response": llm_response.get("data", {}).get("text")},
                                    exc_info=True
                                )
                        else:
                            feedback = "Evaluation failed: LLM call error."
                            self.monitoring_manager.log_error(
                                f"LLM evaluation call failed for question {question_id}: {llm_response.get('message', 'Unknown error')}",
                                {"session_id": session_id, "assessment_id": assessment_id}
                            )
            # score = 0
            # This block was moved up into the LLM evaluation path

            evaluation_results.append({
                "question_id": question_id,
                "knowledge_point_id": knowledge_point_id, # Include KP ID in results
                "score": score,
                "correct": correct,
                "feedback": feedback
            })
            overall_score_sum += score

            # Record mastery update suggestion
            mastery_updates.append({
                "knowledge_point_id": knowledge_point_id,
                "status": new_mastery_status, # Use 'status' key consistent with MBM schema
                "last_assessed_time": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                "last_assessed_score": score / 100.0 if score is not None else None # Assuming score is 0-100
            })

        overall_score = (overall_score_sum / processed_answers) if processed_answers > 0 else 0

        # 2. Log assessment results to MemoryBankManager
        log_payload = {
            "session_id": session_id,
            "assessment_id": assessment_id,
            "results": evaluation_results, # Log the detailed results
            "original_questions_summary": [ # Log summary of original questions for context
                {"question_id": q_id, "knowledge_point_id": q_data.get("knowledge_point_id"), "text_preview": q_data.get("text", "")[:50] + "..."}
                for q_id, q_data in original_questions.items()
            ],
           "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
           # MBM's save_assessment_log should handle its own internal timestamping if needed, but providing one here is good practice.
       }
        log_request = {"operation": "save_assessment_log", "payload": log_payload}
        log_response = self.memory_bank_manager.process_request(log_request)
        if log_response.get("status") != "success":
             self.monitoring_manager.log_error(
                 f"Failed to save assessment log: {log_response.get('message', 'Unknown error')}",
                 {"session_id": session_id, "assessment_id": assessment_id}
             )
             # Continue processing even if logging fails? Or return error? Decide based on requirements.

        # 3. Trigger progress update via UpdateManager
        if mastery_updates:
             update_payload = {
                 "session_id": session_id, # Include session ID for context
                 "assessment_id": assessment_id, # Include assessment ID
                 "updates": mastery_updates # Send list of updates needed
             }
             self.monitoring_manager.log_info("Triggering progress update.", {"session_id": session_id, "num_updates": len(mastery_updates)})
             # Use a specific event type like 'assessment_completed'
             self.update_manager.trigger_backup(event="assessment_completed", payload=update_payload)
        else:
             self.monitoring_manager.log_info("No mastery updates to trigger.", {"session_id": session_id})


        # 4. Construct and return the final response
        self.monitoring_manager.log_info(
            f"Assessment {assessment_id} submitted and processed.",
            {"session_id": session_id, "num_answers": processed_answers, "overall_score": overall_score}
        )
        return {
            "status": "success",
            "data": {
                "results": evaluation_results,
                "overall_score": overall_score,
                # "mastery_updates": mastery_updates # Maybe don't return this, it's handled by UpdateManager
            },
            "message": "Assessment processed successfully."
        }

def get_mode_context(self) -> Optional[Dict[str, Any]]:
        """
        Gathers context from the AssessorModule.
        This might include an ID of an assessment currently in progress.
        """
        # # Example: return {"current_assessment_id": self.active_assessment_id}
        # self.monitoring_manager.log_info("AssessorModule.get_mode_context called.")
        # return None # Placeholder
        pass

def load_mode_context(self, context_data: Dict[str, Any]) -> None:
        """
        Loads context into the AssessorModule.
        """
        # # Example: self.active_assessment_id = context_data.get("current_assessment_id")
        # self.monitoring_manager.log_info(f"AssessorModule.load_mode_context called with data: {context_data}")
        pass # Placeholder
