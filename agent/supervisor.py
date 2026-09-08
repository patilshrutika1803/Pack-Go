"""Supervisor intent classification and query initialization."""
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from logger.logging import get_logger
from models.schemas import SupervisorDecision
from prompt_library.supervisor_prompt import SYSTEM_PROMPT
from utils.llm_loader import build_structured_output, invoke_with_fallback

logger = get_logger(__name__)


def supervisor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the query and classify it with structured LLM output."""
    logger.info("Supervisor: extracting query and classifying intent.")

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

    try:
        decision = invoke_with_fallback(
            lambda llm: build_structured_output(llm, SupervisorDecision),
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)],
        )
        intent = decision.intent if hasattr(decision, "intent") else decision["intent"]
    except Exception as exc:
        logger.error("Supervisor intent classification failed: %s", exc)
        intent = "plan_trip"

    logger.info("Supervisor: intent = '%s'", intent)
    return {"query": query, "intent": intent, "completed_agents": ["Supervisor"]}
