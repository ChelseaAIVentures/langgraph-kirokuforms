"""Basic tests for the langgraph-kirokuforms library.

These tests verify core functionality like:
- API connectivity
- Creating HITL tasks
- Retrieving task results
- Integration with LangGraph
"""

import os
import pytest
import time
from unittest import mock
from kirokuforms import KirokuFormsHITL, create_kiroku_interrupt_handler

# Configuration for tests
API_KEY = os.environ.get("KIROKU_TEST_API_KEY", "test-api-key")
BASE_URL = os.environ.get("KIROKU_TEST_API_URL", "http://localhost:4321/api/mcp")

@pytest.fixture
def hitl_client():
    """Create a KirokuFormsHITL client for testing"""
    return KirokuFormsHITL(
        api_key=API_KEY,
        base_url=BASE_URL
    )

def test_api_connection(hitl_client):
    """Test that the client can connect to the API and retrieve capabilities"""
    # Making a simple API request to verify connectivity
    # This assumes _request is accessible for testing
    response = hitl_client._request("GET", "")
    
    assert "name" in response
    assert response["name"] == "KirokuForms MCP Server"
    assert "capabilities" in response
    assert "tools" in response["capabilities"]
    assert "hitl/requestInput" in response["capabilities"]["tools"]

def test_create_task(hitl_client):
    """Test creating a HITL task"""
    task_id = f"test-task-{int(time.time())}"
    
    task = hitl_client.create_task(
        title="Test Task",
        description="This is a test task created by the Python library",
        fields=[
            {
                "type": "text",
                "label": "Test Question",
                "name": "question_1",
                "required": True
            },
            {
                "type": "radio",
                "label": "Approval",
                "name": "approval",
                "required": True,
                "options": [
                    {"label": "Yes", "value": "yes"},
                    {"label": "No", "value": "no"}
                ]
            }
        ],
        task_id=task_id
    )
    
    assert task is not None
    assert "taskId" in task
    assert task["taskId"] == task_id
    assert "formId" in task
    assert "formUrl" in task

def test_get_task_result(hitl_client):
    """Test retrieving a task result (mock response)"""
    # Since we can't wait for human input in automated tests,
    # we'll mock the API response
    
    with mock.patch.object(hitl_client, '_request') as mock_request:
        # Configure the mock to return a fake completed task
        mock_request.return_value = {
            "status": "completed",
            "submission": {
                "question_1": "Test response",
                "approval": "yes"
            }
        }
        
        # Get the result for a fake task ID
        result = hitl_client.get_task_result("mock-task-id", wait=False)
        
        assert result is not None
        assert "question_1" in result
        assert result["question_1"] == "Test response"
        assert "approval" in result
        assert result["approval"] == "yes"

def test_create_verification_task(hitl_client):
    """Test creating a verification task with data to verify"""
    task_id = f"verify-task-{int(time.time())}"
    
    # Create a verification task with some data to verify
    task = hitl_client.create_verification_task(
        title="Verify Data",
        description="Please verify this information is correct",
        data={
            "customer_name": "John Doe",
            "purchase_amount": 199.99,
            "shipping_address": "123 Main St",
            "is_priority": True
        },
        task_id=task_id
    )
    
    assert task is not None
    assert "taskId" in task
    assert task["taskId"] == task_id
    assert "formId" in task
    assert "formUrl" in task

def test_interrupt_handler():
    """Test creating and using an interrupt handler for LangGraph"""
    # Create a mock KirokuFormsHITL to avoid real API calls
    with mock.patch('kirokuforms.KirokuFormsHITL') as MockClient:
        # Configure the mock to return appropriate values
        mock_client = MockClient.return_value
        mock_client.create_verification_task.return_value = {"taskId": "test-task-id"}
        mock_client.get_task_result.return_value = {"is_correct": "yes", "comments": "Looks good"}
        
        # Create the interrupt handler
        handler = create_kiroku_interrupt_handler("test-api-key")
        
        # Test the handler with a sample state and interrupt data
        state = {"key": "value"}
        interrupt_data = {
            "title": "Verify Data",
            "description": "Please verify this information",
            "data": {"field1": "value1", "field2": "value2"}
        }
        
        # Call the handler
        result = handler(state, interrupt_data)
        
        # Verify the result
        assert "human_verification" in result
        assert result["human_verification"]["completed"] is True
        assert result["human_verification"]["task_id"] == "test-task-id"
        assert "result" in result["human_verification"]
        
        # Verify the original state was preserved
        assert "key" in result
        assert result["key"] == "value"

def test_webhook_integration(hitl_client):
    """Test creating a task with webhook callback URL"""
    task_id = f"webhook-task-{int(time.time())}"
    callback_url = "https://example.com/webhook"
    
    # Create a task with a webhook callback
    task = hitl_client.create_task(
        title="Webhook Test Task",
        description="Task with webhook callback",
        fields=[
            {
                "type": "text",
                "label": "Feedback",
                "name": "feedback",
                "required": True
            }
        ],
        task_id=task_id,
        callback_url=callback_url
    )
    
    assert task is not None
    assert "taskId" in task
    assert task["taskId"] == task_id
    # The response doesn't typically echo back the callback_url,
    # but we're testing that it was accepted without error