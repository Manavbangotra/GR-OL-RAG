"""Embedding generation utilities"""

from sentence_transformers import SentenceTransformer
from typing import List, Union
import numpy as np
from app.config import settings


class EmbeddingGenerator:
    """Generate embeddings using sentence-transformers"""
    
    def __init__(self, model_name: str = None):
        """Initialize the embedding model
        
        Args:
            model_name: Name of the sentence-transformer model
        """
        self.model_name = model_name or settings.embedding_model
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text
        
        Args:
            text: Input text
            
        Returns:
            List of floats representing the embedding
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts
            batch_size: Batch size for processing
            
        Returns:
            List of embeddings
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=True
        )
        return embeddings.tolist()
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings
        
        Returns:
            Embedding dimension
        """
        return self.embedding_dim


# Global embedding generator instance
_embedding_generator = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get or create the global embedding generator instance
    
    Returns:
        EmbeddingGenerator instance
    """
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator
