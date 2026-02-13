"""Application configuration using Pydantic Settings"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # MongoDB Configuration
    mongodb_uri: str = Field(default="mongodb://localhost:27017/", env="MONGODB_URI")
    mongodb_db_name: str = Field(default="rag_chatbot", env="MONGODB_DB_NAME")
    mongodb_collection: str = Field(default="checkpoints", env="MONGODB_COLLECTION")
    
    # LLM Configuration
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    groq_model: str = Field(default="gpt-oss-120b", env="GROQ_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5:1.7b", env="OLLAMA_MODEL")
    default_llm_provider: Literal["groq", "ollama"] = Field(default="groq", env="DEFAULT_LLM_PROVIDER")
    
    # ChromaDB Configuration
    chroma_persist_directory: str = Field(default="./chroma_db", env="CHROMA_PERSIST_DIRECTORY")
    chroma_collection_name: str = Field(default="dropshipping_docs", env="CHROMA_COLLECTION_NAME")
    
    # Embedding Model
    embedding_model: str = Field(default="all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    
    # Document Processing
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    max_upload_size_mb: int = Field(default=50, env="MAX_UPLOAD_SIZE_MB")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_reload: bool = Field(default=True, env="API_RELOAD")
    
    # Retrieval Configuration
    top_k_results: int = Field(default=5, env="TOP_K_RESULTS")
    similarity_threshold: float = Field(default=0.7, env="SIMILARITY_THRESHOLD")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
