# -*- coding: utf-8 -*-
"""API 网关主文件。

使用 FastAPI 实现，定义了所有面向前端的 HTTP 接口，
负责请求的接收、初步校验、路由到相应的后端服务模块，
并处理响应的聚合与返回。
"""
# src/api_gateway/gateway.py
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, HTTPException, Path, Query, Request
from pydantic import BaseModel

# Assuming LearningAssistantApp is accessible or passed during initialization
# We need a way to access the main app instance.
# For now, we'll design the gateway class to accept it.
if TYPE_CHECKING:
    from app import (
        LearningAssistantApp,
    )  # Relative import might need adjustment depending on execution context

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Request Models ---
class InteractionRequest(BaseModel):
    user_input: str
    current_mode: Optional[str] = None  # As per handbook example


# --- API Gateway Class ---
class APIGateway:
    """
    API Gateway using FastAPI to route requests to the LearningAssistantApp.
    """

    def __init__(self, learning_app: 'LearningAssistantApp'):
        self.app = FastAPI(title="AI Learning Assistant API Gateway")
        self.learning_app = learning_app
        self._setup_routes()

    def _setup_routes(self):
        """Defines the API routes."""

        @self.app.post("/api/v1/session/{session_id}/interact", tags=["Interaction"])
        async def handle_interaction_endpoint(
            session_id: str = Path(
                ...,
                title="Session ID",
                description="The unique identifier for the user session",
            ),
            request_body: InteractionRequest = None,  # Make body optional for flexibility initially
        ) -> Dict[str, Any]:
            """
            Handles core user interaction requests.
            Routes requests to the ModeController via LearningAssistantApp.
            """
            if not request_body or not request_body.user_input:
                # Handle cases where user_input might come differently, or log error
                # For now, require it based on the handbook example.
                logger.error(
                    f"Interaction request for session {session_id} missing user_input."
                )
                raise HTTPException(
                    status_code=400, detail="Missing 'user_input' in request body."
                )

            logger.info(
                f"Gateway received interaction for session {session_id}: {request_body.user_input}"
            )
            try:
                # Call the central handler in the main app
                response = self.learning_app.handle_interaction(
                    session_id=session_id,
                    user_input=request_body.user_input,
                    # Pass current_mode if needed by handle_interaction later
                )
                logger.info(f"Gateway sending response for session {session_id}")
                return response
            except Exception as e:
                logger.exception(
                    f"Error handling interaction for session {session_id}: {e}"
                )
                # Use MonitoringManager if available in learning_app
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        f"API Gateway error during interaction for session {session_id}",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500, detail="Internal server error during interaction."
                )

        @self.app.get("/api/v1/visualizations/knowledge_graph", tags=["Visualizations"])
        async def get_knowledge_graph(
            user_id: str = Query(
                ...,
                title="User ID",
                description="Identifier for the user whose graph is requested",
            ),
            depth: Optional[int] = Query(
                None,
                title="Depth",
                description="Optional depth for the graph traversal",
            ),
            root_node_id: Optional[str] = Query( # Added root_node_id
                None,
                title="Root Node ID",
                description="Optional root node ID for the graph traversal"
            ),
        ) -> Dict[str, Any]:
            """
            Provides data for knowledge graph visualization.
            Routes requests to the VisualizationGenerator via LearningAssistantApp.
            """
            logger.info(
                f"Gateway received knowledge graph request for user {user_id} with depth {depth}"
            )
            try:
                params = {}
                if depth is not None:
                    params["depth"] = depth
                if root_node_id is not None: # Added handling for root_node_id
                    params["root_node_id"] = root_node_id
                # Call the visualization handler in the main app
                response = self.learning_app.get_visualization(
                    viz_type="knowledge_graph", user_id=user_id, params=params
                )
                logger.info(
                    f"Gateway sending knowledge graph response for user {user_id}"
                )
                return response
            except Exception as e:
                logger.exception(
                    f"Error generating knowledge graph for user {user_id}: {e}"
                )
                # Use MonitoringManager if available
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        f"API Gateway error during knowledge graph generation for user {user_id}",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error generating visualization.",
                )

        @self.app.get("/api/v1/memory/knowledge_point/{kp_id}", tags=["Memory Bank"])
        async def get_knowledge_point_details(
            kp_id: str = Path(
                ...,
                title="Knowledge Point ID",
                description="The unique identifier for the knowledge point",
            )
        ) -> Dict[str, Any]:
            """
            Retrieves details for a specific knowledge point.
            Routes requests to the MemoryBankManager.
            """
            logger.info(
                f"Gateway received request for knowledge point details: {kp_id}"
            )
            try:
                response = self.learning_app.memory_bank_manager.process_request(
                    {
                        "operation": "get_knowledge_point",
                        "payload": {"knowledge_point_id": kp_id},
                    }
                )
                if response.get("status") == "error":
                    # Handle cases like 'not found' more gracefully if possible
                    error_message = response.get(
                        "message", "Error retrieving knowledge point."
                    )
                    logger.warning(
                        f"Error from MemoryBankManager for kp_id {kp_id}: {error_message}"
                    )
                    # Determine appropriate HTTP status code based on MBM response
                    # For now, a generic 404 if data is null, else 500 or 400
                    if (
                        response.get("data") is None
                        and "not found" in error_message.lower()
                    ):
                        raise HTTPException(status_code=404, detail=error_message)
                    raise HTTPException(
                        status_code=400, detail=error_message
                    )  # Or 500 if it's an internal MBM error

                logger.info(f"Gateway sending knowledge point details for: {kp_id}")
                return response  # Assuming MBM returns a FastAPI-compatible response
            except HTTPException:  # Re-raise HTTPExceptions directly
                raise
            except Exception as e:
                logger.exception(f"Error retrieving knowledge point {kp_id}: {e}")
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        f"API Gateway error retrieving knowledge point {kp_id}",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error retrieving knowledge point.",
                )

        @self.app.get("/api/v1/session/{session_id}/context", tags=["Session"])
        async def get_session_context(
            session_id: str = Path(
                ...,
                title="Session ID",
                description="The unique identifier for the user session",
            )
        ) -> Dict[str, Any]:
            """
            Retrieves the learning context for a specific session.
            Routes requests to the MemoryBankManager.
            """
            logger.info(f"Gateway received request for session context: {session_id}")
            try:
                response = self.learning_app.memory_bank_manager.process_request(
                    {
                        "operation": "get_learning_context",
                        "payload": {"session_id": session_id},
                    }
                )
                if response.get("status") == "error":
                    error_message = response.get(
                        "message", "Error retrieving session context."
                    )
                    logger.warning(
                        f"Error from MemoryBankManager for session context {session_id}: {error_message}"
                    )
                    if (
                        response.get("data") is None
                        and "not found" in error_message.lower()
                    ):  # Example
                        raise HTTPException(status_code=404, detail=error_message)
                    raise HTTPException(status_code=400, detail=error_message)

                logger.info(f"Gateway sending session context for: {session_id}")
                return response
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"Error retrieving session context {session_id}: {e}")
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        f"API Gateway error retrieving session context {session_id}",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error retrieving session context.",
                )

        @self.app.get(
            "/api/v1/visualizations/progress_dashboard", tags=["Visualizations"]
        )
        async def get_progress_dashboard(
            user_id: str = Query(
                ...,
                title="User ID",
                description="Identifier for the user whose dashboard is requested",
            )
            # Add other specific query parameters if defined in VisualizationGenerator or handbook
        ) -> Dict[str, Any]:
            """
            Provides data for progress dashboard visualization.
            Routes requests to the VisualizationGenerator via LearningAssistantApp.
            """
            logger.info(
                f"Gateway received progress dashboard request for user {user_id}"
            )
            try:
                # Call the visualization handler in the main app
                response = self.learning_app.get_visualization(
                    viz_type="progress_dashboard",
                    user_id=user_id,
                    params={} # Explicitly pass params={}
                )
                logger.info(
                    f"Gateway sending progress dashboard response for user {user_id}"
                )
                if response.get("status") == "error":
                    error_message = response.get(
                        "message", "Error generating progress dashboard."
                    )
                    logger.warning(
                        f"Error from VisualizationGenerator for progress_dashboard for user {user_id}: {error_message}"
                    )
                    raise HTTPException(status_code=400, detail=error_message)  # Or 500
                return response
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(
                    f"Error generating progress dashboard for user {user_id}: {e}"
                )
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        f"API Gateway error during progress dashboard generation for user {user_id}",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error generating progress dashboard.",
                )

        @self.app.get("/api/v1/config/{key}", tags=["Admin", "Configuration"])
        async def get_configuration_value(
            key: str = Path(
                ...,
                title="Config Key",
                description="The key of the configuration value to retrieve (e.g., 'llm.model')",
            )
        ) -> Dict[str, Any]:
            """
            Retrieves a specific configuration value.
            Routes requests to the ConfigManager.
            """
            logger.info(f"Gateway received request for configuration key: {key}")
            try:
                # Directly call ConfigManager as it's simpler and doesn't usually have complex 'operations'
                value = self.learning_app.config_manager.get_config(key)

                if value is None:
                    # Check if it's a section or a specific key that truly doesn't exist
                    # For simplicity, if get_config returns None, assume not found.
                    logger.warning(f"Configuration key '{key}' not found.")
                    raise HTTPException(
                        status_code=404, detail=f"Configuration key '{key}' not found."
                    )

                logger.info(f"Gateway sending configuration value for key: {key}")
                # Standardize response format if not already
                return {"status": "success", "key": key, "value": value}
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"Error retrieving configuration for key {key}: {e}")
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        f"API Gateway error retrieving config for key {key}",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal server error retrieving configuration for key {key}.",
                )

        @self.app.get("/api/v1/monitoring/status", tags=["Admin", "Monitoring"])
        async def get_monitoring_status(
            # Define query parameters based on MonitoringManager.get_system_status if any
            # For example:
            # component: Optional[str] = Query(None, description="Specific component to get status for")
        ) -> Dict[str, Any]:
            """
            Retrieves system monitoring status.
            Routes requests to the MonitoringManager.
            """
            logger.info("Gateway received request for monitoring status.")
            try:
                # Assuming get_system_status might take some payload or specific query params
                # For now, calling it without specific params. Adjust if MonitoringManager expects them.
                # payload = {} # Construct payload from query_params if needed
                # response = self.learning_app.monitoring_manager.get_system_status(payload=payload)

                # Simpler direct call if no complex payload, assuming it returns a dict
                status_data = self.learning_app.monitoring_manager.get_system_status()

                logger.info("Gateway sending monitoring status.")
                # Ensure the response is a dict or can be converted to one by FastAPI
                if not isinstance(status_data, dict):  # Basic check
                    # Or if it's a Pydantic model, FastAPI handles it.
                    # If it's a custom object, it might need serialization.
                    # For now, assume it's a dict or FastAPI serializable.
                    logger.warning(
                        f"Monitoring status data is not a dict: {type(status_data)}"
                    )
                    # Fallback or reformat if necessary
                    return {"status": "success", "data": status_data}  # Example wrapper

                return status_data  # Or wrap it: {"status": "success", "data": status_data}
            except Exception as e:
                logger.exception(f"Error retrieving monitoring status: {e}")
                if hasattr(
                    self.learning_app, "monitoring_manager"
                ):  # Log with its own manager
                    self.learning_app.monitoring_manager.log(
                        "error",
                        "API Gateway error retrieving monitoring status",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error retrieving monitoring status.",
                )

        @self.app.get("/api/v1/monitoring/logs", tags=["Admin", "Monitoring"])
        async def get_monitoring_logs(
            # Define query parameters based on MonitoringManager.query_logs
            # Example from handbook: log_type, module_name, limit
            log_type: Optional[str] = Query(
                None, description="Filter by log type (e.g., 'error', 'info')"
            ),
            module_name: Optional[str] = Query(
                None, description="Filter by module name"
            ),
            limit: Optional[int] = Query(
                100, description="Maximum number of log entries to return"
            ),
        ) -> Dict[str, Any]:  # Or List[Dict[str,Any]] if it's a list of logs
            """
            Retrieves system logs.
            Routes requests to the MonitoringManager.
            """
            logger.info(
                f"Gateway received request for monitoring logs with params: type={log_type}, module={module_name}, limit={limit}"
            )
            try:
                payload = {}
                if log_type:
                    payload["log_type"] = log_type
                if module_name:
                    payload["module_name"] = module_name
                if limit:
                    payload["limit"] = limit

                # logs_data = self.learning_app.monitoring_manager.query_logs(payload=payload)
                # Assuming query_logs directly takes these as args or a dict
                logs_data = self.learning_app.monitoring_manager.query_logs(
                    log_type=log_type, module_name=module_name, limit=limit
                )

                logger.info("Gateway sending monitoring logs.")
                # Ensure the response is a dict or can be converted by FastAPI
                # Typically, this would be a list of log entries, which FastAPI handles.
                # Wrapping in a standard response structure:
                return {"status": "success", "data": logs_data}
            except Exception as e:
                logger.exception(f"Error retrieving monitoring logs: {e}")
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        "API Gateway error retrieving monitoring logs",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error retrieving monitoring logs.",
                )

        # Add more routes here as needed (e.g., for backup, config, other visualizations)
        # Example: Backup route
        @self.app.post("/api/v1/backup", tags=["Admin"])
        async def trigger_backup_endpoint(request: Request) -> Dict[str, Any]:
            """Triggers a manual data backup."""
            logger.info("Gateway received manual backup trigger request.")
            try:
                # Extract reason if provided in body, otherwise use default
                reason = "Manual trigger via API Gateway"
                try:
                    body = await request.json()
                    reason = body.get("reason", reason)
                except Exception:
                    logger.warning(
                        "Could not parse request body for backup reason, using default."
                    )

                response = self.learning_app.trigger_backup_action(reason=reason)
                logger.info("Gateway sending backup trigger response.")
                return response
            except Exception as e:
                logger.exception(f"Error triggering backup: {e}")
                if hasattr(self.learning_app, "monitoring_manager"):
                    self.learning_app.monitoring_manager.log(
                        "error",
                        "API Gateway error during backup trigger",
                        {"error": str(e), "module": "APIGateway"},
                    )
                raise HTTPException(
                    status_code=500, detail="Internal server error triggering backup."
                )

    def get_fastapi_app(self) -> FastAPI:
        """Returns the FastAPI application instance."""
        return self.app


# --- Standalone Run Function (for testing or separate deployment) ---
def run_gateway(
    learning_app: 'LearningAssistantApp', host: str = "127.0.0.1", port: int = 8000
):
    """
    Initializes and runs the FastAPI gateway server.
    """
    gateway = APIGateway(learning_app)
    fastapi_app = gateway.get_fastapi_app()
    logger.info(f"Starting API Gateway server on {host}:{port}")
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


# Example of how this might be run (though typically integrated into app.py)
# if __name__ == "__main__":
#     # This requires creating a dummy or real LearningAssistantApp instance
#     # For standalone testing, you might mock the app instance
#     class MockLearningApp:
#         def handle_interaction(self, session_id: str, user_input: str):
#             print(f"MockApp: Handling interaction for {session_id} with input: {user_input}")
#             return {"status": "success", "response": {"content": f"Mock response to {user_input}"}}
#         def get_visualization(self, viz_type: str, user_id: str, params: Optional[Dict] = None):
#             print(f"MockApp: Getting viz {viz_type} for {user_id} with params {params}")
#             return {"status": "success", "data": {"nodes": [], "links": []}}
#         def trigger_backup_action(self, reason: str):
#             print(f"MockApp: Triggering backup because: {reason}")
#             return {"status": "success", "message": "Mock backup started"}
#         # Mock monitoring manager for logging tests
#         class MockMonitor:
#             def log(self, level, message, details=None):
#                 print(f"MockMonitor [{level.upper()}]: {message} {details or ''}")
#         monitoring_manager = MockMonitor()

#     mock_app_instance = MockLearningApp()
#     run_gateway(mock_app_instance)
