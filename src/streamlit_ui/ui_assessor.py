# -*- coding: utf-8 -*-
"""
Streamlit UI for the Assessor Module.

This module defines the Streamlit interface for assessment-related activities,
such as generating quizzes, taking tests, and reviewing assessment results.
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

class AssessorUI:
    """
    Manages the Streamlit UI components for the Assessor module.
    """
    def __init__(self, session_id: Optional[str] = None, mbm_instance: Optional[Any] = None):
        """
        Initializes the AssessorUI.

        Args:
            session_id (Optional[str]): The current user's session ID.
            mbm_instance (Optional[Any]): An instance of MemoryBankManager for direct calls.
        """
        self.session_id = session_id
        self.mbm_instance = mbm_instance

        if 'assessor_current_assessment' not in st.session_state:
            st.session_state.assessor_current_assessment = None # Stores the generated assessment (questions, etc.)
        if 'assessor_assessment_type' not in st.session_state:
            st.session_state.assessor_assessment_type = "quiz" # Default type
        if 'assessor_selected_kps' not in st.session_state:
            st.session_state.assessor_selected_kps = [] # List of KP IDs for assessment
        if 'assessor_num_questions' not in st.session_state:
            st.session_state.assessor_num_questions = 5
        if 'assessor_difficulty' not in st.session_state:
            st.session_state.assessor_difficulty = "medium"
        if 'assessor_user_answers' not in st.session_state:
            st.session_state.assessor_user_answers = {} # {question_id: answer}
        if 'assessor_results' not in st.session_state:
            st.session_state.assessor_results = None # Stores feedback/score after submission

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

    def display_assessor_view(self):
        """
        Renders the main assessor UI section.
        """
        st.header("📝 Assessment Center")
        st.write("Test your knowledge, generate quizzes, and track your understanding.")

        tab1, tab2, tab3 = st.tabs(["Generate Assessment", "Take Assessment", "View Results"])

        with tab1:
            self.display_assessment_generation_form()
        with tab2:
            self.display_take_assessment()
        with tab3:
            self.display_assessment_results()
            
    def display_assessment_generation_form(self):
        """
        UI for users to configure and generate new assessments.
        """
        st.subheader("⚙️ Generate New Assessment")

        # Select KPs for assessment
        # In a real app, this would be a more sophisticated KP selector
        # For now, allow manual input of KP IDs or use a search similar to LearnerUI
        
        # Option 1: Use all KPs (simplified)
        # Option 2: Select KPs (more complex UI needed, for now text input)
        kp_ids_input = st.text_area(
            "Enter Knowledge Point IDs for assessment (comma-separated, or leave blank for broader assessment):",
            value=", ".join(st.session_state.assessor_selected_kps),
            key="assessor_kp_ids_for_generation"
        )
        if kp_ids_input:
            st.session_state.assessor_selected_kps = [kp_id.strip() for kp_id in kp_ids_input.split(',') if kp_id.strip()]
        else:
            st.session_state.assessor_selected_kps = []


        st.session_state.assessor_assessment_type = st.selectbox(
            "Assessment Type:",
            options=["quiz", "test", "flashcards"], # Add more types as supported
            index=["quiz", "test", "flashcards"].index(st.session_state.assessor_assessment_type),
            key="assessor_assessment_type_select"
        )
        
        st.session_state.assessor_num_questions = st.number_input(
            "Number of Questions:", 
            min_value=1, max_value=50, 
            value=st.session_state.assessor_num_questions, 
            step=1,
            key="assessor_num_questions_input"
        )

        st.session_state.assessor_difficulty = st.select_slider(
            "Difficulty Level:",
            options=["easy", "medium", "hard"],
            value=st.session_state.assessor_difficulty,
            key="assessor_difficulty_slider"
        )

        if st.button("Generate Assessment", key="assessor_generate_button"):
            if not st.session_state.assessor_selected_kps and st.session_state.assessor_assessment_type != "flashcards": # Flashcards might not need specific KPs
                st.warning("Please select at least one Knowledge Point ID for quiz/test generation, or provide topics.")
                # Potentially allow topic-based generation too
            else:
                generation_payload = {
                    "assessment_type": st.session_state.assessor_assessment_type,
                    "knowledge_point_ids": st.session_state.assessor_selected_kps,
                    "num_questions": st.session_state.assessor_num_questions,
                    "difficulty": st.session_state.assessor_difficulty,
                    # "topics": [] # Could add topic-based generation
                }
                # API call to generate assessment
                response = self._handle_api_call("save_ga", generation_payload) # Assuming save_ga also generates
                
                if response.get("status") == "success" and response.get("data"):
                    st.session_state.assessor_current_assessment = response.get("data")
                    st.session_state.assessor_user_answers = {} # Reset answers for new assessment
                    st.session_state.assessor_results = None # Reset previous results
                    st.success("Assessment generated successfully! Go to 'Take Assessment' tab.")
                    st.balloons()
                else:
                    st.error(f"Failed to generate assessment: {response.get('message', 'Unknown error')}")
                    st.session_state.assessor_current_assessment = None
        
        st.info("Note: The actual assessment generation logic (calling LLMs, etc.) happens in the backend via the API.")


    def display_take_assessment(self):
        """
        UI for the user to take the currently generated assessment.
        """
        st.subheader("✍️ Take Assessment")
        if not st.session_state.assessor_current_assessment:
            st.info("No assessment generated or loaded. Please generate one from the 'Generate Assessment' tab.")
            return

        assessment_data = st.session_state.assessor_current_assessment
        questions = assessment_data.get("questions", []) # Assuming questions is a list of dicts

        if not questions:
            st.warning("The generated assessment has no questions.")
            return
        
        st.markdown(f"**Assessment Type:** {assessment_data.get('assessment_type', 'N/A').capitalize()}")
        st.markdown(f"**Difficulty:** {assessment_data.get('difficulty', 'N/A').capitalize()}")
        
        # Use a form for submitting all answers at once
        with st.form(key="assessment_form"):
            for i, q_item in enumerate(questions):
                question_id = q_item.get("id", f"q_{i}")
                question_text = q_item.get("text", "N/A")
                options = q_item.get("options", []) # For multiple choice
                q_type = q_item.get("type", "unknown") # e.g., 'multiple_choice', 'short_answer', 'true_false'

                st.markdown(f"--- \n **Question {i+1}:** {question_text}")

                if q_type == "multiple_choice" and options:
                    # Ensure options are strings for display
                    display_options = [str(opt) for opt in options]
                    st.session_state.assessor_user_answers[question_id] = st.radio(
                        "Your answer:", 
                        options=display_options, 
                        key=f"answer_{question_id}",
                        index=None # No default selection
                    )
                elif q_type == "true_false":
                     st.session_state.assessor_user_answers[question_id] = st.radio(
                        "Your answer:", 
                        options=["True", "False"], 
                        key=f"answer_{question_id}",
                        index=None
                    )
                elif q_type == "short_answer":
                    st.session_state.assessor_user_answers[question_id] = st.text_input(
                        "Your answer:", 
                        key=f"answer_{question_id}"
                    )
                else: # Fallback for unknown or unsupported types
                    st.text_input(f"Your answer (type: {q_type}):", key=f"answer_{question_id}")
            
            submitted = st.form_submit_button("Submit Answers")

        if submitted:
            # All answers are in st.session_state.assessor_user_answers
            submission_payload = {
                "assessment_id": assessment_data.get("assessment_id"),
                "answers": st.session_state.assessor_user_answers,
                # "user_id": self.session_id # Or however user is identified
            }
            # API call to submit answers and get results
            # This would typically be 'save_al' (save assessment log) which might also return graded results
            response = self._handle_api_call("save_al", submission_payload)
            
            if response.get("status") == "success":
                st.session_state.assessor_results = response.get("data") # Expecting score, feedback, etc.
                st.success("Assessment submitted successfully! Check 'View Results' tab.")
                st.balloons()
            else:
                st.error(f"Failed to submit assessment: {response.get('message', 'Unknown error')}")
                st.session_state.assessor_results = None


    def display_assessment_results(self):
        """
        Displays the results of the last submitted assessment.
        """
        st.subheader("📊 Assessment Results")
        if st.session_state.assessor_results:
            results = st.session_state.assessor_results
            st.metric(label="Your Score", value=f"{results.get('score', 0.0):.2f}%")
            
            st.markdown(f"**Overall Feedback:** {results.get('overall_feedback', 'N/A')}")

            if results.get('detailed_feedback'):
                st.write("**Detailed Breakdown:**")
                for item_feedback in results.get('detailed_feedback', []):
                    q_text = item_feedback.get('question_text', 'Question')
                    user_ans = item_feedback.get('user_answer', 'N/A')
                    correct_ans = item_feedback.get('correct_answer', 'N/A')
                    is_correct = item_feedback.get('is_correct', False)
                    feedback_text = item_feedback.get('feedback', '')

                    status_emoji = "✅" if is_correct else "❌"
                    st.markdown(f"--- \n {status_emoji} **{q_text}**")
                    st.markdown(f"   - Your Answer: {user_ans}")
                    if not is_correct and correct_ans != 'N/A':
                        st.markdown(f"   - Correct Answer: {correct_ans}")
                    if feedback_text:
                        st.markdown(f"   - *Feedback: {feedback_text}*")
        else:
            st.info("No assessment results to display. Please take an assessment first.")

# To run this UI component independently for testing (optional)
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Assessor UI Test")
    
    mock_session_id = "test_session_assessor_001"

    class MockMBMAssessor: # Simplified mock for assessor flow
        def process_request(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            st.sidebar.info(f"Mock Assessor MBM called: {operation} with {payload}")
            if operation == "save_ga": # Simulate generation
                return {"status": "success", "data": {
                    "assessment_id": "gen_assess_123",
                    "assessment_type": payload.get("assessment_type"),
                    "difficulty": payload.get("difficulty"),
                    "questions": [
                        {"id": "q1", "text": "What is 2+2?", "type": "multiple_choice", "options": ["3", "4", "5"]},
                        {"id": "q2", "text": "Is Python fun?", "type": "true_false"},
                        {"id": "q3", "text": "Explain Streamlit.", "type": "short_answer"},
                    ]
                }}
            if operation == "save_al": # Simulate submission and grading
                answers = payload.get("answers", {})
                score = 0
                if answers.get("q1") == "4": score += 33.33
                if answers.get("q2") == "True": score += 33.33
                # Short answer needs manual or AI grading, mock simple correct
                if "streamlit" in answers.get("q3","").lower(): score += 33.34
                
                return {"status": "success", "data": {
                    "score": score,
                    "overall_feedback": "Good effort! (Mocked)",
                    "detailed_feedback": [
                        {"question_text": "What is 2+2?", "user_answer": answers.get("q1"), "correct_answer": "4", "is_correct": answers.get("q1") == "4"},
                        {"question_text": "Is Python fun?", "user_answer": answers.get("q2"), "correct_answer": "True", "is_correct": answers.get("q2") == "True"},
                        {"question_text": "Explain Streamlit.", "user_answer": answers.get("q3"), "is_correct": "streamlit" in answers.get("q3","").lower(), "feedback": "Mock feedback for short answer."}
                    ]
                }}
            return {"status": "error", "message": "Mock operation not implemented."}

    # assessor_ui = AssessorUI(session_id=mock_session_id, mbm_instance=MockMBMAssessor())
    assessor_ui = AssessorUI(session_id=mock_session_id) # Test with placeholder API

    st.sidebar.title("Assessor Module")
    assessor_ui.display_assessor_view()

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Debug Info (Session State):**")
    st.sidebar.json(st.session_state)