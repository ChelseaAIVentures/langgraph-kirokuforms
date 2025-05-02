"""KirokuForms client for Human-in-the-Loop integration with LangGraph.

This module provides a client for creating and managing human review tasks 
in KirokuForms, with special support for LangGraph integration.
"""

import requests
import json
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import logging

# Configure logging
logger = logging.getLogger("kirokuforms")

class KirokuFormsHITL:
    """
    KirokuForms client for human-in-the-loop integration with LangGraph.
    """
    
    def __init__(
        self, 
        api_key: str,
        base_url: str = "https://api.kirokuforms.com/mcp",
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize the KirokuForms HITL client.
        
        Args:
            api_key: Your KirokuForms API key
            base_url: The KirokuForms MCP API base URL
            webhook_url: Optional URL for webhook notifications
            webhook_secret: Secret for webhook verification
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')  # Remove trailing slash if present
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Verify connection on initialization
        logger.debug(f"Initializing KirokuFormsHITL client with URL: {base_url}")
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Make an API request to KirokuForms.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (without leading slash)
            data: Optional request data
            
        Returns:
            API response data
            
        Raises:
            ValueError: If the API returns an error
            ConnectionError: If the connection fails
        """
        url = f"{self.base_url}/{endpoint}".rstrip('/')  # Ensure no double slashes
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Add logging
        logger.debug(f"Making {method} request to {url}")
        
        # Implement retry logic
        retries = 0
        while retries <= self.max_retries:
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                # Check for successful status code
                response.raise_for_status()
                
                # Try to parse JSON response
                try:
                    result = response.json()
                    if not result.get("success", False):
                        error = result.get("error", {})
                        error_msg = error.get("message", "Unknown error")
                        error_code = error.get("code", "UNKNOWN_ERROR")
                        logger.error(f"API Error {error_code}: {error_msg}")
                        raise ValueError(f"API Error ({error_code}): {error_msg}")
                    return result.get("data", {})
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON response: {response.text}")
                    raise ValueError(f"Invalid response from API: {response.text}")
                
            except requests.exceptions.RequestException as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(f"Request failed after {self.max_retries} retries: {str(e)}")
                    raise ConnectionError(f"Failed to connect to KirokuForms API: {str(e)}")
                
                # Exponential backoff with jitter
                wait_time = 2 ** retries + (time.time() % 1)
                logger.warning(f"Request failed, retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
    
    def create_task(
        self,
        title: str,
        description: str = "",
        fields: List[Dict[str, Any]] = None,
        template_id: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None,
        expiration: Optional[str] = None,
        priority: str = "medium",
        task_id: Optional[str] = None,
        callback_url: Optional[str] = None
    ) -> Dict:
        """
        Create a human-in-the-loop task.
        
        Args:
            title: Task title
            description: Task description
            fields: Form fields configuration (if not using template)
            template_id: ID of a form template to use (alternative to fields)
            initial_data: Pre-filled data for the form fields
            expiration: Expiration time (e.g., "24h", "7d")
            priority: Task priority ("low", "medium", "high")
            task_id: Optional custom task ID
            callback_url: URL to notify when task is completed
            
        Returns:
            Task information including ID and form URL
            
        Raises:
            ValueError: If neither fields nor template_id is provided
        """
        if fields is None and template_id is None:
            raise ValueError("Either fields or template_id must be provided")
        
        data = {
            "title": title,
            "description": description,
            "initialData": initial_data or {},
            "settings": {
                "expiration": expiration,
                "priority": priority,
                "taskId": task_id,
                "callbackUrl": callback_url or self.webhook_url
            }
        }

         # Add templateId or fields, but not both with fields being empty
        if template_id is not None:
            data["templateId"] = template_id
            # Only add fields if non-empty when using a template
            if fields and len(fields) > 0:
                data["fields"] = fields
        elif fields is not None:
            # Using fields without template
            if len(fields) == 0:
                raise ValueError("At least one field is required when not using a template")
            data["fields"] = fields

        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        data["settings"] = {k: v for k, v in data["settings"].items() if v is not None}
        
        return self._request("POST", "tools/request-human-review", data)
    
    def create_verification_task(
        self,
        title: str,
        description: str,
        data: Dict[str, Any],
        fields: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict:
        """
        Create a verification task with data to be verified.
        
        Args:
            title: Task title
            description: Task description
            data: Data to be verified
            fields: Optional custom fields (defaults to standard verification fields)
            **kwargs: Additional arguments for create_task
            
        Returns:
            Task information including ID and form URL
        """
        # Generate default verification fields if not provided
        if fields is None:
            fields = []
            # Create fields based on the data structure
            for key, value in data.items():
                field_type = "text"
                if isinstance(value, (int, float)):
                    field_type = "number"
                elif isinstance(value, bool):
                    field_type = "radio"
                
                if field_type == "radio" and isinstance(value, bool):
                    fields.append({
                        "type": field_type,
                        "label": key.replace("_", " ").title(),
                        "name": key,
                        "required": True,
                        "options": [
                            {"label": "True", "value": "true"},
                            {"label": "False", "value": "false"}
                        ],
                        "defaultValue": str(value).lower()
                    })
                else:
                    fields.append({
                        "type": field_type,
                        "label": key.replace("_", " ").title(),
                        "name": key,
                        "required": True,
                        "defaultValue": str(value)
                    })
            
            # Add verification fields
            fields.append({
                "type": "radio",
                "label": "Is this information correct?",
                "name": "is_correct",
                "required": True,
                "options": [
                    {"label": "Yes", "value": "yes"},
                    {"label": "No", "value": "no"}
                ]
            })
            
            fields.append({
                "type": "textarea",
                "label": "Comments or Corrections",
                "name": "comments",
                "required": False
            })
        
        return self.create_task(title, description, fields=fields, **kwargs)
    
    def get_task_result(self, task_id: str, wait: bool = True, timeout: int = 3600) -> Dict:
        """
        Get the result of a HITL task.
        
        Args:
            task_id: Task ID to retrieve
            wait: Whether to wait for the result if not available
            timeout: Maximum time to wait in seconds
            
        Returns:
            Task result data
            
        Raises:
            TimeoutError: If the task is not completed within the timeout
        """
        endpoint = f"resources/hitl/tasks/{task_id}"
        
        start_time = time.time()
        while True:
            result = self._request("GET", endpoint)
            
            if result.get("status") == "completed":
                return result.get("submission", {})
            
            if not wait or (time.time() - start_time) > timeout:
                raise TimeoutError(f"Task {task_id} not completed within timeout")
            
            # Wait before checking again
            time.sleep(5)
    
    def list_tasks(
        self, 
        status: Optional[str] = None, 
        limit: int = 10, 
        offset: int = 0
    ) -> Dict:
        """
        List HITL tasks.
        
        Args:
            status: Filter by status (pending, completed, expired, canceled)
            limit: Maximum number of tasks to return
            offset: Pagination offset
            
        Returns:
            List of tasks and pagination information
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if status:
            params["status"] = status
        
        # Convert params to URL query string
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"resources/hitl/tasks?{query_string}"
        
        return self._request("GET", endpoint)
    
    def cancel_task(self, task_id: str) -> Dict:
        """
        Cancel a pending HITL task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            Updated task information
        """
        return self._request("POST", f"resources/hitl/tasks/{task_id}/cancel")


def create_kiroku_interrupt_handler(api_key: str, **kwargs) -> Callable:
    """
    Create a LangGraph interrupt handler for KirokuForms.
    
    Args:
        api_key: KirokuForms API key
        **kwargs: Additional arguments for KirokuFormsHITL
        
    Returns:
        An interrupt handler function for LangGraph
    """
    client = KirokuFormsHITL(api_key, **kwargs)
    
    def interrupt_handler(state: Dict, interrupt_data: Dict) -> Dict:
        """
        LangGraph interrupt handler for human verification.
        
        Args:
            state: Current state of the graph
            interrupt_data: Data for the interrupt
            
        Returns:
            Updated state with human verification
        """
        # Extract task information from interrupt_data
        title = interrupt_data.get("title", "Human Verification Required")
        description = interrupt_data.get("description", "Please verify the following information")
        fields = interrupt_data.get("fields", [])
        data = interrupt_data.get("data", {})
        wait_for_result = interrupt_data.get("wait_for_result", True)
        
        if not fields and data:
            # Create a verification task based on the data
            task = client.create_verification_task(
                title=title,
                description=description,
                data=data
            )
        else:
            # Create a task with custom fields
            task = client.create_task(
                title=title,
                description=description,
                fields=fields
            )
        
        # Initialize result structure
        result = {
            **state,
            "human_verification": {
                "completed": False,
                "task_id": task["taskId"],
                "form_url": task["formUrl"],
                "result": None
            }
        }
        
        # Wait for the task to be completed if requested
        if wait_for_result:
            try:
                submission = client.get_task_result(task["taskId"])
                result["human_verification"]["completed"] = True
                result["human_verification"]["result"] = submission
            except TimeoutError as e:
                # Task not completed, return pending state
                logger.warning(f"Task {task['taskId']} not completed: {str(e)}")
        
        return result
    
    return interrupt_handler