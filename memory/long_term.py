"""
Long-term memory using local persistent ChromaDB to save and retrieve past trip preferences.
"""
import chromadb
from typing import List, Optional
from logger.logging import get_logger

logger = get_logger(__name__)

class LongTermMemory:
    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initializes the ChromaDB persistent client."""
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name="trip_preferences")

    def save_preferences(
        self, 
        thread_id: str, 
        destination: str, 
        travel_style: str, 
        interests: List[str], 
        things_to_avoid: List[str], 
        budget: float, 
        duration: int
    ) -> None:
        """Saves a completed trip profile to memory."""
        document = (
            f"Destination: {destination}. Style: {travel_style}. "
            f"Interests: {', '.join(interests)}. Avoids: {', '.join(things_to_avoid)}. "
            f"Budget: {budget}. Duration: {duration} days."
        )
        try:
            # We use upsert to overwrite if thread_id already exists
            self.collection.upsert(
                documents=[document],
                metadatas=[{"thread_id": thread_id, "destination": destination}],
                ids=[thread_id]
            )
            logger.info(f"Saved long-term preferences for thread {thread_id}")
        except Exception as e:
            logger.error(f"Could not save to ChromaDB: {e}")

    def retrieve_past_trips(self, query: str, n_results: int = 2) -> str:
        """Retrieves semantic past trips to inform the preference extractor."""
        try:
            # Ensure there's something to retrieve
            if self.collection.count() == 0:
                return ""
                
            # Limit n_results to the total number of documents
            n_results = min(n_results, self.collection.count())
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            if results and results.get("documents") and len(results["documents"][0]) > 0:
                past_context = " | ".join(results["documents"][0])
                return f"Past trips suggest this user prefers: {past_context}"
        except Exception as e:
            logger.error(f"Error retrieving from ChromaDB: {e}")
        return ""
