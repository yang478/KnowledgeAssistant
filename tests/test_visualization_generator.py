"""Unit tests for the VisualizationGenerator class."""

import unittest
from unittest.mock import patch, MagicMock, ANY

# Ensure the necessary modules can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from visualization_generator.visualization_generator import VisualizationGenerator
from memory_bank_manager.memory_bank_manager import MemoryBankManager # For spec
from config_manager.config_manager import ConfigManager # For spec
from monitoring_manager.monitoring_manager import MonitoringManager # For spec

class TestVisualizationGenerator(unittest.TestCase):
    """Tests for the VisualizationGenerator."""

    def setUp(self):
        """Set up a VisualizationGenerator instance with mocked dependencies."""
        self.mock_memory_bank_manager = MagicMock(spec=MemoryBankManager)
        self.mock_config_manager = MagicMock(spec=ConfigManager) # Config might be used for viz options
        self.mock_monitoring_manager = MagicMock(spec=MonitoringManager)

        # Simulate config for visualization (if any, simplified)
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: {
            "visualization.knowledge_graph.default_depth": 3,
            "visualization.progress_dashboard.default_time_period": "last_30_days",
        }.get(key, default)

        self.visualization_generator = VisualizationGenerator(
            memory_bank_manager=self.mock_memory_bank_manager,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
        )

    def test_initialization(self):
        """Test that VisualizationGenerator initializes correctly."""
        self.assertIsNotNone(self.visualization_generator.memory_bank_manager)
        self.assertIsNotNone(self.visualization_generator.config_manager)
        self.assertIsNotNone(self.visualization_generator.monitoring_manager)
        # Assuming VisualizationGenerator.__init__ calls self.monitoring_manager.log_info(...)
        self.mock_monitoring_manager.log_info.assert_called_once_with("VisualizationGenerator initialized") # Removed dot and used assert_called_once_with

    def test_get_knowledge_graph_data_success(self):
        """Test successful generation of knowledge graph data."""
        # Arrange
        user_id = "user123"
        depth = 2
        root_node_id = "kp_root"
        
        mock_nodes_data = [
            {"id": "kp_root", "name": "Root Topic", "status": "mastered"},
            {"id": "kp_child1", "name": "Child 1", "status": "learning"},
        ]
        mock_edges_data = [
            {"source": "kp_root", "target": "kp_child1", "relation": "dependency"}
        ]
        # Assume MBM has a method to fetch graph-compatible data
        # self.mock_memory_bank_manager.get_knowledge_graph_elements.return_value = (mock_nodes_data, mock_edges_data) # Replaced
        # VisualizationGenerator now calls process_request with "get_all_kps"
        # and then processes this data into nodes and edges.
        # The mock_nodes_data and mock_edges_data are for the *output* of VisualizationGenerator,
        # not directly for MBM's output for "get_all_kps".
        # MBM's "get_all_kps" should return a list of knowledge point dicts.
        mock_mbm_kps_data = [
            {"id": "kp_root", "title": "Root Topic", "status": "mastered", "dependencies": []},
            {"id": "kp_child1", "title": "Child 1", "status": "learning", "dependencies": ["kp_root"]},
             # Add more KPs if the test logic for nodes/edges requires it
        ]
        self.mock_memory_bank_manager.process_request.return_value = {
            "status": "success",
            "data": mock_mbm_kps_data
            # This data will be processed by VisualizationGenerator to create nodes and edges
        }
        # Act
        response = self.visualization_generator.get_knowledge_graph_data(
            user_id=user_id, depth=depth, root_node_id=root_node_id
        )

        # Assert
        self.mock_monitoring_manager.log_info.assert_any_call( # Changed to log_info
            f"Generating knowledge graph data for user {user_id}, depth {depth}, root {root_node_id}."
            # Consider removing ANY if VisualizationGenerator logs exactly this.
        )
        # self.mock_memory_bank_manager.get_knowledge_graph_elements.assert_called_once_with( # Replaced
        #     user_id=user_id, depth=depth, root_node_id=root_node_id, filter_params=None # or {}
        # )
        self.mock_memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_all_kps", # Changed from get_all_syllabus_topics
            "payload": {}
        })
        
        self.assertEqual(response["status"], "success")
        self.assertIn("nodes", response["data"])
        self.assertIn("links", response["data"]) # VisualizationGenerator output uses "links"
        # The number of nodes/links depends on how mock_mbm_kps_data is processed
        # For the example mock_mbm_kps_data:
        # Nodes: kp_root, kp_child1 (2 nodes)
        # Links: kp_root -> kp_child1 (1 link)
        self.assertEqual(len(response["data"]["nodes"]), 2)
        self.assertEqual(len(response["data"]["links"]), 1)
        self.assertEqual(response["data"]["links"][0]["source"], "kp_root") # Corrected based on mock_mbm_kps_data processing
        self.assertEqual(response["data"]["links"][0]["target"], "kp_child1") # Corrected
        self.assertEqual(response["message"], "Knowledge graph data generated successfully.")

    def test_get_progress_dashboard_data_success(self):
        """Test successful generation of progress dashboard data."""
        # Arrange
        user_id = "user456"
        time_period = "last_7_days"
        
        mock_dashboard_summary = {
            "total_learning_time": "10h 30m",
            "knowledge_points_mastered": 5,
            "average_assessment_score": 88.5,
        }
        mock_progress_over_time = [
            {"date": "2023-01-01", "learning_time": 60, "newly_mastered": 1},
            {"date": "2023-01-02", "learning_time": 90, "newly_mastered": 0},
        ]
        mock_mastery_dist = {"mastered": 15, "learning": 5, "not_started": 10}

        # Assume MBM has methods to fetch this data
        # self.mock_memory_bank_manager.get_progress_summary_stats.return_value = mock_dashboard_summary # Replaced
        # self.mock_memory_bank_manager.get_progress_over_time_data.return_value = mock_progress_over_time # Replaced
        # self.mock_memory_bank_manager.get_mastery_distribution.return_value = mock_mastery_dist # Replaced

        # VisualizationGenerator calls "get_all_kps" and calculates stats internally.
        # Provide a list of KPs that would result in the mock_dashboard_summary, etc.
        mock_kps_for_dashboard = [
            {"id": "kp1", "title": "Topic 1", "status": "mastered"},
            {"id": "kp2", "title": "Topic 2", "status": "mastered"},
            {"id": "kp3", "title": "Topic 3", "status": "mastered"},
            {"id": "kp4", "title": "Topic 4", "status": "mastered"},
            {"id": "kp5", "title": "Topic 5", "status": "mastered"}, # 5 mastered
            {"id": "kp6", "title": "Topic 6", "status": "learning"},
            {"id": "kp7", "title": "Topic 7", "status": "learning"},
            {"id": "kp8", "title": "Topic 8", "status": "learning"},
            {"id": "kp9", "title": "Topic 9", "status": "learning"},
            {"id": "kp10", "title": "Topic 10", "status": "learning"}, # 5 learning
            {"id": "kp11", "title": "Topic 11", "status": "not_started"}, # 1 not_started
            {"id": "kp12", "title": "Topic 12", "status": "review"},      # 1 review
            {"id": "kp13", "title": "Topic 13", "status": "unknown_status"}, # 1 unknown
            # Total 13 points
        ]
        self.mock_memory_bank_manager.process_request.return_value = {
            "status": "success",
            "data": mock_kps_for_dashboard
        }
        # Act
        response = self.visualization_generator.get_progress_dashboard_data(
            user_id=user_id, time_period=time_period
        )

        # Assert
        self.mock_monitoring_manager.log_info.assert_any_call( # Changed to log_info
            f"Generating progress dashboard data for user {user_id}, period {time_period}."
            # Consider removing ANY
        )
        # self.mock_memory_bank_manager.get_progress_summary_stats.assert_called_once_with(user_id, time_period) # Replaced
        # self.mock_memory_bank_manager.get_progress_over_time_data.assert_called_once_with(user_id, time_period) # Replaced
        # self.mock_memory_bank_manager.get_mastery_distribution.assert_called_once_with(user_id) # Replaced
        self.mock_memory_bank_manager.process_request.assert_called_once_with({
            "operation": "get_all_kps", # Changed from get_all_syllabus_topics
            "payload": {}
        })
        self.assertEqual(response["status"], "success")
        # The actual values depend on how VisualizationGenerator processes mock_kps_for_dashboard
        # For the updated mock_kps_for_dashboard:
        # mastered: 5, learning: 5, not_started: 1, review: 1, unknown: 1
        # total_points for overall_progress calculation in VG is len(all_knowledge_points) = 13
        # overall_progress = (5 / 13 * 100) approx 38.46
        self.assertEqual(response["data"]["overall_progress"], round(5/13*100, 2))
        self.assertEqual(response["data"]["status_distribution"]["mastered"], 5)
        self.assertEqual(response["data"]["status_distribution"]["learning"], 5)
        self.assertEqual(response["data"]["status_distribution"]["not_started"], 1)
        self.assertEqual(response["data"]["status_distribution"]["review"], 1)
        self.assertEqual(response["data"]["status_distribution"]["unknown"], 1)
        self.assertEqual(response["message"], "Progress dashboard data generated successfully.")

    def test_get_knowledge_graph_data_mbm_error(self):
        """Test error handling if MBM fails during knowledge graph data retrieval."""
        # Arrange
        user_id = "user_err_kg"
        # self.mock_memory_bank_manager.get_knowledge_graph_elements.side_effect = Exception("MBM connection error for KG") # Replaced
        self.mock_memory_bank_manager.process_request.return_value = { # Corrected: ensure this is a dictionary for .get
            "status": "error", "message": "MBM connection error for KG from process_request"
        }
        # Act
        response = self.visualization_generator.get_knowledge_graph_data(user_id=user_id)

        # Assert
        self.assertEqual(response["status"], "error")
        self.assertTrue("Failed to retrieve knowledge data for graph." in response["message"]) # Matches VG error message
        self.mock_monitoring_manager.log_error.assert_any_call(
            "Failed to get knowledge points from MemoryBankManager for graph", # Message from VG
            context={"user_id": user_id, "response": "MBM connection error for KG from process_request"} # Context from VG
        )

    def test_get_progress_dashboard_data_mbm_error(self):
        """Test error handling if MBM fails during progress dashboard data retrieval."""
        # Arrange
        user_id = "user_err_dash"
        # self.mock_memory_bank_manager.get_progress_summary_stats.side_effect = Exception("MBM error for dashboard") # Replaced
        self.mock_memory_bank_manager.process_request.return_value = { # Corrected: ensure this is a dictionary for .get
            "status": "error", "message": "MBM error for dashboard from process_request"
        }
        # Act
        response = self.visualization_generator.get_progress_dashboard_data(user_id=user_id)

        # Assert
        self.assertEqual(response["status"], "error")
        self.assertTrue("Failed to retrieve knowledge data for dashboard." in response["message"]) # Matches VG error message
        self.mock_monitoring_manager.log_error.assert_any_call(
            "Failed to get knowledge points from MemoryBankManager for dashboard", # Message from VG
            context={"user_id": user_id, "response": "MBM error for dashboard from process_request"} # Context from VG
        )

if __name__ == '__main__':
    unittest.main()
