"""Unit tests for the MemoryBankManager class."""

import unittest
from unittest.mock import MagicMock, ANY, patch # Restore patch import

# Ensure the necessary modules can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.memory_bank_manager.db_utils import DBUtil # Import for spec
from config_manager.config_manager import ConfigManager # For spec
from monitoring_manager.monitoring_manager import MonitoringManager # For spec

# Define constants for patch targets
MODULE_PATH_MBM_INTERNAL = "src.memory_bank_manager.memory_bank_manager"
MODULE_PATH_DB_UTILS = "src.memory_bank_manager.db_utils" # Path where DBUtil is defined

class TestMemoryBankManager(unittest.TestCase):
    """Tests for the MemoryBankManager."""

    # Restore standard patching using decorators for ALL managers
    # Try patching DBUtil where it's DEFINED as a last resort
    @patch(f"{MODULE_PATH_DB_UTILS}.DBUtil", autospec=True)               # Innermost patch
    @patch(f"{MODULE_PATH_MBM_INTERNAL}.KnowledgePointManager", autospec=True)
    @patch(f"{MODULE_PATH_MBM_INTERNAL}.LearningContextManager", autospec=True)
    @patch(f"{MODULE_PATH_MBM_INTERNAL}.AssessmentDataManager", autospec=True)
    @patch(f"{MODULE_PATH_MBM_INTERNAL}.ResourceManager", autospec=True)
    @patch(f"{MODULE_PATH_MBM_INTERNAL}.BackupManager", autospec=True) # Re-added autospec=True
    def setUp(
        self,
        # Order corresponds to REVERSE order of decorators
        MockBackupManager, # Now autospec'd
        MockResourceManager,
        MockAssessmentDataManager,
        MockLearningContextManager,
        MockKnowledgePointManager,
        MockDBUtil # Added back, corresponds to DBUtil patch
    ):
        """Set up a MemoryBankManager instance with mocked dependencies."""
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_monitoring_manager = MagicMock(spec=MonitoringManager)

        # --- Configure standard mocks from decorators ---
        # Configure DBUtil mock
        MockDBUtil.__file__ = "src/memory_bank_manager/db_utils.py" # Configure CLASS attribute
        
        # Create a mock instance that will be returned by MockDBUtil()
        # This instance should already have init_db configured by autospec.
        mock_configured_db_instance = MagicMock(spec=DBUtil) # Use DBUtil for spec if available, else rely on autospec from class
        # mock_configured_db_instance.init_db = MagicMock(return_value=None, name='ConfiguredInitDBOnInstance') # autospec should handle this
        MockDBUtil.return_value = mock_configured_db_instance
        self.mock_db_utils_instance = mock_configured_db_instance # Store for assertions

        # Configure other mocks
        self.mock_kp_manager_instance = MockKnowledgePointManager.return_value
        self.mock_lc_manager_instance = MockLearningContextManager.return_value
        self.mock_ad_manager_instance = MockAssessmentDataManager.return_value
        self.mock_res_manager_instance = MockResourceManager.return_value
        
        # BackupManager is now autospec'd. Its return_value will be an instance
        # that already has methods like perform_backup (as MagicMocks) if they exist on the real class.
        self.mock_backup_manager_instance = MockBackupManager.return_value
        # We can further configure these if needed for specific test return values, e.g.:
        # self.mock_backup_manager_instance.perform_backup.return_value = {"status": "success"}
        # For the AttributeError, their mere existence as MagicMocks due to autospec is key.


        # Simulate db_path from config
        def mock_get_config_side_effect(key, default_val=None):
            if key == "DATABASE_SETTINGS":
                # Return a dict with db_path and potentially schema_file if needed
                return {"db_path": "dummy_path/test.db", "schema_file": None} 
            elif key == "BACKUP_SETTINGS":
                 return {"backup_directory": "dummy_backups/", "max_backups": 5}
            # For other keys, return the default value that was passed to get_config
            return default_val
        self.mock_config_manager.get_config.side_effect = mock_get_config_side_effect

        # Instantiate the MemoryBankManager (should happen after mocks are configured)
        self.memory_bank_manager = MemoryBankManager(
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
        )

        # Store references to the *mock classes* for asserting instantiation calls
        self.MockDBUtil_class = MockDBUtil # Store the patched class from decorator
        self.MockKnowledgePointManager_class = MockKnowledgePointManager
        self.MockLearningContextManager_class = MockLearningContextManager
        self.MockAssessmentDataManager_class = MockAssessmentDataManager
        self.MockResourceManager_class = MockResourceManager
        self.MockBackupManager_class = MockBackupManager

    def test_initialization_of_sub_managers(self):
        """Test that all sub-managers are initialized correctly."""
        # Check config was called for DB settings
        self.mock_config_manager.get_config.assert_any_call("DATABASE_SETTINGS")
        
        # Check DBUtil was instantiated
        self.MockDBUtil_class.assert_called_once_with(db_path="dummy_path/test.db", monitoring_manager=self.mock_monitoring_manager)
        # init_db is no longer called directly by MemoryBankManager; DBUtil.__init__ handles initialization.
        # So, we remove the assertion for self.mock_db_utils_instance.init_db.assert_called_once()

        # Check sub-managers were instantiated with the DBUtil instance and MonitoringManager instance
        self.MockKnowledgePointManager_class.assert_called_once_with(db_util=self.mock_db_utils_instance, monitoring_manager=self.mock_monitoring_manager)
        self.MockLearningContextManager_class.assert_called_once_with(db_util=self.mock_db_utils_instance, monitoring_manager=self.mock_monitoring_manager)
        self.MockAssessmentDataManager_class.assert_called_once_with(db_util=self.mock_db_utils_instance, monitoring_manager=self.mock_monitoring_manager)
        self.MockResourceManager_class.assert_called_once_with(db_util=self.mock_db_utils_instance, monitoring_manager=self.mock_monitoring_manager)
        self.MockBackupManager_class.assert_called_once_with(db_util=self.mock_db_utils_instance, config_manager=self.mock_config_manager, monitoring_manager=self.mock_monitoring_manager)

        # Check instances are stored as attributes with correct names
        self.assertIsNotNone(self.memory_bank_manager.db_util)
        self.assertIs(self.memory_bank_manager.db_util, self.mock_db_utils_instance)
        self.assertIsNotNone(self.memory_bank_manager.knowledge_point_manager)
        self.assertIs(self.memory_bank_manager.knowledge_point_manager, self.mock_kp_manager_instance)
        self.assertIsNotNone(self.memory_bank_manager.learning_context_manager)
        self.assertIs(self.memory_bank_manager.learning_context_manager, self.mock_lc_manager_instance)
        self.assertIsNotNone(self.memory_bank_manager.assessment_data_manager)
        self.assertIs(self.memory_bank_manager.assessment_data_manager, self.mock_ad_manager_instance)
        self.assertIsNotNone(self.memory_bank_manager.resource_manager)
        self.assertIs(self.memory_bank_manager.resource_manager, self.mock_res_manager_instance)
        self.assertIsNotNone(self.memory_bank_manager.backup_manager)
        self.assertIs(self.memory_bank_manager.backup_manager, self.mock_backup_manager_instance)

    def test_process_request_get_kp_success(self):
        """Test process_request routes 'get_kp' to KnowledgePointManager.get_knowledge_point."""
        # Arrange
        operation = "get_kp"
        payload = {"id": "kp_test_123"}
        expected_data = {"status": "success", "data": {"id": "kp_test_123", "title": "Test KP"}}
        self.mock_kp_manager_instance.get_knowledge_point.return_value = expected_data

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_kp_manager_instance.get_knowledge_point.assert_called_once_with(payload)
        self.assertEqual(result, expected_data)
        self.mock_monitoring_manager.log_info.assert_any_call(f"Processing request for operation: {operation} with payload: {payload}")
        self.mock_monitoring_manager.log_info.assert_any_call(f"Operation {operation} completed with status: success")

    def test_process_request_update_kp_success(self):
        """Test process_request routes 'update_kp' to KnowledgePointManager.update_knowledge_point."""
        # Arrange
        operation = "update_kp"
        payload = {"id": "kp_test_456", "data": {"title": "Updated Title"}}
        expected_response = {"status": "success", "id": "kp_test_456"}
        self.mock_kp_manager_instance.update_knowledge_point.return_value = expected_response

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_kp_manager_instance.update_knowledge_point.assert_called_once_with(payload)
        self.assertEqual(result, expected_response)

    def test_process_request_delete_kp_success(self):
        """Test process_request routes 'delete_kp' to KnowledgePointManager.delete_knowledge_point."""
        # Arrange
        operation = "delete_kp"
        payload = {"id": "kp_test_789"}
        expected_response = {"status": "success"}
        self.mock_kp_manager_instance.delete_knowledge_point.return_value = expected_response

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_kp_manager_instance.delete_knowledge_point.assert_called_once_with(payload)
        self.assertEqual(result, expected_response)

    def test_process_request_get_lc_success(self):
        """Test process_request routes 'get_lc' to LearningContextManager.get_learning_context."""
        # Arrange
        operation = "get_lc"
        payload = {"session_id": "session_abc"}
        expected_context = {"status": "success", "data": {"current_topic": "topic_xyz"}}
        self.mock_lc_manager_instance.get_learning_context.return_value = expected_context

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_lc_manager_instance.get_learning_context.assert_called_once_with(payload)
        self.assertEqual(result, expected_context)

    def test_process_request_save_lc_success(self):
        """Test process_request routes 'save_lc' to LearningContextManager.save_learning_context."""
        # Arrange
        operation = "save_lc"
        payload = {"session_id": "session_def", "context_data": {"progress": 50}}
        expected_response = {"status": "success"}
        self.mock_lc_manager_instance.save_learning_context.return_value = expected_response

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_lc_manager_instance.save_learning_context.assert_called_once_with(payload)
        self.assertEqual(result, expected_response)
        
    def test_process_request_update_progress_success(self):
        """Test process_request routes 'update_progress' to LearningContextManager.update_progress."""
        # Arrange
        operation = "update_progress"
        payload = {"session_id": "sess_prog_update", "updates": [{"kp_id": "kp1", "status": "mastered"}], "summary": "Mastered kp1"}
        expected_response = {"status": "success", "message": "Progress updated"}
        self.mock_lc_manager_instance.update_progress.return_value = expected_response # Assumes update_progress is on LCManager

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_lc_manager_instance.update_progress.assert_called_once_with(payload)
        self.assertEqual(result, expected_response)

    def test_process_request_save_al_success(self):
        """Test process_request routes 'save_al' to AssessmentDataManager.save_assessment_log."""
        # Arrange
        operation = "save_al"
        payload = {"log_data": {"assessment_id": "assess1", "score": 90}}
        expected_response = {"status": "success"}
        self.mock_ad_manager_instance.save_assessment_log.return_value = expected_response

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_ad_manager_instance.save_assessment_log.assert_called_once_with(payload)
        self.assertEqual(result, expected_response)

    def test_process_request_unknown_operation(self):
        """Test process_request handles an unknown operation string."""
        # Arrange
        operation = "unknown_operation"
        payload = {"data": "some_data"}
        expected_response = {"status": "error", "message": f"Unknown operation: {operation}"}

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.assertEqual(result, expected_response)
        self.mock_monitoring_manager.log_warning.assert_called_with(f"Unknown operation requested: {operation}")

    def test_process_request_handler_exception(self):
        """Test process_request handles exceptions raised by sub-manager methods."""
        # Arrange
        operation = "get_kp"
        payload = {"id": "kp_exception"}
        error_message = "Database connection lost"
        self.mock_kp_manager_instance.get_knowledge_point.side_effect = ConnectionError(error_message)
        expected_response = {"status": "error", "message": f"An unexpected error occurred processing {operation}: {error_message}"}

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_kp_manager_instance.get_knowledge_point.assert_called_once_with(payload)
        self.assertEqual(result, expected_response)
        self.mock_monitoring_manager.log_error.assert_called_once_with(
            f"Error during operation {operation} with payload {payload}: {error_message}", exc_info=True
        )

    def test_close_db_connection_delegates(self):
        """Test that close_db_connection calls the db_util's method."""
        # Act
        self.memory_bank_manager.close_db_connection()
        # Assert
        self.mock_db_utils_instance.close_connection.assert_called_once()
        self.mock_monitoring_manager.log_info.assert_any_call("MemoryBankManager: Database connection closed.")

    def test_process_request_create_kp_success(self):
        """Test process_request routes 'create_kp' to KnowledgePointManager.create_knowledge_point."""
        # Arrange
        operation = "create_kp"
        payload = {"title": "New KP", "content": "Some content", "category": "Test"}
        expected_response = {"status": "success", "kp_id": "new_kp_123"}
        self.mock_kp_manager_instance.create_knowledge_point.return_value = expected_response

        # Act
        result = self.memory_bank_manager.process_request(operation, payload)

        # Assert
        self.mock_kp_manager_instance.create_knowledge_point.assert_called_once_with(payload)
        self.assertEqual(result, expected_response)
        self.mock_monitoring_manager.log_info.assert_any_call(f"Processing request for operation: {operation} with payload: {payload}")
        self.mock_monitoring_manager.log_info.assert_any_call(f"Operation {operation} completed with status: success")

    def test_process_request_save_generated_assessment_success(self):
        """Test process_request routes 'save_ga' to AssessmentDataManager.save_generated_assessment (success)."""
        operation = "save_ga"
        assessment_payload_data = {
            "assessment_id": "test_assessment_001",
            "assessment_type": "quiz",
            "questions": [{"question_id": "q1", "text": "What is 1+1?"}],
            "generated_at": "2023-01-01T12:00:00Z"
        }
        # process_request expects the entire payload for the sub-manager as its 'payload' argument
        request_payload = assessment_payload_data
        
        expected_response_from_submanager = {"status": "success", "assessment_id": "test_assessment_001"}
        self.mock_ad_manager_instance.save_generated_assessment.return_value = expected_response_from_submanager

        result = self.memory_bank_manager.process_request(operation, request_payload)

        self.mock_ad_manager_instance.save_generated_assessment.assert_called_once_with(request_payload)
        self.assertEqual(result, expected_response_from_submanager)
        self.mock_monitoring_manager.log_info.assert_any_call(f"Processing request for operation: {operation} with payload: {request_payload}")
        self.mock_monitoring_manager.log_info.assert_any_call(f"Operation {operation} completed with status: success")

    def test_process_request_save_generated_assessment_db_error(self):
        """Test process_request routes 'save_ga' to AssessmentDataManager.save_generated_assessment (DB error)."""
        operation = "save_ga"
        assessment_payload_data = {
            "assessment_id": "test_assessment_002",
            "assessment_type": "short_answer",
            "questions": [{"text": "Why?"}]
        }
        request_payload = assessment_payload_data
        
        error_message_from_submanager = "DB write error"
        expected_response_from_submanager = {"status": "error", "message": error_message_from_submanager}
        self.mock_ad_manager_instance.save_generated_assessment.return_value = expected_response_from_submanager
        
        # If the sub-manager itself handles the exception and returns an error dict:
        result = self.memory_bank_manager.process_request(operation, request_payload)
        self.mock_ad_manager_instance.save_generated_assessment.assert_called_once_with(request_payload)
        self.assertEqual(result, expected_response_from_submanager)

        # If the sub-manager raises an exception that process_request catches:
        self.mock_ad_manager_instance.save_generated_assessment.reset_mock() # Reset for new side_effect
        raised_exception = Exception(error_message_from_submanager)
        self.mock_ad_manager_instance.save_generated_assessment.side_effect = raised_exception
        
        result_on_exception = self.memory_bank_manager.process_request(operation, request_payload)
        self.mock_ad_manager_instance.save_generated_assessment.assert_called_once_with(request_payload)
        self.assertEqual(result_on_exception["status"], "error")
        self.assertIn(f"An unexpected error occurred processing {operation}: {error_message_from_submanager}", result_on_exception["message"])
        self.mock_monitoring_manager.log_error.assert_called_with(
            f"Error during operation {operation} with payload {request_payload}: {raised_exception}", exc_info=True
        )

    def test_process_request_get_generated_assessment_success(self):
        """Test process_request routes 'get_ga' to AssessmentDataManager.get_generated_assessment (success)."""
        operation = "get_ga"
        assessment_id = "test_assessment_003"
        request_payload = {"assessment_id": assessment_id} # This is the payload for get_generated_assessment
        
        expected_assessment_data = {
            "assessment_id": assessment_id,
            "assessment_type": "fill_in_blank",
            "questions": [{"question_id": "q2", "text": "What is Python?"}],
            "generated_at": "2023-01-02T10:00:00Z"
        }
        expected_response_from_submanager = {"status": "success", "data": expected_assessment_data}
        self.mock_ad_manager_instance.get_generated_assessment.return_value = expected_response_from_submanager

        result = self.memory_bank_manager.process_request(operation, request_payload)

        self.mock_ad_manager_instance.get_generated_assessment.assert_called_once_with(request_payload)
        self.assertEqual(result, expected_response_from_submanager)

    def test_process_request_get_generated_assessment_not_found(self):
        """Test process_request routes 'get_ga' to AssessmentDataManager.get_generated_assessment (not found)."""
        operation = "get_ga"
        assessment_id = "test_assessment_non_existent"
        request_payload = {"assessment_id": assessment_id}
        
        expected_response_from_submanager = {"status": "not_found", "message": f"Generated assessment with id {assessment_id} not found."}
        self.mock_ad_manager_instance.get_generated_assessment.return_value = expected_response_from_submanager

        result = self.memory_bank_manager.process_request(operation, request_payload)

        self.mock_ad_manager_instance.get_generated_assessment.assert_called_once_with(request_payload)
        self.assertEqual(result, expected_response_from_submanager)

    def test_process_request_get_generated_assessment_db_error(self):
        """Test process_request routes 'get_ga' to AssessmentDataManager.get_generated_assessment (DB error)."""
        operation = "get_ga"
        assessment_id = "test_assessment_db_error"
        request_payload = {"assessment_id": assessment_id}

        # If sub-manager returns error dict
        error_message_from_submanager = "DB read error"
        expected_response_from_submanager = {"status": "error", "message": error_message_from_submanager}
        self.mock_ad_manager_instance.get_generated_assessment.return_value = expected_response_from_submanager
        
        result = self.memory_bank_manager.process_request(operation, request_payload)
        self.mock_ad_manager_instance.get_generated_assessment.assert_called_once_with(request_payload)
        self.assertEqual(result, expected_response_from_submanager)

        # If sub-manager raises an exception
        self.mock_ad_manager_instance.get_generated_assessment.reset_mock()
        raised_exception = Exception(error_message_from_submanager)
        self.mock_ad_manager_instance.get_generated_assessment.side_effect = raised_exception

        result_on_exception = self.memory_bank_manager.process_request(operation, request_payload)
        self.mock_ad_manager_instance.get_generated_assessment.assert_called_once_with(request_payload)
        self.assertEqual(result_on_exception["status"], "error")
        self.assertIn(f"An unexpected error occurred processing {operation}: {error_message_from_submanager}", result_on_exception["message"])
        self.mock_monitoring_manager.log_error.assert_called_with(
            f"Error during operation {operation} with payload {request_payload}: {raised_exception}", exc_info=True
        )
if __name__ == '__main__':
    unittest.main()
