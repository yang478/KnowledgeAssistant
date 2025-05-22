"""Unit tests for the AssessorModule class - Handle Request focused."""

import unittest
from unittest.mock import patch, MagicMock, ANY
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from assessor_module.assessor_module import AssessorModule
from memory_bank_manager.memory_bank_manager import MemoryBankManager # For spec
from llm_interface.llm_interface import LLMInterface # For spec
from config_manager.config_manager import ConfigManager # For spec
from monitoring_manager.monitoring_manager import MonitoringManager # For spec
from update_manager.update_manager import UpdateManager # For spec

# Helper function for test_handle_request_generic_exception
def raiser_func_for_test_generic_exception(*args, **kwargs):
    raise RuntimeError("Raised by raiser_func for test_generic_exception")

class TestAssessorModule(unittest.TestCase):
    """Tests for the AssessorModule - Handle Request focused."""

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
            "assessor.prompts.evaluate_answer": {
                "multiple_choice": "Evaluate this MCQ answer. KP: {knowledge_point_id}, Q: {original_question}, A: {user_answer}, Opts: {options}. Provide score, correct, feedback, new_mastery_status.",
                "short_answer": "Evaluate this short answer. KP: {knowledge_point_id}, Q: {original_question}, A: {user_answer}. Provide score, correct, feedback, new_mastery_status.",
                "default": "Evaluate this answer. KP: {knowledge_point_id}, Q: {original_question}, A: {user_answer}. Provide score, correct, feedback, new_mastery_status."
            },
            "assessor.default_question_type": "multiple_choice",
            "assessor.difficulty_levels": {"easy": {}, "medium": {}, "hard": {}},
            "assessor.llm_config.generation": {"default": {"temperature": 0.7}},
            "assessor.llm_config.evaluation": {"default": {"temperature": 0.5}},
            "assessor.generation_strategies": {"multiple_choice": {"use_question_bank": False}},
            "assessor.evaluation_strategies": {"multiple_choice": {"direct_comparison": False}},
            "assessor.scoring_rubrics": {},
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

    def test_initialization(self):
        """Test that AssessorModule initializes correctly."""
        self.assertIsNotNone(self.assessor_module.memory_bank_manager)
        self.assertIsNotNone(self.assessor_module.llm_interface)
        self.assertIsNotNone(self.assessor_module.config_manager)
        self.assertIsNotNone(self.assessor_module.monitoring_manager)
        self.assertIsNotNone(self.assessor_module.update_manager)
        self.mock_monitoring_manager.log_info.assert_called_once_with("AssessorModule initialized with configurations.")

    def test_handle_request_generate_assessment_missing_kp_ids(self):
        """Test handle_request with generate_assessment and missing knowledge_point_ids."""
        session_id = "sess_handle_gen_missing_kp"
        request_type = "generate_assessment"
        payload = {"assessment_type": "multiple_choice", "difficulty": "medium"} # Missing knowledge_point_ids

        response = self.assessor_module.handle_request(session_id, request_type, payload)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "knowledge_point_ids are required to generate an assessment.")
        self.mock_monitoring_manager.log_warning.assert_called_with(
            "generate_assessment request missing knowledge_point_ids.",
            {"session_id": session_id}
        )

    def test_handle_request_submit_assessment_missing_assessment_id(self):
        """Test handle_request with submit_assessment and missing assessment_id."""
        session_id = "sess_handle_submit_missing_id"
        request_type = "submit_assessment"
        payload = {"answers": [{"question_id": "q1", "answer": "A"}]} # Missing assessment_id

        response = self.assessor_module.handle_request(session_id, request_type, payload)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "assessment_id and answers list are required for submit_assessment.")
        self.mock_monitoring_manager.log_error.assert_called_with(
            "submit_assessment request missing assessment_id or answers.",
            {"session_id": session_id}
        )

    def test_handle_request_submit_assessment_missing_answers(self):
        """Test handle_request with submit_assessment and missing answers."""
        session_id = "sess_handle_submit_missing_ans"
        request_type = "submit_assessment"
        payload = {"assessment_id": "assess123"} # Missing answers

        response = self.assessor_module.handle_request(session_id, request_type, payload)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "assessment_id and answers list are required for submit_assessment.")
        self.mock_monitoring_manager.log_error.assert_called_with(
            "submit_assessment request missing assessment_id or answers.",
            {"session_id": session_id}
        )

    def test_handle_request_unsupported_request_type(self):
        """Test handle_request with an unsupported request_type."""
        session_id = "sess_handle_unsupported"
        request_type = "unknown_request_type"
        payload = {}

        response = self.assessor_module.handle_request(session_id, request_type, payload)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], f"Unsupported request type for AssessorModule: {request_type}")
        self.mock_monitoring_manager.log_warning.assert_called_with(
            f"Unsupported request type received: {request_type}",
            {"session_id": session_id}
        )

    @patch('src.assessor_module.assessor_module.AssessorModule._generate_assessment', side_effect=raiser_func_for_test_generic_exception)
    def test_handle_request_generic_exception(self, mock_generate_assessment):
        """Test handle_request when an unexpected Exception occurs."""
        session_id = "sess_handle_generic_exception"
        request_type = "generate_assessment"
        payload = {"knowledge_point_ids": ["kp1"]}

        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": {"id": "kp1", "title": "KP Title", "content": "KP Content"}},
            {"status": "success"}
        ]
        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": json.dumps([{"knowledge_point_id": "kp1", "text": "A question", "type": "default"}])}}

        response = self.assessor_module.handle_request(session_id, request_type, payload)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["message"], "An internal server error occurred in AssessorModule.")
        self.mock_monitoring_manager.log_error.assert_called_with(
            "Unhandled exception in AssessorModule.handle_request: Raised by raiser_func for test_generic_exception",
            {"session_id": session_id},
            exc_info=True
        )
        mock_generate_assessment.assert_called_once()

if __name__ == '__main__':
    unittest.main()