# packages/langgraph-kirokuforms/kirokuforms.py

import requests
import json
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta

class KirokuFormsHITL:
    """
    KirokuForms client for human-in-the-loop integration with LangGraph.
    """
    
    def __init__(
        self, 
        api_key: str,
        base_url: str = "https://api.kirokuforms.com/mcp",
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None
    ):
        """
        Initialize the KirokuForms HITL client.
        
        Args:
            api_key: Your KirokuForms API key
            base_url: The KirokuForms MCP API base URL
            webhook_url: Optional URL for webhook notifications
            webhook_secret: Secret for webhook verification
        """
        self.api_key = api_key
        self.base_url = base_url
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make an API request to KirokuForms."""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data
        )
        
        try:
            result = response.json()
            if not result.get("success", False):
                error = result.get("error", {})
                raise ValueError(f"API Error: {error.get('message', 'Unknown error')}")
            return result.get("data", {})
        except json.JSONDecodeError:
            raise ValueError(f"Invalid response from API: {response.text}")
    
    def create_task(
        self,
        title: str,
        description: str = "",
        fields: List[Dict[str, Any]] = [],
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
            fields: Form fields configuration
            expiration: Expiration time (e.g., "24h", "7d")
            priority: Task priority ("low", "medium", "high")
            task_id: Optional custom task ID
            callback_url: URL to notify when task is completed
            
        Returns:
            Task information including ID and form URL
        """
        data = {
            "title": title,
            "description": description,
            "fields": fields,
            "settings": {
                "expiration": expiration,
                "priority": priority,
                "taskId": task_id,
                "callbackUrl": callback_url or self.webhook_url
            }
        }
        
        return self._request("POST", "tools/hitl/requestInput", data)
    
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
        
        return self.create_task(title, description, fields, **kwargs)
    
    def get_task_result(self, task_id: str, wait: bool = True, timeout: int = 3600) -> Dict:
        """
        Get the result of a HITL task.
        
        Args:
            task_id: Task ID to retrieve
            wait: Whether to wait for the result if not available
            timeout: Maximum time to wait in seconds
            
        Returns:
            Task result data
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
        
        # Wait for the task to be completed (blocking)
        result = client.get_task_result(task["taskId"])
        
        # Update the state with the result
        return {
            **state,
            "human_verification": {
                "completed": True,
                "task_id": task["taskId"],
                "result": result
            }
        }
    
    return interrupt_handler