"""MongoDB checkpointer for LangGraph conversation memory (async with Motor)"""

from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class MongoDBCheckpointer:
    """Async MongoDB-based checkpointer using Motor driver"""

    def __init__(
        self,
        mongodb_uri: str = None,
        db_name: str = None,
        collection_name: str = None
    ):
        self.mongodb_uri = mongodb_uri or settings.mongodb_uri
        self.db_name = db_name or settings.mongodb_db_name
        self.collection_name = collection_name or settings.mongodb_collection

        # Async Motor client
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.collection_name]

        self._indexes_created = False
        logger.info(f"Initialized async MongoDB checkpointer: {self.db_name}.{self.collection_name}")

    async def _ensure_indexes(self):
        """Create indexes once (idempotent)."""
        if self._indexes_created:
            return
        await self.collection.create_index("thread_id")
        await self.collection.create_index([("thread_id", 1), ("timestamp", -1)])
        await self.collection.create_index([("user_id", 1), ("timestamp", -1)])
        self._indexes_created = True

    async def save_state(
        self,
        thread_id: str,
        state: Dict[str, Any],
        user_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        """Save state as structured JSON (no pickle)."""
        try:
            await self._ensure_indexes()

            doc = {
                "thread_id": thread_id,
                "query": state.get("query", ""),
                "answer": state.get("answer", {}),
                "context": state.get("context", ""),
                "conversation_history": state.get("conversation_history", []),
                "llm_provider": state.get("llm_provider"),
                "top_k": state.get("top_k", 5),
                "timestamp": datetime.utcnow(),
            }

            set_on_insert = {}
            if user_id:
                set_on_insert["user_id"] = user_id
            if title:
                set_on_insert["title"] = title

            update = {"$set": doc}
            if set_on_insert:
                update["$setOnInsert"] = set_on_insert

            await self.collection.update_one(
                {"thread_id": thread_id},
                update,
                upsert=True
            )

            logger.debug(f"Saved state for thread: {thread_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving state: {e}")
            return False

    async def load_state(
        self,
        thread_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load state as structured JSON (no pickle)."""
        try:
            doc = await self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("timestamp", -1)]
            )

            if doc:
                return {
                    "query": doc.get("query", ""),
                    "answer": doc.get("answer", {}),
                    "context": doc.get("context", ""),
                    "conversation_history": doc.get("conversation_history", []),
                    "llm_provider": doc.get("llm_provider"),
                    "top_k": doc.get("top_k", 5),
                    "thread_id": thread_id,
                    "retrieved_docs": [],
                }

            return None

        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return None

    async def get_conversation_history(self, thread_id: str) -> list:
        """Get conversation history for a thread."""
        try:
            doc = await self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("timestamp", -1)]
            )

            if doc and "conversation_history" in doc:
                return doc["conversation_history"]

            return []

        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

    async def get_user_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all conversations belonging to a user, most recent first."""
        try:
            await self._ensure_indexes()
            cursor = self.collection.find(
                {"user_id": user_id},
                {"thread_id": 1, "title": 1, "timestamp": 1, "conversation_history": 1, "_id": 0},
            ).sort("timestamp", DESCENDING)

            results = []
            async for doc in cursor:
                history = doc.get("conversation_history", [])
                results.append({
                    "thread_id": doc["thread_id"],
                    "title": doc.get("title", "New Chat"),
                    "timestamp": doc.get("timestamp", datetime.utcnow()).isoformat(),
                    "message_count": len(history),
                })
            return results
        except Exception as e:
            logger.error(f"Error getting user conversations: {e}")
            return []

    async def verify_thread_owner(self, thread_id: str, user_id: str) -> bool:
        """Check whether a thread belongs to a given user."""
        doc = await self.collection.find_one(
            {"thread_id": thread_id},
            {"user_id": 1, "_id": 0},
        )
        if not doc:
            return False
        return doc.get("user_id") == user_id

    async def rename_thread(self, thread_id: str, title: str) -> bool:
        """Update the title of a conversation thread."""
        result = await self.collection.update_one(
            {"thread_id": thread_id},
            {"$set": {"title": title}},
        )
        return result.modified_count > 0

    async def create_empty_thread(self, thread_id: str, user_id: str) -> bool:
        """Create an empty conversation thread for a user."""
        try:
            await self._ensure_indexes()
            doc = {
                "thread_id": thread_id,
                "user_id": user_id,
                "title": "New Chat",
                "timestamp": datetime.utcnow(),
                "conversation_history": [],
            }
            await self.collection.update_one(
                {"thread_id": thread_id},
                {"$setOnInsert": doc},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Error creating empty thread: {e}")
            return False

    async def delete_thread(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread."""
        result = await self.collection.delete_many({"thread_id": thread_id})
        logger.info(f"Deleted {result.deleted_count} checkpoints for thread: {thread_id}")
        return result.deleted_count

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")


# Global checkpointer instance
_checkpointer = None


def get_checkpointer() -> MongoDBCheckpointer:
    """Get or create the global checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MongoDBCheckpointer()
    return _checkpointer
