"""Unit tests for the AssessorModule class - Generate Assessment focused."""

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
    """Tests for the AssessorModule - Generate Assessment focused."""

    def setUp(self):
        """Set up an AssessorModule instance with mocked dependencies."""
        self.mock_memory_bank_manager = MagicMock(spec=MemoryBankManager)
        self.mock_llm_interface = MagicMock(spec=LLMInterface)
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_monitoring_manager = MagicMock(spec=MonitoringManager)
        self.mock_update_manager = MagicMock(spec=UpdateManager)

        mock_configs = {
            "assessor.prompts.generate_question": {
                "multiple_choice": "Generate a multiple choice question for topic: {knowledge_points_content} with difficulty {difficulty}. Count: {count}",
                "short_answer": "Generate a short answer question for topic: {knowledge_points_content} with difficulty {difficulty}. Count: {count}",
                "default": "Generate a question for topic: {knowledge_points_content} with difficulty {difficulty}. Type: {assessment_type}. Count: {count}"
            },
            "assessor.prompts.evaluate_answer": { # Still needed for full module init
                "multiple_choice": "Evaluate this MCQ answer...",
                "short_answer": "Evaluate this short answer...",
                "default": "Evaluate this answer..."
            },
            "assessor.default_question_type": "multiple_choice",
            "assessor.difficulty_levels": {"easy": {}, "medium": {}, "hard": {}},
            "assessor.llm_config.generation": {"default": {"temperature": 0.7}},
            "assessor.llm_config.evaluation": {"default": {"temperature": 0.5}}, # Still needed
            "assessor.generation_strategies": {"multiple_choice": {"use_question_bank": False}},
            "assessor.evaluation_strategies": {"multiple_choice": {"direct_comparison": False}}, # Still needed
            "assessor.scoring_rubrics": {}, # Still needed
            "assessor_module.default_difficulty": "medium",
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

    def test_generate_assessment_success(self):
        """Test successful generation of assessment questions."""
        session_id = "sess_gen_assess"
        mock_kp_lists_data = {"id": "kp_lists", "title": "Python Lists", "content": "Lists are ordered sequences."}
        mock_kp_dicts_data = {"id": "kp_dicts", "title": "Python Dictionaries", "content": "Dicts are key-value pairs."}
        
        def mock_mbm_process_request_generate(request):
            if request["operation"] == "get_knowledge_point":
                kp_id = request["payload"]["knowledge_point_id"]
                if kp_id == "kp_lists":
                    return {"status": "success", "data": mock_kp_lists_data}
                elif kp_id == "kp_dicts":
                    return {"status": "success", "data": mock_kp_dicts_data}
            elif request["operation"] == "save_generated_assessment":
                return {"status": "success"}
            return {"status": "error", "message": "Unknown operation in mock"}

        self.mock_memory_bank_manager.process_request.side_effect = mock_mbm_process_request_generate
        
        combined_llm_output = json.dumps([
            {"knowledge_point_id": "kp_lists", "text": "Generated question for Python Lists?", "type": "multiple_choice", "options": ["A", "B"], "correct_answer": "A"},
            {"knowledge_point_id": "kp_dicts", "text": "Generated question for Python Dictionaries?", "type": "short_answer"}
        ])
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": combined_llm_output}}

        response = self.assessor_module._generate_assessment(
            session_id=session_id,
            knowledge_point_ids=["kp_lists", "kp_dicts"],
            assessment_type="multiple_choice",
            difficulty="medium"
        )

        self.mock_monitoring_manager.log_info.assert_any_call(
             f"Generating assessment for session: {session_id}",
             {"kp_ids": ["kp_lists", "kp_dicts"], "type": "multiple_choice", "difficulty": "medium", "count": None}
        )
        self.assertEqual(self.mock_memory_bank_manager.process_request.call_count, 3)
        mbm_calls = self.mock_memory_bank_manager.process_request.call_args_list
        self.assertEqual(mbm_calls[0][0][0]["operation"], "get_knowledge_point")
        self.assertEqual(mbm_calls[1][0][0]["operation"], "get_knowledge_point")
        self.mock_llm_interface.generate_text.assert_called_once()
        self.assertEqual(mbm_calls[2][0][0]["operation"], "save_generated_assessment")
        self.assertEqual(response["status"], "success")
        self.assertIn("assessment_id", response["data"])
        self.assertEqual(len(response["data"]["questions"]), 2)

    def test_generate_assessment_llm_error(self):
        """Test error handling if LLM fails during question generation."""
        session_id = "sess_gen_llm_err"
        kp_ids = ["kp_any"]
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": {"id": "kp_any", "title": "Any", "content": "Anything"}}
        self.mock_llm_interface.generate_text.return_value = {"status": "error", "message": "LLM down"}

        response = self.assessor_module._generate_assessment(session_id, kp_ids, "default_type", "medium")

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "LLM call failed during question generation: LLM down")
        save_call_found = any(call[0][0]["operation"] == "save_generated_assessment" for call in self.mock_memory_bank_manager.process_request.call_args_list)
        self.assertFalse(save_call_found)

    def test_generate_assessment_use_question_bank_true(self):
        """Test _generate_assessment when use_question_bank is True."""
        session_id = "sess_gen_qbank"
        kp_ids = ["kp_qbank"]
        assessment_type = "multiple_choice"
        difficulty = "easy"

        temp_mock_configs = copy.deepcopy(self.mock_configs)
        if "assessor.generation_strategies" not in temp_mock_configs:
            temp_mock_configs["assessor.generation_strategies"] = {}
        if assessment_type not in temp_mock_configs["assessor.generation_strategies"]:
            temp_mock_configs["assessor.generation_strategies"][assessment_type] = {}
        temp_mock_configs["assessor.generation_strategies"][assessment_type]["use_question_bank"] = True
        
        original_side_effect = self.mock_config_manager.get_config.side_effect
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: temp_mock_configs.get(key, default)

        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": {"id": "kp_qbank", "title": "QBank Topic", "content": "Content for QBank."}},
            {"status": "success", "data": {"questions": []}}, 
            {"status": "success"} 
        ]
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": json.dumps([{"knowledge_point_id": "kp_qbank", "text": "LLM Q for QBank", "type": assessment_type}])}}

        current_assessor_module = AssessorModule( # Re-init with temp config
            memory_bank_manager=self.mock_memory_bank_manager,
            llm_interface=self.mock_llm_interface,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
            update_manager=self.mock_update_manager,
        )
        response = current_assessor_module._generate_assessment(session_id, kp_ids, assessment_type, difficulty)

        self.mock_monitoring_manager.log_info.assert_any_call(
            f"Attempting to use question bank for assessment type: {assessment_type}", {"session_id": session_id}
        )
        self.mock_llm_interface.generate_text.assert_called_once()
        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["questions"]), 1)
        self.mock_config_manager.get_config.side_effect = original_side_effect

    def test_generate_assessment_mbm_get_kp_error(self):
        """Test _generate_assessment when MBM fails to get knowledge point content."""
        session_id = "sess_gen_mbm_kp_err"
        kp_ids = ["kp_non_existent"]
        self.mock_memory_bank_manager.process_request.return_value = {"status": "error", "message": "KP not found"}
        response = self.assessor_module._generate_assessment(session_id, kp_ids, "default_type", "medium")
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "Failed to retrieve content for any requested knowledge points.")
        self.mock_monitoring_manager.log_warning.assert_called_with(
            "Failed to retrieve content for any KPs.", {"kp_ids": kp_ids, "session_id": session_id}
        )

    def test_generate_assessment_missing_prompt_template(self):
        """Test _generate_assessment with a missing prompt template for the assessment type."""
        session_id = "sess_gen_no_prompt"
        kp_ids = ["kp_valid"]
        assessment_type = "non_existent_type" # This type won't have a prompt
        difficulty = "medium"

        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": {"id": "kp_valid", "content": "Valid content"}}
        
        response = self.assessor_module._generate_assessment(session_id, kp_ids, assessment_type, difficulty)

        self.assertEqual(response["status"], "error")
        self.assertTrue(f"No prompt template found for assessment type: {assessment_type}" in response["message"])
        self.mock_monitoring_manager.log_error.assert_called_with(
            f"Prompt template for assessment type '{assessment_type}' not found.",
            {"session_id": session_id}
        )

    def test_generate_assessment_prompt_format_key_error(self):
        """Test _generate_assessment when prompt formatting fails due to a KeyError."""
        session_id = "sess_gen_prompt_key_err"
        kp_ids = ["kp_format_err"]
        assessment_type = "short_answer" # Assume this uses {knowledge_points_content}
        difficulty = "medium"

        # MBM returns KP data
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": {"id": "kp_format_err", "content": "Content here"}}
        
        # Modify config to have a prompt that will cause a KeyError (e.g., missing a key it tries to format)
        original_prompt = self.mock_configs["assessor.prompts.generate_question"][assessment_type]
        self.mock_configs["assessor.prompts.generate_question"][assessment_type] = "This prompt needs {missing_key}"
        
        response = self.assessor_module._generate_assessment(session_id, kp_ids, assessment_type, difficulty)

        self.assertEqual(response["status"], "error")
        self.assertTrue("Error formatting prompt for question generation" in response["message"])
        
        # Restore original prompt
        self.mock_configs["assessor.prompts.generate_question"][assessment_type] = original_prompt

    def test_generate_assessment_llm_returns_not_a_list(self):
        """Test _generate_assessment when LLM returns data that is not a valid JSON list."""
        session_id = "sess_gen_llm_not_list"
        kp_ids = ["kp_llm_invalid_json"]
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": {"id": "kp_llm_invalid_json", "content": "Content"}}, # get_kp
            {"status": "success"} # save_assessment (will be called if LLM part fails later)
        ]
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": "This is not JSON"}}

        response = self.assessor_module._generate_assessment(session_id, kp_ids, "default_type", "medium")
        
        self.assertEqual(response["status"], "error")
        self.assertTrue("LLM output for question generation was not valid JSON or not a list." in response["message"])

    def test_generate_assessment_llm_returns_invalid_question_structure(self):
        """Test _generate_assessment when LLM returns a list but items lack required keys."""
        session_id = "sess_gen_llm_invalid_struct"
        kp_ids = ["kp_llm_bad_struct"]
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": {"id": "kp_llm_bad_struct", "content": "Content"}},
            {"status": "success"} 
        ]
        # LLM returns a list, but a question is missing 'text' or 'knowledge_point_id'
        llm_output = json.dumps([{"knowledge_point_id": "kp_llm_bad_struct"}, {"text": "Another question"}]) # Missing 'text' in first, 'kp_id' in second
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": llm_output}}

        response = self.assessor_module._generate_assessment(session_id, kp_ids, "default_type", "medium")

        self.assertEqual(response["status"], "error")
        # This error message might be "No valid questions generated by LLM." if all are filtered out.
        # Or it could be more specific if the validation catches it earlier.
        # Based on current code, it will likely be "No valid questions generated by LLM."
        self.assertTrue("No valid questions generated by LLM." in response["message"] or "Invalid question structure from LLM" in response["message"])


    def test_generate_assessment_llm_returns_mismatched_kp_id(self):
        """Test _generate_assessment when LLM returns questions for a KP ID not requested."""
        session_id = "sess_gen_llm_mismatch_kp"
        requested_kp_ids = ["kp_requested"]
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": {"id": "kp_requested", "content": "Content"}},
            {"status": "success"}
        ]
        llm_output = json.dumps([{"knowledge_point_id": "kp_unrequested", "text": "Q for wrong KP", "type": "default"}])
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": llm_output}}

        response = self.assessor_module._generate_assessment(session_id, requested_kp_ids, "default_type", "medium")
        
        self.assertEqual(response["status"], "error") # Or success with 0 questions if it filters them
        # Current logic filters these out, leading to "No valid questions"
        self.assertEqual(response["message"], "No valid questions generated by LLM.")


    def test_generate_assessment_llm_no_valid_questions(self):
        """Test _generate_assessment when LLM returns an empty list or all questions are invalid."""
        session_id = "sess_gen_llm_no_valid"
        kp_ids = ["kp_no_valid_q"]
        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": {"id": "kp_no_valid_q", "content": "Content"}},
            {"status": "success"}
        ]
        llm_output = json.dumps([]) # Empty list of questions
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": llm_output}}

        response = self.assessor_module._generate_assessment(session_id, kp_ids, "default_type", "medium")

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "No valid questions generated by LLM.")

    def test_generate_assessment_mbm_save_assessment_error(self):
        """Test _generate_assessment when MBM fails to save the generated assessment."""
        session_id = "sess_gen_mbm_save_err"
        kp_ids = ["kp_save_err"]
        
        def mock_mbm_process_request_save_fail(request):
            if request["operation"] == "get_knowledge_point":
                return {"status": "success", "data": {"id": "kp_save_err", "content": "Content"}}
            elif request["operation"] == "save_generated_assessment":
                return {"status": "error", "message": "DB save failed"} # MBM save fails
            return {"status": "error", "message": "Unknown op"}

        self.mock_memory_bank_manager.process_request.side_effect = mock_mbm_process_request_save_fail
        llm_output = json.dumps([{"knowledge_point_id": "kp_save_err", "text": "A question", "type": "default"}])
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": llm_output}}

        response = self.assessor_module._generate_assessment(session_id, kp_ids, "default_type", "medium")

        self.assertEqual(response["status"], "error")
        self.assertTrue("Failed to save the generated assessment: DB save failed" in response["message"])

if __name__ == '__main__':
    unittest.main()