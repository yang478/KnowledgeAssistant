# -*- coding: utf-8 -*-
"""
Streamlit UI for the Planner Module.

This module defines the Streamlit interface for interacting with the
planner functionalities, such as creating and managing learning plans,
setting goals, and scheduling study sessions.
"""
import streamlit as st
from typing import Callable, Dict, Any, Optional

# Attempt to import the API call utility, make it optional for now
try:
    from .ui_utils import call_api_gateway
except ImportError:
    # Define a placeholder if ui_utils or call_api_gateway is not yet available
    def call_api_gateway(operation: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        st.error("API Gateway call function is not available. Please ensure ui_utils.py is correctly set up.")
        return {"status": "error", "message": "API Gateway not available."}

class PlannerUI:
    """
    Manages the Streamlit UI components for the Planner module.
    """
    def __init__(self, session_id: Optional[str] = None, mbm_instance: Optional[Any] = None):
        """
        Initializes the PlannerUI.

        Args:
            session_id (Optional[str]): The current user's session ID.
            mbm_instance (Optional[Any]): An instance of MemoryBankManager, if available directly.
                                         Otherwise, API calls will be used.
        """
        self.session_id = session_id
        self.mbm_instance = mbm_instance # For potential direct calls if app structure allows

        if 'current_plan' not in st.session_state:
            st.session_state.current_plan = None
        if 'planner_goals' not in st.session_state:
            st.session_state.planner_goals = []
        if 'planner_tasks' not in st.session_state:
            st.session_state.planner_tasks = []

    def _handle_api_call(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper for making API calls, either directly or via gateway.
        """
        if self.mbm_instance:
            # Direct call if mbm_instance is provided (e.g. within the same process)
            # This assumes mbm_instance has a process_request method
            try:
                return self.mbm_instance.process_request(operation, payload)
            except Exception as e:
                st.error(f"Direct MBM call error for {operation}: {e}")
                return {"status": "error", "message": str(e)}
        else:
            # Fallback to API gateway call
            return call_api_gateway(operation, payload, session_id=self.session_id)

    def display_planner(self):
        """
        Renders the main planner UI section.
        """
        st.header("🎯 Learning Planner")
        st.write("Organize your learning journey, set goals, and track your progress.")

        # Tabs for different planner functionalities
        tab1, tab2, tab3, tab4 = st.tabs(["My Plan", "Set Goals", "Manage Tasks", "Knowledge Map View"])

        with tab1:
            self.display_current_plan()
        with tab2:
            self.display_goal_setting()
        with tab3:
            self.display_task_management()
        with tab4:
            self.display_knowledge_map_integration() # Placeholder

    def display_current_plan(self):
        """
        Displays the user's current learning plan.
        """
        st.subheader("My Current Learning Plan")
        if st.session_state.current_plan:
            st.write(f"**Plan Name:** {st.session_state.current_plan.get('name', 'N/A')}")
            st.write(f"**Description:** {st.session_state.current_plan.get('description', 'N/A')}")
            # Further details like KPs, schedule, etc.
        else:
            st.info("No active learning plan. Create one in 'Set Goals' or 'Manage Tasks'.")
        
        if st.button("Load Example Plan (Placeholder)"):
            # Placeholder: In a real app, this would call an API to load/create a plan
            st.session_state.current_plan = {
                "name": "Introduction to Python",
                "description": "Learn the basics of Python programming.",
                "goals": ["Understand variables", "Learn control flow"],
                "tasks": [{"name": "Read Chapter 1", "status": "pending"}]
            }
            st.success("Example plan loaded.")
            st.rerun()

    def display_goal_setting(self):
        """
        UI for users to set or modify their learning goals.
        """
        st.subheader("Set Your Learning Goals")
        goal_description = st.text_area("Describe your learning goal (e.g., 'Master Python data structures', 'Understand calculus basics'):")
        
        # Example: Link goals to Knowledge Points
        # In a real app, this would involve searching/selecting KPs
        # For now, a simple text input for related topics
        related_topics_input = st.text_input("Enter related topics or Knowledge Point IDs (comma-separated):")

        if st.button("Add Goal"):
            if goal_description:
                new_goal = {
                    "description": goal_description,
                    "related_topics": [topic.strip() for topic in related_topics_input.split(',')] if related_topics_input else [],
                    "status": "active" # or 'pending'
                }
                # Placeholder: API call to save the goal
                # response = self._handle_api_call("planner_add_goal", {"goal_data": new_goal})
                # if response.get("status") == "success":
                #    st.session_state.planner_goals.append(new_goal) # Or fetch updated list
                #    st.success("Goal added successfully!")
                #    st.rerun()
                # else:
                #    st.error(f"Failed to add goal: {response.get('message', 'Unknown error')}")
                st.session_state.planner_goals.append(new_goal) # Simulate success
                st.success(f"Goal '{goal_description}' added (simulated).")
                st.rerun()

            else:
                st.warning("Please describe your goal.")

        if st.session_state.planner_goals:
            st.write("---")
            st.write("**Current Goals:**")
            for i, goal in enumerate(st.session_state.planner_goals):
                st.markdown(f"- **{goal['description']}** (Topics: {', '.join(goal['related_topics']) if goal['related_topics'] else 'N/A'})")
                if st.button(f"Mark as Complete (Goal {i+1})", key=f"complete_goal_{i}"):
                    # Placeholder for API call
                    st.session_state.planner_goals[i]['status'] = 'completed'
                    st.success(f"Goal '{goal['description']}' marked as complete (simulated).")
                    st.rerun()


    def display_task_management(self):
        """
        UI for managing specific tasks related to learning goals.
        """
        st.subheader("Manage Learning Tasks")
        task_name = st.text_input("New task name (e.g., 'Read Chapter 1 of X', 'Complete Y exercise'):")
        
        # Link task to a goal (optional)
        # goal_options = ["None"] + [g['description'] for g in st.session_state.planner_goals if g.get('status') != 'completed']
        # selected_goal_desc = st.selectbox("Link to existing goal (optional):", goal_options)

        if st.button("Add Task"):
            if task_name:
                new_task = {
                    "name": task_name,
                    "status": "pending",
                    # "linked_goal_description": selected_goal_desc if selected_goal_desc != "None" else None
                }
                # Placeholder: API call to save the task
                # response = self._handle_api_call("planner_add_task", {"task_data": new_task})
                # if response.get("status") == "success":
                #    st.session_state.planner_tasks.append(new_task) # Or fetch updated list
                #    st.success("Task added successfully!")
                #    st.rerun()
                # else:
                #    st.error(f"Failed to add task: {response.get('message', 'Unknown error')}")
                st.session_state.planner_tasks.append(new_task)
                st.success(f"Task '{task_name}' added (simulated).")
                st.rerun()
            else:
                st.warning("Please enter a task name.")

        if st.session_state.planner_tasks:
            st.write("---")
            st.write("**Current Tasks:**")
            for i, task in enumerate(st.session_state.planner_tasks):
                task_status = task.get('status', 'pending')
                col1, col2 = st.columns([3,1])
                with col1:
                    st.markdown(f"- {task['name']} (Status: {task_status})")
                with col2:
                    if task_status == 'pending':
                        if st.button(f"Start", key=f"start_task_{i}"):
                            st.session_state.planner_tasks[i]['status'] = 'in_progress'
                            st.rerun()
                    elif task_status == 'in_progress':
                        if st.button(f"Complete", key=f"complete_task_{i}"):
                            st.session_state.planner_tasks[i]['status'] = 'completed'
                            st.rerun()
    
    def display_knowledge_map_integration(self):
        """
        Placeholder for integrating with a knowledge map visualization.
        This could show KPs related to the plan, goals, or tasks.
        """
        st.subheader("Knowledge Map View (Planner)")
        st.info("This section will visualize knowledge points related to your current plan, goals, and tasks. (Future Implementation)")
        # Example: Could use a graph visualization library if KPs and relations are fetched
        # For now, just list related KPs if any are identified in goals/tasks
        
        related_kps_in_plan = set()
        for goal in st.session_state.planner_goals:
            for topic in goal.get('related_topics', []):
                related_kps_in_plan.add(topic)
        
        # Add KPs from tasks if tasks can be linked to KPs directly
        # For example, if a task is "Review KP: kp_id_123"

        if related_kps_in_plan:
            st.write("**Knowledge Points tentatively related to your plan:**")
            for kp_id_or_topic in related_kps_in_plan:
                st.markdown(f"- {kp_id_or_topic}")
        else:
            st.write("No specific knowledge points explicitly linked in current goals yet.")


# To run this UI component independently for testing (optional)
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Planner UI Test")
    
    # Mock session_id for testing
    mock_session_id = "test_session_planner_001"
    
    # Initialize and display the Planner UI
    planner_ui = PlannerUI(session_id=mock_session_id)
    
    st.sidebar.title("Planner Module")
    # You could add navigation or global settings here if needed for standalone test
    
    planner_ui.display_planner()

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Debug Info (Session State):**")
    st.sidebar.json(st.session_state)