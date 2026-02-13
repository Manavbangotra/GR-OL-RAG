"""ChromaDB vector store operations"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path

from app.config import settings
from app.utils.embeddings import get_embedding_generator
from app.services.document_processor import DocumentChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB vector store for document embeddings"""
    
    def __init__(self):
        """Initialize ChromaDB client and collection"""
        self.persist_directory = settings.chroma_persist_directory
        self.collection_name = settings.chroma_collection_name
        
        # Create persist directory if it doesn't exist
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Dropshipping and Service Points documents"}
        )
        
        # Get embedding generator
        self.embedding_generator = get_embedding_generator()
        
        logger.info(f"Initialized ChromaDB collection: {self.collection_name}")
    
    def add_documents(
        self,
        chunks: List[DocumentChunk]
    ) -> int:
        """Add document chunks to the vector store
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
        
        # Prepare data for ChromaDB
        ids = []
        documents = []
        metadatas = []
        
        for chunk in chunks:
            # Create unique ID
            chunk_id = f"{chunk.metadata.get('filename', 'unknown')}_{chunk.chunk_id}"
            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append(chunk.metadata)
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(documents)} chunks...")
        embeddings = self.embedding_generator.generate_embeddings(documents)
        
        # Add to collection
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(chunks)} chunks to vector store")
        return len(chunks)
    
    def search(
        self,
        query: str,
        top_k: int = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Semantic search in the vector store
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of search results with content, metadata, and scores
        """
        if top_k is None:
            top_k = settings.top_k_results
        
        # Generate query embedding
        query_embedding = self.embedding_generator.generate_embedding(query)
        
        # Search in collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        formatted_results = []
        
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                # ChromaDB returns distances (lower is better)
                # Convert to similarity score (higher is better)
                distance = results['distances'][0][i]
                similarity = 1 / (1 + distance)  # Convert distance to similarity
                
                formatted_results.append({
                    "content": doc,
                    "metadata": results['metadatas'][0][i],
                    "score": similarity
                })
        
        logger.info(f"Search returned {len(formatted_results)} results")
        return formatted_results
    
    def delete_by_filename(self, filename: str) -> int:
        """Delete all chunks from a specific file
        
        Args:
            filename: Name of the file to delete
            
        Returns:
            Number of chunks deleted
        """
        # Get all documents with this filename
        results = self.collection.get(
            where={"filename": filename}
        )
        
        if results['ids']:
            self.collection.delete(ids=results['ids'])
            logger.info(f"Deleted {len(results['ids'])} chunks from {filename}")
            return len(results['ids'])
        
        return 0
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection
        
        Returns:
            Dictionary with collection statistics
        """
        count = self.collection.count()
        
        return {
            "collection_name": self.collection_name,
            "total_chunks": count,
            "persist_directory": self.persist_directory
        }
    
    def reset_collection(self):
        """Delete all documents from the collection"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Dropshipping and Service Points documents"}
        )
        logger.warning(f"Reset collection: {self.collection_name}")


# Global vector store instance
_vector_store = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance
    
    Returns:
        VectorStore instance
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
