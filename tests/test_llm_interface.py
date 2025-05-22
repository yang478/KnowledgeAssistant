# -*- coding: utf-8 -*-
"""Pytest unit tests for the LLMInterface class."""

import pytest
import requests
import time
import json
from unittest.mock import MagicMock, call # Import call for checking print calls

# Ensure the llm_interface and config_manager modules can be imported
# This might be handled by pytest configuration (e.g., conftest.py or pytest.ini)
# For now, keeping a similar approach to the original test file for path adjustment.
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from llm_interface.llm_interface import LLMInterface
from config_manager.config_manager import ConfigManager


@pytest.fixture
def mock_config_manager(mocker):
    """Fixture for a mocked ConfigManager."""
    mock_cm = mocker.MagicMock(spec=ConfigManager)
    # Default configuration values
    mock_cm.get_config.side_effect = lambda key, default=None: {
        "llm.api_key": "test_api_key",
        "llm.api_endpoint": "http://fake-llm-api.com/v1/chat/completions",
        "llm.default_model": "test-default-model",
        "llm.request_timeout": 10,
        "llm.retry_attempts": 3,
        "llm.retry_delay": 1,
        "llm.retry_on_status_codes": [429, 500, 502, 503, 504],
        "llm.default_max_tokens": 50,
        "llm.default_temperature": 0.5,
    }.get(key, default)
    return mock_cm

@pytest.fixture
def llm_interface_instance(mock_config_manager):
    """Fixture for an LLMInterface instance with a mocked ConfigManager."""
    return LLMInterface(config_manager=mock_config_manager)

def test_initialization_successful(llm_interface_instance, mock_config_manager):
    """Test successful initialization with all configurations."""
    assert llm_interface_instance.api_key == "test_api_key"
    assert llm_interface_instance.api_endpoint == "http://fake-llm-api.com/v1/chat/completions"
    assert llm_interface_instance.default_model == "test-default-model"
    assert llm_interface_instance.request_timeout == 10
    assert llm_interface_instance.retry_attempts == 3
    assert llm_interface_instance.retry_delay == 1
    assert llm_interface_instance.retry_on_status_codes == [429, 500, 502, 503, 504]
    assert llm_interface_instance.default_max_tokens == 50
    assert llm_interface_instance.default_temperature == 0.5

def test_initialization_missing_api_key(mocker, mock_config_manager):
    """Test initialization with a missing API key."""
    mock_config_manager.get_config.side_effect = lambda key, default=None: {
        "llm.api_key": None, # Missing API key
        "llm.api_endpoint": "http://fake-llm-api.com/v1/chat/completions",
        "llm.default_model": "test-default-model",
    }.get(key, default)

    mock_print = mocker.patch('builtins.print')
    llm_interface = LLMInterface(config_manager=mock_config_manager)
    
    mock_print.assert_any_call("Warning: LLM_API_KEY not found in configuration.")
    assert llm_interface.api_key is None
    
    result = llm_interface.generate_text("test prompt")
    assert result["status"] == "error"
    assert result["message"] == "LLM API key or endpoint not configured."

def test_initialization_missing_api_endpoint(mocker, mock_config_manager):
    """Test initialization with a missing API endpoint."""
    mock_config_manager.get_config.side_effect = lambda key, default=None: {
        "llm.api_key": "test_api_key",
        "llm.api_endpoint": None, # Missing API endpoint
        "llm.default_model": "test-default-model",
    }.get(key, default)

    mock_print = mocker.patch('builtins.print')
    llm_interface = LLMInterface(config_manager=mock_config_manager)

    mock_print.assert_any_call("Warning: LLM_API_ENDPOINT not found in configuration. Real HTTP calls will fail.")
    assert llm_interface.api_endpoint is None

    result = llm_interface.generate_text("test prompt")
    assert result["status"] == "error"
    assert result["message"] == "LLM API key or endpoint not configured."


def test_generate_text_success_first_attempt(mocker, llm_interface_instance):
    """Test successful text generation on the first API call attempt."""
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Successful LLM response"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    mock_requests_post = mocker.patch("requests.post", return_value=mock_response)
    mocker.patch('builtins.print') # Mock print to avoid seeing attempt logs

    prompt = "Hello LLM!"
    result = llm_interface_instance.generate_text(prompt)

    assert result["status"] == "success"
    assert result["data"]["text"] == "Successful LLM response"
    assert result["data"]["usage"]["total_tokens"] == 30
    mock_requests_post.assert_called_once()
    args, kwargs = mock_requests_post.call_args
    assert kwargs["json"]["model"] == "test-default-model"
    assert kwargs["json"]["messages"][0]["content"] == prompt

def test_generate_text_success_with_custom_model_config(mocker, llm_interface_instance):
    """Test successful text generation with custom model configuration."""
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Custom model response"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 15, "total_tokens": 20},
    }
    mock_requests_post = mocker.patch("requests.post", return_value=mock_response)
    mocker.patch('builtins.print')

    prompt = "Custom prompt"
    model_config = {
        "model_name": "custom-test-model",
        "max_tokens": 100,
        "temperature": 0.8,
        "stream": False
    }
    result = llm_interface_instance.generate_text(prompt, model_config=model_config)

    assert result["status"] == "success"
    assert result["data"]["text"] == "Custom model response"
    mock_requests_post.assert_called_once()
    args, kwargs = mock_requests_post.call_args
    assert kwargs["json"]["model"] == "custom-test-model"
    assert kwargs["json"]["max_tokens"] == 100
    assert kwargs["json"]["temperature"] == 0.8
    assert kwargs["json"]["stream"] is False

def test_generate_text_success_after_retry_on_status_code(mocker, llm_interface_instance):
    """Test successful text generation after retrying due to a retryable HTTP status code."""
    mock_failure_response = mocker.MagicMock(spec=requests.Response)
    mock_failure_response.status_code = 429  # Retryable status code
    mock_failure_response.text = "Too Many Requests"

    mock_success_response = mocker.MagicMock(spec=requests.Response)
    mock_success_response.status_code = 200
    mock_success_response.json.return_value = {
        "choices": [{"message": {"content": "Success after retry"}}],
        "usage": {"total_tokens": 25},
    }
    # Fail once, then succeed
    mock_requests_post = mocker.patch("requests.post", side_effect=[mock_failure_response, mock_success_response])
    mock_time_sleep = mocker.patch("time.sleep")
    mock_print = mocker.patch('builtins.print')

    result = llm_interface_instance.generate_text("Retry prompt")

    assert result["status"] == "success"
    assert result["data"]["text"] == "Success after retry"
    assert mock_requests_post.call_count == 2
    mock_time_sleep.assert_called_once_with(llm_interface_instance.retry_delay)
    mock_print.assert_any_call(f"Attempt 1/{llm_interface_instance.retry_attempts} to call LLM API: {llm_interface_instance.api_endpoint}")
    mock_print.assert_any_call(f"LLM API returned 429. Retrying in {llm_interface_instance.retry_delay}s...")
    mock_print.assert_any_call(f"Attempt 2/{llm_interface_instance.retry_attempts} to call LLM API: {llm_interface_instance.api_endpoint}")


def test_generate_text_failure_after_all_retries_on_status_code(mocker, llm_interface_instance):
    """Test text generation failure after all retries on a persistent retryable HTTP status code."""
    mock_failure_response = mocker.MagicMock(spec=requests.Response)
    mock_failure_response.status_code = 503 # Retryable
    mock_failure_response.text = "Service Unavailable"

    mock_requests_post = mocker.patch("requests.post", return_value=mock_failure_response) # Always fail
    mock_time_sleep = mocker.patch("time.sleep")
    mocker.patch('builtins.print')

    result = llm_interface_instance.generate_text("Persistent failure prompt")

    assert result["status"] == "error"
    assert "LLM API request failed after all retry attempts" in result["message"]
    assert mock_requests_post.call_count == llm_interface_instance.retry_attempts
    assert mock_time_sleep.call_count == llm_interface_instance.retry_attempts -1


def test_generate_text_failure_non_retryable_status_code(mocker, llm_interface_instance):
    """Test text generation failure on a non-retryable HTTP status code (e.g., 400)."""
    mock_error_response = mocker.MagicMock(spec=requests.Response)
    mock_error_response.status_code = 400 # Bad Request (not in retry list)
    mock_error_response.text = "Invalid request payload"
    
    mock_requests_post = mocker.patch("requests.post", return_value=mock_error_response)
    mock_time_sleep = mocker.patch("time.sleep") # Should not be called
    mocker.patch('builtins.print')

    result = llm_interface_instance.generate_text("Bad request prompt")

    assert result["status"] == "error"
    assert "LLM API request failed with status 400" in result["message"]
    assert "Invalid request payload" in result["message"]
    mock_requests_post.assert_called_once()
    mock_time_sleep.assert_not_called()

def test_generate_text_timeout_failure_after_all_retries(mocker, llm_interface_instance):
    """Test text generation failure due to timeout after all retries."""
    mock_requests_post = mocker.patch("requests.post", side_effect=requests.exceptions.Timeout("Request timed out"))
    mock_time_sleep = mocker.patch("time.sleep")
    mocker.patch('builtins.print')

    result = llm_interface_instance.generate_text("Timeout prompt")

    assert result["status"] == "error"
    assert "LLM API request timed out after multiple retries" in result["message"]
    assert mock_requests_post.call_count == llm_interface_instance.retry_attempts
    assert mock_time_sleep.call_count == llm_interface_instance.retry_attempts -1

def test_generate_text_request_exception_failure_after_all_retries(mocker, llm_interface_instance):
    """Test text generation failure due to a generic RequestException after all retries."""
    mock_requests_post = mocker.patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection failed"))
    mock_time_sleep = mocker.patch("time.sleep")
    mocker.patch('builtins.print')

    result = llm_interface_instance.generate_text("Connection error prompt")

    assert result["status"] == "error"
    assert "LLM API request failed after multiple retries: Connection failed" in result["message"]
    assert mock_requests_post.call_count == llm_interface_instance.retry_attempts
    assert mock_time_sleep.call_count == llm_interface_instance.retry_attempts -1

def test_generate_text_invalid_json_response(mocker, llm_interface_instance):
    """Test handling of an invalid JSON response from the API."""
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
    
    mock_requests_post = mocker.patch("requests.post", return_value=mock_response)
    mocker.patch('builtins.print')

    result = llm_interface_instance.generate_text("Invalid JSON prompt")

    assert result["status"] == "error"
    assert "Error parsing LLM JSON response" in result["message"]
    mock_requests_post.assert_called_once()

def test_generate_text_missing_content_in_response_non_streaming(mocker, llm_interface_instance):
    """Test handling of a successful API response that's missing expected content (non-streaming)."""
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    # Simulate missing 'content' or malformed structure
    mock_response.json.return_value = { 
        "choices": [{"message": {}}], # "content" key is missing
        "usage": {"total_tokens": 5}
    }
    mock_requests_post = mocker.patch("requests.post", return_value=mock_response)
    mocker.patch('builtins.print')

    # Default is non-streaming
    result = llm_interface_instance.generate_text("Missing content prompt")

    assert result["status"] == "error"
    assert result["message"] == "LLM response missing content."

def test_generate_text_success_with_stream_true_allows_empty_content(mocker, llm_interface_instance):
    """Test that if stream=True, empty content in the initial (non-streamed) response part is acceptable."""
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": ""}}], # Empty content
        "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
    }
    mock_requests_post = mocker.patch("requests.post", return_value=mock_response)
    mocker.patch('builtins.print')

    prompt = "Stream prompt"
    model_config = {"stream": True} # Explicitly set stream to True
    result = llm_interface_instance.generate_text(prompt, model_config=model_config)

    assert result["status"] == "success" # Should be success as stream might deliver content later
    assert result["data"]["text"] == "" # Initial content is empty
    assert result["data"]["usage"]["total_tokens"] == 10
    args, kwargs = mock_requests_post.call_args
    assert kwargs["json"]["stream"] is True


def test_generate_text_success_with_stream_not_in_config_defaults_to_false(mocker, llm_interface_instance):
    """Test that if stream is not in model_config, it defaults to False in payload."""
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Default non-stream response"}}],
        "usage": {"total_tokens": 10},
    }
    mock_requests_post = mocker.patch("requests.post", return_value=mock_response)
    mocker.patch('builtins.print')

    prompt = "Default stream behavior"
    model_config = {"model_name": "some-model"} # stream not specified
    result = llm_interface_instance.generate_text(prompt, model_config=model_config)

    assert result["status"] == "success"
    args, kwargs = mock_requests_post.call_args
    assert "stream" in kwargs["json"]
    assert kwargs["json"]["stream"] is False
