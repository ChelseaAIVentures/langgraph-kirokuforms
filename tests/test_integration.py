"""Integration tests for the langgraph-kirokuforms library.

These tests verify the complete workflow from creating a task
through task submission and result retrieval.
"""

import os
import pytest
import time
import json
import requests
from pathlib import Path
from kirokuforms import KirokuFormsHITL

# Try to load credentials from file
CREDS_FILE = Path(__file__).parent / '.test-credentials.json'
if CREDS_FILE.exists():
    with open(CREDS_FILE, 'r') as f:
        TEST_CREDS = json.load(f)
    API_KEY = TEST_CREDS.get('api_key')
    API_URL = TEST_CREDS.get('base_url')
else:
    # Fall back to environment variables
    API_KEY = os.environ.get("KIROKU_TEST_API_KEY")
    API_URL = os.environ.get("KIROKU_TEST_API_URL", "http://localhost:4321/api/mcp")

# Skip all tests if no credentials are available
pytestmark = pytest.mark.skipif(
    not API_KEY,
    reason="No test credentials available. Run setup_test_env.py first."
)

@pytest.fixture
def hitl_client():
    """Create a KirokuFormsHITL client for testing with real credentials"""
    return KirokuFormsHITL(
        api_key=API_KEY,
        base_url=API_URL
    )

@pytest.fixture
def task_id():
    """Generate a unique task ID for tests"""
    return f"integration-test-{int(time.time())}"

@pytest.mark.integration
def test_mcp_capabilities(hitl_client):
    """Test retrieving MCP server capabilities"""
    capabilities = hitl_client._request("GET", "")
    
    # Verify server info
    assert "name" in capabilities
    assert capabilities["name"] == "KirokuForms MCP Server"
    
    # Verify capabilities structure
    assert "capabilities" in capabilities
    assert "tools" in capabilities["capabilities"]
    assert "hitl/requestInput" in capabilities["capabilities"]["tools"]
    
    print(f"Server capabilities: {json.dumps(capabilities, indent=2)}")

@pytest.mark.integration
def test_create_and_get_task(hitl_client, task_id):
    """Test creating a task and retrieving its details"""
    # 1. Create task
    task = hitl_client.create_task(
        title=f"Integration Test Task {task_id}",
        description="This task tests the full integration workflow",
        fields=[
            {
                "type": "text",
                "label": "Feedback",
                "name": "feedback",
                "required": True,
                "defaultValue": "Pre-filled feedback for testing"
            },
            {
                "type": "radio",
                "label": "Rating",
                "name": "rating",
                "required": True,
                "options": [
                    {"label": "Good", "value": "good"},
                    {"label": "Average", "value": "average"},
                    {"label": "Poor", "value": "poor"}
                ]
            }
        ],
        task_id=task_id
    )
    
    # Verify task creation
    assert task is not None
    assert "taskId" in task
    assert task["taskId"] == task_id
    assert "formId" in task
    assert "formUrl" in task
    
    form_id = task["formId"]
    form_url = task["formUrl"]
    print(f"Created task with form URL: {form_url}")
    
    # 2. Get task status (should be pending)
    task_status = hitl_client._request("GET", f"resources/hitl/tasks/{task_id}")
    assert task_status is not None
    assert "status" in task_status
    assert task_status["status"] == "pending"
    
    return {
        "task_id": task_id,
        "form_id": form_id,
        "form_url": form_url
    }

@pytest.mark.integration
def test_submit_and_verify(hitl_client, task_id):
    """
    Test submitting data to a task and verifying the result
    
    This test:
    1. Creates a task
    2. Submits data to the form programmatically
    3. Verifies the task status changes to completed
    4. Retrieves and verifies the submission data
    """
    # 1. Create the task
    task_info = test_create_and_get_task(hitl_client, task_id)
    form_id = task_info["form_id"]
    
    # 2. Extract task token from the form URL
    # The token is usually part of the form URL or needs to be retrieved separately
    # This is a simplified approach - in a real test, you might need to get it from the API
    response = requests.get(task_info["form_url"])
    # Just checking we can access the form page
    assert response.status_code == 200
    
    # For the test, we'll try to directly submit to the form endpoint
    # In a real scenario, you'd parse the form page to get the token
    # and potentially the API endpoint
    
    # 3. Submit data to the form
    submission_data = {
        "feedback": "Test feedback from integration test",
        "rating": "good"
    }
    
    # Make the submission request
    submission_url = f"{API_URL.replace('/mcp', '')}/forms/{form_id}"
    print(f"Submitting to: {submission_url}")
    
    submission_response = requests.post(
        submission_url,
        headers={"Content-Type": "application/json"},
        json=submission_data
    )
    
    # Check submission was successful
    assert submission_response.status_code == 200
    submission_result = submission_response.json()
    assert submission_result["success"] is True
    print(f"Submission response: {json.dumps(submission_result, indent=2)}")
    
    # 4. Give the system time to process the submission
    time.sleep(2)
    
    # 5. Check task status - should now be completed
    task_status = hitl_client._request("GET", f"resources/hitl/tasks/{task_id}")
    assert task_status is not None
    assert "status" in task_status
    assert task_status["status"] == "completed"
    
    # 6. Check if the submission data is correct
    assert "submission" in task_status
    submission = task_status["submission"]
    assert "feedback" in submission
    assert submission["feedback"] == "Test feedback from integration test"
    assert "rating" in submission
    assert submission["rating"] == "good"
    
    print(f"Task completion verified with submission: {json.dumps(submission, indent=2)}")
    
    # 7. Test the get_task_result method
    result = hitl_client.get_task_result(task_id, wait=False)
    assert result is not None
    assert "feedback" in result
    assert result["feedback"] == "Test feedback from integration test"
    assert "rating" in result
    assert result["rating"] == "good"
    
    print("Integration test completed successfully!")