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
from pathlib import Path
import logging # Import logging

# Configure logging for simple test
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Set script logging to DEBUG


# Add the parent directory to path for importing the library
# This allows importing 'kirokuforms' if running the script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the KirokuForms library
from kirokuforms import KirokuFormsHITL

# --- Credential Loading (Copy from test_integration.py) ---
CREDS_FILE = Path(__file__).parent / '.test-credentials.json'
if CREDS_FILE.exists():
    logger.info("Loading credentials from .test-credentials.json")
    with open(CREDS_FILE, 'r') as f:
        TEST_CREDS = json.load(f)
    TEST_API_KEY = TEST_CREDS.get('api_key')
    API_BASE_URL = TEST_CREDS.get('base_url', "http://localhost:4321/api/mcp") # Default if not in file
    TEST_TEMPLATE_ID = TEST_CREDS.get('template_id') # Load template ID too

else:
    # Fall back to environment variables
    logger.info("Loading credentials from environment variables")
    TEST_API_KEY = os.environ.get("KIROKU_TEST_API_KEY")
    API_BASE_URL = os.environ.get("KIROKU_TEST_API_URL", "http://localhost:4321/api/mcp") # Default if not set
    TEST_TEMPLATE_ID = os.environ.get("KIROKU_TEST_TEMPLATE_ID") # Load template ID env var


# Ensure API_BASE_URL is just the base without /mcp if needed elsewhere
if API_BASE_URL and API_BASE_URL.endswith('/mcp'):
    BASE_URL = API_BASE_URL.replace('/mcp', '')
elif API_BASE_URL:
     BASE_URL = API_BASE_URL # Assume it's already the base
else:
     BASE_URL = None # Handle case where API_BASE_URL is None

logger.info(f"Using API URL: {API_BASE_URL}")
if TEST_API_KEY:
     logger.info(f"Using API Key: {TEST_API_KEY[:5]}...")
else:
     logger.warning("KIROKU_TEST_API_KEY not found. Simple test will not run.")

logger.info(f"Using Test Template ID: {TEST_TEMPLATE_ID}")


# --- End Credential Loading ---


def run_simple_test():
    """Run a simple test of the KirokuFormsHITL client."""
    print("\n=== KirokuForms HITL Simple Test ===")

    # Check if credentials were loaded
    if not TEST_API_KEY or not API_BASE_URL:
         print("Skipping simple test: API Key or Base URL not found.")
         print("Ensure .test-credentials.json exists or environment variables are set.")
         return # Exit the function if no credentials


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
        # Option 1: Create task using template ID (preferred if a reliable test template exists)
        if TEST_TEMPLATE_ID:
            print(f"Using template ID: {TEST_TEMPLATE_ID}")
            task = client.create_task(
                title=f"Simple Test Task ({task_id})",
                description="This is a test task created by the simple_test.py script",
                template_id=TEST_TEMPLATE_ID,
                # Add initial_data if needed by the template
                initial_data={
                     "question": "Test question from simple_test.py (via template)" # Example field name, depends on template
                },
                task_id=task_id
            )
        else:
            # Option 2: Create task with custom fields (if no template ID is provided)
            print("No template ID provided, creating task with custom fields.")
            task = client.create_task(
                title=f"Simple Test Task ({task_id})",
                description="This is a test task created by the simple_test.py script",
                fields=[
                    {
                        "type": "text",
                        "label": "Test Question",
                        "name": "test_question", # Using a clearer name here
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
        print(f"Task ID (External): {task['taskId']}")
        print(f"Task ID (Internal HITL): {task['hitlTaskId']}") # MCP should return this now
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

        # Use the client's get_task_result method which handles polling
        try:
             # get_task_result expects the EXTERNAL task_id
             result = client.get_task_result(task["taskId"], wait=True, timeout=timeout)
             print("\nTask completed successfully!")
             print("\n=== Submission Results ===")
             pprint(result)
        except TimeoutError:
             print("\nTest timed out waiting for submission.")
             # Optionally fetch status one last time if needed for debugging
             try:
                 final_status = client._request("GET", f"resources/hitl/tasks/{task['taskId']}").get("status", "unknown")
                 print(f"Task {task['taskId']} final status was: {final_status}")
             except Exception:
                 print("Could not retrieve final task status.")


    except Exception as e:
        print(f"Error creating or checking task: {str(e)}")
        logger.exception("Error details:") # Log exception details

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    run_simple_test()