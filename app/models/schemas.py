"""Pydantic models for API requests and responses"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    """Response for document upload"""
    success: bool
    message: str
    filename: str
    chunks_created: int
    document_id: Optional[str] = None


class QueryRequest(BaseModel):
    """Request model for chat queries"""
    query: str = Field(..., description="User query", min_length=1)
    thread_id: Optional[str] = Field(None, description="Conversation thread ID for memory")
    llm_provider: Optional[str] = Field(None, description="LLM provider: 'groq' or 'ollama'")
    top_k: Optional[int] = Field(None, description="Number of documents to retrieve", ge=1, le=20)


class SourceDocument(BaseModel):
    """Source document metadata"""
    content: str
    filename: str
    page: Optional[int] = None
    score: float


class StructuredAnswer(BaseModel):
    """Structured LLM answer"""
    answer: str = Field(..., description="The generated answer")
    confidence: float = Field(..., description="Confidence score between 0 and 1", ge=0, le=1)
    sources_used: List[str] = Field(default_factory=list, description="List of source filenames used")


class QueryResponse(BaseModel):
    """Response model for chat queries"""
    query: str
    answer: str
    confidence: float
    sources: List[SourceDocument]
    thread_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationMessage(BaseModel):
    """Single conversation message"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime


class ConversationHistory(BaseModel):
    """Conversation history response"""
    thread_id: str
    messages: List[ConversationMessage]
    total_messages: int


class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, bool] = Field(default_factory=dict)
    details: Optional[Dict[str, Any]] = None
