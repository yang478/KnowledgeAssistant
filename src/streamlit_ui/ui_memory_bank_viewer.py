# -*- coding: utf-8 -*-
"""
Streamlit UI for the Memory Bank Viewer.

This module defines the Streamlit interface for browsing and inspecting
the contents of the memory bank, such as knowledge points, relationships,
and metadata.
"""
import streamlit as st
from typing import Callable, Dict, Any, Optional, List
import pandas as pd # For displaying tabular data

# Attempt to import the API call utility
try:
    from .ui_utils import call_api_gateway
except ImportError:
    def call_api_gateway(operation: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        st.error("API Gateway call function is not available. Please ensure ui_utils.py is correctly set up.")
        return {"status": "error", "message": "API Gateway not available."}

class MemoryBankViewerUI:
    """
    Manages the Streamlit UI components for viewing the Memory Bank.
    """
    def __init__(self, session_id: Optional[str] = None, mbm_instance: Optional[Any] = None):
        """
        Initializes the MemoryBankViewerUI.

        Args:
            session_id (Optional[str]): The current user's session ID.
            mbm_instance (Optional[Any]): An instance of MemoryBankManager for direct calls.
        """
        self.session_id = session_id
        self.mbm_instance = mbm_instance

        if 'viewer_all_kps_data' not in st.session_state:
            st.session_state.viewer_all_kps_data = []
        if 'viewer_selected_kp_details' not in st.session_state:
            st.session_state.viewer_selected_kp_details = None
        if 'viewer_filter_category' not in st.session_state:
            st.session_state.viewer_filter_category = "All"
        if 'viewer_filter_tag' not in st.session_state:
            st.session_state.viewer_filter_tag = ""


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

    def display_viewer_view(self):
        """
        Renders the main memory bank viewer UI section.
        """
        st.header("🏦 Memory Bank Explorer")
        st.write("Browse, search, and inspect the knowledge stored in your memory bank.")

        self.load_all_kps_if_empty() # Load KPs on first display or if empty

        # Filtering options
        self.display_filters()

        # Display KPs in a table or list
        self.display_kp_list()
        
        # Display details of a selected KP
        self.display_selected_kp_details()

    def load_all_kps_if_empty(self):
        """Loads all KPs if the session state is empty."""
        if not st.session_state.viewer_all_kps_data:
            self.fetch_all_kps_data()
            
    def fetch_all_kps_data(self):
        """Fetches all KPs from the backend."""
        response = self._handle_api_call("get_all_kps", {})
        if response.get("status") == "success":
            st.session_state.viewer_all_kps_data = response.get("data", [])
        else:
            st.error(f"Failed to load Knowledge Points: {response.get('message', 'Unknown error')}")
            st.session_state.viewer_all_kps_data = []


    def display_filters(self):
        """Displays filtering options for KPs."""
        st.sidebar.subheader("Filter Knowledge Points")
        
        # Fetch categories and tags for filter dropdowns
        # These could be fetched once and stored, or fetched on demand
        all_kps = st.session_state.viewer_all_kps_data
        
        categories = ["All"] + sorted(list(set(kp.get('category', 'N/A') for kp in all_kps if kp.get('category'))))
        st.session_state.viewer_filter_category = st.sidebar.selectbox(
            "Filter by Category:", 
            options=categories,
            index=categories.index(st.session_state.viewer_filter_category) if st.session_state.viewer_filter_category in categories else 0,
            key="viewer_cat_filter"
        )

        # For tags, it might be better to have a text input for now, or a multi-select if tags are numerous
        st.session_state.viewer_filter_tag = st.sidebar.text_input(
            "Filter by Tag (enter one tag):", 
            value=st.session_state.viewer_filter_tag,
            key="viewer_tag_filter"
        ).strip()

        if st.sidebar.button("Apply Filters / Refresh List", key="viewer_apply_filters"):
            # Refetch or re-filter client-side based on complexity
            # For now, client-side filtering is implemented in display_kp_list
            st.rerun() 
            # If server-side filtering is preferred:
            # payload = {}
            # if st.session_state.viewer_filter_category != "All":
            #     payload["category"] = st.session_state.viewer_filter_category
            # if st.session_state.viewer_filter_tag:
            #     payload["tags"] = [st.session_state.viewer_filter_tag] # Assuming API expects a list
            # response = self._handle_api_call("search_kps", payload) # Or a dedicated filter endpoint
            # if response.get("status") == "success":
            #     st.session_state.viewer_all_kps_data = response.get("data", [])
            # else:
            #     st.error("Failed to apply filters via API.")


    def display_kp_list(self):
        """
        Displays a list/table of Knowledge Points, optionally filtered.
        """
        st.subheader("Knowledge Point Overview")
        
        kps_to_display = st.session_state.viewer_all_kps_data
        
        # Apply filters (client-side for this example)
        if st.session_state.viewer_filter_category != "All":
            kps_to_display = [kp for kp in kps_to_display if kp.get('category') == st.session_state.viewer_filter_category]
        
        if st.session_state.viewer_filter_tag:
            tag_to_filter = st.session_state.viewer_filter_tag.lower()
            kps_to_display = [
                kp for kp in kps_to_display 
                if kp.get('tags') and isinstance(kp.get('tags'), list) and 
                   any(tag_to_filter == str(tag).lower() for tag in kp.get('tags'))
            ]

        if not kps_to_display:
            st.info("No Knowledge Points match the current filters, or the memory bank is empty.")
            return

        # Prepare data for display (e.g., in a Pandas DataFrame for Streamlit's table/dataframe elements)
        display_data = []
        for kp in kps_to_display:
            display_data.append({
                "ID": kp.get("id"),
                "Title": kp.get("title", "N/A"),
                "Category": kp.get("category", "N/A"),
                "Status": kp.get("status", "N/A"),
                "Tags": ", ".join(kp.get("tags", []) if kp.get("tags") else []),
                "Priority": kp.get("priority", "N/A")
            })
        
        df = pd.DataFrame(display_data)
        
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Allow selecting a KP from the list/table to view details
        # This could be done by making IDs clickable or adding a selectbox
        kp_id_options = [""] + [kp.get("id") for kp in kps_to_display if kp.get("id")]
        selected_kp_id = st.selectbox(
            "Select KP ID to view details:", 
            options=kp_id_options,
            index=0,
            key="viewer_select_kp_for_detail"
        )

        if selected_kp_id:
            # Fetch full details for the selected KP
            response = self._handle_api_call("get_kp", {"id": selected_kp_id})
            if response.get("status") == "success" and response.get("data"):
                st.session_state.viewer_selected_kp_details = response.get("data")
            else:
                st.error(f"Failed to fetch details for KP {selected_kp_id}: {response.get('message')}")
                st.session_state.viewer_selected_kp_details = None
            st.rerun() # Rerun to update the detail view

    def display_selected_kp_details(self):
        """
        Displays detailed information about a selected Knowledge Point.
        """
        if st.session_state.viewer_selected_kp_details:
            st.subheader("Knowledge Point Details")
            kp_details = st.session_state.viewer_selected_kp_details
            
            st.markdown(f"#### {kp_details.get('title', 'N/A')}")
            st.json(kp_details, expanded=False) # Display all fields in a collapsible JSON view

            # Could also display fields more nicely:
            # st.markdown(f"**ID:** `{kp_details.get('id')}`")
            # ... and so on for other fields like content, created_at, updated_at, etc.
            
            if st.button("Clear Detail View", key="viewer_clear_detail"):
                st.session_state.viewer_selected_kp_details = None
                st.rerun()
        else:
            st.caption("Select a KP from the list above to see its details here.")


# To run this UI component independently for testing (optional)
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Memory Bank Viewer Test")
    
    mock_session_id = "test_session_viewer_001"

    class MockMBMViewer:
        _kps = [
            {"id": "kp001", "title": "Introduction to Python", "content": "Python is a versatile language.", "category": "Programming", "tags": ["python", "beginner"], "status": "mastered", "priority": 1},
            {"id": "kp002", "title": "Data Structures in Python", "content": "Lists, Dictionaries, Sets, Tuples.", "category": "Programming", "tags": ["python", "data structures"], "status": "learning", "priority": 2},
            {"id": "kp003", "title": "Calculus Basics", "content": "Limits and Derivatives.", "category": "Math", "tags": ["calculus", "math"], "status": "new", "priority": 1},
            {"id": "kp004", "title": "Advanced Python", "content": "Decorators, Generators, Metaclasses.", "category": "Programming", "tags": ["python", "advanced"], "status": "new", "priority": 3},
        ]
        def process_request(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            st.sidebar.info(f"Mock Viewer MBM called: {operation} with {payload}")
            if operation == "get_all_kps":
                return {"status": "success", "data": self._kps}
            if operation == "get_kp":
                kp_id = payload.get("id")
                found_kp = next((kp for kp in self._kps if kp.get("id") == kp_id), None)
                if found_kp:
                    return {"status": "success", "data": found_kp}
                return {"status": "error", "message": "KP not found (mock)."}
            return {"status": "error", "message": "Mock operation not implemented."}

    # viewer_ui = MemoryBankViewerUI(session_id=mock_session_id, mbm_instance=MockMBMViewer())
    viewer_ui = MemoryBankViewerUI(session_id=mock_session_id) # Test with placeholder API

    st.sidebar.title("Memory Bank Viewer")
    viewer_ui.display_viewer_view()

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Debug Info (Session State):**")
    st.sidebar.json(st.session_state)