"""AI 个人知识库学习助手主应用程序。

负责初始化和协调各个核心模块，管理学习会话的生命周期，
并作为 API 网关和 Streamlit UI 的主要后端逻辑处理单元。
"""

import threading  # For running gateway in a separate thread

# src/app.py
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import uvicorn  # For running the gateway

from assessor_module.assessor_module import AssessorModule
from config_manager.config_manager import ConfigManager
from learner_module.learner_module import LearnerModule
from llm_interface.llm_interface import LLMInterface
from memory_bank_manager.memory_bank_manager import MemoryBankManager

# Import newly created modules
from mode_controller.mode_controller import ModeController
from monitoring_manager.monitoring_manager import MonitoringManager
from planner_module.planner_module import PlannerModule
from reviewer_module.reviewer_module import ReviewerModule
from src.api_gateway.gateway import APIGateway # Moved import out of TYPE_CHECKING
if TYPE_CHECKING:
    pass # APIGateway already imported for type checking if needed elsewhere
from update_manager.update_manager import UpdateManager
from visualization_generator.visualization_generator import VisualizationGenerator


import os # Add os import for path manipulation

class LearningAssistantApp:
    """
    Main application class to initialize and wire up all backend modules.
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initializes the application and its modules.

        Args:
            config_dir: Optional path to the configuration directory.
                        If None, ConfigManager uses its default (project root).
        """
        print("Initializing ConfigManager...")
        self.config_manager = ConfigManager(config_dir=config_dir)

        print("Initializing MonitoringManager...")
        self.monitoring_manager = MonitoringManager(self.config_manager)

        # Now initialize other modules, passing dependencies
        print("Initializing MemoryBankManager...")
        # Pass MonitoringManager to MemoryBankManager
        self.memory_bank_manager = MemoryBankManager(
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,  # Inject MonitoringManager
        )

        print("Initializing LLMInterface...")
        # Pass MonitoringManager to LLMInterface
        self.llm_interface = LLMInterface(
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,  # Inject MonitoringManager
        )

        print("Initializing UpdateManager...")
        # Initialize UpdateManager (depends on MBM, Config, Monitor)
        self.update_manager = UpdateManager(
            memory_bank_manager=self.memory_bank_manager,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
        )

        print("Initializing LearnerModule...")
        # Pass MonitoringManager and UpdateManager to LearnerModule
        self.learner_module = LearnerModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,  # Inject MonitoringManager
            update_manager=self.update_manager,  # Inject UpdateManager
        )

        print("Initializing AssessorModule...")
        # Pass MonitoringManager and UpdateManager to AssessorModule
        self.assessor_module = AssessorModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,  # Inject MonitoringManager
            update_manager=self.update_manager,  # Inject UpdateManager
        )

        print("Initializing PlannerModule...")
        # Pass MonitoringManager to PlannerModule
        self.planner_module = PlannerModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,  # Inject MonitoringManager
        )

        print("Initializing ReviewerModule...")
        # Initialize ReviewerModule (depends on MBM, LLM, Config, Monitor)
        self.reviewer_module = ReviewerModule(
            memory_bank_manager=self.memory_bank_manager,
            llm_interface=self.llm_interface,
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
            update_manager=self.update_manager,  # Inject UpdateManager
        )

        print("Initializing ModeController...")
        # Initialize ModeController (depends on Config, Monitor, and all mode modules)
        self.mode_controller = ModeController(
            config_manager=self.config_manager,
            monitoring_manager=self.monitoring_manager,
            planner_module=self.planner_module,
            learner_module=self.learner_module,
            assessor_module=self.assessor_module,
            reviewer_module=self.reviewer_module,
        )

        print("Initializing VisualizationGenerator...")
        # Initialize VisualizationGenerator (depends on MBM, Monitor, Config)
        self.visualization_generator = VisualizationGenerator(
            memory_bank_manager=self.memory_bank_manager,
            monitoring_manager=self.monitoring_manager,
            config_manager=self.config_manager,
        )

        # Conditional import for runtime
        # if not TYPE_CHECKING: # No longer needed as it's imported at module level
        #     from src.api_gateway.gateway import APIGateway
        self.api_gateway_instance: 'APIGateway' = APIGateway(
            learning_app=self
        )  # Pass the app instance
        print("API Gateway initialized.")

        print("Application initialization complete.")

    # --- Refactored Interaction Point ---
    def handle_interaction(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """
        Central point for handling user interactions via the ModeController.
        This replaces direct calls to individual modules from the UI/API layer.
        """
        self.monitoring_manager.log(
            "info",
            f"App received interaction for session {session_id}",
            {"module": "LearningAssistantApp", "session_id": session_id},
        )
        try:
            # Route the request through the ModeController
            response = self.mode_controller.handle_request(
                session_id=session_id,
                user_input=user_input,
                # current_mode_suggestion could be added if provided by UI/API
            )
            return response
        except Exception as e:
            error_message = f"Error in handle_interaction: {str(e)}"
            self.monitoring_manager.log(
                "error",
                error_message,
                {
                    "module": "LearningAssistantApp",
                    "session_id": session_id,
                    "user_input": user_input,
                    "exception_type": type(e).__name__,
                },
            )
            return {
                "status": "error",
                "message": "An internal error occurred while handling your request.",
            }

    # --- Methods for specific non-mode actions (e.g., via API Gateway) ---
    def get_visualization(
        self, viz_type: str, user_id: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Handles requests for visualization data."""
        self.monitoring_manager.log(
            "info",
            f"App received visualization request: {viz_type} for user {user_id}",
            {
                "module": "LearningAssistantApp",
                "user_id": user_id,
                "viz_type": viz_type,
                "params": params or {},
            },
        )
        params = params or {}
        try:
            if viz_type == "knowledge_graph":
                return self.visualization_generator.get_knowledge_graph_data(
                    user_id=user_id, **params
                )
            elif viz_type == "progress_dashboard":
                return self.visualization_generator.get_progress_dashboard_data(
                    user_id=user_id
                )
            else:
                self.monitoring_manager.log(
                    "warning",
                    f"Unknown visualization type requested: {viz_type}",
                    {
                        "module": "LearningAssistantApp",
                        "user_id": user_id,
                        "viz_type": viz_type,
                    },
                )
                return {
                    "status": "error",
                    "message": f"Unknown visualization type: {viz_type}",
                }
        except Exception as e:
            error_message = f"Error in get_visualization for type {viz_type}: {str(e)}"
            self.monitoring_manager.log(
                "error",
                error_message,
                {
                    "module": "LearningAssistantApp",
                    "user_id": user_id,
                    "viz_type": viz_type,
                    "params": params,
                    "exception_type": type(e).__name__,
                },
            )
            return {
                "status": "error",
                "message": "An internal error occurred while generating visualization.",
            }

    def trigger_backup_action(self, reason: str = "Manual trigger") -> Dict[str, Any]:
        """Handles requests to trigger a manual backup."""
        self.monitoring_manager.log(
            "info",
            f"App received manual backup trigger request. Reason: {reason}",
            {"module": "LearningAssistantApp", "reason": reason},
        )
        try:
            return self.update_manager.trigger_backup(
                event="manual_trigger", payload={"reason": reason}
            )
        except Exception as e:
            error_message = f"Error in trigger_backup_action: {str(e)}"
            self.monitoring_manager.log(
                "error",
                error_message,
                {
                    "module": "LearningAssistantApp",
                    "reason": reason,
                    "exception_type": type(e).__name__,
                },
            )
            return {
                "status": "error",
                "message": "An internal error occurred while triggering backup.",
            }

    def start(self):
        """
        Starts the application services (e.g., API Gateway).
        """
        print("Starting application services...")
        # Start the API Gateway in a separate thread to avoid blocking
        # The API Gateway will receive requests and route them
        gateway_app = self.api_gateway_instance.get_fastapi_app()

        # Get host and port from config, with defaults
        gateway_config = self.config_manager.get_config("api_gateway") or {}
        host = gateway_config.get("host", "127.0.0.1")
        port = gateway_config.get("port", 8000)

        print(f"Attempting to start API Gateway on {host}:{port}...")

        # Uvicorn needs to be run in a way that doesn't block the main thread
        # if other app services were to run concurrently in the same process.
        # For simplicity here, if app.start() is the last thing, direct run is okay,
        # but for potential future extensions, threading is safer.

        # We will run uvicorn directly here. If this `start()` method was intended
        # to be non-blocking for other services in `LearningAssistantApp`,
        # then threading `uvicorn.run` would be necessary.
        # For now, assume `app.start()` is the entry point to run the server.

        # Note: If streamlit_app.py is the primary entry point and it's already running
        # an event loop, starting another uvicorn server directly might conflict
        # or require careful management. The typical pattern is one main async event loop.
        # However, for a backend API, running uvicorn like this is standard.
        # The interaction with streamlit_app.py will now be via HTTP requests
        # to this gateway, not direct Python calls.

        try:
            # This is a blocking call. The application will serve requests until uvicorn is stopped.
            uvicorn.run(gateway_app, host=host, port=port, log_level="info")
            print(f"API Gateway started successfully on {host}:{port}.")
        except Exception as e:
            print(f"Failed to start API Gateway: {e}")
            self.monitoring_manager.log(
                "error",
                "Failed to start API Gateway",
                {"error": str(e), "module": "LearningAssistantApp"},
            )
            # Optionally re-raise or handle more gracefully
            raise


# Example of how to run the app
if __name__ == "__main__":
    # Determine project root to pass as config_dir
    # Assuming app.py is in src/, and config.json is in the project root (one level up from src/)
    project_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"Setting configuration directory to: {project_root_dir}")
    app = LearningAssistantApp(config_dir=project_root_dir)
    app.start()
