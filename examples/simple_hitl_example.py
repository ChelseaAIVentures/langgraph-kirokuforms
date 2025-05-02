"""Simple test script for langgraph-kirokuforms.

This script provides a quick way to test the KirokuForms HITL integration
without running full pytest tests. It creates a task, displays a link for
human verification, and waits for the human feedback before continuing.

Usage:
    python simple_test.py
"""

import os
import sys
import time
import json
import webbrowser
from pprint import pprint
from pathlib import Path
import logging
import argparse
from datetime import datetime

# Configure logging for simple test
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add the parent directory to path for importing the library
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the KirokuForms library
from kirokuforms import KirokuFormsHITL

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description='Test the KirokuForms HITL integration.')
parser.add_argument('--open-browser', action='store_true', help='Automatically open the form URL in browser')
parser.add_argument('--timeout', type=int, default=300, help='Timeout in seconds (default: 300)')
parser.add_argument('--template', type=str, help='Template ID to use instead of custom fields')
args = parser.parse_args()

# --- Credential Loading ---
CREDS_FILE = Path(__file__).parent.parent / '.credentials.json'
if CREDS_FILE.exists():
    logger.info("Loading credentials from .credentials.json")
    with open(CREDS_FILE, 'r') as f:
        TEST_CREDS = json.load(f)
    TEST_API_KEY = TEST_CREDS.get('api_key')
    API_BASE_URL = TEST_CREDS.get('base_url', "http://localhost:4321/api/mcp")
    TEST_TEMPLATE_ID = TEST_CREDS.get('template_id') or args.template
    # TEST_TEMPLATE_ID = None
else:
    logger.info("Loading credentials from environment variables")
    TEST_API_KEY = os.environ.get("KIROKU_TEST_API_KEY")
    API_BASE_URL = os.environ.get("KIROKU_TEST_API_URL", "http://localhost:4321/api/mcp")
    TEST_TEMPLATE_ID = os.environ.get("KIROKU_TEST_TEMPLATE_ID") or args.template

if API_BASE_URL and API_BASE_URL.endswith('/mcp'):
    BASE_URL = API_BASE_URL.replace('/mcp', '')
elif API_BASE_URL:
    BASE_URL = API_BASE_URL
else:
    BASE_URL = None

def print_color(text, color="default"):
    """Print colored text for better readability."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "default": "\033[0m"
    }
    
    end_color = "\033[0m"
    color_code = colors.get(color, colors["default"])
    print(f"{color_code}{text}{end_color}")

def print_header(text):
    """Print a section header."""
    separator = "=" * 60
    print("\n" + separator)
    print_color(text, "cyan")
    print(separator)

def print_step(text):
    """Print a step in the process."""
    print_color(f"\n➤ {text}", "blue")

def print_success(text):
    """Print a success message."""
    print_color(f"✓ {text}", "green")

def print_error(text):
    """Print an error message."""
    print_color(f"✗ {text}", "red")

def print_warning(text):
    """Print a warning message."""
    print_color(f"⚠ {text}", "yellow")

def print_progress(current, total=None):
    """Print a progress indicator."""
    if total:
        print_color(f"[{current}/{total}]", "magenta")
    else:
        print_color(f"[{current}s]", "magenta")
    sys.stdout.flush()

def run_simple_test():
    """Run a simple test of the KirokuForms HITL client."""
    print_header("KirokuForms HITL Simple Test")
    
    # Check if credentials were loaded
    if not TEST_API_KEY or not API_BASE_URL:
        print_error("API Key or Base URL not found.")
        print("Ensure .test-credentials.json exists or environment variables are set.")
        return

    # Display test configuration
    print_step("Test Configuration")
    print(f"API URL: {API_BASE_URL}")
    print(f"API Key: {TEST_API_KEY[:5]}...")
    print(f"Template ID: {TEST_TEMPLATE_ID or 'Not specified, using custom fields'}")
    print(f"Browser Auto-Open: {'Enabled' if args.open_browser else 'Disabled'}")
    print(f"Timeout: {args.timeout} seconds")

    # Initialize the client
    print_step("Initializing HITL Client")
    client = KirokuFormsHITL(
        api_key=TEST_API_KEY,
        base_url=API_BASE_URL
    )

    # Test MCP capabilities
    print_step("Testing Connection")
    try:
        capabilities = client._request("GET", "")
        print_success("Connection successful!")
        print(f"Server: {capabilities.get('name', 'Unknown')} version {capabilities.get('version', 'Unknown')}")
        
        hitl_capability = capabilities.get("capabilities", {}).get("tools", {}).get("hitl/requestInput")
        if hitl_capability is not None:
            print_success("HITL capability available")
        else:
            print_warning("HITL capability not found")
    except Exception as e:
        print_error(f"Connection failed: {str(e)}")
        sys.exit(1)

    # Create a test task
    print_step("Creating HITL Task")
    task_id = f"simple-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    try:
        if TEST_TEMPLATE_ID:
            print(f"Using template ID: {TEST_TEMPLATE_ID}")
            task = client.create_task(
                title=f"Simple Test Task",
                description="This task requires your verification. Please review and respond.",
                template_id=TEST_TEMPLATE_ID,
                initial_data={
                    "question": "Is this HITL integration working correctly?"
                },
                task_id=task_id
            )
        else:
            print("Creating task with custom fields")
            task = client.create_task(
                title=f"Simple Test Task",
                description="This task requires your verification. Please review and respond.",
                fields=[
                    {
                        "type": "text",
                        "label": "Verification Question",
                        "name": "question",
                        "required": True,
                        "defaultValue": "Is this HITL integration working correctly?"
                    },
                    {
                        "type": "textarea",
                        "label": "Feedback",
                        "name": "feedback",
                        "required": True,
                        "placeholder": "Please provide feedback about this integration"
                    },
                    {
                        "type": "radio",
                        "label": "Approval",
                        "name": "approval",
                        "required": True,
                        "options": [
                            {"label": "Yes, it works!", "value": "yes"},
                            {"label": "No, there are issues", "value": "no"}
                        ]
                    }
                ],
                task_id=task_id
            )

        print_success("Task created successfully!")
        print(f"Task ID (External): {task['taskId']}")
        print(f"Task ID (Internal): {task['hitlTaskId']}")
        print(f"Form URL: {task['formUrl']}")

        # Open browser if requested
        if args.open_browser:
            print_step("Opening form in browser")
            webbrowser.open(task['formUrl'])
        
        # Wait for manual submission
        print_header("Manual Task Submission Required")
        print("Please complete the following steps:")
        print_color("1. Open the form URL in your browser (if not automatically opened)", "yellow")
        print_color(f"   {task['formUrl']}", "cyan")
        print_color("2. Complete and submit the form", "yellow")
        print_color("3. Wait for this script to detect the submission", "yellow")
        print_color("\nThis script will wait for your submission...", "magenta")
        print_color("(Press Ctrl+C to cancel the test)\n", "red")

        # Poll for result
        print_step("Waiting for task completion")
        start_time = time.time()
        elapsed = 0
        progress_interval = 10  # seconds between progress updates
        next_progress = progress_interval
        
        try:
            while elapsed < args.timeout:
                # Check if it's time to show a progress update
                if elapsed >= next_progress:
                    print_progress(elapsed)
                    next_progress += progress_interval
                
                # Try to get task result (will return when completed)
                try:
                    # Set a short timeout for each poll attempt
                    result = client.get_task_result(task["taskId"], wait=False)
                    # If we get here, the task is completed
                    break
                except TimeoutError:
                    # Task not completed yet, continue polling
                    pass
                except Exception as e:
                    if "not completed" in str(e):
                        # Task still pending, continue polling
                        pass
                    else:
                        # Some other error
                        print_error(f"Error checking task status: {str(e)}")
                        raise
                
                # Sleep before next poll
                time.sleep(5)
                elapsed = int(time.time() - start_time)
            
            # If we exited the loop but elapsed >= timeout, then we timed out
            if elapsed >= args.timeout:
                raise TimeoutError(f"Task not completed within {args.timeout} seconds")
            
            # Otherwise, get the full result
            print_progress(elapsed)
            print_success("Task completed!")
            result = client.get_task_result(task["taskId"], wait=False)
            
            print_header("Submission Results")
            print(json.dumps(result, indent=2))
            
            # Analyze the result
            if "approval" in result and result["approval"] == "yes":
                print_success("HITL integration test passed! The human approved.")
            else:
                print_warning("HITL integration test completed, but the human did not approve.")
                print(f"Feedback: {result.get('feedback', 'No feedback provided')}")
            
        except TimeoutError:
            print_error(f"\nTask not completed within {args.timeout} seconds")
            # Try to get the current status for debugging
            try:
                status = client._request("GET", f"resources/hitl/tasks/{task['taskId']}").get("status", "unknown")
                print(f"Current task status: {status}")
            except Exception:
                print("Could not retrieve current task status")
        except KeyboardInterrupt:
            print_warning("\nTest cancelled by user")
        except Exception as e:
            print_error(f"\nError waiting for task completion: {str(e)}")
            logger.exception("Error details:")

    except Exception as e:
        print_error(f"Error creating task: {str(e)}")
        logger.exception("Error details:")

    print_header("Test Complete")

if __name__ == "__main__":
    run_simple_test()