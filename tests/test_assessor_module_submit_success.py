"""Unit tests for the AssessorModule class - Submit Assessment Success focused."""

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
    """Tests for the AssessorModule - Submit Assessment Success focused."""

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

    def test_submit_assessment_success(self):
        """Test successful submission and evaluation of assessment answers."""
        session_id = "sess_submit_assess"
        assessment_id = "assess_xyz123"
        q1_id = "q_uuid_kp1"
        q2_id = "q_uuid_kp2"
        
        user_answers = [
            {"question_id": q1_id, "answer": "Correct answer for q1"},
            {"question_id": q2_id, "answer": "Slightly off for q2"},
        ]
        
        mock_retrieved_assessment_data = {
            "assessment_id": assessment_id,
            "questions": [
                {"question_id": q1_id, "knowledge_point_id": "kp1", "text": "Q1 Text", "type": "short_answer"},
                {"question_id": q2_id, "knowledge_point_id": "kp2", "text": "Q2 Text", "type": "short_answer"}
            ]
        }
        
        llm_eval_q1_output = json.dumps({"score": 100, "correct": True, "feedback": "Well done.", "new_mastery_status": "mastered"})
        llm_eval_q2_output = json.dumps({"score": 50, "correct": False, "feedback": "Check concept X.", "new_mastery_status": "learning"})
        
        def mock_mbm_process_request_submit(request):
            if request["operation"] == "get_generated_assessment":
                if request["payload"]["assessment_id"] == assessment_id:
                    return {"status": "success", "data": mock_retrieved_assessment_data}
            elif request["operation"] == "save_assessment_log":
                return {"status": "success"}
            return {"status": "error", "message": "Unknown operation in submit mock"}

        self.mock_memory_bank_manager.process_request.side_effect = mock_mbm_process_request_submit
        self.mock_llm_interface.generate_text.side_effect = [
            {"status": "success", "data": {"text": llm_eval_q1_output}},
            {"status": "success", "data": {"text": llm_eval_q2_output}},
        ]

        response = self.assessor_module._submit_assessment(
            session_id=session_id,
            assessment_id=assessment_id,
            answers=user_answers
        )

        self.mock_monitoring_manager.log_info.assert_any_call(
            f"Submitting assessment for session: {session_id}",
            {"assessment_id": assessment_id, "num_answers": len(user_answers)}
        )
        self.assertEqual(self.mock_memory_bank_manager.process_request.call_count, 2)
        mbm_calls_submit = self.mock_memory_bank_manager.process_request.call_args_list
        self.assertEqual(mbm_calls_submit[0][0][0]["operation"], "get_generated_assessment")
        self.assertEqual(self.mock_llm_interface.generate_text.call_count, 2)
        self.assertEqual(mbm_calls_submit[1][0][0]["operation"], "save_assessment_log")
        self.mock_update_manager.trigger_backup.assert_called_once()
        update_call_args = self.mock_update_manager.trigger_backup.call_args
        self.assertEqual(update_call_args[1]['event'], "assessment_completed")
        self.assertEqual(len(update_call_args[1]['payload']["updates"]), 2)

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["results"]), 2)
        self.assertIn("overall_score", response["data"])

    def test_submit_assessment_direct_comparison_true_correct(self):
        """Test _submit_assessment with direct_comparison True and correct answer."""
        session_id = "sess_submit_direct_corr"
        assessment_id = "assess_direct_corr"
        q_id = "q_direct_1"
        user_answers = [{"question_id": q_id, "answer": "Option A"}]
        
        mock_retrieved_assessment_data = {
            "assessment_id": assessment_id,
            "questions": [{
                "question_id": q_id, "knowledge_point_id": "kp_direct", "text": "MCQ Q1", 
                "type": "multiple_choice", "options": ["Option A", "Option B"], "correct_answer": "Option A"
            }]
        }
        
        temp_mock_configs = copy.deepcopy(self.mock_configs)
        assessment_type = "multiple_choice"
        if "assessor.evaluation_strategies" not in temp_mock_configs:
            temp_mock_configs["assessor.evaluation_strategies"] = {}
        if assessment_type not in temp_mock_configs["assessor.evaluation_strategies"]:
            temp_mock_configs["assessor.evaluation_strategies"][assessment_type] = {}
        temp_mock_configs["assessor.evaluation_strategies"][assessment_type]["direct_comparison"] = True
        
        original_side_effect = self.mock_config_manager.get_config.side_effect
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: temp_mock_configs.get(key, default)

        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data}, # get_assessment
            {"status": "success"} # save_log
        ]
        
        current_assessor_module = AssessorModule(
            memory_bank_manager=self.mock_memory_bank_manager,
            llm_interface=self.mock_llm_interface,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
            update_manager=self.mock_update_manager,
        )
        response = current_assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["results"]), 1)
        self.assertTrue(response["data"]["results"][0]["correct"])
        self.assertEqual(response["data"]["results"][0]["score"], 100)
        self.mock_llm_interface.generate_text.assert_not_called() # LLM should not be called
        self.mock_config_manager.get_config.side_effect = original_side_effect

    def test_submit_assessment_direct_comparison_true_incorrect(self):
        """Test _submit_assessment with direct_comparison True and incorrect answer."""
        session_id = "sess_submit_direct_incorr"
        assessment_id = "assess_direct_incorr"
        q_id = "q_direct_2"
        user_answers = [{"question_id": q_id, "answer": "Option C"}] # Incorrect
        
        mock_retrieved_assessment_data = {
            "assessment_id": assessment_id,
            "questions": [{
                "question_id": q_id, "knowledge_point_id": "kp_direct_inc", "text": "MCQ Q2", 
                "type": "multiple_choice", "options": ["X", "Y"], "correct_answer": "X"
            }]
        }
        
        temp_mock_configs = copy.deepcopy(self.mock_configs)
        assessment_type = "multiple_choice"
        if "assessor.evaluation_strategies" not in temp_mock_configs:
            temp_mock_configs["assessor.evaluation_strategies"] = {}
        if assessment_type not in temp_mock_configs["assessor.evaluation_strategies"]:
            temp_mock_configs["assessor.evaluation_strategies"][assessment_type] = {}
        temp_mock_configs["assessor.evaluation_strategies"][assessment_type]["direct_comparison"] = True
        
        original_side_effect = self.mock_config_manager.get_config.side_effect
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: temp_mock_configs.get(key, default)

        self.mock_memory_bank_manager.process_request.side_effect = [
            {"status": "success", "data": mock_retrieved_assessment_data},
            {"status": "success"}
        ]
        
        current_assessor_module = AssessorModule(
            memory_bank_manager=self.mock_memory_bank_manager,
            llm_interface=self.mock_llm_interface,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
            update_manager=self.mock_update_manager,
        )
        response = current_assessor_module._submit_assessment(session_id, assessment_id, user_answers)

        self.assertEqual(response["status"], "success")
        self.assertEqual(len(response["data"]["results"]), 1)
        self.assertFalse(response["data"]["results"][0]["correct"])
        self.assertEqual(response["data"]["results"][0]["score"], 0)
        self.mock_llm_interface.generate_text.assert_not_called()
        self.mock_config_manager.get_config.side_effect = original_side_effect

if __name__ == '__main__':
    unittest.main()