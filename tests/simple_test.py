"""Simple test script for langgraph-kirokuforms.

This script provides a quick way to test the KirokuForms HITL integration
without running full pytest tests. It performs basic operations like:
1. Connecting to the KirokuForms API
2. Creating a HITL task
3. Displaying the task URL for manual submission
4. Waiting for and displaying the task result

Usage:
    python simple_test.py
"""

import os
import sys
import time
import json
from pprint import pprint

# Add the parent directory to path for importing the library
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the KirokuForms library and test config
from kirokuforms import KirokuFormsHITL
from tests.test_config import TEST_API_KEY, API_BASE_URL, TEST_TEMPLATE_ID

def run_simple_test():
    """Run a simple test of the KirokuFormsHITL client."""
    print("\n=== KirokuForms HITL Simple Test ===\n")
    
    # Initialize the client
    print(f"Initializing client with API key: {TEST_API_KEY[:10]}...")
    client = KirokuFormsHITL(
        api_key=TEST_API_KEY,
        base_url=API_BASE_URL
    )
    
    # Test MCP capabilities
    print("\nTesting connection and retrieving capabilities...")
    try:
        capabilities = client._request("GET", "")
        print("Connection successful!")
        print("Server name:", capabilities.get("name", "Unknown"))
        print("Server version:", capabilities.get("version", "Unknown"))
        
        # Check for HITL capability
        hitl_capability = capabilities.get("capabilities", {}).get("tools", {}).get("hitl/requestInput")
        if hitl_capability is not None:
            print("HITL capability available: ✓")
        else:
            print("HITL capability not found: ✗")
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        sys.exit(1)
    
    # Create a test task
    print("\nCreating a test HITL task...")
    task_id = f"simple-test-{int(time.time())}"
    try:
        # Option 1: Create task using template ID
        if TEST_TEMPLATE_ID:
            print(f"Using template ID: {TEST_TEMPLATE_ID}")
            task = client.create_task(
                title=f"Simple Test Task ({task_id})",
                description="This is a test task created by the simple_test.py script",
                template_id=TEST_TEMPLATE_ID,
                initial_data={
                    "question": "Test question from simple_test.py"
                },
                task_id=task_id
            )
        else:
            # Option 2: Create task with custom fields
            task = client.create_task(
                title=f"Simple Test Task ({task_id})",
                description="This is a test task created by the simple_test.py script",
                fields=[
                    {
                        "type": "text",
                        "label": "Test Question",
                        "name": "question",
                        "required": True,
                        "defaultValue": "Test question from simple_test.py"
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
        
        print("Task created successfully!")
        print(f"Task ID: {task['taskId']}")
        print(f"Form ID: {task['formId']}")
        print(f"Form URL: {task['formUrl']}")
        
        # Wait for manual submission
        print("\n=== Manual Task Submission Required ===")
        print("Please open the Form URL in your browser and submit the form.")
        print("This script will wait for the submission.")
        print("(Press Ctrl+C to cancel the test)")
        
        # Poll for result
        print("\nWaiting for task completion...")
        start_time = time.time()
        timeout = 300  # 5 minutes
        result = None
        
        while time.time() - start_time < timeout:
            try:
                task_status = client._request("GET", f"resources/hitl/tasks/{task_id}")
                status = task_status.get("status")
                print(f"Current status: {status}")
                
                if status == "completed":
                    result = task_status.get("submission", {})
                    break
            except Exception as e:
                print(f"Error checking status: {str(e)}")
            
            # Wait before checking again
            time.sleep(5)
        
        # Check if we got a result
        if result:
            print("\nTask completed successfully!")
            print("\n=== Submission Results ===")
            pprint(result)
        else:
            print("\nTest timed out waiting for submission.")
        
    except Exception as e:
        print(f"Error creating or checking task: {str(e)}")
    
    print("\n=== Test Complete ===\n")

if __name__ == "__main__":
    run_simple_test()