# -*- coding: utf-8 -*-
"""
Streamlit UI for the Learner Module.

This module defines the Streamlit interface for learner-focused activities,
such as interacting with knowledge points, taking notes, and engaging
in learning sessions.
"""
import streamlit as st
from typing import Callable, Dict, Any, Optional, List

# Attempt to import the API call utility
try:
    from .ui_utils import call_api_gateway
except ImportError:
    def call_api_gateway(operation: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        st.error("API Gateway call function is not available. Please ensure ui_utils.py is correctly set up.")
        return {"status": "error", "message": "API Gateway not available."}

class LearnerUI:
    """
    Manages the Streamlit UI components for the Learner module.
    """
    def __init__(self, session_id: Optional[str] = None, mbm_instance: Optional[Any] = None):
        """
        Initializes the LearnerUI.

        Args:
            session_id (Optional[str]): The current user's session ID.
            mbm_instance (Optional[Any]): An instance of MemoryBankManager for direct calls.
        """
        self.session_id = session_id
        self.mbm_instance = mbm_instance

        if 'learner_current_kp' not in st.session_state:
            st.session_state.learner_current_kp = None # Stores the full KP data
        if 'learner_kps_for_review' not in st.session_state:
            st.session_state.learner_kps_for_review = []
        if 'learner_search_results' not in st.session_state:
            st.session_state.learner_search_results = []
        if 'learner_note_content' not in st.session_state:
            st.session_state.learner_note_content = ""


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

    def display_learner_view(self):
        """
        Renders the main learner UI section.
        """
        st.header("🧠 Learning Zone")
        st.write("Explore knowledge points, review materials, and deepen your understanding.")

        # Layout: Search/Browse KPs, Current KP display, Review Queue
        col1, col2 = st.columns([2, 1])

        with col1:
            self.display_kp_search_and_selection()
            self.display_current_kp()

        with col2:
            self.display_review_queue()
            self.display_note_taking() # Simple note taking for current KP

    def display_kp_search_and_selection(self):
        """
        UI for searching and selecting knowledge points.
        """
        st.subheader("🔍 Find Knowledge Points")
        search_term = st.text_input("Search by title, tag, or keyword:", key="learner_search_term")
        
        col_search_btn, col_get_all_btn = st.columns(2)
        with col_search_btn:
            if st.button("Search KPs", key="learner_search_button"):
                if search_term:
                    # API call to search KPs
                    response = self._handle_api_call("search_kps", {"query": search_term})
                    if response.get("status") == "success":
                        st.session_state.learner_search_results = response.get("data", [])
                        if not st.session_state.learner_search_results:
                            st.info("No knowledge points found matching your search.")
                    else:
                        st.error(f"Search failed: {response.get('message', 'Unknown error')}")
                        st.session_state.learner_search_results = []
                else:
                    st.warning("Please enter a search term.")
        
        with col_get_all_btn:
            if st.button("Show All KPs", key="learner_get_all_kps_button"):
                response = self._handle_api_call("get_all_kps", {})
                if response.get("status") == "success":
                    st.session_state.learner_search_results = response.get("data", [])
                    if not st.session_state.learner_search_results:
                        st.info("No knowledge points found in the memory bank.")
                else:
                    st.error(f"Failed to fetch all KPs: {response.get('message', 'Unknown error')}")
                    st.session_state.learner_search_results = []


        if st.session_state.learner_search_results:
            st.write("**Search Results:**")
            # Display results in a more selectable way
            kp_titles = [f"{kp.get('title', 'N/A')} (ID: {kp.get('id', 'N/A')})" for kp in st.session_state.learner_search_results]
            selected_kp_title_with_id = st.selectbox(
                "Select a Knowledge Point to view:", 
                options=kp_titles, 
                index=None, # Nothing selected by default
                placeholder="Choose a KP...",
                key="learner_selected_kp_from_search"
            )

            if selected_kp_title_with_id:
                # Extract ID from the selected string, assuming format "Title (ID: id_value)"
                try:
                    selected_id = selected_kp_title_with_id.split("(ID: ")[1][:-1]
                    # Find the full KP data from search results
                    selected_kp_data = next((kp for kp in st.session_state.learner_search_results if kp.get('id') == selected_id), None)
                    if selected_kp_data:
                        st.session_state.learner_current_kp = selected_kp_data
                        st.session_state.learner_note_content = selected_kp_data.get("notes", "") # Load notes if available
                        st.success(f"Selected KP: {selected_kp_data.get('title')}")
                        st.rerun() # Rerun to update the display_current_kp section
                    else:
                        st.error("Could not find selected KP data. Please try again.")
                except Exception as e:
                    st.error(f"Error processing selection: {e}")


    def display_current_kp(self):
        """
        Displays the currently selected knowledge point.
        """
        st.subheader("📖 Current Knowledge Point")
        if st.session_state.learner_current_kp:
            kp = st.session_state.learner_current_kp
            st.markdown(f"### {kp.get('title', 'No Title')}")
            st.markdown(f"**ID:** `{kp.get('id', 'N/A')}`")
            st.markdown(f"**Category:** {kp.get('category', 'N/A')}")
            st.markdown(f"**Tags:** {', '.join(kp.get('tags', [])) if kp.get('tags') else 'N/A'}")
            st.markdown(f"**Status:** {kp.get('status', 'N/A')}")
            
            with st.expander("Content", expanded=True):
                st.markdown(kp.get('content', 'No content available.'))

            # Placeholder for actions like "Mark as learning", "Add to review", etc.
            col_action1, col_action2, col_action3 = st.columns(3)
            with col_action1:
                if st.button("Mark as 'Learning'", key="learner_mark_learning"):
                    # API call to update KP status
                    response = self._handle_api_call("update_kp", {"id": kp['id'], "status": "learning"})
                    if response.get("status") == "success":
                        st.session_state.learner_current_kp['status'] = "learning"
                        st.success("KP status updated to 'learning'.")
                        st.rerun()
                    else:
                        st.error(f"Failed to update status: {response.get('message')}")
            with col_action2:
                if st.button("Mark as 'Mastered'", key="learner_mark_mastered"):
                    response = self._handle_api_call("update_kp", {"id": kp['id'], "status": "mastered"})
                    if response.get("status") == "success":
                        st.session_state.learner_current_kp['status'] = "mastered"
                        st.success("KP status updated to 'mastered'.")
                        st.rerun()
                    else:
                        st.error(f"Failed to update status: {response.get('message')}")
            with col_action3:
                if st.button("Add to Review Queue", key="learner_add_to_review"):
                    # This might be implicit if status changes, or a separate flag/API
                    st.info("Functionality to explicitly add to a manual review queue to be implemented.")


            # Display related KPs if available
            related_kps = kp.get('related_kps', [])
            if related_kps:
                st.markdown("**Related Knowledge Points:**")
                for rel_kp_id in related_kps:
                    # In a real app, you might want to make these clickable to load the related KP
                    st.markdown(f"- `{rel_kp_id}` (Details would require another fetch or pre-loading)")
        else:
            st.info("No knowledge point selected. Use the search above to find and select one.")

    def display_review_queue(self):
        """
        Displays KPs due for review.
        """
        st.subheader("🗓️ Review Queue")
        if st.button("Fetch KPs for Review", key="learner_fetch_review"):
            # API call to get KPs for review (e.g., based on spaced repetition logic)
            response = self._handle_api_call("get_kps_for_review", {}) # Payload might include user_id or context
            if response.get("status") == "success":
                st.session_state.learner_kps_for_review = response.get("data", [])
                if not st.session_state.learner_kps_for_review:
                    st.info("No KPs currently due for review.")
            else:
                st.error(f"Failed to fetch review queue: {response.get('message', 'Unknown error')}")
                st.session_state.learner_kps_for_review = []
        
        if st.session_state.learner_kps_for_review:
            st.write("**Items to Review:**")
            for kp_review_item in st.session_state.learner_kps_for_review:
                # kp_review_item could be full KP data or just summary
                kp_title = kp_review_item.get('title', 'N/A')
                kp_id = kp_review_item.get('id', 'N/A')
                if st.button(f"Review: {kp_title} (ID: {kp_id})", key=f"learner_review_kp_{kp_id}"):
                    # Load this KP into the main view
                    # This might involve another API call if only summary data is in review queue
                    full_kp_data_resp = self._handle_api_call("get_kp", {"id": kp_id})
                    if full_kp_data_resp.get("status") == "success" and full_kp_data_resp.get("data"):
                        st.session_state.learner_current_kp = full_kp_data_resp.get("data")
                        st.session_state.learner_note_content = st.session_state.learner_current_kp.get("notes", "")
                        st.success(f"Loaded '{kp_title}' for review.")
                        st.rerun()
                    else:
                        st.error(f"Could not load KP {kp_id} for review: {full_kp_data_resp.get('message')}")
        else:
            st.caption("Click 'Fetch KPs for Review' to populate.")

    def display_note_taking(self):
        """
        Simple note-taking UI for the current KP.
        """
        st.subheader("📝 My Notes")
        if st.session_state.learner_current_kp:
            kp_id = st.session_state.learner_current_kp.get("id")
            st.session_state.learner_note_content = st.text_area(
                "Notes for this Knowledge Point:", 
                value=st.session_state.learner_note_content, # Persist notes in session state temporarily
                height=150,
                key=f"learner_notes_for_{kp_id}" 
            )
            if st.button("Save Notes", key=f"learner_save_notes_{kp_id}"):
                # API call to save notes (e.g., as part of KP data or a separate notes entity)
                # This might be an update_kp operation with a 'notes' field
                payload = {
                    "id": kp_id,
                    "notes": st.session_state.learner_note_content 
                }
                response = self._handle_api_call("update_kp", payload) # Assuming 'notes' is a field in KP
                if response.get("status") == "success":
                    st.success("Notes saved successfully (simulated update to KP).")
                    # Update the current_kp in session_state if notes are part of it
                    if st.session_state.learner_current_kp:
                         st.session_state.learner_current_kp['notes'] = st.session_state.learner_note_content
                else:
                    st.error(f"Failed to save notes: {response.get('message')}")
        else:
            st.info("Select a Knowledge Point to take notes.")


# To run this UI component independently for testing (optional)
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Learner UI Test")
    
    mock_session_id = "test_session_learner_001"
    
    # For standalone testing, you might mock the mbm_instance or ensure call_api_gateway has a mock
    # Example of a very simple mock MBM for testing UI flow without real backend:
    class MockMBM:
        def process_request(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            st.sidebar.info(f"Mock MBM called: {operation} with {payload}")
            if operation == "search_kps":
                return {"status": "success", "data": [
                    {"id": "kp1", "title": "Mock KP 1", "content": "Content for KP1", "tags": ["mock"], "status": "new"},
                    {"id": "kp2", "title": "Mock KP 2", "content": "Content for KP2", "tags": ["test"], "status": "learning"},
                ]}
            if operation == "get_all_kps":
                 return {"status": "success", "data": [
                    {"id": "kp1", "title": "Mock KP 1 (All)", "content": "Content for KP1", "tags": ["mock"], "status": "new"},
                    {"id": "kp2", "title": "Mock KP 2 (All)", "content": "Content for KP2", "tags": ["test"], "status": "learning"},
                    {"id": "kp3", "title": "Mock KP 3 (All)", "content": "Content for KP3", "tags": ["example"], "status": "mastered", "notes": "Initial notes for KP3"},
                ]}
            if operation == "get_kp":
                kp_id = payload.get("id")
                if kp_id == "kp3":
                     return {"status": "success", "data": {"id": "kp3", "title": "Mock KP 3 (Detail)", "content": "Detailed content for KP3", "tags": ["example"], "status": "mastered", "notes": "Initial notes for KP3"}}
                return {"status": "success", "data": {"id": kp_id, "title": f"Mock KP {kp_id} (Detail)", "content": f"Detail for {kp_id}"}}
            if operation == "update_kp":
                return {"status": "success", "message": "KP updated (mocked)."}
            if operation == "get_kps_for_review":
                return {"status": "success", "data": [
                    {"id": "kp_rev1", "title": "Review Item 1"},
                    {"id": "kp_rev2", "title": "Review Item 2"},
                ]}
            return {"status": "error", "message": "Mock operation not implemented."}

    # learner_ui = LearnerUI(session_id=mock_session_id, mbm_instance=MockMBM())
    learner_ui = LearnerUI(session_id=mock_session_id) # Test with call_api_gateway placeholder
    
    st.sidebar.title("Learner Module")
    learner_ui.display_learner_view()

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Debug Info (Session State):**")
    st.sidebar.json(st.session_state)