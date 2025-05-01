# LangGraph-KirokuForms Integration

**Human-in-the-Loop integration between LangGraph and KirokuForms**

This library provides a seamless integration for Human-in-the-Loop (HITL) capabilities in LangGraph workflows using KirokuForms as the interface for human review tasks.

## Installation

```bash
pip install langgraph-kirokuforms
```

## Quick Start

```python
from kirokuforms import KirokuFormsHITL, create_kiroku_interrupt_handler
from langgraph.graph import StateGraph

# Initialize the KirokuForms client
kiroku_client = KirokuFormsHITL(
    api_key="your-api-key",
    base_url="https://api.kirokuforms.com/mcp"
)

# Create a LangGraph interrupt handler
human_review = create_kiroku_interrupt_handler(
    api_key="your-api-key",
    base_url="https://api.kirokuforms.com/mcp"
)

# Example LangGraph node that requests human review
def request_verification(state):
    return human_review(state, {
        "title": "Verify Data",
        "description": "Please verify this information is correct",
        "data": {
            "customer_name": state["customer_name"],
            "purchase_amount": state["purchase_amount"],
            "shipping_address": state["shipping_address"]
        }
    })

# Use in a LangGraph workflow
workflow = StateGraph()
workflow.add_node("request_verification", request_verification)
# ... add other nodes and edges
```

## Features

- Create human review tasks with customizable forms
- Use existing form templates or generate dynamic forms
- Support for verification tasks with approve/reject decisions
- Wait for human input synchronously or asynchronously
- Full integration with LangGraph interrupt patterns
- Support for webhooks when tasks are completed

## Examples

See the [examples](./examples) directory for complete workflow examples.

## Development

### Setup for Development

1. Clone the repository
2. Install development dependencies: `pip install -e ".[dev]"`
3. Run tests: `pytest tests/`

### Testing with KirokuForms

To test with a running KirokuForms instance:

1. Set the API key and base URL in your environment:
   ```bash
   export KIROKU_API_KEY="your-api-key"
   export KIROKU_API_URL="http://localhost:4321/api/mcp"
   ```

2. Run the simple test script:
   ```bash
   python tests/simple_test.py
   ```

## License

MIT
