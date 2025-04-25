# KirokuForms Integration for LangGraph

This package provides a seamless integration between KirokuForms and LangGraph for human-in-the-loop AI workflows.

## Installation

```bash
pip install langgraph-kirokuforms


## Usage

```python
from langgraph.graph import StateGraph
from kirokuforms import KirokuFormsHITL, create_kiroku_interrupt_handler

# Initialize KirokuForms client
client = KirokuFormsHITL(api_key="your_api_key")

# Create a human verification task
result = client.create_verification_task(
    title="Verify Data",
    description="Please verify this information is correct",
    data={"company": "Acme Corp", "revenue": 1500000}
)

# Or use with LangGraph interrupts
interrupt_handler = create_kiroku_interrupt_handler(api_key="your_api_key")

# Use in your LangGraph workflow
workflow = StateGraph()
# ... configure graph nodes and edges

app = workflow.compile(
    interrupt_before=["process_data"],
    interrupt_handlers={"human_verification": interrupt_handler}
)
```

See the [full documentation](https://kirokuforms.com/docs/langgraph) for more details
