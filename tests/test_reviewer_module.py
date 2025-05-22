"""Unit tests for the ReviewerModule class."""

import unittest
from unittest.mock import patch, MagicMock, ANY

# Ensure the necessary modules can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from reviewer_module.reviewer_module import ReviewerModule
from memory_bank_manager.memory_bank_manager import MemoryBankManager # For spec
from llm_interface.llm_interface import LLMInterface # For spec
from config_manager.config_manager import ConfigManager # For spec
from monitoring_manager.monitoring_manager import MonitoringManager # For spec
from update_manager.update_manager import UpdateManager # For spec

class TestReviewerModule(unittest.TestCase):
    """Tests for the ReviewerModule."""

    def setUp(self):
        """Set up a ReviewerModule instance with mocked dependencies."""
        self.mock_memory_bank_manager = MagicMock(spec=MemoryBankManager)
        self.mock_llm_interface = MagicMock(spec=LLMInterface)
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_monitoring_manager = MagicMock(spec=MonitoringManager)
        self.mock_update_manager = MagicMock(spec=UpdateManager)

        # Simulate config for reviewer (simplified)
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: {
            "reviewer_module.review_strategy": "spaced_repetition_v1",
            "reviewer_module.llm_prompt_template.summarize_for_review": "Summarize key points for: {topic_content}",
            "reviewer_module.max_review_items": 5,
        }.get(key, default)

        self.reviewer_module = ReviewerModule(
            memory_bank_manager=self.mock_memory_bank_manager,
            llm_interface=self.mock_llm_interface,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager
        )

    def test_initialization(self):
        """Test that ReviewerModule initializes correctly."""
        self.assertIsNotNone(self.reviewer_module.memory_bank_manager)
        self.assertIsNotNone(self.reviewer_module.llm_interface)
        self.assertIsNotNone(self.reviewer_module.config_manager)
        self.assertIsNotNone(self.reviewer_module.monitoring_manager)
        # self.assertIsNotNone(self.reviewer_module.um) # um is not a direct dependency of ReviewerModule __init__
        # Assuming ReviewerModule.__init__ calls self.monitoring_manager.log_info(...)
        self.mock_monitoring_manager.log_info.assert_any_call("ReviewerModule initialized.")

    def test_get_review_suggestions_success(self):
        """Test successful retrieval of review suggestions."""
        # Arrange
        session_id = "sess_get_review"
        user_input = "what should I review?" # Input to the handler in ModeController
        # current_mode_name is 'reviewer'

        mock_all_topics_data = [
            {"id": "kp1", "title": "Topic 1", "status": "mastered", "last_reviewed": "2023-01-01T00:00:00Z", "priority_score": 0.5},
            {"id": "kp2", "title": "Topic 2", "status": "learning", "last_reviewed": "2023-03-01T00:00:00Z", "priority_score": 0.9}, # Higher score
            {"id": "kp3", "title": "Topic 3", "status": "mastered", "last_reviewed": "2023-02-15T00:00:00Z", "priority_score": 0.7},
        ]
        # Assume MBM has a method that returns topics with calculated review scores or relevant data
        # self.mock_memory_bank_manager.get_topics_for_review.return_value = sorted(  # Replaced by process_request
        #     mock_all_topics_data, key=lambda x: x["priority_score"], reverse=True
        # )
        self.mock_memory_bank_manager.process_request.return_value = {
            "status": "success",
            "data": sorted(mock_all_topics_data, key=lambda x: x["priority_score"], reverse=True)
        }
        
        # Act
        # get_review_suggestions is the main entry point from ModeController
        response = self.reviewer_module.get_review_suggestions(
            session_id=session_id,
            user_input=user_input, 
            current_mode_name="reviewer"
        )

        # Assert
        self.mock_monitoring_manager.log_info.assert_any_call( # Changed to log_info
            f"Getting review suggestions for session {session_id}." # Removed ANY for direct string match if appropriate
        )
        # self.mock_memory_bank_manager.get_topics_for_review.assert_called_once_with( # Replaced
        #     user_id=ANY,
        #     strategy="spaced_repetition_v1",
        #     max_items=5
        # )
        self.mock_memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_kps_for_review", # Actual operation name from MBM
            "payload": {
                "user_id": ANY, # Or session_id, depending on ReviewerModule's internal logic
                "strategy": "spaced_repetition_v1",
                "limit": 5
            }
        })
        
        self.assertEqual(response["status"], "success")
        self.assertIn("suggestions", response["data"])
        self.assertIsInstance(response["data"]["suggestions"], list)
        self.assertEqual(len(response["data"]["suggestions"]), 3) # All 3 topics returned, sorted
        self.assertEqual(response["data"]["suggestions"][0]["knowledge_point_id"], "kp2") # Highest priority
        self.assertEqual(response["data"]["suggestions"][1]["knowledge_point_id"], "kp3")
        self.assertEqual(response["data"]["suggestions"][2]["knowledge_point_id"], "kp1")


    def test_provide_review_material_success(self):
        """Test successful provision of review material for a specific knowledge point."""
        # Arrange
        session_id = "sess_provide_review"
        user_input_kp_request = "review kp_functions" # User input might be "review functions"
                                                    # and internal logic maps to "kp_functions"
        
        # Assume internal logic extracts knowledge_point_id from user_input
        knowledge_point_id = "kp_functions"
        
        mock_kp_data = {"id": knowledge_point_id, "title": "Python Functions", "content": "Functions are blocks of code..."}
        # self.mock_memory_bank_manager.get_knowledge_point.return_value = mock_kp_data # Replaced

        # update_progress mock response
        mock_update_progress_response = {"status": "success"}

        def provide_material_process_request_side_effect(request_dict):
            operation = request_dict.get("operation")
            payload = request_dict.get("payload", {})
            if operation == "get_kp" and payload.get("id") == knowledge_point_id:
                return {"status": "success", "data": mock_kp_data}
            elif operation == "update_progress" and payload.get("knowledge_point_id") == knowledge_point_id:
                return mock_update_progress_response
            return {"status": "error", "message": f"Unhandled MBM operation: {operation} in provide_material test"}

        self.mock_memory_bank_manager.process_request.side_effect = provide_material_process_request_side_effect
        
        llm_summary = "Key points about functions: ..."
        self.mock_llm_interface.generate_text.return_value = {
            "status": "success", "data": {"text": llm_summary}
        }

        # Act
        # provide_review_material is the main entry point from ModeController
        response = self.reviewer_module.provide_review_material(
            session_id=session_id,
            user_input=user_input_kp_request, # Contains the KP to review
            current_mode_name="reviewer"
        )

        # Assert
        self.mock_monitoring_manager.log_info.assert_any_call( # Changed to log_info
            f"Providing review material for session {session_id}, input: {user_input_kp_request}"
        )
        # self.mock_memory_bank_manager.get_knowledge_point.assert_called_once_with(ANY) # Replaced
        
        # LLM generate_text for summary
        # expected_prompt_summary = f"Summarize key points for: {mock_kp_data['content']}"
        self.mock_llm_interface.generate_text.assert_called_once_with(prompt=ANY, model_config=None)
        
        # self.mock_memory_bank_manager.update_progress.assert_called_once_with( # Replaced
        #     knowledge_point_id=ANY,
        #     updates={"last_reviewed": ANY}
        # )

        # Assert calls to process_request
        self.mock_memory_bank_manager.process_request.assert_any_call({
            "operation": "get_kp",
            "payload": {"id": knowledge_point_id} # Assuming ReviewerModule extracts this ID
        })
        self.mock_memory_bank_manager.process_request.assert_any_call({
            "operation": "update_progress",
            "payload": {"knowledge_point_id": knowledge_point_id, "updates": {"last_reviewed": ANY}}
        })
        
        self.mock_update_manager.trigger_update.assert_called_once()

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["response"]["type"], "review_material")
        self.assertEqual(response["response"]["knowledge_point_id"], knowledge_point_id)
        self.assertEqual(response["response"]["title"], mock_kp_data["title"])
        self.assertEqual(response["response"]["content"], llm_summary) # Or a mix of original and summary

    def test_get_review_suggestions_mbm_error(self):
        """Test error handling if MBM fails during suggestion retrieval."""
        # Arrange
        session_id = "sess_review_mbm_err"
        user_input = "review"
        # self.mock_memory_bank_manager.get_topics_for_review.side_effect = Exception("MBM DB error") # Replaced
        self.mock_memory_bank_manager.process_request.return_value = {
            "status": "error", "message": "MBM DB error from process_request"
        }
        # Act
        response = self.reviewer_module.get_review_suggestions(session_id, user_input, "reviewer")

        # Assert
        self.assertEqual(response["status"], "error")
        self.assertTrue("Failed to retrieve review suggestions: MBM DB error from process_request" in response["message"])
        self.mock_monitoring_manager.log_error.assert_any_call( # Changed to log_error
            "Error getting review suggestions: MBM DB error from process_request"
        )

    def test_provide_review_material_kp_not_found(self):
        """Test error handling if the requested knowledge point for review is not found."""
        # Arrange
        session_id = "sess_provide_kp_not_found"
        user_input_non_existent_kp = "review kp_non_existent"
        # self.mock_memory_bank_manager.get_knowledge_point.return_value = None # Replaced
        
        # Simulate MBM returning None (or error) when "get_kp" is called for a non-existent KP
        def kp_not_found_process_request_side_effect(request_dict):
            operation = request_dict.get("operation")
            # payload = request_dict.get("payload", {}) # Assuming ReviewerModule extracts 'kp_non_existent_id'
            if operation == "get_kp": # And payload ID matches "kp_non_existent_id"
                return {"status": "success", "data": None} # KP not found
            return {"status": "error", "message": "Unhandled MBM op in kp_not_found test"}

        self.mock_memory_bank_manager.process_request.side_effect = kp_not_found_process_request_side_effect
        # Act
        response = self.reviewer_module.provide_review_material(session_id, user_input_non_existent_kp, "reviewer")

        # Assert
        self.assertEqual(response["status"], "error")
        # The exact KP ID extracted depends on internal logic
        self.assertTrue("Knowledge point" in response["message"]) 
        self.assertTrue("not found" in response["message"])
        self.mock_llm_interface.generate_text.assert_not_called()
        self.mock_memory_bank_manager.update_progress.assert_not_called()

if __name__ == '__main__':
    unittest.main()
