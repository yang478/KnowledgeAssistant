"""Unit tests for the APIGateway class and its FastAPI app."""

import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure the necessary modules can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from api_gateway.gateway import APIGateway
# LearningAssistantApp is a dependency, will be mocked
# from app import LearningAssistantApp # For spec if needed

class TestAPIGateway(unittest.TestCase):
    """Tests for the APIGateway."""

    def setUp(self):
        """Set up an APIGateway instance with a mocked LearningAssistantApp."""
        self.mock_learning_app = MagicMock() # spec=LearningAssistantApp
        
        # Mock methods of LearningAssistantApp that APIGateway calls
        self.mock_learning_app.handle_interaction.return_value = {"status": "success", "response": "interaction handled"}
        self.mock_learning_app.get_visualization.return_value = {"status": "success", "data": {"viz_type": "graph", "nodes": []}}
        self.mock_learning_app.trigger_backup_action.return_value = {"status": "success", "message": "backup triggered"}
        self.mock_learning_app.config_manager.get_config.return_value = {} # For API key check if any

        self.api_gateway = APIGateway(learning_app=self.mock_learning_app)
        self.client = TestClient(self.api_gateway.get_fastapi_app())

    def test_initialization(self):
        """Test that APIGateway initializes correctly."""
        self.assertIsNotNone(self.api_gateway.learning_app) # Changed app_instance to learning_app
        self.assertIsNotNone(self.api_gateway.app) # Changed router to app (FastAPI instance)
        # FastAPI app is directly available as self.api_gateway.app after __init__

    def test_interact_endpoint(self):
        """Test the /session/{session_id}/interact endpoint."""
        session_id = "test_session_123"
        request_payload = {"user_input": "Hello assistant", "timestamp": "2023-01-01T00:00:00Z"}
        
        response = self.client.post(f"/api/v1/session/{session_id}/interact", json=request_payload)
        
        self.assertEqual(response.status_code, 200)
        self.mock_learning_app.handle_interaction.assert_called_once_with(
            session_id=session_id,
            user_input=request_payload["user_input"],
            # current_mode_suggestion is optional, so it might be None or not passed if not in payload
            # timestamp=request_payload["timestamp"] # Check if gateway passes this through
        )
        self.assertEqual(response.json(), {"status": "success", "response": "interaction handled"})

    def test_get_knowledge_graph_visualization_endpoint(self):
        """Test the /visualizations/knowledge_graph endpoint."""
        user_id = "user_kg_viz"
        params = {"depth": "2", "root_node_id": "kp_root_viz"} # FastAPI converts query params to correct types
        
        response = self.client.get(f"/api/v1/visualizations/knowledge_graph?user_id={user_id}&depth=2&root_node_id=kp_root_viz")
        
        self.assertEqual(response.status_code, 200)
        self.mock_learning_app.get_visualization.assert_called_once_with(
            viz_type="knowledge_graph",
            user_id=user_id,
            params={"depth": 2, "root_node_id": "kp_root_viz"} 
        )
        self.assertEqual(response.json(), {"status": "success", "data": {"viz_type": "graph", "nodes": []}})

    def test_get_progress_dashboard_visualization_endpoint(self):
        """Test the /visualizations/progress_dashboard endpoint."""
        user_id = "user_pd_viz"
        
        response = self.client.get(f"/api/v1/visualizations/progress_dashboard?user_id={user_id}")
        
        self.assertEqual(response.status_code, 200)
        self.mock_learning_app.get_visualization.assert_called_once_with(
            viz_type="progress_dashboard",
            user_id=user_id,
            params={} # No extra params in this case
        )
        # Assuming get_visualization returns a dict that is directly converted to JSON
        self.assertEqual(response.json(), self.mock_learning_app.get_visualization.return_value)


    def test_trigger_backup_endpoint(self):
        """Test the /admin/backup endpoint."""
        request_payload = {"reason": "Routine weekly backup"}
        
        response = self.client.post("/api/v1/backup", json=request_payload) # Corrected endpoint from /admin/backup to /backup
        
        self.assertEqual(response.status_code, 200)
        self.mock_learning_app.trigger_backup_action.assert_called_once_with(
            reason=request_payload["reason"]
        )
        self.assertEqual(response.json(), {"status": "success", "message": "backup triggered"})

    def test_interact_endpoint_missing_input(self):
        """Test interact endpoint with missing user_input."""
        session_id = "test_session_bad_request"
        # Missing 'user_input'
        request_payload = {"timestamp": "2023-01-01T00:00:00Z"} 
        
        response = self.client.post(f"/api/v1/session/{session_id}/interact", json=request_payload)
        
        # FastAPI should return a 422 Unprocessable Entity for validation errors
        self.assertEqual(response.status_code, 422) 
        # The exact error detail depends on Pydantic model validation
        self.assertIn("detail", response.json())

    def test_get_knowledge_point_details_success(self):
        """Test GET /api/v1/memory/knowledge_point/{kp_id} successfully."""
        kp_id = "kp_test_123"
        expected_data = {"id": kp_id, "title": "Test Knowledge Point", "content": "Details"}
        self.mock_learning_app.memory_bank_manager.process_request.return_value = {
            "status": "success",
            "data": expected_data
        }
        
        response = self.client.get(f"/api/v1/memory/knowledge_point/{kp_id}")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "data": expected_data})
        self.mock_learning_app.memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_knowledge_point",
            "payload": {"knowledge_point_id": kp_id},
        })

    def test_get_knowledge_point_details_not_found(self):
        """Test GET /api/v1/memory/knowledge_point/{kp_id} when KP is not found."""
        kp_id = "kp_not_found_456"
        self.mock_learning_app.memory_bank_manager.process_request.return_value = {
            "status": "error",
            "message": "Knowledge point not found.",
            "data": None
        }
        
        response = self.client.get(f"/api/v1/memory/knowledge_point/{kp_id}")
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], "Knowledge point not found.")
        self.mock_learning_app.memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_knowledge_point",
            "payload": {"knowledge_point_id": kp_id},
        })

    def test_get_knowledge_point_details_generic_error(self):
        """Test GET /api/v1/memory/knowledge_point/{kp_id} for a generic MBM error."""
        kp_id = "kp_error_789"
        self.mock_learning_app.memory_bank_manager.process_request.return_value = {
            "status": "error",
            "message": "Some MBM error occurred.",
            "data": {"info": "error details"} # Data is not None
        }

        response = self.client.get(f"/api/v1/memory/knowledge_point/{kp_id}")

        self.assertEqual(response.status_code, 400) # As per gateway logic
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], "Some MBM error occurred.")
        self.mock_learning_app.memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_knowledge_point",
            "payload": {"knowledge_point_id": kp_id},
        })

    def test_get_session_context_success(self):
        """Test GET /api/v1/session/{session_id}/context successfully."""
        session_id = "session_test_ctx_123"
        expected_data = {"session_id": session_id, "current_topics": ["topic1"], "unresolved_questions": []}
        self.mock_learning_app.memory_bank_manager.process_request.return_value = {
            "status": "success",
            "data": expected_data
        }
        
        response = self.client.get(f"/api/v1/session/{session_id}/context")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "data": expected_data})
        self.mock_learning_app.memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_learning_context",
            "payload": {"session_id": session_id},
        })

    def test_get_session_context_not_found(self):
        """Test GET /api/v1/session/{session_id}/context when session context is not found."""
        session_id = "session_not_found_ctx_456"
        self.mock_learning_app.memory_bank_manager.process_request.return_value = {
            "status": "error",
            "message": "Session context not found.",
            "data": None
        }
        
        response = self.client.get(f"/api/v1/session/{session_id}/context")
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], "Session context not found.")
        self.mock_learning_app.memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_learning_context",
            "payload": {"session_id": session_id},
        })

    def test_get_session_context_generic_error(self):
        """Test GET /api/v1/session/{session_id}/context for a generic MBM error."""
        session_id = "session_error_ctx_789"
        self.mock_learning_app.memory_bank_manager.process_request.return_value = {
            "status": "error",
            "message": "MBM error retrieving context.",
            "data": {"info": "error details"} # Data is not None
        }

        response = self.client.get(f"/api/v1/session/{session_id}/context")

        self.assertEqual(response.status_code, 400) # As per gateway logic
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], "MBM error retrieving context.")
        self.mock_learning_app.memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_learning_context",
            "payload": {"session_id": session_id},
        })

    def test_get_configuration_value_success(self):
        """Test GET /api/v1/config/{key} successfully."""
        config_key = "llm.model"
        expected_value = "gpt-4"
        self.mock_learning_app.config_manager.get_config.return_value = expected_value
        
        response = self.client.get(f"/api/v1/config/{config_key}")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "key": config_key, "value": expected_value})
        self.mock_learning_app.config_manager.get_config.assert_called_once_with(config_key)

    def test_get_configuration_value_not_found(self):
        """Test GET /api/v1/config/{key} when key is not found."""
        config_key = "non.existent.key"
        self.mock_learning_app.config_manager.get_config.return_value = None
        
        response = self.client.get(f"/api/v1/config/{config_key}")
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], f"Configuration key '{config_key}' not found.")
        self.mock_learning_app.config_manager.get_config.assert_called_once_with(config_key)

    def test_get_configuration_value_generic_error(self):
        """Test GET /api/v1/config/{key} for a generic ConfigManager error."""
        config_key = "error.key"
        self.mock_learning_app.config_manager.get_config.side_effect = Exception("ConfigManager internal error")

        response = self.client.get(f"/api/v1/config/{config_key}")

        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], f"Internal server error retrieving configuration for key {config_key}.")
        self.mock_learning_app.config_manager.get_config.assert_called_once_with(config_key)

    def test_get_monitoring_status_success(self):
        """Test GET /api/v1/monitoring/status successfully."""
        expected_status_data = {"status": "success", "data": {"db_connection": "ok", "llm_service": "active"}}
        # In gateway.py, get_monitoring_status returns the raw data, not wrapped.
        # Let's adjust the mock to return the inner data, and the test to expect the direct data.
        # Or, more consistently with other endpoints, the gateway should wrap it.
        # For now, let's assume the gateway *should* return it directly if monitoring_manager returns a dict.
        # The current gateway code for get_monitoring_status does:
        #   status_data = self.learning_app.monitoring_manager.get_system_status()
        #   return status_data
        # So the mock should return what the client expects directly from the endpoint.
        self.mock_learning_app.monitoring_manager.get_system_status.return_value = expected_status_data
        
        response = self.client.get("/api/v1/monitoring/status")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected_status_data) # Expecting direct data
        self.mock_learning_app.monitoring_manager.get_system_status.assert_called_once_with()

    def test_get_monitoring_status_generic_error(self):
        """Test GET /api/v1/monitoring/status for a generic MonitoringManager error."""
        self.mock_learning_app.monitoring_manager.get_system_status.side_effect = Exception("Monitoring internal error")

        response = self.client.get("/api/v1/monitoring/status")

        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], "Internal server error retrieving monitoring status.")
        self.mock_learning_app.monitoring_manager.get_system_status.assert_called_once_with()

    def test_get_monitoring_logs_success_with_params(self):
        """Test GET /api/v1/monitoring/logs successfully with all query parameters."""
        expected_logs_data = [{"timestamp": "2023-01-01T10:00:00Z", "level": "ERROR", "message": "Test error log"}]
        self.mock_learning_app.monitoring_manager.query_logs.return_value = expected_logs_data
        
        log_type = "error"
        module_name = "test_module"
        limit = 10
        
        response = self.client.get(f"/api/v1/monitoring/logs?log_type={log_type}&module_name={module_name}&limit={limit}")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "data": expected_logs_data})
        self.mock_learning_app.monitoring_manager.query_logs.assert_called_once_with(
            log_type=log_type, module_name=module_name, limit=limit
        )

    def test_get_monitoring_logs_success_no_params(self):
        """Test GET /api/v1/monitoring/logs successfully with no query parameters (defaults)."""
        expected_logs_data = [{"timestamp": "2023-01-02T10:00:00Z", "level": "INFO", "message": "Test info log"}]
        self.mock_learning_app.monitoring_manager.query_logs.return_value = expected_logs_data
        
        response = self.client.get("/api/v1/monitoring/logs")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success", "data": expected_logs_data})
        # Gateway passes None for log_type and module_name, and default 100 for limit if not provided.
        self.mock_learning_app.monitoring_manager.query_logs.assert_called_once_with(
            log_type=None, module_name=None, limit=100 # Limit has a default of 100 in gateway
        )

    def test_get_monitoring_logs_generic_error(self):
        """Test GET /api/v1/monitoring/logs for a generic MonitoringManager error."""
        self.mock_learning_app.monitoring_manager.query_logs.side_effect = Exception("Monitoring logs internal error")

        response = self.client.get("/api/v1/monitoring/logs?limit=5")

        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.json())
        self.assertEqual(response.json()["detail"], "Internal server error retrieving monitoring logs.")
        self.mock_learning_app.monitoring_manager.query_logs.assert_called_once_with(
            log_type=None, module_name=None, limit=5
        )


if __name__ == '__main__':
    unittest.main()
