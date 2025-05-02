# LangGraph KirokuForms Integration

**Human-in-the-Loop integration between LangGraph and KirokuForms**

This library provides a seamless integration for Human-in-the-Loop (HITL) capabilities in LangGraph workflows using KirokuForms as the interface for human review tasks. It implements the Model Context Protocol (MCP) for standardized AI-human interaction.

## Installation

```bash
pip install langgraph-kirokuforms
```

## Quick Start

```python
from langgraph_kirokuforms import KirokuFormsHITL, create_kiroku_interrupt_handler
from langgraph.graph import StateGraph

# Initialize the KirokuForms client
kiroku_client = KirokuFormsHITL(
    api_key="your-api-key",
    base_url="https://www.kirokuforms.com/api/hitl"
)

# Create a LangGraph interrupt handler
human_review = create_kiroku_interrupt_handler(
    api_key="your-api-key",
    base_url="https://www.kirokuforms.com/api/hitl"
)

# Example LangGraph node that requests human review
def request_verification(state):
    # This will pause the workflow and create a task for human review
    return human_review(state, {
        "title": "Verify Data",
        "description": "Please verify this information is correct",
        "fields": [
            {
                "type": "text",
                "label": "Customer Name",
                "name": "customer_name",
                "required": True,
                "defaultValue": state["customer_name"]
            },
            {
                "type": "number",
                "label": "Purchase Amount",
                "name": "purchase_amount",
                "required": True,
                "defaultValue": state["purchase_amount"]
            },
            {
                "type": "textarea",
                "label": "Shipping Address",
                "name": "shipping_address",
                "required": True,
                "defaultValue": state["shipping_address"]
            },
            {
                "type": "radio",
                "label": "Information is Correct",
                "name": "is_correct",
                "required": True,
                "options": [
                    {"label": "Yes", "value": "yes"},
                    {"label": "No", "value": "no"}
                ]
            }
        ],
        "wait_for_completion": True  # Whether to wait synchronously
    })

# Use in a LangGraph workflow
workflow = StateGraph(channels=["human_review"])
workflow.add_node("request_verification", request_verification)
# ... add other nodes and edges
```

## Core Concepts

### Model Context Protocol (MCP)

KirokuForms implements the Model Context Protocol (MCP), a standardized interface for AI systems to request human input. This reduces integration complexity by providing a consistent way for LangGraph workflows to:

1. Request human review of specific data
2. Generate appropriate interfaces for human reviewers
3. Receive and process human feedback
4. Resume execution with that feedback

### Interrupt Handlers

The library provides interrupt handlers compatible with LangGraph's checkpointing system, allowing workflows to:

1. Pause execution when human input is needed
2. Store the current state
3. Resume execution when human input is provided
4. Branch flow based on human decisions

## API Reference

### `KirokuFormsHITL`

The main client class for interacting with KirokuForms' HITL API.

#### Constructor

```python
KirokuFormsHITL(
    api_key: str,
    base_url: str = "https://www.kirokuforms.com/api/hitl",
    webhook_url: Optional[str] = None,
    webhook_secret: Optional[str] = None,
    timeout: int = 10,
    max_retries: int = 3
)
```

- **api_key**: Your KirokuForms API key
- **base_url**: The KirokuForms API base URL
- **webhook_url**: Optional URL for webhook notifications
- **webhook_secret**: Secret for webhook verification
- **timeout**: Request timeout in seconds
- **max_retries**: Maximum number of retries for failed requests

#### Methods

##### `create_task`

```python
create_task(
    title: str,
    description: str = "",
    fields: Optional[List[Dict[str, Any]]] = None,
    template_id: Optional[str] = None,
    initial_data: Optional[Dict[str, Any]] = None,
    expiration: Optional[str] = None,
    priority: str = "medium",
    task_id: Optional[str] = None,
    callback_url: Optional[str] = None
) -> Dict[str, Any]
```

Creates a human-in-the-loop task.

- **title**: The title of the task
- **description**: Detailed instructions for the human reviewer
- **fields**: List of field definitions (see Field Types below)
- **template_id**: Optional template ID instead of fields
- **initial_data**: Pre-filled values for the form
- **expiration**: Time until task expires (e.g., "2h", "1d")
- **priority**: Task priority ("low", "medium", "high")
- **task_id**: Optional client-defined ID for the task
- **callback_url**: URL for webhook notification

Returns a dictionary containing:
- **taskId**: The external task ID
- **hitlTaskId**: The internal task ID
- **formId**: The ID of the generated form
- **formUrl**: The URL where the task can be viewed and completed

##### `create_verification_task`

```python
create_verification_task(
    title: str,
    description: str,
    data: Dict[str, Any],
    fields: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any
) -> Dict[str, Any]
```

Creates a verification task with data to be verified.

- **title**: The title of the task
- **description**: Detailed instructions for the human reviewer
- **data**: The data to be verified (automatically generates appropriate fields)
- **fields**: Optional custom fields (if not provided, generated from data)
- **kwargs**: Additional parameters passed to create_task

##### `get_task_result`

```python
get_task_result(
    task_id: str,
    wait: bool = True,
    timeout: int = 3600
) -> Dict[str, Any]
```

Gets the result (form data) of a HITL task.

- **task_id**: The ID of the task
- **wait**: Whether to wait for completion if task is pending
- **timeout**: Maximum time to wait in seconds

Returns the submitted form data when the task is completed.

##### `list_tasks`

```python
list_tasks(
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]
```

Lists HITL tasks.

- **status**: Filter by status ("pending", "completed", "cancelled", "expired")
- **limit**: Maximum number of tasks to return
- **offset**: Pagination offset

##### `cancel_task`

```python
cancel_task(
    task_id: str
) -> Dict[str, Any]
```

Cancels a pending HITL task.

- **task_id**: The ID of the task to cancel

### `create_kiroku_interrupt_handler`

```python
create_kiroku_interrupt_handler(
    api_key: str,
    **kwargs: Any
) -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
```

Creates a LangGraph interrupt handler for KirokuForms.

- **api_key**: Your KirokuForms API key
- **kwargs**: Additional parameters passed to the KirokuFormsHITL constructor

Returns a function that can be used as an interrupt handler in LangGraph.

## Field Types

The library supports the following field types for form generation:

| Type | Description | Properties |
|------|-------------|------------|
| `text` | Single-line text input | label, name, required, defaultValue, placeholder, validation |
| `textarea` | Multi-line text input | label, name, required, defaultValue, placeholder, rows, validation |
| `number` | Numeric input | label, name, required, defaultValue, min, max, step, validation |
| `email` | Email input with validation | label, name, required, defaultValue, placeholder, validation |
| `select` | Dropdown selection | label, name, required, defaultValue, options, validation |
| `radio` | Radio button group | label, name, required, defaultValue, options, validation |
| `checkbox` | Checkbox or checkbox group | label, name, required, defaultValue, options, validation |
| `date` | Date picker | label, name, required, defaultValue, min, max, validation |

## Examples

### Basic Verification Task

```python
from langgraph_kirokuforms import KirokuFormsHITL
from langgraph.graph import StateGraph

# Initialize client
client = KirokuFormsHITL(
    api_key="your-api-key",
    base_url="https://www.kirokuforms.com/api/hitl"
)

# Create a simple verification task
response = client.create_task(
    title="Verify Transaction",
    description="Please review this transaction for approval",
    fields=[
        {
            "type": "text",
            "label": "Transaction ID",
            "name": "transaction_id",
            "required": True,
            "defaultValue": "TRX-12345"
        },
        {
            "type": "number",
            "label": "Amount",
            "name": "amount",
            "required": True,
            "defaultValue": 1245.00
        },
        {
            "type": "text",
            "label": "Recipient",
            "name": "recipient",
            "required": True,
            "defaultValue": "Acme Corp"
        },
        {
            "type": "radio",
            "label": "Approve Transaction?",
            "name": "approved",
            "required": True,
            "options": [
                {"label": "Approve", "value": "approve"},
                {"label": "Reject", "value": "reject"}
            ]
        }
    ]
)

# Get task URL to share with reviewer
review_url = response["formUrl"]
print(f"Review this transaction at: {review_url}")

# Check task status
task_id = response["taskId"]
status = client.get_task_status(task_id)
print(f"Task status: {status['status']}")

# Wait for task completion (blocking)
result = client.wait_for_task_completion(task_id, timeout=3600)
print(f"Verification result: {result}")
```

### Asynchronous Workflow with Webhook

```python
from langgraph_kirokuforms import create_kiroku_interrupt_handler
from langgraph.graph import StateGraph

# Create interrupt handler with webhook configuration
human_review = create_kiroku_interrupt_handler(
    api_key="your-api-key",
    base_url="https://www.kirokuforms.com/api/hitl",
    webhook_url="https://your-server.com/webhook/langgraph",
    webhook_secret="your-webhook-secret"
)

# Define nodes
def process_data(state):
    # Process data logic
    return {"processed_data": state["input_data"]}

def request_human_review(state):
    # This creates a task and returns immediately with checkpoint data
    return human_review(state, {
        "title": "Review Generated Content",
        "description": "Please review the following content for accuracy and quality",
        "wait_for_completion": False,  # Don't block execution
        "fields": [
            {
                "type": "textarea",
                "label": "Generated Content",
                "name": "content",
                "required": True,
                "defaultValue": state["processed_data"]
            },
            {
                "type": "radio",
                "label": "Content Quality",
                "name": "quality",
                "required": True,
                "options": [
                    {"label": "Excellent", "value": "excellent"},
                    {"label": "Good", "value": "good"},
                    {"label": "Needs Improvement", "value": "needs_improvement"},
                    {"label": "Poor", "value": "poor"}
                ]
            },
            {
                "type": "textarea",
                "label": "Suggested Improvements",
                "name": "improvements",
                "required": False
            }
        ]
    })

def handle_approved(state):
    # Logic for approved review
    return {"status": "approved", "final_data": state["human_input"]}

def handle_rejected(state):
    # Logic for rejected review
    return {"status": "rejected", "reason": state["human_input"]["improvements"]}

# Build graph
workflow = StateGraph(channels=["human_review"])
workflow.add_node("process_data", process_data)
workflow.add_node("request_review", request_human_review)
workflow.add_node("handle_approved", handle_approved)
workflow.add_node("handle_rejected", handle_rejected)

# Add edges
workflow.add_edge("process_data", "request_review")
workflow.add_conditional_edges(
    "request_review",
    lambda state: "approved" if state["human_input"]["quality"] in ["excellent", "good"] else "rejected",
    {
        "approved": "handle_approved",
        "rejected": "handle_rejected"
    }
)

# Create app
app = workflow.compile()
```

## Development

### Setup for Development

1. Clone the repository
   ```bash
   git clone https://github.com/kirokuforms/langgraph-kirokuforms.git
   cd langgraph-kirokuforms
   ```

2. Install development dependencies
   ```bash
   pip install -e ".[dev]"
   ```

3. Run tests
   ```bash
   pytest tests/
   ```

### Testing with KirokuForms

To test with a running KirokuForms instance:

1. Set the API key and base URL in your environment:
   ```bash
   export KIROKU_API_KEY="your-api-key"
   export KIROKU_API_URL="https://www.kirokuforms.com/api/hitl"
   ```

2. Run the simple test script:
   ```bash
   python tests/simple_test.py
   ```

## Troubleshooting

### Common Issues

- **Authentication Errors**: Ensure your API key is correct and has appropriate permissions
- **Task Creation Failing**: Verify that all required fields are provided in the correct format
- **Webhook Not Triggering**: Check webhook URL accessibility and secret configuration
- **Form Not Displaying**: Ensure field definitions are correctly formatted or template_id exists

For more detailed troubleshooting, see our [troubleshooting guide](https://docs.kirokuforms.com/docs/mcp/tools/hitl).

## License

MIT
