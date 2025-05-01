"""Example of using KirokuForms HITL with LangGraph.

This example demonstrates how to create a LangGraph workflow that
includes human-in-the-loop verification steps using KirokuForms.
"""

import os
import sys
import time
from typing import Dict, Any, List, Tuple, TypedDict, Annotated
from datetime import datetime

# Add the parent directory to path for importing the library
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the KirokuForms library
from kirokuforms import KirokuFormsHITL, create_kiroku_interrupt_handler

# Import LangGraph
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver
from langgraph.checkpoint.base import Checkpoint

# Your KirokuForms API key (replace with your own or use environment variable)
API_KEY = os.environ.get("KIROKU_API_KEY", "test-hitl-key-459dcc53-c26c-445b-84ff-bef3b167ba75")

# KirokuForms API URL (replace with your own if not using localhost)
API_URL = os.environ.get("KIROKU_API_URL", "http://localhost:4321/api/mcp")

# Define the state schema for TypeScript-like type safety
class WorkflowState(TypedDict):
    customer_name: str
    customer_email: str
    purchase_amount: float
    transaction_approved: bool
    risk_score: int
    transaction_id: str
    human_verification: Dict[str, Any]

# Initialize the KirokuForms client
kiroku_client = KirokuFormsHITL(
    api_key=API_KEY,
    base_url=API_URL
)

# Create the LangGraph interrupt handler
human_review = create_kiroku_interrupt_handler(
    api_key=API_KEY,
    base_url=API_URL
)

# Define workflow nodes
def process_transaction(state: Dict) -> Dict:
    """Process the transaction and calculate risk score."""
    print(f"Processing transaction for {state['customer_name']}...")
    
    # Simulate processing logic
    risk_score = 75 if state["purchase_amount"] > 1000 else 25
    transaction_id = f"TX-{int(time.time())}"
    
    # Update state
    return {
        **state,
        "risk_score": risk_score,
        "transaction_id": transaction_id
    }

def should_request_human_review(state: Dict) -> str:
    """Determine if human review is needed based on risk score."""
    print(f"Evaluating risk score: {state['risk_score']}...")
    
    if state["risk_score"] > 50:
        print("High risk transaction - requesting human review")
        return "request_human_review"
    else:
        print("Low risk transaction - auto-approving")
        return "auto_approve"

def request_human_review(state: Dict) -> Dict:
    """Request human review through KirokuForms."""
    print("Requesting human verification...")
    
    # Prepare data for human review
    verification_data = {
        "customer_name": state["customer_name"],
        "customer_email": state["customer_email"],
        "purchase_amount": state["purchase_amount"],
        "transaction_id": state["transaction_id"],
        "risk_score": state["risk_score"]
    }
    
    # Use the human_review interrupt handler to request verification
    updated_state = human_review(state, {
        "title": f"Verify High-Risk Transaction: {state['transaction_id']}",
        "description": "Please review this high-risk transaction and approve or reject it.",
        "data": verification_data
    })
    
    return updated_state

def determine_approval(state: Dict) -> str:
    """Determine if the transaction is approved based on human review."""
    print("Determining approval based on human review...")
    
    # Check if human verification was completed
    verification = state.get("human_verification", {})
    if not verification.get("completed", False):
        print("Human verification not completed - defaulting to rejection")
        return "reject"
    
    # Get the verification result
    result = verification.get("result", {})
    is_correct = result.get("is_correct", "no")
    
    if is_correct == "yes":
        print("Human verified transaction data as correct - approving")
        return "approve"
    else:
        print("Human rejected transaction data - rejecting")
        return "reject"

def auto_approve(state: Dict) -> Dict:
    """Auto-approve the transaction."""
    print(f"Auto-approving transaction {state['transaction_id']}...")
    
    return {
        **state,
        "transaction_approved": True
    }

def approve_transaction(state: Dict) -> Dict:
    """Approve the transaction after human review."""
    print(f"Human approved transaction {state['transaction_id']}...")
    
    return {
        **state,
        "transaction_approved": True
    }

def reject_transaction(state: Dict) -> Dict:
    """Reject the transaction."""
    print(f"Rejecting transaction {state['transaction_id']}...")
    
    return {
        **state,
        "transaction_approved": False
    }

def create_workflow() -> Tuple[StateGraph, Checkpoint]:
    """Create the transaction approval workflow with human-in-the-loop."""
    # Create the state graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("process_transaction", process_transaction)
    workflow.add_node("request_human_review", request_human_review)
    workflow.add_node("auto_approve", auto_approve)
    workflow.add_node("approve_transaction", approve_transaction)
    workflow.add_node("reject_transaction", reject_transaction)
    
    # Add edges
    workflow.add_conditional_edges(
        "process_transaction",
        should_request_human_review,
        {
            "request_human_review": "request_human_review",
            "auto_approve": "auto_approve"
        }
    )
    workflow.add_conditional_edges(
        "request_human_review",
        determine_approval,
        {
            "approve": "approve_transaction",
            "reject": "reject_transaction"
        }
    )
    
    # Set end nodes
    workflow.add_edge("auto_approve", END)
    workflow.add_edge("approve_transaction", END)
    workflow.add_edge("reject_transaction", END)
    
    # Create memory saver for state
    memory = MemorySaver()
    
    # Compile the workflow
    compiled_workflow = workflow.compile()
    
    return compiled_workflow, memory

def main():
    """Run an example transaction workflow."""
    # Create the workflow
    workflow, memory = create_workflow()
    
    # Create test transaction data
    transaction = {
        "customer_name": "John Doe",
        "customer_email": "john.doe@example.com",
        "purchase_amount": 1500.00,
        "transaction_approved": False,
        "risk_score": 0,
        "transaction_id": "",
        "human_verification": {}
    }
    
    # Run the workflow with checkpointing
    print("\n=== Starting Transaction Workflow ===\n")
    config = {"configurable": {"checkpoint": memory}}
    result = workflow.invoke(transaction, config=config)
    
    # Print the result
    print("\n=== Workflow Result ===\n")
    print(f"Transaction ID: {result['transaction_id']}")
    print(f"Customer: {result['customer_name']} ({result['customer_email']})")
    print(f"Amount: ${result['purchase_amount']:.2f}")
    print(f"Risk Score: {result['risk_score']}")
    print(f"Approved: {result['transaction_approved']}")
    
    if "human_verification" in result and result["human_verification"].get("completed"):
        print("\nHuman Verification Details:")
        print(f"  Task ID: {result['human_verification']['task_id']}")
        
        if result["human_verification"].get("result"):
            verification = result["human_verification"]["result"]
            print(f"  Is Correct: {verification.get('is_correct', 'N/A')}")
            print(f"  Comments: {verification.get('comments', 'N/A')}")
    
    print("\n=== Workflow Complete ===\n")

if __name__ == "__main__":
    main()