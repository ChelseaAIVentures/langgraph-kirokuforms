"""Integration tests for the langgraph-kirokuforms library.

These tests verify the complete workflow from creating a task
through task submission and result retrieval, including webhook delivery.
"""

import os
import sys
# Add the parent directory to path for importing the library
# This allows importing 'kirokuforms' if running the script directly from the project root/tests dir
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import pytest
import random
import time
import json
import requests
from pathlib import Path
# Now the import should work
from kirokuforms import KirokuFormsHITL
import logging
import http.server
import threading
from urllib.parse import urlparse

# --- Rest of the code from the previous response follows ---

# Configure logging for better visibility during tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Set test file logging to DEBUG

# Configure requests logging to see HTTP activity
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True # Ensure requests logs go to the basicConfig stream


# --- Test Credentials and Configuration ---
CREDS_FILE = Path(__file__).parent.parent / '.credentials.json'
if CREDS_FILE.exists():
    with open(CREDS_FILE, 'r') as f:
        TEST_CREDS = json.load(f)
    API_KEY = TEST_CREDS.get('api_key')
    # Default to the local development URL for integration tests if not specified
    API_URL = TEST_CREDS.get('base_url', "http://localhost:4321/api/mcp")
else:
    # Fall back to environment variables
    API_KEY = os.environ.get("KIROKU_TEST_API_KEY")
    # Default to the local development URL for integration tests
    API_URL = os.environ.get("KIROKU_TEST_API_URL", "http://localhost:4321/api/mcp")


# Ensure BASE_URL is correctly derived from API_URL at the top
if API_URL and API_URL.endswith('/mcp'):
    BASE_URL = API_URL.replace('/mcp', '') # e.g. http://192.168.240.1:4321/api
elif API_URL:
     # If API_URL doesn't end in /mcp, assume it ends in /api or equivalent
     BASE_URL = API_URL
else:
     BASE_URL = None # Handle case where API_URL is None
logger.info(f"Using API URL: {API_URL}")
if API_KEY:
     logger.info(f"Using API Key: {API_KEY[:5]}...")
else:
     logger.warning("KIROKU_TEST_API_KEY not found. Tests will be skipped.")


# Skip all tests in this file if no credentials are available
pytestmark = pytest.mark.skipif(
    not API_KEY,
    reason="No test credentials available. Ensure .test-credentials.json exists or KIROKU_TEST_API_KEY is set."
)

# --- Mock Webhook Server Setup ---

WEBHOOK_PORT = 4444 # Choose a port for the mock webhook server

# Global list to store received webhook call payloads
mock_webhook_calls = []

class MockWebhookHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the mock webhook server."""
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            logger.warning("[PYTHON MOCK WEBHOOK] Received POST with no body")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": "No body"}).encode('utf-8'))
            return

        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data)
            logger.info(f"[PYTHON MOCK WEBHOOK] Received payload:\n{json.dumps(payload, indent=2)}")
            # Append the payload to the global list
            global mock_webhook_calls
            mock_webhook_calls.append(payload)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "received": True}).encode('utf-8'))
        except json.JSONDecodeError:
            logger.error(f"[PYTHON MOCK WEBHOOK] Failed to parse JSON from body: {post_data.decode('utf-8')}")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": "Invalid JSON"}).encode('utf-8'))
        except Exception as e:
            logger.exception("[PYTHON MOCK WEBHOOK] Error handling request:") # Log exception details
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def log_message(self, format, *args):
        # Suppress default http.server logging output for cleaner test logs
        pass

@pytest.fixture(scope="module", autouse=True) # autouse=True runs it once per module automatically
def mock_webhook_server():
    """Fixture to start and stop the mock webhook server."""
    server_address = ('localhost', WEBHOOK_PORT)
    try:
        httpd = http.server.HTTPServer(server_address, MockWebhookHandler)
    except OSError as e:
        # Handle case where the port is already in use
        logger.error(f"[PYTHON TEST SETUP] Failed to start mock webhook server on port {WEBHOOK_PORT}: {e}")
        pytest.skip(f"Could not start mock webhook server on port {WEBHOOK_PORT}. Is another process running?")
        return # Skip the fixture setup

    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True # Allows the main thread to exit even if server is running
    server_thread.start()

    logger.info(f"[PYTHON TEST SETUP] Mock webhook server started on port {WEBHOOK_PORT}")

    # Clear calls at the start of the module scope
    global mock_webhook_calls
    mock_webhook_calls = []

    # Provide the URL that the backend should call
    webhook_url = f"http://localhost:{WEBHOOK_PORT}/webhook"
    yield webhook_url

    # Teardown: Stop the server thread
    logger.info(f"[PYTHON TEST TEARDOWN] Stopping mock webhook server on port {WEBHOOK_PORT}")
    httpd.shutdown()
    server_thread.join(timeout=5) # Give thread a moment to clean up

@pytest.fixture(autouse=True) # autouse=True runs it before every test function
def clear_webhook_calls_per_test():
    """Fixture to clear the mock webhook calls list before each test function."""
    global mock_webhook_calls
    mock_webhook_calls = []
    # No yield needed as it's just setup

# --- Pytest Fixtures ---

@pytest.fixture
def hitl_client():
    """Create a KirokuFormsHITL client for testing with real credentials"""
    # Client logging level set in module setup
    return KirokuFormsHITL(
        api_key=API_KEY,
        # Ensure the client uses the BASE_URL without the trailing /api for _request calls
        # However, the client uses base_url + endpoint, and endpoint starts with /
        # Let's stick to passing API_URL to the client constructor
        base_url=API_URL
    )

@pytest.fixture
def task_id():
    """Generate a unique task ID for tests"""
    # Use milliseconds and a random number for higher uniqueness
    return f"integration-test-{int(time.time() * 1000)}-{random.randint(0, 999)}"

# --- Integration Tests ---

@pytest.mark.integration
def test_mcp_capabilities(hitl_client):
    """Test retrieving MCP server capabilities"""
    logger.info("\n--- Running test_mcp_capabilities ---")
    capabilities = hitl_client._request("GET", "")

    # Verify server info
    assert "name" in capabilities
    assert capabilities["name"] == "KirokuForms MCP Server"

    # Verify capabilities structure
    assert "capabilities" in capabilities
    assert "tools" in capabilities["capabilities"]
    assert "hitl/requestInput" in capabilities["capabilities"]["tools"]

    logger.info(f"Server capabilities: {json.dumps(capabilities, indent=2)}")


@pytest.mark.integration
def test_create_and_get_task(hitl_client, task_id):
    """Test creating a task and retrieving its details"""
    logger.info(f"\n--- Running test_create_and_get_task for task ID: {task_id} ---")
    # 1. Create task
    # Use fields to create a dynamic template for this test
    fields_config = [
         { "type": "text", "label": "Feedback", "name": "feedback_field", "required": True },
         { "type": "radio", "label": "Rating", "name": "rating_field", "required": True, "options": [{"label": "Good", "value": "good"}, {"label": "Average", "value": "average"}, {"label": "Poor", "value": "poor"}] }
    ]
    task = hitl_client.create_task(
        title=f"Integration Test Task {task_id}",
        description="This task tests creating and getting task details",
        fields=fields_config,
        task_id=task_id # External task ID
    )

    # Verify task creation response
    assert task is not None
    assert "taskId" in task # External ID
    assert task["taskId"] == task_id
    assert "hitlTaskId" in task # Internal ID returned by MCP endpoint
    assert "formId" in task
    assert "formUrl" in task

    external_task_id_response = task["taskId"]
    internal_hitl_task_id_response = task["hitlTaskId"]
    form_id = task["formId"]
    form_url = task["formUrl"]

    logger.info(f"Created task with form URL: {form_url}")
    logger.info(f"External Task ID: {external_task_id_response}")
    logger.info(f"Internal HITL Task ID: {internal_hitl_task_id_response}")

    # 2. Get task status using the EXTERNAL task ID (this is what the resources endpoint expects)
    # Poll briefly to ensure the task is created and accessible and has relations
    logger.info(f"Polling task status for external ID: {external_task_id_response}")
    start_time = time.time()
    timeout = 20 # Longer timeout to ensure relations like accessTokens/template are available
    task_status = None
    while time.time() - start_time < timeout:
         try:
             details = hitl_client._request("GET", f"resources/hitl/tasks/{external_task_id_response}")
             logger.debug(f"Polling details for {external_task_id_response}: status={details.get('status')}, id={details.get('id')}, tokens={len(details.get('accessTokens',[]))}, template={details.get('template') is not None}, fields={details.get('template', {}).get('fields') is not None}")

             # Check for pending status and required relations in the GET response
             # Now that the backend endpoint returns 'id', we can check against it
             if details.get("status") == "pending" and details.get("id") == internal_hitl_task_id_response and details.get("accessTokens") is not None and len(details.get("accessTokens",[])) > 0 and details.get("template", {}).get("fields") is not None and len(details.get("template", {}).get("fields", [])) == len(fields_config):
                 task_status = details
                 break
         except Exception as e:
              logger.debug(f"Error during initial task status poll: {e}")
              pass # Ignore errors during polling
         time.sleep(1) # Wait before retry

    assert task_status is not None and task_status.get("status") == "pending", f"Task {external_task_id_response} not found or not pending and ready after creation timeout. Last polled details: {task_status}"
    assert task_status["id"] == internal_hitl_task_id_response
    logger.info(f"Task {external_task_id_response} found with status: {task_status['status']} and details loaded.")


@pytest.mark.integration
def test_submit_and_verify(hitl_client, task_id, mock_webhook_server): # Add mock_webhook_server fixture
    """
    Test submitting data to a task and verifying the result via BOTH polling and webhook

    This test:
    1. Creates a task with the mock server's URL as the callback
    2. Fetches task details to get internal ID, token, and field names
    3. Submits data to the correct submission endpoint using the token and internal ID
    4. Verifies the task status changes to completed by polling
    5. Verifies the submission data via polling (using get_task_result)
    6. Checks that the mock webhook server received a call
    7. Verifies the data in the received webhook payload
    """
    logger.info(f"\n--- Running test_submit_and_verify for task ID: {task_id} ---")

    webhook_callback_url = mock_webhook_server # Get the URL from the fixture
    logger.info(f"Using webhook callback URL: {webhook_callback_url}")

    # 1. Create the task (directly within this test)
    # Use fields to create a dynamic template for this test, using consistent names
    fields_config = [
         { "type": "text", "label": "Feedback", "name": "feedback_field", "required": True },
         { "type": "radio", "label": "Rating", "name": "rating_field", "required": True, "options": [{"label": "Good", "value": "good"}, {"label": "Average", "value": "average"}, {"label": "Poor", "value": "poor"}] }
    ]
    # --- COPY START: Task Creation Logic from test_create_and_get_task ---
    task = hitl_client.create_task(
        title=f"Integration Test Task {task_id}",
        description="This task tests the full integration workflow including webhooks",
        fields=fields_config,
        task_id=task_id, # External task ID for THIS test function's unique ID
        callback_url=webhook_callback_url # <-- Provide the mock webhook URL here
    )

    # Verify task creation response structure
    assert task is not None
    assert "taskId" in task # External ID
    assert task["taskId"] == task_id
    assert "hitlTaskId" in task # Internal ID returned by MCP endpoint
    assert "formId" in task
    assert "formUrl" in task

    external_task_id = task["taskId"] # Use task_id from fixture
    internal_hitl_task_id = task["hitlTaskId"]
    form_id = task["formId"]
    form_url = task["formUrl"]
    # --- COPY END ---

    logger.info(f"Task created with External ID: {external_task_id}, Internal ID: {internal_hitl_task_id}")


    # 2. Get the full task details including internal ID, token, and template fields
    # Use the external_task_id for this GET request on the resources endpoint
    logger.info(f"Fetching full task details for external ID: {external_task_id}")
    # Poll until status is pending AND required relations are available
    start_time = time.time()
    timeout = 20 # Longer timeout
    full_task_details = None
    while time.time() - start_time < timeout:
         try:
             details = hitl_client._request("GET", f"resources/hitl/tasks/{external_task_id}")
             logger.debug(f"Polling details for {external_task_id}: status={details.get('status')}, id={details.get('id')}, tokens={len(details.get('accessTokens',[]))}, template={details.get('template') is not None}, fields={details.get('template', {}).get('fields') is not None}")
             # Check for pending status AND required relations in the GET response
             if details.get("status") == "pending" and details.get("id") == internal_hitl_task_id and details.get("accessTokens") is not None and len(details.get("accessTokens",[])) > 0 and details.get("template", {}).get("fields") is not None and len(details.get("template", {}).get("fields", [])) == len(fields_config):
                 full_task_details = details
                 break
         except Exception as e:
              logger.debug(f"Error during task details poll: {e}")
              pass # Ignore errors during polling
         time.sleep(1) # Wait before retry


    assert full_task_details is not None, f"Task {external_task_id} details not found or not ready after creation timeout. Last details polled: {full_task_details}"
    assert full_task_details.get("status") == "pending"
    assert full_task_details.get("id") == internal_hitl_task_id # Verify internal ID from GET response
    assert full_task_details.get("callbackUrl") == webhook_callback_url # Verify callback URL is set


    access_tokens = full_task_details.get("accessTokens", [])
    template_fields = full_task_details.get("template", {}).get("fields", [])

    assert len(access_tokens) > 0, "Task should have at least one access token after polling"
    assert len(template_fields) == len(fields_config), f"Expected {len(fields_config)} template fields, found {len(template_fields)} after polling"


    # Extract the field names created by the backend from the dynamic template
    actual_field_names = {f.get('name') for f in template_fields if f.get('name')}
    expected_field_names = {"feedback_field", "rating_field"}
    assert actual_field_names == expected_field_names, f"Backend did not create template fields with expected names. Got {actual_field_names}, Expected {expected_field_names}"

    # Find the first valid token
    task_token = None
    if access_tokens:
        task_token = access_tokens[0].get("token")

    assert task_token is not None, "No valid token found for the task after polling"
    logger.info(f"Found token: {task_token[:6]}...")


    # 3. Prepare submission data using the actual field names from the template
    submission_data_raw = {
        "feedback_field": "Test feedback from integration test",
        "rating_field": "good" # Using the names we expect the backend created
    }

    # Construct the full submission payload including internal task ID and token
    full_submission_payload = {
        **submission_data_raw, # Add the mapped field data
        "taskId": internal_hitl_task_id, # Add the internal HITL task ID for the submission endpoint
        "token": task_token # Add the access token for the submission endpoint
    }

    logger.info(f"Constructed full submission payload for submission endpoint:\n{json.dumps(full_submission_payload, indent=2)}")


    # 4. Submit data to the correct task submission endpoint
    submission_endpoint_url = f"{BASE_URL}/submissions/task"
    logger.info(f"Submitting to task endpoint: {submission_endpoint_url}")

    submission_response = requests.post(
        submission_endpoint_url,
        headers={"Content-Type": "application/json"},
        json=full_submission_payload,
        timeout=hitl_client.timeout
    )

    # Check submission was successful
    submission_response.raise_for_status()
    submission_result = submission_response.json()
    assert submission_result.get("success", False) is True
    # Assert that submissionId is in the 'data' part of the response
    assert "data" in submission_result
    assert submission_result["data"] is not None # Ensure data is not null
    assert "submissionId" in submission_result["data"] # <-- CORRECTED ASSERTION
    logger.info(f"Submission successful. Response:\n{json.dumps(submission_result, indent=2)}")

    # 5. Give the system time for async processing (task completion, event emission, webhook sending)
    logger.info("Waiting for task completion and webhook delivery...")
    time.sleep(5) # Increased sleep to allow time for webhook delivery and event processing


    # 6. Verify the task status is completed by polling the resources endpoint
    logger.info(f"Polling task status for external ID: {external_task_id} to confirm completion...")
    # Use get_task_result with wait=True, it handles polling
    polling_timeout = 30 # Max 30 seconds
    try:
        # get_task_result returns the submission data directly
        submission_result_data_from_poll = hitl_client.get_task_result(external_task_id, wait=True, timeout=polling_timeout)
        logger.info("Task status polling confirmed completed.")
    except TimeoutError:
        # Fetch status one last time if polling times out for debugging
        final_task_status_details = hitl_client._request("GET", f"resources/hitl/tasks/{external_task_id}")
        final_status = final_task_status_details.get("status", "unknown")
        logger.error(f"Task {external_task_id} did not complete within {polling_timeout} seconds. Final status: {final_status}")
        raise AssertionError(f"Task {external_task_id} did not complete within {polling_timeout} seconds. Final status: {final_status}")


    assert submission_result_data_from_poll is not None, "Polling for task result failed or returned no data"

    # 7. Verify the submission data is correct in the completed task details (from polling)
    logger.info(f"Verifying submission data from polling result:\n{json.dumps(submission_result_data_from_poll, indent=2)}")
    assert "feedback_field" in submission_result_data_from_poll
    assert submission_result_data_from_poll["feedback_field"] == submission_data_raw["feedback_field"]
    assert "rating_field" in submission_result_data_from_poll
    assert submission_result_data_from_poll["rating_field"] == submission_data_raw["rating_field"]
    logger.info("Submission data from polling verified.")


    # 8. Check that the mock webhook server received a call
    logger.info(f"Checking mock webhook server calls ({len(mock_webhook_calls)} calls received so far)...")
    # Wait briefly to ensure the async webhook has time to arrive if it hasn't already
    time.sleep(2)
    logger.info(f"Checking mock webhook server calls again ({len(mock_webhook_calls)} calls received)...")
    assert len(mock_webhook_calls) > 0, "Mock webhook server should have received at least one call after task completion"

    # 9. Find the relevant webhook call and verify its payload
    relevant_webhook_call = None
    for call_payload in mock_webhook_calls:
        # Webhook payload uses the external taskId
        if call_payload.get("taskId") == external_task_id and call_payload.get("eventType") == "hitl.task.completed":
            relevant_webhook_call = call_payload
            break

    assert relevant_webhook_call is not None, f"Mock webhook server did not receive a 'hitl.task.completed' call for task {external_task_id}"
    logger.info(f"Relevant webhook call received:\n{json.dumps(relevant_webhook_call, indent=2)}")


    assert relevant_webhook_call.get("eventType") == "hitl.task.completed"
    assert relevant_webhook_call.get("taskId") == external_task_id
    assert relevant_webhook_call.get("data", {}).get("status") == "completed"
    webhook_submission_data = relevant_webhook_call.get("data", {}).get("formData", {})
    assert webhook_submission_data is not None, "Webhook payload missing formData"

    # Verify the submission data within the webhook payload using the actual field names
    logger.info("Verifying submission data from webhook payload...")
    assert "feedback_field" in webhook_submission_data
    assert webhook_submission_data["feedback_field"] == submission_data_raw["feedback_field"]
    assert "rating_field" in webhook_submission_data
    assert webhook_submission_data["rating_field"] == submission_data_raw["rating_field"]
    logger.info("Submission data from webhook verified.")


    logger.info("\n--- test_submit_and_verify completed successfully (Webhook and Polling verified)! ---")