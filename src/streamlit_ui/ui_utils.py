# -*- coding: utf-8 -*-
"""
Streamlit UI Utility Functions.

This module provides common utility functions that can be shared across
different Streamlit UI modules, such as a centralized API gateway caller.
"""
import streamlit as st
import requests # For making HTTP requests to the API Gateway
from typing import Dict, Any, Optional

# Centralized API Gateway Configuration (could also come from a config file)
# Ensure this is configured correctly for your deployment.
# If API Gateway is running in the same project (e.g. FastAPI app),
# this might be 'http://localhost:8000/api/v1' or similar.
# If it's a separate service, use its full URL.
API_GATEWAY_URL = st.secrets.get("API_GATEWAY_URL", "http://localhost:8000/api/v1/memory_bank") # Default, adjust as needed

def call_api_gateway(operation: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Makes a call to the backend API Gateway.

    Args:
        operation (str): The specific operation to be performed (e.g., "create_kp", "get_lc").
                         This will be part of the request body or URL path depending on API design.
        payload (Dict[str, Any]): The data to send with the request.
        session_id (Optional[str]): The user's session ID, if applicable, for context.

    Returns:
        Dict[str, Any]: The JSON response from the API gateway.
                        Typically includes {"status": "success/error", "data": ..., "message": ...}.
    """
    request_body = {
        "operation": operation,
        "payload": payload
    }
    headers = {
        "Content-Type": "application/json"
    }
    if session_id:
        headers["X-Session-ID"] = session_id # Example header for session ID

    api_endpoint = API_GATEWAY_URL # The main endpoint that routes based on 'operation'

    try:
        # Using st.spinner for user feedback during API calls
        with st.spinner(f"Communicating with Memory Bank for '{operation}'..."):
            response = requests.post(api_endpoint, json=request_body, headers=headers, timeout=30) # 30-second timeout
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
            
            response_json = response.json()
            
            # Log or display success/error based on a conventional 'status' field in the response
            if response_json.get("status") == "error":
                st.toast(f"API Error for {operation}: {response_json.get('message', 'Unknown API error')}", icon="🚨")
            elif response_json.get("status") == "success":
                 st.toast(f"API call '{operation}' successful.", icon="✅")
            
            return response_json

    except requests.exceptions.HTTPError as http_err:
        st.error(f"API Gateway HTTP error for {operation}: {http_err} - Response: {http_err.response.text}")
        return {"status": "error", "message": f"HTTP error: {http_err}", "details": http_err.response.text if http_err.response else "No response body"}
    except requests.exceptions.ConnectionError as conn_err:
        st.error(f"API Gateway connection error for {operation}: {conn_err}. Is the backend server running at {API_GATEWAY_URL}?")
        return {"status": "error", "message": f"Connection error: {conn_err}"}
    except requests.exceptions.Timeout as timeout_err:
        st.error(f"API Gateway request timed out for {operation}: {timeout_err}")
        return {"status": "error", "message": f"Timeout: {timeout_err}"}
    except requests.exceptions.RequestException as req_err:
        st.error(f"API Gateway request error for {operation}: {req_err}")
        return {"status": "error", "message": f"Request error: {req_err}"}
    except ValueError as json_err: # Includes JSONDecodeError
        st.error(f"Error decoding JSON response from API Gateway for {operation}: {json_err}")
        # Attempt to show raw response if JSON decoding fails
        raw_response_text = "Could not retrieve raw response."
        if 'response' in locals() and hasattr(response, 'text'):
            raw_response_text = response.text
        return {"status": "error", "message": f"JSON decode error: {json_err}", "raw_response": raw_response_text}


# Example of another utility function that might be useful
def format_timestamp(ts_string: Optional[str]) -> str:
    """
    Formats a timestamp string (e.g., ISO format) into a more readable form.
    Returns 'N/A' if the timestamp is None or invalid.
    """
    if not ts_string:
        return "N/A"
    try:
        from datetime import datetime
        # Assuming ts_string is in a common format like ISO or easily parsable
        dt_object = datetime.fromisoformat(ts_string.replace("Z", "+00:00")) # Handle Z for UTC
        return dt_object.strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return ts_string # Return original if parsing fails

# Example of how to use secrets for configuration
def get_app_setting(setting_name: str, default: Any = None) -> Any:
    """
    Retrieves an application setting, potentially from Streamlit secrets.
    """
    if st.secrets.has_key(setting_name):
        return st.secrets[setting_name]
    return default

if __name__ == "__main__":
    # This block can be used for testing the utility functions
    st.title("UI Utils Test Page")

    st.subheader("Test API Gateway Call")
    test_op = st.text_input("Operation name (e.g., 'get_all_kps'):", "get_all_kps")
    test_payload_str = st.text_area("Payload (JSON string):", '{}')
    
    if st.button("Test Call API Gateway"):
        import json
        try:
            payload_dict = json.loads(test_payload_str)
            st.write(f"Calling API Gateway with operation: {test_op}, payload: {payload_dict}")
            result = call_api_gateway(test_op, payload_dict)
            st.write("API Response:")
            st.json(result)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON in payload: {e}")
        except Exception as e:
            st.error(f"An error occurred during test: {e}")

    st.subheader("Test Timestamp Formatter")
    raw_ts = st.text_input("Enter ISO Timestamp (e.g., 2023-10-27T10:30:00Z):", "2023-10-27T10:30:00Z")
    if raw_ts:
        st.write(f"Formatted: {format_timestamp(raw_ts)}")
    
    st.subheader("Test App Setting")
    secret_key_to_test = st.text_input("Enter a secret key to test (e.g., 'API_GATEWAY_URL'):", "API_GATEWAY_URL")
    default_val = st.text_input("Default value if not found:", "Not Set")
    retrieved_setting = get_app_setting(secret_key_to_test, default_val)
    st.write(f"Setting '{secret_key_to_test}': {retrieved_setting}")

    st.info(f"Default API Gateway URL from code: {API_GATEWAY_URL}")
    st.markdown("To test `call_api_gateway` effectively, ensure your API Gateway is running and `API_GATEWAY_URL` is correctly configured (e.g., in `secrets.toml`).")