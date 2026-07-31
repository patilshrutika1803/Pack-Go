"""
Streaming utility for SSE (Server-Sent Events) formatting.
"""
import json
from typing import Any, Optional

def format_sse_event(status: str, agent: str, message: str, data: Optional[Any] = None) -> str:
    """
    Formats a dictionary of data into a Server-Sent Event string.
    
    Args:
        status: Current status (e.g., 'running', 'reflecting', 'done').
        agent: Name of the agent emitting the event.
        message: Human readable message describing the current action.
        data: Optional payload or partial result.
        
    Returns:
        A string formatted as a standard SSE event.
    """
    event_payload = {
        "status": status,
        "agent": agent,
        "message": message
    }
    
    if data is not None:
        # If data is a Pydantic model, convert to dict
        if hasattr(data, "model_dump"):
            event_payload["data"] = data.model_dump(mode="json")
        else:
            event_payload["data"] = data
            
    # Serialize to JSON, ensuring no newlines break the SSE format
    json_data = json.dumps(event_payload)
    
    return f"data: {json_data}\n\n"
