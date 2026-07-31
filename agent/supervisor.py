"""
Supervisor agent — single-pass, runs ONCE at workflow start.

In the new linear pipeline the Supervisor does NOT route between agents.
Its only job is to extract the user's query from the messages list
and store it in state so downstream agents can read it via state['query'].
"""
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage
from logger.logging import get_logger

logger = get_logger(__name__)


def supervisor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts the user query from state['messages'] and stores it as state['query'].
    Returns immediately — no LLM call, no routing decision.
    The fixed pipeline handles sequencing: Supervisor → PE → Research → Weather → Budget → Itinerary → Critic.
    """
    logger.info("Supervisor: initializing workflow, extracting user query.")

    # Pull query from messages list (most recent HumanMessage)
    query = state.get("query", "").strip()
    if not query:
        messages: List = state.get("messages", [])
        for msg in reversed(messages):
            content = getattr(msg, "content", "") if hasattr(msg, "content") else str(msg)
            if content and content.strip():
                query = content.strip()
                logger.info("Supervisor: extracted query from messages list.")
                break

    if not query:
        logger.warning("Supervisor: no query found in state or messages.")

    logger.info(f"Supervisor: query = '{query[:80]}{'...' if len(query) > 80 else ''}'")
    return {"query": query}
