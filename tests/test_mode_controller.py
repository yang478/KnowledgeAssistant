import pytest
from unittest.mock import MagicMock, patch

from src.mode_controller.mode_controller import ModeController
from src.config_manager.config_manager import ConfigManager
from src.llm_interface.llm_interface import LLMInterface
from src.memory_bank_manager.memory_bank_manager import MemoryBankManager
from src.monitoring_manager.monitoring_manager import MonitoringManager
# Import other mode modules as needed, e.g.:
# from src.planner_module.planner_module import PlannerModule
# from src.learner_module.learner_module import LearnerModule
# from src.assessor_module.assessor_module import AssessorModule
# from src.reviewer_module.reviewer_module import ReviewerModule


@pytest.fixture
def mock_config_manager():
    """Fixture for a mocked ConfigManager."""
    mock = MagicMock(spec=ConfigManager)
    # Default config for LLM intent recognition
    mock.get_value.side_effect = lambda key, default=None: {
        "mode_controller.intent_recognition.rules.enabled": True,
        "mode_controller.intent_recognition.llm.enabled": True,
        "mode_controller.intent_recognition.llm.prompt_template": "Test prompt: {user_request}",
        "mode_controller.intent_recognition.llm.model_name": "test_model",
        "mode_controller.default_mode": "planner",
        "mode_controller.modes": {
            "planner": {"module": "PlannerModule", "config": {}},
            "learner": {"module": "LearnerModule", "config": {}},
            "assessor": {"module": "AssessorModule", "config": {}},
            "reviewer": {"module": "ReviewerModule", "config": {}},
        },
        "llm_interface.default": {"api_key": "test_key", "base_url": "http://localhost/v1"}
    }.get(key, default)
    return mock

@pytest.fixture
def mock_llm_interface():
    """Fixture for a mocked LLMInterface."""
    return MagicMock(spec=LLMInterface)

@pytest.fixture
def mock_memory_bank_manager():
    """Fixture for a mocked MemoryBankManager."""
    return MagicMock(spec=MemoryBankManager)

@pytest.fixture
def mock_monitoring_manager():
    """Fixture for a mocked MonitoringManager."""
    mock = MagicMock(spec=MonitoringManager)
    mock.log_info = MagicMock()
    mock.log_error = MagicMock()
    mock.log_warning = MagicMock()
    return mock

@pytest.fixture
def mock_planner_module():
    mock = MagicMock()
    mock.handle_request = MagicMock(return_value={"status": "success", "message": "Planner processed"})
    mock.get_mode_context = MagicMock(return_value={"planner_context": "some_data"})
    mock.load_mode_context = MagicMock()
    return mock

@pytest.fixture
def mock_learner_module():
    mock = MagicMock()
    mock.handle_request = MagicMock(return_value={"status": "success", "message": "Learner processed"})
    mock.get_mode_context = MagicMock(return_value=None) # Example: Learner has no context to save
    mock.load_mode_context = MagicMock()
    return mock

# Add fixtures for AssessorModule and ReviewerModule if they are part of the initial tests

@pytest.fixture
def mode_controller(mock_config_manager, mock_llm_interface, mock_memory_bank_manager, mock_monitoring_manager,
                    mock_planner_module, mock_learner_module):
    """Fixture for ModeController with mocked dependencies."""
    # Patch the module loading within ModeController's __init__
    with patch.dict(ModeController.MODE_MODULE_MAP, {
        "PlannerModule": lambda config,monitoring_manager,memory_bank_manager,llm_interface,update_manager: mock_planner_module,
        "LearnerModule": lambda config,monitoring_manager,memory_bank_manager,llm_interface,update_manager: mock_learner_module,
        # Add other modes as they are introduced into tests
        # "AssessorModule": lambda config,monitoring_manager,memory_bank_manager,llm_interface,update_manager: mock_assessor_module,
        # "ReviewerModule": lambda config,monitoring_manager,memory_bank_manager,llm_interface,update_manager: mock_reviewer_module,
    }):
        controller = ModeController(
            config_manager=mock_config_manager,
            monitoring_manager=mock_monitoring_manager,
            memory_bank_manager=mock_memory_bank_manager,
            llm_interface=mock_llm_interface,
            update_manager=MagicMock() # Mock UpdateManager for now
        )
        # Ensure current_mode is initialized, e.g., to default or a known state for tests
        controller.current_mode = "planner"
        controller.current_mode_module = mock_planner_module
        return controller


class TestModeControllerLLMIntent:
    def test_determine_mode_llm_call_failure_falls_back(self, mode_controller, mock_llm_interface, mock_monitoring_manager, mock_config_manager):
        """
        Test that if the LLM call fails during intent recognition,
        the mode controller logs an error and falls back to the current mode.
        """
        user_request = "I want to learn about Python decorators."
        current_mode_before_call = mode_controller.current_mode

        # Simulate LLM call failure
        mock_llm_interface.generate_text.return_value = {"status": "error", "message": "LLM API unreachable"}

        # Call the private method _determine_mode
        # This assumes _determine_mode is accessible for testing or refactored to be part of a public method's flow.
        # For now, we'll test it directly. If it's strictly private and hard to test,
        # we might need to test it via handle_request.
        determined_mode_info = mode_controller._determine_mode(user_request)

        # Assertions
        mock_llm_interface.generate_text.assert_called_once()
        mock_monitoring_manager.log_error.assert_called_with(
            f"LLM intent recognition failed: LLM API unreachable. Falling back."
        )
        
        # Check that the mode falls back to the current mode (or default if current_mode was None)
        # The _determine_mode method might return the mode name and module, or just the name.
        # Adjust based on its actual return signature.
        # For this test, let's assume _determine_mode returns a tuple (mode_name, mode_module)
        # or None if it falls back without changing.
        # If it falls back, it should effectively not suggest a *new* mode.
        
        # If _determine_mode is meant to return the *new* mode if successful,
        # and current_mode if falling back, or a specific fallback mode.
        # Based on the description "falls back to the current mode",
        # it implies no change is made or the current mode is re-affirmed.
        
        # Let's assume _determine_mode returns the mode name it decided on.
        # If it falls back, it should return the current_mode.
        assert determined_mode_info == current_mode_before_call # or mode_controller.default_mode if that's the fallback logic
        
        # Alternatively, if _determine_mode directly sets self.current_mode and self.current_mode_module on fallback,
        # then we would check that:
        # assert mode_controller.current_mode == current_mode_before_call
        # assert mode_controller.current_mode_module is mode_controller.mode_modules[current_mode_before_call]

        # For now, let's assume _determine_mode returns the name of the mode it determined.
        # If it failed and fell back, it should return the original mode.
        # The actual implementation of _determine_mode will dictate the precise assertion.
        # This is a FAILING test scenario setup.
        
        # A more robust check might be that no mode switch effectively happened.
        # If _determine_mode is supposed to return a new mode or None/current if no change.
        # Let's refine based on expected behavior of _determine_mode:
        # If LLM fails, _determine_mode should return the *current_mode* to signify no change.
        new_mode_name = determined_mode_info # Assuming it returns just the name
        assert new_mode_name == current_mode_before_call
        # And no actual switch should have been triggered if called from handle_request
        # but since we call _determine_mode directly, we check its return.