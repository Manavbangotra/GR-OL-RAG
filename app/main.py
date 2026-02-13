"""FastAPI application for RAG chatbot"""

# IMPORTANT: Fix SQLite3 version for ChromaDB compatibility
# This must be imported BEFORE any chromadb imports
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import logging
import shutil
from datetime import datetime
from typing import Optional

from app.config import settings
from app.models.schemas import (
    DocumentUploadResponse,
    QueryRequest,
    QueryResponse,
    ConversationHistory,
    ConversationMessage,
    HealthCheck
)
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import get_vector_store
from app.services.rag_workflow import get_rag_workflow
from app.checkpointer.mongo_checkpointer import get_checkpointer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="RAG Chatbot API",
    description="Dropshipping & Service Points RAG Chatbot with LangGraph",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create documents directory
DOCUMENTS_DIR = Path("./documents")
DOCUMENTS_DIR.mkdir(exist_ok=True)

# Initialize services
vector_store = None
checkpointer = None
rag_workflow = None
document_processor = DocumentProcessor()


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global vector_store, checkpointer, rag_workflow
    
    logger.info("Starting RAG Chatbot API...")
    
    try:
        # Initialize vector store
        vector_store = get_vector_store()
        logger.info("✓ Vector store initialized")
        
        # Initialize checkpointer
        checkpointer = get_checkpointer()
        logger.info("✓ MongoDB checkpointer initialized")
        
        # Initialize RAG workflow
        rag_workflow = get_rag_workflow(checkpointer=checkpointer)
        logger.info("✓ RAG workflow initialized")
        
        logger.info("🚀 RAG Chatbot API ready!")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down RAG Chatbot API...")
    
    if checkpointer:
        checkpointer.close()
    
    logger.info("✓ Shutdown complete")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "RAG Chatbot API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthCheck, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    services = {}
    details = {}
    
    # Check ChromaDB
    try:
        stats = vector_store.get_collection_stats()
        services["chromadb"] = True
        details["chromadb"] = stats
    except Exception as e:
        services["chromadb"] = False
        details["chromadb_error"] = str(e)
    
    # Check MongoDB
    try:
        checkpointer.client.admin.command('ping')
        services["mongodb"] = True
    except Exception as e:
        services["mongodb"] = False
        details["mongodb_error"] = str(e)
    
    # Check LLM
    try:
        # Simple check - just verify service is initialized
        services["llm"] = rag_workflow is not None
    except Exception as e:
        services["llm"] = False
        details["llm_error"] = str(e)
    
    # Overall status
    all_healthy = all(services.values())
    status_str = "healthy" if all_healthy else "degraded"
    
    return HealthCheck(
        status=status_str,
        services=services,
        details=details
    )


@app.post("/upload", response_model=DocumentUploadResponse, tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document
    
    Supported formats: PDF, TXT, DOCX, MD
    """
    try:
        # Validate file type
        allowed_extensions = {'.pdf', '.txt', '.docx', '.md'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. Allowed: {allowed_extensions}"
            )
        
        # Check file size
        max_size = settings.max_upload_size_mb * 1024 * 1024  # Convert to bytes
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {settings.max_upload_size_mb}MB"
            )
        
        # Save file
        file_path = DOCUMENTS_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Saved file: {file.filename}")
        
        # Process document
        chunks = document_processor.process_document(str(file_path))
        
        # Add to vector store
        chunks_added = vector_store.add_documents(chunks)
        
        logger.info(f"Added {chunks_added} chunks to vector store")
        
        return DocumentUploadResponse(
            success=True,
            message="Document uploaded and processed successfully",
            filename=file.filename,
            chunks_created=chunks_added,
            document_id=file.filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )


@app.post("/query", response_model=QueryResponse, tags=["Chat"])
async def query_chatbot(request: QueryRequest):
    """Query the RAG chatbot
    
    Performs semantic search and generates an answer using LLM
    """
    try:
        # Run RAG workflow
        result = rag_workflow.run(
            query=request.query,
            thread_id=request.thread_id,
            llm_provider=request.llm_provider,
            top_k=request.top_k or settings.top_k_results
        )
        
        # Format response
        response = QueryResponse(
            query=result["query"],
            answer=result["answer"],
            confidence=result["confidence"],
            sources=result["sources"],
            thread_id=result["thread_id"]
        )
        
        logger.info(f"Query processed: {request.query[:50]}... (confidence: {result['confidence']})")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


@app.get("/history/{thread_id}", response_model=ConversationHistory, tags=["Chat"])
async def get_conversation_history(thread_id: str):
    """Get conversation history for a thread"""
    try:
        # Get messages from checkpointer
        messages_data = checkpointer.get_conversation_history(thread_id)
        
        # Format messages
        messages = []
        for msg in messages_data:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append(ConversationMessage(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=datetime.utcnow()
                ))
        
        return ConversationHistory(
            thread_id=thread_id,
            messages=messages,
            total_messages=len(messages)
        )
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving history: {str(e)}"
        )


@app.delete("/history/{thread_id}", tags=["Chat"])
async def delete_conversation(thread_id: str):
    """Delete conversation history for a thread"""
    try:
        deleted_count = checkpointer.delete_thread(thread_id)
        
        return {
            "success": True,
            "message": f"Deleted {deleted_count} checkpoints for thread {thread_id}",
            "thread_id": thread_id,
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting conversation: {str(e)}"
        )


@app.get("/stats", tags=["Admin"])
async def get_stats():
    """Get system statistics"""
    try:
        vector_stats = vector_store.get_collection_stats()
        
        return {
            "vector_store": vector_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting stats: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload
    )
