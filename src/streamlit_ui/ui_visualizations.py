# -*- coding: utf-8 -*-
"""
Streamlit UI for Visualizations.

This module defines the Streamlit interface for displaying various
visualizations related to the knowledge bank, learning progress,
KP relationships, etc.
"""
import streamlit as st
from typing import Callable, Dict, Any, Optional, List
import pandas as pd
import plotly.express as px # For interactive charts
import plotly.graph_objects as go # For more custom plots like network graphs

# Attempt to import the API call utility
try:
    from .ui_utils import call_api_gateway
except ImportError:
    def call_api_gateway(operation: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        st.error("API Gateway call function is not available. Please ensure ui_utils.py is correctly set up.")
        return {"status": "error", "message": "API Gateway not available."}

class VisualizationsUI:
    """
    Manages the Streamlit UI components for displaying visualizations.
    """
    def __init__(self, session_id: Optional[str] = None, mbm_instance: Optional[Any] = None):
        """
        Initializes the VisualizationsUI.

        Args:
            session_id (Optional[str]): The current user's session ID.
            mbm_instance (Optional[Any]): An instance of MemoryBankManager for direct calls.
        """
        self.session_id = session_id
        self.mbm_instance = mbm_instance

        if 'viz_kp_data' not in st.session_state: # Data for KP status, categories etc.
            st.session_state.viz_kp_data = [] 
        if 'viz_kp_relations_data' not in st.session_state: # Data for network graph
            st.session_state.viz_kp_relations_data = {"nodes": [], "edges": []}
        if 'viz_progress_data' not in st.session_state: # Learning progress over time
            st.session_state.viz_progress_data = []


    def _handle_api_call(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for making API calls."""
        if self.mbm_instance:
            try:
                return self.mbm_instance.process_request(operation, payload)
            except Exception as e:
                st.error(f"Direct MBM call error for {operation}: {e}")
                return {"status": "error", "message": str(e)}
        else:
            return call_api_gateway(operation, payload, session_id=self.session_id)

    def display_visualizations_view(self):
        """
        Renders the main visualizations UI section.
        """
        st.header("📊 Visual Insights")
        st.write("Explore your knowledge bank and learning patterns through visualizations.")

        # Load data if not already loaded
        if not st.session_state.viz_kp_data:
            self.load_visualization_data()

        tab1, tab2, tab3 = st.tabs(["KP Overview", "Knowledge Network", "Learning Progress"])

        with tab1:
            self.display_kp_overview_charts()
        with tab2:
            self.display_knowledge_network_graph()
        with tab3:
            self.display_learning_progress_charts()
            
    def load_visualization_data(self):
        """Loads data required for all visualizations."""
        # Fetch all KPs for status, category, tag distributions
        kp_response = self._handle_api_call("get_all_kps", {})
        if kp_response.get("status") == "success":
            st.session_state.viz_kp_data = kp_response.get("data", [])
        else:
            st.error(f"Failed to load KP data for visualizations: {kp_response.get('message')}")
            st.session_state.viz_kp_data = []

        # Fetch KP relations for network graph
        # This might need a dedicated API endpoint or processing get_all_kps if relations are embedded
        # For now, let's assume an endpoint 'get_all_kp_relations' or similar
        # Or, we can construct it from 'related_kps' field in each KP
        
        nodes = []
        edges = []
        if st.session_state.viz_kp_data:
            kp_map = {kp['id']: kp for kp in st.session_state.viz_kp_data}
            for kp in st.session_state.viz_kp_data:
                nodes.append({"id": kp['id'], "label": kp.get('title', kp['id']), "group": kp.get('category', 'Default')})
                if kp.get('related_kps'):
                    for related_id in kp.get('related_kps'):
                        if related_id in kp_map: # Ensure target node exists
                             # Add edge, could add relation_type if available
                            edges.append({"from": kp['id'], "to": related_id})
        st.session_state.viz_kp_relations_data = {"nodes": nodes, "edges": edges}


        # Fetch learning progress data (e.g., KPs mastered over time, review scores)
        # This would require specific API endpoints like 'get_learning_history' or 'get_assessment_summary'
        # Placeholder for now:
        # progress_response = self._handle_api_call("get_learning_progress_summary", {})
        # if progress_response.get("status") == "success":
        #     st.session_state.viz_progress_data = progress_response.get("data", [])
        # else:
        #     st.error(f"Failed to load progress data: {progress_response.get('message')}")
        st.session_state.viz_progress_data = [
            {"date": "2023-01-01", "kps_mastered": 5, "avg_score": 70},
            {"date": "2023-01-08", "kps_mastered": 8, "avg_score": 75},
            {"date": "2023-01-15", "kps_mastered": 12, "avg_score": 80},
        ] # Mock data

    def display_kp_overview_charts(self):
        """
        Displays charts summarizing Knowledge Points (e.g., by status, category).
        """
        st.subheader("Knowledge Point Overview")
        if not st.session_state.viz_kp_data:
            st.info("No KP data available to display charts.")
            if st.button("Retry loading KP data"):
                self.load_visualization_data()
                st.rerun()
            return

        df_kps = pd.DataFrame(st.session_state.viz_kp_data)

        if df_kps.empty:
            st.info("KP data is empty.")
            return
            
        # Chart 1: KPs by Status
        if 'status' in df_kps.columns:
            status_counts = df_kps['status'].value_counts().reset_index()
            status_counts.columns = ['status', 'count']
            fig_status = px.pie(status_counts, names='status', values='count', title="KPs by Status")
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.warning("KP data does not contain 'status' information for chart.")

        # Chart 2: KPs by Category
        if 'category' in df_kps.columns:
            category_counts = df_kps['category'].value_counts().reset_index()
            category_counts.columns = ['category', 'count']
            fig_category = px.bar(category_counts, x='category', y='count', title="KPs by Category", color='category')
            st.plotly_chart(fig_category, use_container_width=True)
        else:
            st.warning("KP data does not contain 'category' information for chart.")
            
        # Chart 3: Tag Cloud/Frequency (Simplified as bar chart)
        if 'tags' in df_kps.columns:
            all_tags = []
            for tags_list in df_kps['tags'].dropna(): # Ensure tags_list is not NaN
                if isinstance(tags_list, list):
                    all_tags.extend(tags_list)
            if all_tags:
                tags_df = pd.DataFrame(all_tags, columns=['tag'])
                tag_counts = tags_df['tag'].value_counts().nlargest(15).reset_index() # Top 15 tags
                tag_counts.columns = ['tag', 'count']
                fig_tags = px.bar(tag_counts, x='tag', y='count', title="Top 15 Tag Frequency")
                st.plotly_chart(fig_tags, use_container_width=True)
            else:
                st.info("No tags found in KPs to display frequency chart.")
        else:
            st.warning("KP data does not contain 'tags' information for chart.")


    def display_knowledge_network_graph(self):
        """
        Displays an interactive network graph of KPs and their relationships.
        This is a more complex visualization.
        """
        st.subheader("Knowledge Network Graph")
        
        nodes_data = st.session_state.viz_kp_relations_data.get("nodes", [])
        edges_data = st.session_state.viz_kp_relations_data.get("edges", [])

        if not nodes_data:
            st.info("No data available to display knowledge network. Ensure KPs and their relations are loaded.")
            if st.button("Retry loading network data"):
                self.load_visualization_data() # This should repopulate viz_kp_relations_data
                st.rerun()
            return

        # Prepare data for Plotly's Scattergl or a dedicated network library
        # For a simple Plotly graph_objects approach:
        node_ids = [node['id'] for node in nodes_data]
        node_labels = [node.get('label', node['id']) for node in nodes_data]
        node_groups = [node.get('group', 'Default') for node in nodes_data] # For coloring by category

        # Create a mapping from ID to index for edges
        id_to_index = {node_id: i for i, node_id in enumerate(node_ids)}

        edge_x = []
        edge_y = []
        
        # Need positions for nodes. Plotly's basic scatter doesn't auto-layout networks well.
        # A force-directed layout is usually needed. For simplicity, we'll just plot nodes
        # and indicate that edges exist, rather than drawing a full interactive graph without a
        # dedicated graph layout library or more complex Plotly setup.
        
        # A more robust solution would use something like `networkx` for layout then plot with Plotly,
        # or a JS library via `st.components.v1.html`.
        
        # Simplified: Show nodes and list edges
        st.write(f"Number of Knowledge Points (Nodes): {len(nodes_data)}")
        st.write(f"Number of Relations (Edges): {len(edges_data)}")

        if nodes_data:
            df_nodes = pd.DataFrame(nodes_data)
            # Simple scatter plot of nodes, colored by group (category)
            # This won't show edges, but gives an idea of node distribution if x,y were meaningful
            # For now, just use index as x and a constant y for a line of nodes
            df_nodes['x'] = range(len(df_nodes))
            df_nodes['y'] = 0 
            
            # Create a Plotly figure
            # This is a very basic representation. A real network graph needs layout algorithms.
            if len(df_nodes) > 0:
                fig = px.scatter(df_nodes, x='x', y='y', text='label', color='group',
                                 title="Knowledge Points (Simplified View - Layout Not Applied)",
                                 hover_name='label', size_max=10) # size can be constant if no size data
                fig.update_traces(textposition='top center')
                fig.update_layout(showlegend=True, xaxis_visible=False, yaxis_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No nodes to plot.")

        if edges_data:
            st.write("**Edges (Relations):**")
            df_edges = pd.DataFrame(edges_data)
            st.dataframe(df_edges, use_container_width=True)
        
        st.caption("Note: A full interactive network graph requires more advanced layout algorithms (e.g., using NetworkX + Plotly, or a dedicated JS library). This is a simplified representation.")


    def display_learning_progress_charts(self):
        """
        Displays charts related to learning progress over time.
        """
        st.subheader("Learning Progress")
        if not st.session_state.viz_progress_data:
            st.info("No learning progress data available.")
            # Add a button to fetch/refresh if applicable
            return

        df_progress = pd.DataFrame(st.session_state.viz_progress_data)
        
        if df_progress.empty:
            st.info("Progress data is empty.")
            return

        # Ensure 'date' is datetime
        if 'date' in df_progress.columns:
            try:
                df_progress['date'] = pd.to_datetime(df_progress['date'])
            except Exception as e:
                st.error(f"Could not parse 'date' column for progress chart: {e}")
                return
        else:
            st.warning("Progress data needs a 'date' column for time-series charts.")
            return

        # Chart 1: KPs Mastered Over Time
        if 'kps_mastered' in df_progress.columns:
            fig_kps_time = px.line(df_progress, x='date', y='kps_mastered', title="KPs Mastered Over Time", markers=True)
            st.plotly_chart(fig_kps_time, use_container_width=True)
        
        # Chart 2: Average Assessment Score Over Time
        if 'avg_score' in df_progress.columns:
            fig_score_time = px.line(df_progress, x='date', y='avg_score', title="Average Assessment Score Over Time", markers=True)
            fig_score_time.update_yaxes(range=[0, 100]) # Assuming score is percentage
            st.plotly_chart(fig_score_time, use_container_width=True)


# To run this UI component independently for testing (optional)
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Visualizations UI Test")
    
    mock_session_id = "test_session_viz_001"

    class MockMBMViz: # Simplified mock for visualization data
        _kps = [
            {"id": "kpA", "title": "Python Basics", "category": "Tech", "tags": ["python"], "status": "mastered", "related_kps": ["kpB"]},
            {"id": "kpB", "title": "Python Functions", "category": "Tech", "tags": ["python"], "status": "learning", "related_kps": ["kpA", "kpC"]},
            {"id": "kpC", "title": "Python Classes", "category": "Tech", "tags": ["python"], "status": "new"},
            {"id": "kpD", "title": "Calculus I", "category": "Math", "tags": ["math"], "status": "mastered"},
        ]
        _progress = [
            {"date": "2023-02-01", "kps_mastered": 10, "avg_score": 78},
            {"date": "2023-02-08", "kps_mastered": 15, "avg_score": 82},
        ]
        def process_request(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            st.sidebar.info(f"Mock Viz MBM called: {operation} with {payload}")
            if operation == "get_all_kps":
                return {"status": "success", "data": self._kps}
            # Add mock for get_learning_progress_summary if you implement it
            # if operation == "get_learning_progress_summary":
            #     return {"status": "success", "data": self._progress}
            return {"status": "error", "message": "Mock operation not implemented."}

    # viz_ui = VisualizationsUI(session_id=mock_session_id, mbm_instance=MockMBMViz())
    viz_ui = VisualizationsUI(session_id=mock_session_id) # Test with placeholder API
    
    st.sidebar.title("Visualizations Module")
    viz_ui.display_visualizations_view()

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Debug Info (Session State):**")
    st.sidebar.json(st.session_state)