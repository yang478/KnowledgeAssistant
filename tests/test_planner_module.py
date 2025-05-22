"""Unit tests for the PlannerModule class."""

import unittest
from unittest.mock import patch, MagicMock, ANY

# Ensure the necessary modules can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from planner_module.planner_module import PlannerModule
from memory_bank_manager.memory_bank_manager import MemoryBankManager # For spec
from llm_interface.llm_interface import LLMInterface # For spec
from config_manager.config_manager import ConfigManager # For spec
from monitoring_manager.monitoring_manager import MonitoringManager # For spec

class TestPlannerModule(unittest.TestCase):
    """Tests for the PlannerModule."""

    def setUp(self):
        """Set up a PlannerModule instance with mocked dependencies."""
        self.mock_memory_bank_manager = MagicMock(spec=MemoryBankManager)
        self.mock_llm_interface = MagicMock(spec=LLMInterface)
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_monitoring_manager = MagicMock(spec=MonitoringManager)

        # Simulate config for planner (simplified)
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: {
            "planner_module.default_planning_strategy": "standard",
            "planner_module.llm_prompt_template.goal_analysis": "Analyze this goal: {goal}",
            "planner_module.llm_prompt_template.plan_generation": "Generate plan for topics: {topics}",
        }.get(key, default)

        self.planner_module = PlannerModule(
            memory_bank_manager=self.mock_memory_bank_manager,
            llm_interface=self.mock_llm_interface,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
        )

    def test_initialization(self):
        """Test that PlannerModule initializes correctly."""
        self.assertIsNotNone(self.planner_module.memory_bank_manager)
        self.assertIsNotNone(self.planner_module.llm_interface)
        self.assertIsNotNone(self.planner_module.config_manager)
        self.assertIsNotNone(self.planner_module.monitoring_manager)
        # Note: The actual log method on monitoring_manager might be log_info, log_error, etc.
        # Assuming the PlannerModule's __init__ calls self.monitoring_manager.log_info(...)
        self.mock_monitoring_manager.log_info.assert_any_call("PlannerModule initialized.")

    def test_generate_study_plan_success_with_goal(self):
        """Test successful study plan generation given a user goal."""
        # Arrange
        session_id = "sess_plan_goal"
        user_input_goal = "master python data structures" # This is the user_input to handle_request
        # current_mode_name will be 'planner' when generate_study_plan is called by ModeController
        
        # Mock MBM calls
        # Assume get_all_syllabus_topics is called to get a list of available topics
        mock_syllabus_topics = [
            {"id": "kp_lists", "title": "Python Lists", "dependencies": [], "status": "not_started"},
            {"id": "kp_dicts", "title": "Python Dictionaries", "dependencies": [], "status": "not_started"},
            {"id": "kp_sets", "title": "Python Sets", "dependencies": ["kp_lists"], "status": "learning"},
        ]
        # self.mock_memory_bank_manager.get_all_syllabus_topics.return_value = mock_syllabus_topics # Replaced by process_request mock

        mock_assessment_log_data = { # Example assessment log data
            "kp_lists": [{"timestamp": "2023-01-01T10:00:00Z", "score": 0.7, "passed": False}]
        }

        def mock_process_request_side_effect(request_dict):
            operation = request_dict.get("operation")
            if operation == "get_all_syllabus_topics":
                return {"status": "success", "data": mock_syllabus_topics}
            elif operation == "get_assessment_log":
                return {"status": "success", "data": mock_assessment_log_data}
            return {"status": "error", "message": f"Unknown MBM operation: {operation}"}

        self.mock_memory_bank_manager.process_request.side_effect = mock_process_request_side_effect
        
        # Mock LLM call for goal analysis (optional, depends on implementation)
        # Let's assume it identifies relevant KPs from the goal
        self.mock_llm_interface.generate_text.side_effect = [
            {"status": "success", "data": {"text": "Relevant KPs: kp_lists, kp_dicts"}}, # Goal analysis
            {"status": "success", "data": {"text": "Plan: 1. Learn Lists. 2. Learn Dictionaries."}} # Plan generation
        ]

        expected_plan_steps = [
            {"knowledge_point_id": "kp_lists", "title": "Python Lists", "action": "学习"},
            {"knowledge_point_id": "kp_dicts", "title": "Python Dictionaries", "action": "学习"},
        ]
        # The actual structure of the plan will depend on the PlannerModule's internal logic

        # Act
        # The user_input to generate_study_plan might be the raw input or processed goal
        response = self.planner_module.generate_study_plan(
            session_id=session_id, 
            user_input=user_input_goal, # This is the user_input from ModeController
            current_mode_name="planner" # Passed by ModeController
        )

        # Assert
        self.mock_monitoring_manager.log.assert_any_call(
            "info", f"Generating study plan for session {session_id} with input: {user_input_goal}", ANY
        )
        # Check MBM calls (example)
        # self.mock_memory_bank_manager.get_all_syllabus_topics.assert_called_once() # Replaced
        self.mock_memory_bank_manager.process_request.assert_any_call(
            {"operation": "get_all_syllabus_topics", "payload": {}}
        )
        self.mock_memory_bank_manager.process_request.assert_any_call(
            {"operation": "get_assessment_log", "payload": {"session_id": session_id}}
        )
        
        # Check LLM calls (example)
        # First call for goal analysis (if implemented)
        # Second call for plan generation based on identified topics/KPs
        # The exact prompts depend on internal logic and templates from config
        self.mock_llm_interface.generate_text.assert_any_call(
            prompt=ANY, # Prompt for goal analysis
            model_config=None # Or specific config
        )
        # The second call's prompt would be based on the result of the first, or syllabus topics
        # This part is highly dependent on the internal logic of generate_study_plan

        self.assertEqual(response["status"], "success")
        self.assertIn("plan_id", response["data"])
        self.assertIn("steps", response["data"])
        self.assertIn("summary", response["data"])
        # More detailed assertions on response["data"]["steps"] would require knowing the exact output format
        # For now, just check that it's a list
        self.assertIsInstance(response["data"]["steps"], list)
        # Example: self.assertEqual(response["data"]["summary"], "Plan: 1. Learn Lists. 2. Learn Dictionaries.")

    def test_generate_study_plan_mbm_error(self):
        """Test error handling when MemoryBankManager fails."""
        # Arrange
        session_id = "sess_plan_mbm_err"
        user_input = "make a plan"
        # self.mock_memory_bank_manager.get_all_syllabus_topics.side_effect = Exception("DB connection failed") # Replaced
        
        # Simulate MBM returning an error status for "get_all_syllabus_topics"
        self.mock_memory_bank_manager.process_request.return_value = {
            "status": "error",
            "message": "MBM DB connection failed"
        }

        # Act
        response = self.planner_module.generate_study_plan(session_id, user_input, "planner")

        # Assert
        self.assertEqual(response["status"], "error")
        # PlannerModule._generate_plan constructs the error message based on the MBM response
        self.assertTrue("Failed to retrieve knowledge points from MemoryBankManager: MBM DB connection failed" in response["message"])
        self.mock_monitoring_manager.log_error.assert_any_call( # Assuming log_error is used
            "Failed to retrieve knowledge points from MemoryBankManager: MBM DB connection failed",
            {"session_id": session_id}
        )

    def test_generate_study_plan_llm_error(self):
        """Test error handling when LLMInterface fails."""
        # Arrange
        session_id = "sess_plan_llm_err"
        user_input = "plan advanced topics"
        # self.mock_memory_bank_manager.get_all_syllabus_topics.return_value = [{"id": "kp_adv", "title": "Advanced"}] # Replaced
        
        # Simulate MBM succeeding for "get_all_syllabus_topics" and "get_assessment_log"
        # but LLM failing.
        mock_syllabus_topics_adv = [{"id": "kp_adv", "title": "Advanced", "dependencies": [], "status": "not_started"}]
        mock_assessment_log_empty = {}

        def mock_process_request_llm_fail_side_effect(request_dict):
            operation = request_dict.get("operation")
            if operation == "get_all_syllabus_topics":
                return {"status": "success", "data": mock_syllabus_topics_adv}
            elif operation == "get_assessment_log":
                 return {"status": "success", "data": mock_assessment_log_empty}
            return {"status": "error", "message": f"Unknown MBM operation: {operation}"}
        
        self.mock_memory_bank_manager.process_request.side_effect = mock_process_request_llm_fail_side_effect
        self.mock_llm_interface.generate_text.return_value = {"status": "error", "message": "LLM API unavailable"}

        # Act
        response = self.planner_module.generate_study_plan(session_id, user_input, "planner")

        # Assert
        self.assertEqual(response["status"], "error")
        self.assertTrue("Error interacting with LLM" in response["message"]) # This check depends on PlannerModule's LLM error handling
        # The PlannerModule's _generate_plan doesn't explicitly have LLM error handling that returns this specific message.
        # It calls LLM for goal analysis (TODO) and potentially plan summarization (TODO).
        # For now, let's assume the LLM error would manifest differently or this test needs refinement
        # based on actual LLM integration points in _generate_plan.
        # If LLM is called and fails, the monitoring log should reflect that.
        # self.mock_monitoring_manager.log_error.assert_any_call( ... ) # This depends on where LLM is called and how errors are logged.
    
    def test_analyze_progress_success(self):
        """Test successful progress analysis."""
        # Arrange
        session_id = "sess_analyze"
        user_id = "user123" # Assuming analyze_progress might need user_id
        
        # Mock MBM calls for progress data
        mock_progress_data = {
            "total_knowledge_points": 50,
            "mastered_count": 20,
            "learning_count": 10,
            "not_started_count": 20,
            "overall_progress_percentage": 50.0 # (20 mastered + 0.5 * 10 learning) / 50
        }
        # Assuming a method in MBM that provides such aggregated data
        self.mock_memory_bank_manager.get_progress_summary.return_value = mock_progress_data
        
        # Act
        # Assuming analyze_progress is another method in PlannerModule
        # If it's not, this test needs to be adapted or removed.
        # The design doc lists "analyze_progress" under PlannerModule.
        response = self.planner_module.analyze_progress(session_id=session_id, user_id=user_id)

        # Assert
        self.mock_monitoring_manager.log.assert_any_call(
            "info", f"Analyzing progress for session {session_id}, user {user_id}", ANY
        )
        self.mock_memory_bank_manager.get_progress_summary.assert_called_once_with(user_id=user_id)
        
        self.assertEqual(response["status"], "success")
        self.assertIn("summary", response["data"])
        self.assertIn("statistics", response["data"])
        self.assertEqual(response["data"]["statistics"]["mastered_count"], 20)
        self.assertTrue("Overall progress is 50.0%" in response["data"]["summary"])


if __name__ == '__main__':
    unittest.main()
