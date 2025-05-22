"""Unit tests for the LearnerModule class."""

import unittest
from unittest.mock import patch, MagicMock, ANY

# Ensure the necessary modules can be imported
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from learner_module.learner_module import LearnerModule
from memory_bank_manager.memory_bank_manager import MemoryBankManager # For spec
from llm_interface.llm_interface import LLMInterface # For spec
from config_manager.config_manager import ConfigManager # For spec
from monitoring_manager.monitoring_manager import MonitoringManager # For spec
from update_manager.update_manager import UpdateManager # For spec

class TestLearnerModule(unittest.TestCase):
    """Tests for the LearnerModule."""

    def setUp(self):
        """Set up a LearnerModule instance with mocked dependencies."""
        self.mock_memory_bank_manager = MagicMock(spec=MemoryBankManager)
        self.mock_llm_interface = MagicMock(spec=LLMInterface)
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_monitoring_manager = MagicMock(spec=MonitoringManager)
        self.mock_update_manager = MagicMock(spec=UpdateManager)

        # Simulate config for learner (simplified)
        # Adjusted to match the keys used in LearnerModule._build_llm_prompt
        self.mock_config_manager.get_config.side_effect = lambda key, default=None: {
            "learner.prompt_templates.ask_question": "Context: {learning_context}\nUser question: {user_input}",
            "learner.prompt_templates.explain_topic": "Explain topic: {topic_title}\nContent: {topic_content}\nContext: {learning_context}",
            "learner.prompt_templates.provide_example": "Provide example for topic: {topic_title}\nContent: {topic_content}\nContext: {learning_context}",
            "learner.prompt_templates.next_step": "Given context: {learning_context}\nSuggest next step. User input: {user_input}",
            "learner.prompt_templates.default": "Processing: {user_input}\nContext: {learning_context}", # Default for unknown
            "learner.prompt_templates.follow_up_instruction": "\n\nSuggest 2-3 follow-up questions as a JSON list: 'Follow-up questions: []'",
            "learner.sanitize.max_input_length": 500,
            "learner.context.history_limit": 10,
            "learner.llm_config.default": {"temperature": 0.5}, # Default LLM config
            "learner.llm_config.ask_question": {"temperature": 0.6, "max_tokens": 300},
            "learner.llm_config.explain_topic": {"temperature": 0.7, "max_tokens": 500},
            "learner.llm_config.provide_example": {"temperature": 0.6, "max_tokens": 600},
            # Add other configs if needed by new tests
        }.get(key, default if default is not None else {}) # Ensure default returns dict for llm_config

        self.learner_module = LearnerModule(
            memory_bank_manager=self.mock_memory_bank_manager,
            llm_interface=self.mock_llm_interface,
            config_manager=self.mock_config_manager,
            monitoring_manager=self.mock_monitoring_manager,
            update_manager=self.mock_update_manager,
        )

    def test_initialization(self):
        """Test that LearnerModule initializes correctly."""
        self.assertIsNotNone(self.learner_module.memory_bank_manager) # Was mbm
        self.assertIsNotNone(self.learner_module.llm_interface) # Was llm
        self.assertIsNotNone(self.learner_module.config_manager) # Was cm
        self.assertIsNotNone(self.learner_module.monitoring_manager) # Was monitor
        self.assertIsNotNone(self.learner_module.update_manager) # Was um
        self.mock_monitoring_manager.log_info.assert_any_call("LearnerModule initialized.")

    def test_handle_request_ask_question_success(self):
        """Test successful handling of an 'ask_question' request."""
        # Arrange
        session_id = "sess_ask_q"
        user_question_text = "What is Python GIL?"
        request_payload = {"text": user_question_text}
        
        mock_context = {"current_topic_id": "kp_gil_context", "history": [], "session_id": session_id, "interaction_history": []}
        mock_kp_data = {"id": "kp_gil_context", "title": "GIL Context KP", "content": "GIL is complex."} # For prompt building if logic uses it
        
        def mock_process_request_ask(request):
            op = request.get("operation")
            payload = request.get("payload", {})
            if op == "get_learning_context" and payload.get("session_id") == session_id:
                return {"status": "success", "data": mock_context}
            elif op == "get_knowledge_point": # If _build_llm_prompt tries to fetch a KP
                 return {"status": "success", "data": mock_kp_data}
            elif op == "save_learning_context" and payload.get("session_id") == session_id:
                 self.assertIn("interaction_history", payload)
                 self.assertTrue(len(payload["interaction_history"]) == 1) # First interaction
                 self.assertEqual(payload["interaction_history"][0]["user_input"], user_question_text)
                 return {"status": "success"}
            self.fail(f"Unhandled MBM operation in mock_process_request_ask: {op} with payload {payload}")
        self.mock_memory_bank_manager.process_request.side_effect = mock_process_request_ask
        
        llm_response_text = "The GIL is a global interpreter lock...\nFollow-up questions: [\"Q1?\", \"Q2?\"]"
        self.mock_llm_interface.generate_text.return_value = {
            "status": "success",
            "data": {"text": llm_response_text, "usage": {"total_tokens": 100}}
        }
        
        # Act
        response = self.learner_module.handle_request(
            session_id=session_id,
            request_type="ask_question",
            payload=request_payload
        )

        # Assert
        self.mock_monitoring_manager.log_info.assert_any_call(
            f"Handling request type: ask_question", {"session_id": session_id}
        )
        self.mock_memory_bank_manager.process_request.assert_any_call(
            {"operation": "get_learning_context", "payload": {"session_id": session_id}}
        )
        
        self.mock_llm_interface.generate_text.assert_called_once_with({
            "prompt": ANY,
            "model_config": {"temperature": 0.6, "max_tokens": 300}
        })
        
        self.mock_memory_bank_manager.process_request.assert_any_call(
             {"operation": "save_learning_context", "payload": ANY}
        )
        self.mock_update_manager.trigger_backup.assert_not_called() # Not called for ask_question

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["response"]["type"], "explanation") # ask_question maps to explanation
        self.assertEqual(response["response"]["content"], "The GIL is a global interpreter lock...")
        self.assertEqual(response["response"]["follow_up_questions"], ["Q1?", "Q2?"])
        self.assertTrue(response["context_updated"])

    def test_handle_request_explain_topic_success(self):
        """Test successful handling of an 'explain_topic' request."""
        # Arrange
        session_id = "sess_explain_t"
        topic_id_to_explain = "kp_decorators"
        request_payload = {"topic_id": topic_id_to_explain}
        
        mock_context = {"current_topic_id": None, "history": [], "session_id": session_id, "interaction_history": []}
        mock_kp_data = {"id": topic_id_to_explain, "title": "Decorators", "content": "Decorators are functions..."}

        def mock_process_request_explain(request):
            op = request.get("operation")
            payload = request.get("payload", {})
            if op == "get_learning_context" and payload.get("session_id") == session_id:
                return {"status": "success", "data": mock_context}
            elif op == "get_knowledge_point" and payload.get("knowledge_point_id") == topic_id_to_explain:
                 return {"status": "success", "data": mock_kp_data}
            elif op == "save_learning_context" and payload.get("session_id") == session_id:
                 self.assertIn(topic_id_to_explain, payload.get("current_topics", []))
                 self.assertEqual(payload["interaction_history"][0]["topic_id"], topic_id_to_explain)
                 return {"status": "success"}
            self.fail(f"Unhandled MBM operation in mock_process_request_explain: {op} with payload {payload}")
        self.mock_memory_bank_manager.process_request.side_effect = mock_process_request_explain
        
        llm_explanation = "In Python, a decorator is a design pattern...\nFollow-up questions: []"
        self.mock_llm_interface.generate_text.return_value = {
            "status": "success",
            "data": {"text": llm_explanation, "usage": {"total_tokens": 120}}
        }

        # Act
        response = self.learner_module.handle_request(
            session_id=session_id,
            request_type="explain_topic",
            payload=request_payload
        )

        # Assert
        self.mock_monitoring_manager.log_info.assert_any_call(
            f"Handling request type: explain_topic", {"session_id": session_id}
        )
        
        self.mock_llm_interface.generate_text.assert_called_once_with({
            "prompt": ANY,
            "model_config": {"temperature": 0.7, "max_tokens": 500}
        })
        
        self.mock_memory_bank_manager.process_request.assert_any_call(
             {"operation": "save_learning_context", "payload": ANY}
        )
        # Check that the payload for trigger_backup is as expected
        self.mock_update_manager.trigger_backup.assert_called_once_with(
            event="learner_topic_interaction_completed",
            payload={
                "session_id": session_id,
                "topic_id": topic_id_to_explain,
                "reason": f"Learner completed interaction with topic: {topic_id_to_explain}"
            }
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["response"]["type"], "explanation")
        self.assertEqual(response["response"]["content"], "In Python, a decorator is a design pattern...")
        self.assertEqual(response["response"]["follow_up_questions"], [])
        self.assertTrue(response["context_updated"])


    def test_handle_request_llm_error(self):
        """Test error handling when LLMInterface fails during a request."""
        # Arrange
        session_id = "sess_llm_err"
        request_payload = {"text": "What is quantum physics?"}
        request_type = "ask_question"
        
        mock_context = {"history": [], "session_id": session_id, "interaction_history": []}
        def mock_process_request_llm_err(request):
            op = request.get("operation")
            payload = request.get("payload", {})
            if op == "get_learning_context" and payload.get("session_id") == session_id:
                return {"status": "success", "data": mock_context}
            # save_learning_context should not be called
            self.assertNotEqual(op, "save_learning_context")
            # Fallback for any other unexpected calls to prevent tests from hanging or passing silently
            return {"status": "error", "message": f"Unexpected MBM op in LLM error test: {op}"}
        self.mock_memory_bank_manager.process_request.side_effect = mock_process_request_llm_err
        
        self.mock_llm_interface.generate_text.return_value = {
            "status": "error", "message": "LLM API rate limit exceeded", "data": None
        }

        # Act
        response = self.learner_module.handle_request(session_id, request_type, request_payload)

        # Assert
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["response"]["content"], "LLM request failed: LLM API rate limit exceeded")
        self.assertFalse(response["context_updated"]) # Context should not be updated on LLM error
        self.mock_monitoring_manager.log_error.assert_any_call(
            "LLM request failed: LLM API rate limit exceeded", {"session_id": session_id}
        )
        
        # Explicitly check that save_learning_context was not part of the calls
        called_operations = [call[0][0].get("operation") for call in self.mock_memory_bank_manager.process_request.call_args_list]
        self.assertNotIn("save_learning_context", called_operations)
        self.mock_update_manager.trigger_backup.assert_not_called()


    def test_handle_request_mbm_error_get_context(self):
        """Test error handling when MBM fails to get context (returns error status)."""
        # Arrange
        session_id = "sess_mbm_ctx_err"
        request_payload = {"text": "Hello"}
        request_type = "ask_question"

        # This mock will only be called once for get_learning_context
        self.mock_memory_bank_manager.process_request.return_value = {"status": "error", "message": "MBM DB down", "data": None}
        
        # Act
        response = self.learner_module.handle_request(session_id, request_type, request_payload)

        # Assert
        self.mock_memory_bank_manager.process_request.assert_called_once_with(
            {"operation": "get_learning_context", "payload": {"session_id": session_id}}
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["response"]["content"], "Failed to get learning context: MBM DB down")
        self.assertFalse(response["context_updated"])
        self.mock_monitoring_manager.log_error.assert_any_call(
            "Failed to get learning context: MBM DB down", {"session_id": session_id}
        )
        self.mock_llm_interface.generate_text.assert_not_called()

    def test_handle_request_invalid_input_no_session_id(self):
        """Test handle_request with missing session_id."""
        response = self.learner_module.handle_request(session_id=None, request_type="ask_question", payload={"text": "Hi"})
        self.assertEqual(response["status"], "error")
        self.assertIn("missing session_id", response["response"]["content"])
        self.assertFalse(response["context_updated"])

    def test_handle_request_invalid_input_no_request_type(self):
        """Test handle_request with missing request_type."""
        response = self.learner_module.handle_request(session_id="sid123", request_type=None, payload={"text": "Hi"})
        self.assertEqual(response["status"], "error")
        # Adjust assertion to match the exact error message from the code
        self.assertEqual(response["response"]["content"], "Invalid request: missing session_id or request_type.")
        self.assertFalse(response["context_updated"])

    def test_handle_request_ask_question_llm_empty_response(self):
        """Test 'ask_question' when LLM returns an empty string."""
        session_id = "sess_ask_empty_llm"
        request_payload = {"text": "Tell me something."}
        mock_context = {"history": [], "session_id": session_id, "interaction_history": []}

        self.mock_memory_bank_manager.process_request.side_effect = lambda req: {
            "get_learning_context": {"status": "success", "data": mock_context},
            "save_learning_context": {"status": "success"} # Context will be updated with empty interaction
        }.get(req.get("operation"))

        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": ""}}

        response = self.learner_module.handle_request(session_id, "ask_question", request_payload)
        self.assertEqual(response["status"], "success") # Code treats empty LLM as success but with specific content
        self.assertEqual(response["response"]["type"], "info")
        self.assertIn("received an empty response", response["response"]["content"])
        self.assertFalse(response["context_updated"]) # Because LLM output was empty, no meaningful interaction to log fully

    def test_handle_request_explain_topic_kp_fetch_fails(self):
        """Test 'explain_topic' when MBM fails to fetch knowledge point."""
        session_id = "sess_explain_kp_fail"
        topic_id = "kp_non_existent"
        request_payload = {"topic_id": topic_id}
        mock_context = {"history": [], "session_id": session_id, "interaction_history": []}

        def mock_mbm_kp_fail(request):
            op = request.get("operation")
            if op == "get_learning_context":
                return {"status": "success", "data": mock_context}
            if op == "get_knowledge_point" and request.get("payload", {}).get("knowledge_point_id") == topic_id:
                return {"status": "error", "message": "KP not found"}
            self.fail(f"Unexpected MBM call in kp_fetch_fails: {op}")
        self.mock_memory_bank_manager.process_request.side_effect = mock_mbm_kp_fail

        response = self.learner_module.handle_request(session_id, "explain_topic", request_payload)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["response"]["content"], "Failed to build LLM prompt.")
        self.assertFalse(response["context_updated"])
        self.mock_llm_interface.generate_text.assert_not_called()
        self.mock_monitoring_manager.log_error.assert_any_call(
            f"Failed to retrieve content for topic {topic_id} for explain_topic: KP not found", {"topic_id": topic_id}
        )

    def test_handle_request_explain_topic_missing_topic_id_in_payload(self):
        """Test 'explain_topic' when topic_id is missing in payload."""
        session_id = "sess_explain_no_tid"
        request_payload = {} # Missing topic_id
        mock_context = {"history": [], "session_id": session_id, "interaction_history": []}
        self.mock_memory_bank_manager.process_request.return_value = {"status": "success", "data": mock_context} # For get_learning_context

        response = self.learner_module.handle_request(session_id, "explain_topic", request_payload)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["response"]["content"], "Failed to build LLM prompt.")
        self.assertFalse(response["context_updated"])
        self.mock_llm_interface.generate_text.assert_not_called()
        self.mock_monitoring_manager.log_error.assert_any_call(
            "Missing topic_id in explain_topic request payload.", {"payload": request_payload}
        )

    def test_handle_request_unknown_request_type(self):
        """Test handling of an unknown request_type."""
        session_id = "sess_unknown_req"
        request_payload = {"data": "some_data"}
        request_type = "unknown_request_type_action"
        mock_context = {"history": [], "session_id": session_id, "interaction_history": []}

        self.mock_memory_bank_manager.process_request.side_effect = lambda req: {
            "get_learning_context": {"status": "success", "data": mock_context},
            "save_learning_context": {"status": "success"}
        }.get(req.get("operation"))

        self.mock_llm_interface.generate_text.return_value = {"status": "success", "data": {"text": "Processed unknown."}}

        response = self.learner_module.handle_request(session_id, request_type, request_payload)
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["response"]["type"], "info") # Default from _determine_response_type
        self.assertEqual(response["response"]["content"], "Processed unknown.")
        self.assertTrue(response["context_updated"])
        self.mock_monitoring_manager.log_warning.assert_any_call(
            f"Building prompt for unknown request type: {request_type}", ANY
        )

    def test_parse_llm_output_various_formats(self):
        """Test _parse_llm_output with different formats of follow-up questions."""
        # Case 1: Correct JSON list
        output1 = "Main content here.\nFollow-up questions: [\"Q1\", \"Q2\"]"
        content1, f_ups1 = self.learner_module._parse_llm_output("ask_question", output1)
        self.assertEqual(content1, "Main content here.")
        self.assertEqual(f_ups1, ["Q1", "Q2"])

        # Case 2: No follow-up questions line
        output2 = "Only content."
        content2, f_ups2 = self.learner_module._parse_llm_output("ask_question", output2)
        self.assertEqual(content2, "Only content.")
        self.assertEqual(f_ups2, [])

        # Case 3: Empty list
        output3 = "Content.\nFollow-up questions: []"
        content3, f_ups3 = self.learner_module._parse_llm_output("ask_question", output3)
        self.assertEqual(content3, "Content.")
        self.assertEqual(f_ups3, [])

        # Case 4: Malformed JSON (should log warning and return empty list)
        output4 = "Content.\nFollow-up questions: [\"Unclosed String, Q2]"
        content4, f_ups4 = self.learner_module._parse_llm_output("ask_question", output4)
        self.assertEqual(content4, "Content.")
        self.assertEqual(f_ups4, [])
        # Adjust assertion to match the actual SyntaxError message from literal_eval and the logged context
        expected_error_msg = "Failed to parse follow-up questions using literal_eval: unterminated string literal (detected at line 1) (<unknown>, line 1)"
        self.mock_monitoring_manager.log_warning.assert_any_call(
            expected_error_msg, {"line": "Follow-up questions: [\"Unclosed String, Q2]"}
        )

        # Case 5: Python literal list (using ast.literal_eval)
        output5 = "Content again.\nFollow-up questions: ['AstQ1', 'AstQ2']"
        content5, f_ups5 = self.learner_module._parse_llm_output("ask_question", output5)
        self.assertEqual(content5, "Content again.")
        self.assertEqual(f_ups5, ["AstQ1", "AstQ2"])

        # Case 6: Not a list after parsing
        output6 = "Content.\nFollow-up questions: \"Not a list\""
        content6, f_ups6 = self.learner_module._parse_llm_output("ask_question", output6)
        self.assertEqual(content6, "Content.")
        self.assertEqual(f_ups6, [])
        # Adjust assertion to match the logged context
        self.mock_monitoring_manager.log_warning.assert_any_call(
            "Parsed follow-up questions is not a list.", {"parsed": "Not a list"}
        )

    def test_sanitize_input(self):
        """Test the _sanitize_input method."""
        self.assertEqual(self.learner_module._sanitize_input("Hello World!"), "Hello World!")
        self.assertEqual(self.learner_module._sanitize_input("Test <script>alert('xss')</script>"), "Test scriptalertxssscript")
        self.assertEqual(self.learner_module._sanitize_input("你好，世界"), "你好世界") # Basic unicode
        self.assertEqual(self.learner_module._sanitize_input(None), "")
        self.assertEqual(self.learner_module._sanitize_input(123), "")
        long_string = "a" * 600
        self.assertEqual(len(self.learner_module._sanitize_input(long_string)), 500) # Max length

    def test_determine_response_type(self):
        """Test the _determine_response_type method."""
        self.assertEqual(self.learner_module._determine_response_type("ask_question"), "explanation")
        self.assertEqual(self.learner_module._determine_response_type("explain_topic"), "explanation")
        self.assertEqual(self.learner_module._determine_response_type("next_step"), "suggestion")
        self.assertEqual(self.learner_module._determine_response_type("provide_example"), "info") # provide_example falls to else
        self.assertEqual(self.learner_module._determine_response_type("unknown_type"), "info")

if __name__ == '__main__':
    unittest.main()
