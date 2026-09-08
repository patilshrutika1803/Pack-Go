"""
Short-term memory management for PACK & GO.
Handles conversation and agent state persistence across sessions using LangGraph's MemorySaver.
"""
import uuid
from typing import Dict, Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from logger.logging import get_logger

logger = get_logger(__name__)

CHECKPOINT_ALLOWED_TYPES = [
    ("models.schemas", "SupervisorDecision"),
    ("models.schemas", "UserPreferences"),
    ("models.schemas", "Place"),
    ("models.schemas", "Restaurant"),
    ("models.schemas", "Hotel"),
    ("models.schemas", "WeatherInfo"),
    ("models.schemas", "CategoryCost"),
    ("models.schemas", "BudgetBreakdown"),
    ("models.schemas", "MealInfo"),
    ("models.schemas", "AttractionVisit"),
    ("models.schemas", "Transport"),
    ("models.schemas", "DayPlan"),
    ("models.schemas", "CriticReview"),
    ("models.schemas", "RevisionRecord"),
    ("models.schemas", "TravelPlan"),
]

class ShortTermMemoryManager:
    """
    Manages short-term memory checkpointers for the LangGraph workflow.
    Ensures that conversation states are persisted correctly based on thread_ids,
    allowing users to send follow-up messages and refine their travel plans.
    """
    
    def __init__(self):
        """
        Initializes the in-memory checkpointer. 
        For a production multi-node environment, this should be backed by RedisSaver or PostgresSaver,
        but we use MemorySaver for local state persistence across async requests.
        """
        self.checkpointer = MemorySaver(
            serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_ALLOWED_TYPES)
        )
        logger.info("Initialized LangGraph MemorySaver for short-term session state.")
        
    def get_checkpointer(self) -> MemorySaver:
        """
        Returns the active checkpointer instance to be passed to the compiled graph.
        """
        return self.checkpointer

    @staticmethod
    def create_thread_config(thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates the LangGraph config dictionary required for the checkpointer to 
        save and load states properly.
        
        Args:
            thread_id: An optional string representing the unique session ID.
                       If None or empty, a new UUID4 will be generated.
                       
        Returns:
            A dictionary containing the 'configurable' key with 'thread_id'.
        """
        if not thread_id:
            thread_id = str(uuid.uuid4())
            logger.debug(f"Generated new thread_id: {thread_id}")
        else:
            logger.debug(f"Reusing existing thread_id: {thread_id}")
            
        return {
            "configurable": {
                "thread_id": thread_id
            }
        }

# Global singleton instance of the checkpointer to be reused across FastAPI requests
_memory_manager_instance = ShortTermMemoryManager()

def get_checkpointer() -> MemorySaver:
    """
    Utility function to retrieve the singleton MemorySaver instance.
    This instance MUST be shared across requests so that thread_ids can resolve to the same memory block.
    """
    return _memory_manager_instance.get_checkpointer()

def get_thread_config(thread_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Utility function to generate the appropriate thread config for a request.
    """
    return ShortTermMemoryManager.create_thread_config(thread_id)
