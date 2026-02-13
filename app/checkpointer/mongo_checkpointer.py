"""MongoDB checkpointer for LangGraph conversation memory"""

from typing import Optional, Dict, Any
from pymongo import MongoClient
import logging
import pickle
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class MongoDBCheckpointer:
    """MongoDB-based checkpointer for LangGraph state persistence"""
    
    def __init__(
        self,
        mongodb_uri: str = None,
        db_name: str = None,
        collection_name: str = None
    ):
        """Initialize MongoDB checkpointer
        
        Args:
            mongodb_uri: MongoDB connection URI
            db_name: Database name
            collection_name: Collection name for checkpoints
        """
        self.mongodb_uri = mongodb_uri or settings.mongodb_uri
        self.db_name = db_name or settings.mongodb_db_name
        self.collection_name = collection_name or settings.mongodb_collection
        
        # Connect to MongoDB
        self.client = MongoClient(self.mongodb_uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.collection_name]
        
        # Create index on thread_id for faster queries
        self.collection.create_index("thread_id")
        self.collection.create_index([("thread_id", 1), ("timestamp", -1)])
        
        logger.info(f"Initialized MongoDB checkpointer: {self.db_name}.{self.collection_name}")
    
    def save_state(
        self,
        thread_id: str,
        state: Dict[str, Any]
    ) -> bool:
        """Save state to MongoDB
        
        Args:
            thread_id: Thread identifier
            state: State dictionary to save
            
        Returns:
            True if successful
        """
        try:
            # Serialize state using pickle
            state_data = pickle.dumps(state)
            
            # Prepare document
            doc = {
                "thread_id": thread_id,
                "state": state_data,
                "timestamp": datetime.utcnow(),
                "conversation_history": state.get("conversation_history", [])
            }
            
            # Insert or update
            self.collection.update_one(
                {"thread_id": thread_id},
                {"$set": doc},
                upsert=True
            )
            
            logger.debug(f"Saved state for thread: {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            return False
    
    def load_state(
        self,
        thread_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load state from MongoDB
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            State dictionary or None
        """
        try:
            # Get latest state for thread
            doc = self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("timestamp", -1)]
            )
            
            if doc and "state" in doc:
                state = pickle.loads(doc["state"])
                logger.debug(f"Loaded state for thread: {thread_id}")
                return state
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return None
    
    def get_conversation_history(self, thread_id: str) -> list:
        """Get conversation history for a thread
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            List of conversation messages
        """
        try:
            doc = self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("timestamp", -1)]
            )
            
            if doc and "conversation_history" in doc:
                return doc["conversation_history"]
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    def delete_thread(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Number of checkpoints deleted
        """
        result = self.collection.delete_many({"thread_id": thread_id})
        logger.info(f"Deleted {result.deleted_count} checkpoints for thread: {thread_id}")
        return result.deleted_count
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")


# Global checkpointer instance
_checkpointer = None


def get_checkpointer() -> MongoDBCheckpointer:
    """Get or create the global checkpointer instance
    
    Returns:
        MongoDBCheckpointer instance
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MongoDBCheckpointer()
    return _checkpointer
