# This is a test comment for codeIF update
# -*- coding: utf-8 -*-
import streamlit as st
import sys
import os
import json # Keep for potential direct use, though ui_utils handles most JSON now.

# Add the src directory to the Python path for backend module imports if necessary,
# though direct backend imports should be minimized in favor of API calls via UI modules.
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import UI Modules
# Since sys.path.append(os.path.join(os.path.dirname(__file__), 'src')) is used,
# modules within 'src' are treated as top-level.
from streamlit_ui.ui_planner import PlannerUI
from streamlit_ui.ui_learner import LearnerUI
from streamlit_ui.ui_assessor import AssessorUI
from streamlit_ui.ui_memory_bank_viewer import MemoryBankViewerUI
from streamlit_ui.ui_visualizations import VisualizationsUI
# The main call_api_gateway is now in ui_utils, imported by each UI module.
# If streamlit_app.py itself needs to make API calls (e.g. for initial health check),
# it could import it from ui_utils. For now, we assume UI modules handle their calls.
# from streamlit_ui.ui_utils import call_api_gateway, get_app_setting

# Import ConfigManager for any app-level configurations if needed
from config_manager.config_manager import ConfigManager

# --- Streamlit Page Configuration (MUST be the first Streamlit command) ---
st.set_page_config(layout="wide", page_title="AI Learning Assistant")

# --- Configuration ---
# ConfigManager can be used for UI-specific settings or API URLs if not hardcoded/in secrets
# config_manager = ConfigManager() # Initialize if needed for app-level settings
# DEFAULT_SESSION_ID = get_app_setting("DEFAULT_SESSION_ID", "streamlit_default_session")
# For simplicity, UI modules will manage their own session state or use a passed session_id.

# --- Session State Initialization for UI classes ---
# Each UI class will manage its own relevant session state internally.
# We might need a global session ID if not handled by authentication.
if 'app_session_id' not in st.session_state:
    # A more robust session ID generation/management would be needed for a real multi-user app
    # For now, a simple default or allowing UI modules to request it.
    st.session_state.app_session_id = "default_streamlit_session"


# --- Main Application Logic ---
def main():
    """
    Main function to run the Streamlit application.
    Handles module selection and delegates rendering to the appropriate UI class.
    """
    st.sidebar.title("🧠 AI Learning Assistant")
    st.sidebar.caption("Modular Streamlit Interface")

    # Initialize MBM instance (placeholder - in a real app, this might be more complex)
    # For now, UI modules will primarily use API calls via ui_utils.
    # If direct MBM access is feasible and desired for some UI modules (e.g. if running in same process without gateway),
    # this is where it could be instantiated and passed.
    mbm_instance_placeholder = None # Or initialize a real one if applicable and configured

    # Module Selection
    selected_module_key = "main_selected_module"
    if selected_module_key not in st.session_state:
        st.session_state[selected_module_key] = "Planner" # Default module

    selected_module = st.sidebar.radio(
        "Select Module:",
        ("Planner", "Learner", "Assessor", "Memory Bank Viewer", "Visualizations"),
        key=selected_module_key,
        index=["Planner", "Learner", "Assessor", "Memory Bank Viewer", "Visualizations"].index(st.session_state[selected_module_key])
    )
    st.session_state[selected_module_key] = selected_module # Persist selection

    # Instantiate the selected UI module and display its view
    # Pass the session_id and potentially the mbm_instance if direct calls are supported/needed.
    current_session_id = st.session_state.app_session_id

    if selected_module == "Planner":
        planner_ui = PlannerUI(session_id=current_session_id, mbm_instance=mbm_instance_placeholder)
        planner_ui.display_planner()
    elif selected_module == "Learner":
        learner_ui = LearnerUI(session_id=current_session_id, mbm_instance=mbm_instance_placeholder)
        learner_ui.display_learner_view()
    elif selected_module == "Assessor":
        assessor_ui = AssessorUI(session_id=current_session_id, mbm_instance=mbm_instance_placeholder)
        assessor_ui.display_assessor_view()
    elif selected_module == "Memory Bank Viewer":
        viewer_ui = MemoryBankViewerUI(session_id=current_session_id, mbm_instance=mbm_instance_placeholder)
        viewer_ui.display_viewer_view()
    elif selected_module == "Visualizations":
        viz_ui = VisualizationsUI(session_id=current_session_id, mbm_instance=mbm_instance_placeholder)
        viz_ui.display_visualizations_view()
    else:
        st.error("Invalid module selected.")

    # --- Footer ---
    st.sidebar.markdown("---")
    st.sidebar.info("© 2024-2025 AI Learning Assistant Project")
    # Display current session ID for debugging if needed
    # st.sidebar.caption(f"Session ID: {current_session_id}")

if __name__ == "__main__":
    main()

# --- Old Code (to be removed or heavily refactored) ---
# The old code from line 69 onwards (Application Initialization, direct module interactions, etc.)
# has been replaced by the new structure using UI module classes.
# The `call_api_gateway` function previously in this file is now expected to be
# in `src.streamlit_ui.ui_utils` and used internally by the UI modules.
# All specific UI logic for Planner, Learner, Assessor, Viewer, Visualizations
# is now encapsulated within their respective UI classes.
