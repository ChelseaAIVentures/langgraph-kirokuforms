import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import requests

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
        max_retries: int = 3,
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
        self.base_url = base_url.rstrip("/")
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.timeout = timeout
        self.max_retries = max_retries

        logger.debug(f"Initializing KirokuFormsHITL client with URL: {self.base_url}")

    def _request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
        url = f"{self.base_url}/{endpoint}".rstrip("/")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"Making {method} request to {url}")

        retries = 0
        while retries <= self.max_retries:
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                try:
                    result = response.json()
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON response: {response.text}")
                    raise ValueError(f"Invalid response from API: {response.text}")

                if not result.get("success", False):
                    error = result.get("error", {})
                    msg = error.get("message", "Unknown error")
                    code = error.get("code", "UNKNOWN_ERROR")
                    logger.error(f"API Error {code}: {msg}")
                    raise ValueError(f"API Error ({code}): {msg}")

                return result.get("data", {})

            except requests.exceptions.RequestException as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(
                        f"Request failed after {self.max_retries} retries: {e}"
                    )
                    raise ConnectionError(f"Failed to connect to KirokuForms API: {e}")

                wait = 2**retries + (time.time() % 1)
                logger.warning(f"Request failed, retrying in {wait:.2f} seconds...")
                time.sleep(wait)

    def create_task(
        self,
        title: str,
        description: str = "",
        fields: Optional[List[Dict[str, Any]]] = None,
        template_id: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None,
        expiration: Optional[str] = None,
        priority: str = "medium",
        task_id: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a human-in-the-loop task.
        """
        if fields is None and template_id is None:
            raise ValueError("Either fields or template_id must be provided")

        payload: Dict[str, Any] = {
            "title": title,
            "description": description,
            "initialData": initial_data or {},
            "settings": {
                "expiration": expiration,
                "priority": priority,
                "taskId": task_id,
                "callbackUrl": callback_url or self.webhook_url,
            },
        }

        if template_id:
            payload["templateId"] = template_id
            if fields:
                payload["fields"] = fields
        elif fields:
            if not fields:
                raise ValueError(
                    "At least one field is required when not using a template"
                )
            payload["fields"] = fields

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        payload["settings"] = {
            k: v for k, v in payload["settings"].items() if v is not None
        }

        return self._request("POST", "tools/request-human-review", payload)

    def create_verification_task(
        self,
        title: str,
        description: str,
        data: Dict[str, Any],
        fields: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a verification task with data to be verified.
        """
        if fields is None:
            fields = []
            for key, value in data.items():
                field_type = (
                    "radio"
                    if isinstance(value, bool)
                    else "number"
                    if isinstance(value, (int, float))
                    else "text"
                )
                base = {
                    "type": field_type,
                    "label": key.replace("_", " ").title(),
                    "name": key,
                    "required": True,
                    "defaultValue": str(value).lower()
                    if field_type == "radio"
                    else str(value),
                }
                if field_type == "radio":
                    base["options"] = [
                        {"label": "True", "value": "true"},
                        {"label": "False", "value": "false"},
                    ]
                fields.append(base)

            fields.extend(
                [
                    {
                        "type": "radio",
                        "label": "Is this information correct?",
                        "name": "is_correct",
                        "required": True,
                        "options": [
                            {"label": "Yes", "value": "yes"},
                            {"label": "No", "value": "no"},
                        ],
                    },
                    {
                        "type": "textarea",
                        "label": "Comments or Corrections",
                        "name": "comments",
                        "required": False,
                    },
                ]
            )

        return self.create_task(title, description, fields=fields, **kwargs)

    def get_task_result(
        self, task_id: str, wait: bool = True, timeout: int = 3600
    ) -> Dict[str, Any]:
        """
        Get the result (form data) of a HITL task.
        """
        endpoint = f"resources/hitl/tasks/{task_id}"
        start = time.time()

        while True:
            result = self._request("GET", endpoint)
            print(f"DEBUG - Raw API response: {json.dumps(result, indent=2)}")
            status = result.get("status")
            if status == "completed":
                # Extract submission data directly from the top-level result
                submission = result.get("submission", {})
                form_data = submission.get("data", {})
                logger.debug(
                    f"Task {task_id} completed. Returning form data: {form_data}"
                )
                return form_data

            if not wait or time.time() - start > timeout:
                final = self._request("GET", endpoint)
                raise TimeoutError(
                    f"Task {task_id} not completed within timeout. "
                    f"Final status: {final.get('status', 'unknown')}"
                )

            logger.debug(f"Task {task_id} status is {status}. Waiting...")
            time.sleep(5)

    def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List HITL tasks.
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        query = "&".join(f"{k}={v}" for k, v in params.items())
        endpoint = f"resources/hitl/tasks?{query}"
        return self._request("GET", endpoint)

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a pending HITL task.
        """
        return self._request("POST", f"resources/hitl/tasks/{task_id}/cancel")


def create_kiroku_interrupt_handler(
    api_key: str, **kwargs: Any
) -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """
    Create a LangGraph interrupt handler for KirokuForms.
    """
    client = KirokuFormsHITL(api_key, **kwargs)

    def interrupt_handler(
        state: Dict[str, Any], interrupt_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        title = interrupt_data.get("title", "Human Verification Required")
        description = interrupt_data.get(
            "description", "Please verify the following information"
        )
        fields = interrupt_data.get("fields", [])
        data = interrupt_data.get("data", {})
        wait_for_result = interrupt_data.get("wait_for_result", True)

        if not fields and data:
            task = client.create_verification_task(
                title=title,
                description=description,
                data=data,
            )
        else:
            task = client.create_task(
                title=title,
                description=description,
                fields=fields,
            )

        result = {
            **state,
            "human_verification": {
                "completed": False,
                "task_id": task.get("taskId"),
                "form_url": task.get("formUrl"),
                "result": None,
            },
        }

        if wait_for_result:
            try:
                submission = client.get_task_result(task["taskId"])
                result["human_verification"]["completed"] = True
                result["human_verification"]["result"] = submission
            except TimeoutError:
                logger.warning(f"Task {task['taskId']} not completed within timeout")

        return result

    return interrupt_handler
