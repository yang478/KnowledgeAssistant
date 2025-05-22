"""Unit tests for the LearningAssistantApp class."""

import unittest
from unittest.mock import MagicMock, patch, call, ANY # Import call for checking multiple calls

# Ensure the necessary modules can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from app import LearningAssistantApp
# Import all module classes that LearningAssistantApp initializes for spec
from config_manager.config_manager import ConfigManager
from monitoring_manager.monitoring_manager import MonitoringManager
from memory_bank_manager.memory_bank_manager import MemoryBankManager
from llm_interface.llm_interface import LLMInterface
from update_manager.update_manager import UpdateManager
from learner_module.learner_module import LearnerModule
from assessor_module.assessor_module import AssessorModule
from planner_module.planner_module import PlannerModule
from reviewer_module.reviewer_module import ReviewerModule
from mode_controller.mode_controller import ModeController
from visualization_generator.visualization_generator import VisualizationGenerator
from api_gateway.gateway import APIGateway


class TestLearningAssistantApp(unittest.TestCase):
    """Tests for the LearningAssistantApp."""

    @patch('src.app.ConfigManager') # Corrected patch target
    @patch('src.app.MonitoringManager') # Corrected patch target
    @patch('src.app.MemoryBankManager') # Corrected patch target
    @patch('src.app.LLMInterface') # Corrected patch target
    @patch('src.app.UpdateManager') # Corrected patch target
    @patch('src.app.LearnerModule') # Corrected patch target
    @patch('src.app.AssessorModule') # Corrected patch target
    @patch('src.app.PlannerModule') # Corrected patch target
    @patch('src.app.ReviewerModule') # Corrected patch target
    @patch('src.app.ModeController') # Corrected patch target
    @patch('src.app.VisualizationGenerator') # Corrected patch target
    @patch('src.app.APIGateway') # Corrected patch target
    @patch('src.app.uvicorn') # Corrected patch target
    def setUp(self, mock_uvicorn, mock_apigateway_class, mock_visualizationgenerator,
              mock_modecontroller, mock_reviewermodule, mock_plannermodule,
              mock_assessormodule, mock_learnermodule, mock_updatemanager, 
              mock_llminterface, mock_memorybankmanager, mock_monitoringmanager, 
              mock_configmanager):
        """Set up a LearningAssistantApp instance with all dependencies mocked."""

        # Reset ConfigManager singleton state before each test
        # to ensure that the patched version is correctly used.
        from src.config_manager.config_manager import ConfigManager as RealConfigManager
        RealConfigManager._instance = None
        RealConfigManager._config = None
        RealConfigManager._config_dir = None # Also reset the config directory
        
        # Store mock instances AND classes on self for later access
        self.mock_uvicorn_class = mock_uvicorn # Store the mock class passed by @patch
        self.mock_apigateway_class = mock_apigateway_class # Store the mock class
        self.mock_visualizationgenerator_class = mock_visualizationgenerator
        self.mock_modecontroller_class = mock_modecontroller
        self.mock_reviewermodule_class = mock_reviewermodule
        self.mock_plannermodule_class = mock_plannermodule
        self.mock_assessormodule_class = mock_assessormodule
        self.mock_learnermodule_class = mock_learnermodule
        self.mock_updatemanager_class = mock_updatemanager
        self.mock_llminterface_class = mock_llminterface
        self.mock_memorybankmanager_class = mock_memorybankmanager
        self.mock_monitoringmanager_class = mock_monitoringmanager
        self.mock_configmanager_class = mock_configmanager

        self.mock_configmanager_instance = self.mock_configmanager_class.return_value
        self.mock_monitoringmanager_instance = self.mock_monitoringmanager_class.return_value
        self.mock_memorybankmanager_instance = self.mock_memorybankmanager_class.return_value
        self.mock_llminterface_instance = self.mock_llminterface_class.return_value
        self.mock_updatemanager_instance = self.mock_updatemanager_class.return_value
        self.mock_learnermodule_instance = self.mock_learnermodule_class.return_value
        self.mock_assessormodule_instance = self.mock_assessormodule_class.return_value
        self.mock_plannermodule_instance = self.mock_plannermodule_class.return_value
        self.mock_reviewermodule_instance = self.mock_reviewermodule_class.return_value
        self.mock_modecontroller_instance = self.mock_modecontroller_class.return_value
        self.mock_visualizationgenerator_instance = self.mock_visualizationgenerator_class.return_value
        self.mock_apigateway_instance = self.mock_apigateway_class.return_value

        # Mock config values needed during app initialization
        # Use side_effect to return different values based on the key
        def mock_get_config(key, default=None):
            print(f"mock_get_config CALLED WITH: key='{key}', default='{default}'") # DEBUG PRINT
            if key == "DATABASE_SETTINGS":
                print("mock_get_config: Matched DATABASE_SETTINGS") # DEBUG PRINT
                return {"db_path": "dummy_path/test_app.db", "schema_file": "dummy_schema.sql"} # Added schema_file
            elif key == "api_gateway":
                return {"host": "127.0.0.1", "port": 8080}.copy()
            # For monitoring settings, let's be explicit
            elif key == "monitoring.logging.enabled":
                return True
            elif key == "monitoring.logging.level":
                return "INFO"
            elif key == "monitoring.logging.filepath":
                return "logs/test_monitoring.log"
            elif key == "monitoring.logging.structured_json":
                return False # Simpler for now
            elif key == "monitoring.logging.rotation":
                return {} # Default empty rotation
            
            print(f"mock_get_config: No match for key '{key}', returning default: {default}") # DEBUG PRINT
            return default

        # CRITICAL: Set the side_effect on the mock instance *before* it's used by LearningAssistantApp's constructor
        self.mock_configmanager_instance.get_config.side_effect = mock_get_config

        # Instantiate the app. This will call the __init__ of LearningAssistantApp
        # which in turn will instantiate all the mocked modules.
        # Pass config_dir="." assuming tests run from project root
        with patch('builtins.print'): # Suppress print statements during test
            self.app = LearningAssistantApp(config_dir=".")

    def test_initialization_of_all_modules(self):
        """Test that all dependent modules are initialized correctly."""
        # Check that constructors of mocked modules were called
        # ConfigManager is called directly in __init__
        # Access the mock classes stored on self during setUp
        self.mock_configmanager_class.assert_called_once_with(config_dir=".")

        # MonitoringManager - Called with positional argument in app.py
        self.mock_monitoringmanager_class.assert_called_once_with(self.mock_configmanager_instance)

        # MemoryBankManager
        self.mock_memorybankmanager_class.assert_called_once_with(
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance
        )
        # LLMInterface
        self.mock_llminterface_class.assert_called_once_with(
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance
        )
        # UpdateManager
        self.mock_updatemanager_class.assert_called_once_with(
            memory_bank_manager=self.mock_memorybankmanager_instance,
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance
        )
        # LearnerModule
        self.mock_learnermodule_class.assert_called_once_with(
            memory_bank_manager=self.mock_memorybankmanager_instance,
            llm_interface=self.mock_llminterface_instance,
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance,
            update_manager=self.mock_updatemanager_instance
        )
        # AssessorModule
        self.mock_assessormodule_class.assert_called_once_with(
            memory_bank_manager=self.mock_memorybankmanager_instance,
            llm_interface=self.mock_llminterface_instance,
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance,
            update_manager=self.mock_updatemanager_instance
        )
        # PlannerModule
        self.mock_plannermodule_class.assert_called_once_with(
            memory_bank_manager=self.mock_memorybankmanager_instance,
            llm_interface=self.mock_llminterface_instance,
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance
        )
        # ReviewerModule
        self.mock_reviewermodule_class.assert_called_once_with(
            memory_bank_manager=self.mock_memorybankmanager_instance,
            llm_interface=self.mock_llminterface_instance,
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance,
            update_manager=self.mock_updatemanager_instance
        )
        # ModeController
        self.mock_modecontroller_class.assert_called_once_with(
            config_manager=self.mock_configmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance,
            planner_module=self.mock_plannermodule_instance,
            learner_module=self.mock_learnermodule_instance,
            assessor_module=self.mock_assessormodule_instance,
            reviewer_module=self.mock_reviewermodule_instance
        )
        # VisualizationGenerator
        self.mock_visualizationgenerator_class.assert_called_once_with(
            memory_bank_manager=self.mock_memorybankmanager_instance,
            monitoring_manager=self.mock_monitoringmanager_instance,
            config_manager=self.mock_configmanager_instance
        )
        # APIGateway
        self.mock_apigateway_class.assert_called_once_with(learning_app=self.app) # Check class was called

        # Check that instances are assigned to app attributes
        self.assertIsNotNone(self.app.config_manager)
        self.assertIsNotNone(self.app.monitoring_manager)
        self.assertIsNotNone(self.app.memory_bank_manager)
        self.assertIsNotNone(self.app.llm_interface)
        self.assertIsNotNone(self.app.update_manager)
        self.assertIsNotNone(self.app.learner_module)
        self.assertIsNotNone(self.app.assessor_module)
        self.assertIsNotNone(self.app.planner_module)
        self.assertIsNotNone(self.app.reviewer_module)
        self.assertIsNotNone(self.app.mode_controller)
        self.assertIsNotNone(self.app.visualization_generator)
        self.assertIsNotNone(self.app.api_gateway_instance) # Check for the APIGateway instance

    def test_handle_interaction_delegates_to_mode_controller(self):
        """Test that handle_interaction delegates to ModeController."""
        session_id = "s1"
        user_input = "Hello"
        expected_response = {"status": "success", "message": "Routed by ModeController"}
        self.mock_modecontroller_instance.handle_request.return_value = expected_response

        response = self.app.handle_interaction(session_id, user_input)

        self.mock_modecontroller_instance.handle_request.assert_called_once_with(
            session_id=session_id, user_input=user_input
        )
        self.assertEqual(response, expected_response)
        self.mock_monitoringmanager_instance.log.assert_any_call(
            "info", f"App received interaction for session {session_id}", ANY
        )

    def test_handle_interaction_error_handling(self):
        """Test error handling in handle_interaction."""
        session_id = "s_err"
        user_input = "Trigger error"
        self.mock_modecontroller_instance.handle_request.side_effect = Exception("ModeController failed")

        response = self.app.handle_interaction(session_id, user_input)
        
        self.assertEqual(response["status"], "error")
        self.assertTrue("An internal error occurred" in response["message"])
        self.mock_monitoringmanager_instance.log.assert_any_call(
            "error", "Error in handle_interaction: ModeController failed", ANY
        )

    def test_get_visualization_delegates_to_visualization_generator(self):
        """Test that get_visualization delegates to VisualizationGenerator."""
        viz_type = "knowledge_graph"
        user_id = "u1"
        params = {"depth": 3}
        expected_data = {"nodes": [], "edges": []}
        self.mock_visualizationgenerator_instance.get_knowledge_graph_data.return_value = expected_data
        
        response = self.app.get_visualization(viz_type, user_id, params)
        
        self.mock_visualizationgenerator_instance.get_knowledge_graph_data.assert_called_once_with(
            user_id=user_id, **params
        )
        self.assertEqual(response, expected_data)

        viz_type_progress = "progress_dashboard"
        self.mock_visualizationgenerator_instance.get_progress_dashboard_data.return_value = {"summary": "good"}
        response_progress = self.app.get_visualization(viz_type_progress, user_id)
        self.mock_visualizationgenerator_instance.get_progress_dashboard_data.assert_called_once_with(
            user_id=user_id
        )
        self.assertEqual(response_progress, {"summary": "good"})


    def test_get_visualization_unknown_type(self):
        """Test get_visualization with an unknown visualization type."""
        response = self.app.get_visualization("unknown_viz", "u1")
        self.assertEqual(response["status"], "error")
        self.assertTrue("Unknown visualization type" in response["message"])

    def test_trigger_backup_action_delegates_to_update_manager(self):
        """Test that trigger_backup_action delegates to UpdateManager."""
        reason = "Manual backup test"
        expected_response = {"status": "success", "path": "/backup.zip"}
        self.mock_updatemanager_instance.trigger_backup.return_value = expected_response

        response = self.app.trigger_backup_action(reason)

        self.mock_updatemanager_instance.trigger_backup.assert_called_once_with(
            event="manual_trigger", payload={"reason": reason}
        )
        self.assertEqual(response, expected_response)

    def test_start_calls_uvicorn_run(self):
        """Test that the start method calls uvicorn.run with correct parameters."""
        mock_fastapi_app = MagicMock()
        # self.app.api_gateway_instance is the actual mocked instance
        # Ensure get_fastapi_app is treated as a mock method on the mock instance
        self.app.api_gateway_instance.get_fastapi_app = MagicMock(return_value=mock_fastapi_app)
        
        # Mock config to return specific host/port for this test
        # Mock config specifically for the start test - use side_effect again or reconfigure
        # Reconfigure side_effect for this specific test case if needed,
        # or ensure the main side_effect handles 'api_gateway' key correctly.
        # The main side_effect already handles 'api_gateway'.

        with patch('builtins.print'): # Suppress print
            self.app.start()

        self.app.api_gateway_instance.get_fastapi_app.assert_called_once()
        # uvicorn.run is mocked at the class level by @patch('app.uvicorn')
        # So, self.mock_uvicorn_instance is not available directly here.
        # We need to access the mock passed to setUp.
        # The mocks are passed in reverse order of @patch decorators.
        # The last @patch is uvicorn, so it's the first arg to setUp.
        
        # Find the uvicorn mock from the setUp arguments
        # Access the mock uvicorn class stored in setUp
        self.mock_uvicorn_class.run.assert_called_once_with(
            mock_fastapi_app, host="127.0.0.1", port=8080, log_level="info"
        )

    def test_start_handles_uvicorn_exception(self):
        """Test that start method handles exceptions from uvicorn.run."""
        # Ensure get_fastapi_app is treated as a mock method
        mock_fastapi_app_for_exception = MagicMock()
        self.app.api_gateway_instance.get_fastapi_app = MagicMock(return_value=mock_fastapi_app_for_exception)
        
        # Access the mock uvicorn class stored in setUp
        self.mock_uvicorn_class.run.side_effect = Exception("Uvicorn failed to start")

        with patch('builtins.print'): # Suppress print
            with self.assertRaises(Exception) as context:
                self.app.start()
        
        self.assertTrue("Uvicorn failed to start" in str(context.exception))
        self.mock_monitoringmanager_instance.log.assert_any_call(
            "error", "Failed to start API Gateway", {"error": "Uvicorn failed to start", "module": "LearningAssistantApp"}
        )

if __name__ == "__main__":
    # This allows running the tests directly from this file
    # Note: The @patch decorators in setUp mean we can't just call unittest.main()
    # without the mocks being active. A more common pattern is to run tests via `python -m unittest discover`.
    # For direct execution with this structure, it's a bit tricky.
    # However, standard test runners will handle this fine.
    print("To run these tests, use a test runner like `python -m unittest discover tests`")
