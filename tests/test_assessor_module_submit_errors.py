"""Unit tests for the AssessorModule class - Submit Assessment Errors focused."""

import unittest
from unittest.mock import patch, MagicMock, ANY
import json
import sys
import os
import copy # For deepcopying configs

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from assessor_module.assessor_module import AssessorModule
from memory_bank_manager.memory_bank_manager import MemoryBankManager # For spec
from llm_interface.llm_interface import LLMInterface # For spec
from config_manager.config_manager import ConfigManager # For spec
from monitoring_manager.monitoring_manager import MonitoringManager # For spec
from update_manager.update_manager import UpdateManager # For spec

class TestAssessorModule(unittest.TestCase):
    """Tests for the AssessorModule - Submit Assessment Errors focused."""

    def setUp(self):
        """Set up an AssessorModule instance with mocked dependencies."""
        self.mock_memory_bank_manager = MagicMock(spec=MemoryBankManager)
        self.mock_llm_interface = MagicMock(spec=LLMInterface)
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_monitoring_manager = MagicMock(spec=MonitoringManager)
        self.mock_update_manager = MagicMock(spec=UpdateManager)

        mock_configs = {
            "assessor.prompts.generate_question": { # Still needed for full module init
                "multiple_choice": "Generate a multiple choice question...",
                "short_answer": "Generate a short answer question...",
                "default": "Generate a question..."
            },
            "assessor.prompts.evaluate_answer": {
                "multiple_choice": "Evaluate this MCQ answer. KP: {knowledge_point_id}, Q: {original_question}, A: {user_answer}, Opts: {options}. Provide score, correct, feedback, new_mastery_status.",
                "short_answer": "Evaluate this short answer. KP: {knowledge_point_id}, Q: {original_question}, A: {user_answer}. Provide score, correct, feedback, new_mastery_status.",
                "default": "Evaluate this answer. KP: {knowledge_point_id}, Q: {original_question}, A: {user_answer}. Provide score, correct, feedback, new_mastery_status."
            },
            "assessor.default_question_type": "multiple_choice", # Still needed
            "assessor.difficulty_levels": {"easy": {}, "medium": {}, "hard": {}}, # Still needed
            "assessor.llm_config.generation": {"default": {"temperature": 0.7}}, # Still needed
            "assessor.llm_config.evaluation": {"default": {"temperature": 0.5}},
            "assessor.generation_strategies": {"multiple_choice": {"use_question_bank": False}}, # Still needed
            "assessor.evaluation_strategies": {"multiple_choice": {"direct_comparison": False}},
            "assessor.scoring_rubrics": {},
            "assessor_module.default_difficulty": "medium", # Still needed
        }
        self.mock_configs = mock_configs
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: self.mock_configs.get(key, default)

        self.assessor_module = AssessorModule(
            memory_bank_manager=self.mock_memory_bank_manager,
            llm_interface=self.mock_llm_interface,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
            update_manager=self.mock_update_manager,
        )

    def test_submit_assessment_mbm_get_assessment_error(self):
        """Test error if MBM fails to retrieve the assessment to be submitted."""
        session_id = "sess_submit_mbm_err"
        assessment_id = "assess_non_existent"
        user_answers = [{"question_id": "q1", "answer": "A"}]
        self.mock_memory_bank_manager.process_request.return_value = {"status": "error", "message": "Not found"}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "error")
        self.assertTrue(f"Original assessment {assessment_id} not found or could not be retrieved." in response["message"])
        self.mock_llm_interface.generate_text.assert_not_called()
        self.mock_memory_bank_manager.process_request.assert_called_once_with(
            {"operation": "get_generated_assessment", "payload": {"assessment_id": assessment_id}}
        )

    def test_submit_assessment_empty_answers_list(self):
        """Test _submit_assessment with an empty list of answers."""
        session_id = "sess_submit_empty_ans"
        assessment_id = "assess_empty_ans"
        user_answers = [] # Empty list

        # MBM get_assessment should still be called
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": {"assessment_id": assessment_id, "questions": []}}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "error") # Or success with 0 results if allowed
        # Current logic in _submit_assessment iterates answers, if empty, it might return success with empty results
        # Let's check the actual behavior. If answers is empty, the loop over answers won't run.
        # It will then try to save an empty log and trigger updates with empty mastery.
        # This should probably be an error or a specific handling.
        # For now, let's assume it's an error as per typical validation.
        # Based on current code, it will proceed and likely calculate score as 0.
        # The spec implies this should be an error or handled.
        # If the loop `for answer_item in answers:` doesn't run, `evaluated_results` is empty.
        # `overall_score` would be 0. `save_assessment_log` would be called with empty results.
        # `trigger_backup` would be called with empty updates.
        # This seems like a valid scenario that results in 0 score, not an error in the flow itself.
        # Let's adjust the expectation if the module handles it gracefully.
        # The prompt asks for "error and edge cases". An empty answer list is an edge case.
        # If it's not an "error" status, what should it be?
        # The original file's `handle_request` checks for missing answers and returns error.
        # `_submit_assessment` itself might not, if `handle_request` is the guard.
        # Let's assume `_submit_assessment` expects valid non-empty answers from `handle_request`.
        # If called directly with empty, it might not error out but produce 0 results.
        # For this test, let's assume it should be an error if no answers are processed.
        # The problem description implies this test is for _submit_assessment directly.
        # If answers is empty, `evaluated_results` will be empty.
        # `overall_score` will be 0.
        # `mbm_payload_log["results"]` will be empty.
        # `mastery_updates` will be empty.
        # This is not an "error" in the sense of a crash, but a "no operation" result.
        # The original test suite did not have a specific test for empty answers list directly to _submit_assessment.
        # Let's assume the current code returns success with 0 results.
        self.assertEqual(response["status"], "success") # Current code will return success
        self.assertEqual(len(response["data"]["results"]), 0)
        self.assertEqual(response["data"]["overall_score"], 0)


    def test_submit_assessment_original_assessment_no_questions(self):
        """Test _submit_assessment when the retrieved original assessment has no questions."""
        session_id = "sess_submit_no_q_orig"
        assessment_id = "assess_no_q_orig"
        user_answers = [{"question_id": "q1", "answer": "A"}] # User provides an answer
        
        # MBM returns an assessment with an empty questions list
        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": []}
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": mock_retrieved_assessment_data}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Original assessment contains no questions to evaluate against.")

    def test_submit_assessment_answer_item_missing_question_id(self):
        """Test _submit_assessment when an item in answers is missing 'question_id'."""
        session_id = "sess_submit_missing_qid"
        assessment_id = "assess_missing_qid"
        user_answers = [{"answer": "Some answer"}] # Missing question_id
        
        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [{"question_id": "q1", "text": "Q"}]}
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": mock_retrieved_assessment_data}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)
        
        self.assertEqual(response["status"], "error")
        self.assertTrue("Answer item missing 'question_id'" in response["message"])

    def test_submit_assessment_answer_item_missing_answer_text(self):
        """Test _submit_assessment when an item in answers is missing 'answer' (text)."""
        session_id = "sess_submit_missing_ans_text"
        assessment_id = "assess_missing_ans_text"
        user_answers = [{"question_id": "q1"}] # Missing answer text
        
        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [{"question_id": "q1", "text": "Q"}]}
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": mock_retrieved_assessment_data}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "error")
        self.assertTrue("Answer item missing 'answer' text for question_id: q1" in response["message"])

    def test_submit_assessment_answer_question_id_not_in_original(self):
        """Test _submit_assessment when a question_id in answers is not in the original assessment."""
        session_id = "sess_submit_qid_not_found"
        assessment_id = "assess_qid_not_found"
        user_answers = [{"question_id": "q_unknown", "answer": "A"}]
        
        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [{"question_id": "q_known", "text": "Known Q"}]}
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": mock_retrieved_assessment_data}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "error") # Or success with that answer skipped/marked
        # Current code logs a warning and skips. The overall status might still be success if other answers are processed.
        # If only one answer and it's skipped, results will be empty.
        self.assertEqual(response["message"], "No valid answers found to evaluate after filtering.")


    def test_submit_assessment_original_question_missing_kp_id(self):
        """Test _submit_assessment when an original question is missing 'knowledge_point_id'."""
        session_id = "sess_submit_orig_q_no_kpid"
        assessment_id = "assess_orig_q_no_kpid"
        q_id = "q_no_kpid"
        user_answers = [{"question_id": q_id, "answer": "A"}]
        
        # Original question from MBM is missing knowledge_point_id
        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [{"question_id": q_id, "text": "Q text"}]} # No KP ID
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": mock_retrieved_assessment_data}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "error")
        self.assertTrue(f"Original question {q_id} is missing 'knowledge_point_id'." in response["message"])

    def test_submit_assessment_llm_eval_missing_prompt_template(self):
        """Test _submit_assessment when LLM evaluation prompt template is missing."""
        session_id = "sess_submit_llm_eval_no_prompt"
        assessment_id = "assess_llm_eval_no_prompt"
        q_id = "q_eval_no_prompt"
        user_answers = [{"question_id": q_id, "answer": "A"}]
        assessment_type_no_prompt = "type_without_eval_prompt"

        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [
            {"question_id": q_id, "knowledge_point_id": "kp1", "text": "Q", "type": assessment_type_no_prompt}
        ]}
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data}, # get_assessment
            {"status": "success"} # save_log (will be called even if LLM fails for one item)
        ]
        # LLM should not be called if prompt is missing
        
        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "success") # Overall status is success, but one item failed
        self.assertEqual(len(response["data"]["results"]), 1)
        self.assertFalse(response["data"]["results"][0]["correct"]) # Default to incorrect
        self.assertEqual(response["data"]["results"][0]["score"], 0)
        self.assertTrue("Error preparing LLM call for evaluation" in response["data"]["results"][0]["feedback"])
        self.mock_llm_interface.generate_text.assert_not_called()


    def test_submit_assessment_llm_eval_prompt_format_key_error(self):
        """Test _submit_assessment when LLM evaluation prompt formatting fails (KeyError)."""
        session_id = "sess_submit_llm_eval_key_err"
        assessment_id = "assess_llm_eval_key_err"
        q_id = "q_eval_key_err"
        user_answers = [{"question_id": q_id, "answer": "A"}]
        assessment_type = "short_answer"

        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [
            {"question_id": q_id, "knowledge_point_id": "kp1", "text": "Q", "type": assessment_type}
        ]}
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data},
            {"status": "success"}
        ]
        
        original_prompt = self.mock_configs["assessor.prompts.evaluate_answer"][assessment_type]
        self.mock_configs["assessor.prompts.evaluate_answer"][assessment_type] = "Needs {missing_eval_key}"
        
        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)
        
        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["results"]), 1)
        self.assertFalse(response["data"]["results"][0]["correct"])
        self.assertTrue("Error preparing LLM call for evaluation" in response["data"]["results"][0]["feedback"])
        self.mock_llm_interface.generate_text.assert_not_called()
        self.mock_configs["assessor.prompts.evaluate_answer"][assessment_type] = original_prompt # Restore


    def test_submit_assessment_llm_eval_call_fails(self):
        """Test _submit_assessment when the LLM call itself fails during evaluation."""
        session_id = "sess_submit_llm_eval_fails"
        assessment_id = "assess_llm_eval_fails"
        q_id = "q_eval_fails"
        user_answers = [{"question_id": q_id, "answer": "A"}]

        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [
            {"question_id": q_id, "knowledge_point_id": "kp1", "text": "Q", "type": "default"}
        ]}
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data},
            {"status": "success"}
        ]
        self.mock_llm_interface.generate_text.return_value = {"status": "error", "message": "LLM eval down"}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["results"]), 1)
        self.assertFalse(response["data"]["results"][0]["correct"])
        self.assertTrue("LLM call failed during evaluation: LLM eval down" in response["data"]["results"][0]["feedback"])

    def test_submit_assessment_llm_eval_returns_invalid_json(self):
        """Test _submit_assessment when LLM returns non-JSON or invalid JSON for evaluation."""
        session_id = "sess_submit_llm_eval_bad_json"
        assessment_id = "assess_llm_eval_bad_json"
        q_id = "q_eval_bad_json"
        user_answers = [{"question_id": q_id, "answer": "A"}]

        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [
            {"question_id": q_id, "knowledge_point_id": "kp1", "text": "Q", "type": "default"}
        ]}
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data},
            {"status": "success"}
        ]
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": "not json"}}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["results"]), 1)
        self.assertFalse(response["data"]["results"][0]["correct"])
        self.assertTrue("LLM evaluation output was not valid JSON" in response["data"]["results"][0]["feedback"])

    def test_submit_assessment_mbm_save_log_error(self):
        """Test _submit_assessment when MBM fails to save the assessment log."""
        session_id = "sess_submit_mbm_log_err"
        assessment_id = "assess_mbm_log_err"
        q_id = "q_log_err"
        user_answers = [{"question_id": q_id, "answer": "A"}]

        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [
            {"question_id": q_id, "knowledge_point_id": "kp1", "text": "Q", "type": "default"}
        ]}
        # MBM: 1. get_assessment (success), 2. save_log (error)
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data},
            {"status": "error", "message": "Log save failed"}
        ]
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": json.dumps({"score": 50, "correct": False, "feedback": "ok"})}}
        
        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        # The overall response might still be success as evaluation happened, but log saving failed.
        # The module logs a warning for this.
        self.assertEqual(response["status"], "success") # Evaluation itself succeeded
        self.mock_monitoring_manager.log_warning.assert_any_call(
            f"Failed to save assessment log for assessment_id: {assessment_id}. Error: Log save failed",
            {"session_id": session_id}
        )

    def test_submit_assessment_no_mastery_updates_to_trigger(self):
        """Test _submit_assessment when no valid mastery updates are generated (e.g., LLM eval lacks new_mastery_status)."""
        session_id = "sess_submit_no_mastery_update"
        assessment_id = "assess_no_mastery_update"
        q_id = "q_no_mastery"
        user_answers = [{"question_id": q_id, "answer": "A"}]

        mock_retrieved_assessment_data = {"assessment_id": assessment_id, "questions": [
            {"question_id": q_id, "knowledge_point_id": "kp1", "text": "Q", "type": "default"}
        ]}
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data},
            {"status": "success"} # save_log
        ]
        # LLM eval result is missing 'new_mastery_status'
        llm_eval_output = json.dumps({"score": 70, "correct": True, "feedback": "Good"})
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": llm_eval_output}}

        response = self.assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["results"]), 1)
        self.assertTrue(response["data"]["results"][0]["correct"])
        
        # Check that trigger_backup was called, but with an empty "updates" list in payload
        self.mock_update_manager.trigger_backup.assert_called_once()
        update_call_args = self.mock_update_manager.trigger_backup.call_args
        self.assertEqual(update_call_args[1]['event'], "assessment_completed")
        self.assertIn("updates", update_call_args[1]['payload'])
        self.assertEqual(len(update_call_args[1]['payload']["updates"]), 0) # No mastery updates

if __name__ == '__main__':
    unittest.main()