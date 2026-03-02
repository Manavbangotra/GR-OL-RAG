"""FastAPI application for RAG chatbot — Phase 1 optimized"""

# IMPORTANT: Fix SQLite3 version for ChromaDB compatibility
# This must be imported BEFORE any chromadb imports
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import asyncio
import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import (
    FastAPI, UploadFile, File, HTTPException, status,
    Depends, BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.models.schemas import (
    DocumentUploadResponse,
    QueryRequest,
    QueryResponse,
    ConversationHistory,
    ConversationMessage,
    HealthCheck,
)
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import get_vector_store
from app.services.rag_workflow import get_rag_workflow
from app.checkpointer.mongo_checkpointer import get_checkpointer
from app.auth.router import router as auth_router
from app.auth.service import get_auth_service
from app.auth.dependencies import get_current_user

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
    version="1.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
app.include_router(auth_router)

# Create documents directory
DOCUMENTS_DIR = Path("./documents")
DOCUMENTS_DIR.mkdir(exist_ok=True)

# Initialize services
vector_store = None
checkpointer = None
rag_workflow = None
document_processor = DocumentProcessor()

# Track background upload jobs
_upload_jobs: Dict[str, Dict[str, Any]] = {}


# -- Pydantic models for new endpoints --
class RenameRequest(BaseModel):
    title: str


class UploadStatusResponse(BaseModel):
    upload_id: str
    status: str  # "processing", "completed", "failed"
    filename: str
    chunks_created: Optional[int] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global vector_store, checkpointer, rag_workflow

    logger.info("Starting RAG Chatbot API...")

    try:
        vector_store = get_vector_store()
        logger.info("Vector store initialized")

        checkpointer = get_checkpointer()
        logger.info("MongoDB checkpointer initialized (async Motor)")

        rag_workflow = get_rag_workflow(checkpointer=checkpointer)
        logger.info("RAG workflow initialized")

        get_auth_service()
        logger.info("Auth service initialized")

        logger.info("RAG Chatbot API ready!")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down RAG Chatbot API...")

    if checkpointer:
        checkpointer.close()

    auth = get_auth_service()
    auth.close()

    logger.info("Shutdown complete")


# ─── Root & Health ──────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "RAG Chatbot API",
        "version": "1.1.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthCheck, tags=["Health"])
async def health_check():
    services = {}
    details = {}

    # Check ChromaDB (sync → thread)
    try:
        stats = await asyncio.to_thread(vector_store.get_collection_stats)
        services["chromadb"] = True
        details["chromadb"] = stats
    except Exception as e:
        services["chromadb"] = False
        details["chromadb_error"] = str(e)

    # Check MongoDB (async Motor)
    try:
        await checkpointer.client.admin.command('ping')
        services["mongodb"] = True
    except Exception as e:
        services["mongodb"] = False
        details["mongodb_error"] = str(e)

    # Check LLM
    services["llm"] = rag_workflow is not None

    all_healthy = all(services.values())
    status_str = "healthy" if all_healthy else "degraded"

    return HealthCheck(
        status=status_str,
        services=services,
        details=details
    )


# ─── Document Upload (Background Task) ─────────────────────────────────

def _process_upload_sync(upload_id: str, file_path: str, filename: str):
    """Background worker: chunk, embed, store. Runs in a thread."""
    try:
        _upload_jobs[upload_id]["status"] = "processing"

        chunks = document_processor.process_document(file_path)
        chunks_added = vector_store.add_documents(chunks)

        _upload_jobs[upload_id].update({
            "status": "completed",
            "chunks_created": chunks_added,
        })
        logger.info(f"[bg] Upload {upload_id}: {chunks_added} chunks from {filename}")

    except Exception as e:
        _upload_jobs[upload_id].update({
            "status": "failed",
            "error": str(e),
        })
        logger.error(f"[bg] Upload {upload_id} failed: {e}")


@app.post("/upload", tags=["Documents"])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
):
    """Upload a document — returns immediately, processes in background.

    Use GET /upload/{upload_id}/status to poll progress.
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.txt', '.docx', '.md'}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Allowed: {allowed_extensions}"
        )

    # Check file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB"
        )

    # Save file to disk
    file_path = DOCUMENTS_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    logger.info(f"Saved file: {file.filename}")

    # Create tracking entry
    upload_id = str(uuid.uuid4())
    _upload_jobs[upload_id] = {
        "status": "queued",
        "filename": file.filename,
        "chunks_created": None,
        "error": None,
    }

    # Kick off processing in background thread
    background_tasks.add_task(_process_upload_sync, upload_id, str(file_path), file.filename)

    return {
        "upload_id": upload_id,
        "status": "queued",
        "filename": file.filename,
        "message": "Document accepted. Poll GET /upload/{upload_id}/status for progress.",
    }


@app.get("/upload/{upload_id}/status", response_model=UploadStatusResponse, tags=["Documents"])
async def upload_status(upload_id: str, current_user: str = Depends(get_current_user)):
    """Check the status of a background upload job."""
    job = _upload_jobs.get(upload_id)
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")

    return UploadStatusResponse(
        upload_id=upload_id,
        status=job["status"],
        filename=job["filename"],
        chunks_created=job.get("chunks_created"),
        error=job.get("error"),
    )


# ─── Query: Original (sync, non-streaming) ─────────────────────────────

@app.post("/query", response_model=QueryResponse, tags=["Chat"])
async def query_chatbot(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
    """Query the RAG chatbot (non-streaming). Use /query/stream for SSE."""
    try:
        # Load conversation history from async checkpointer
        conversation_history = []
        is_first_message = True
        if request.thread_id and checkpointer:
            previous_state = await checkpointer.load_state(request.thread_id)
            if previous_state:
                conversation_history = previous_state.get("conversation_history", [])
                if conversation_history:
                    is_first_message = False

        # Run blocking RAG pipeline in a thread so we don't block the event loop
        def _run():
            # Manually inject loaded history into the workflow
            initial_state = {
                "query": request.query,
                "retrieved_docs": [],
                "context": "",
                "answer": {},
                "conversation_history": conversation_history,
                "thread_id": request.thread_id or "default",
                "llm_provider": request.llm_provider,
                "top_k": request.top_k or settings.top_k_results,
            }
            result = rag_workflow.graph.invoke(initial_state)
            return result

        result = await asyncio.to_thread(_run)

        # Save state async
        if request.thread_id and checkpointer:
            await checkpointer.save_state(
                request.thread_id,
                result,
                user_id=current_user,
                title=request.query[:80] if is_first_message else None,
            )

        response = QueryResponse(
            query=result["query"],
            answer=result["answer"].get("answer", ""),
            confidence=result["answer"].get("confidence", 0.0),
            sources=rag_workflow._format_sources(result["retrieved_docs"]),
            thread_id=request.thread_id
        )

        logger.info(f"Query processed: {request.query[:50]}... (confidence: {result['answer'].get('confidence', 0.0)})")
        return response

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


# ─── Query: SSE Streaming (NEW) ────────────────────────────────────────

@app.post("/query/stream", tags=["Chat"])
async def query_chatbot_stream(
    request: QueryRequest,
    current_user: str = Depends(get_current_user),
):
    """Query the RAG chatbot with Server-Sent Events streaming.

    SSE events emitted:
      event: sources   — JSON array of source documents (sent first)
      event: token     — individual LLM token (sent as they arrive)
      event: done      — signals end of stream (data contains thread_id)
      event: error     — error message
    """
    try:
        # 1. Load conversation history (async)
        conversation_history = []
        is_first_message = True
        if request.thread_id and checkpointer:
            previous_state = await checkpointer.load_state(request.thread_id)
            if previous_state:
                conversation_history = previous_state.get("conversation_history", [])
                if conversation_history:
                    is_first_message = False

        # 2. Retrieve + format context in a thread (sync ChromaDB + embeddings)
        def _retrieve():
            return rag_workflow.run_stream(
                query=request.query,
                thread_id=request.thread_id,
                llm_provider=request.llm_provider,
                top_k=request.top_k or settings.top_k_results,
            )

        retrieval_result = await asyncio.to_thread(_retrieve)

        # 3. Build SSE generator
        async def event_generator():
            full_answer = []

            # Emit sources first
            sources_data = [s.model_dump() for s in retrieval_result["sources"]]
            yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

            # Stream LLM tokens (blocking generator → run in thread)
            def _token_gen():
                return list(rag_workflow.stream_tokens(
                    query=retrieval_result["query"],
                    context=retrieval_result["context"],
                    conversation_history=conversation_history,
                    llm_provider=request.llm_provider,
                ))

            # We can't easily iterate a sync generator from async, so we use
            # a queue-based bridge for true token-by-token streaming
            import queue
            token_queue = queue.Queue()
            _SENTINEL = object()

            def _produce_tokens():
                try:
                    for token in rag_workflow.stream_tokens(
                        query=retrieval_result["query"],
                        context=retrieval_result["context"],
                        conversation_history=conversation_history,
                        llm_provider=request.llm_provider,
                    ):
                        token_queue.put(token)
                except Exception as e:
                    token_queue.put(e)
                finally:
                    token_queue.put(_SENTINEL)

            # Start producer in a thread
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _produce_tokens)

            # Consume tokens and yield SSE events
            while True:
                try:
                    item = await asyncio.to_thread(token_queue.get, timeout=60)
                except Exception:
                    yield f"event: error\ndata: {{\"error\": \"Stream timeout\"}}\n\n"
                    break

                if item is _SENTINEL:
                    break
                if isinstance(item, Exception):
                    yield f"event: error\ndata: {json.dumps({'error': str(item)})}\n\n"
                    break

                full_answer.append(item)
                yield f"event: token\ndata: {json.dumps({'token': item})}\n\n"

            # Save state after streaming completes (async)
            answer_text = "".join(full_answer)
            if request.thread_id and checkpointer:
                updated_history = conversation_history.copy()
                updated_history.append({"role": "user", "content": request.query})
                updated_history.append({"role": "assistant", "content": answer_text})

                state_to_save = {
                    "query": request.query,
                    "answer": {"answer": answer_text, "confidence": 0.0, "sources_used": []},
                    "context": retrieval_result["context"],
                    "conversation_history": updated_history,
                    "llm_provider": request.llm_provider,
                    "top_k": request.top_k or settings.top_k_results,
                }
                await checkpointer.save_state(
                    request.thread_id,
                    state_to_save,
                    user_id=current_user,
                    title=request.query[:80] if is_first_message else None,
                )

            # Signal done
            yield f"event: done\ndata: {json.dumps({'thread_id': request.thread_id})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error(f"Error in streaming query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


# ─── Conversation History ──────────────────────────────────────────────

@app.get("/history/{thread_id}", response_model=ConversationHistory, tags=["Chat"])
async def get_conversation_history(
    thread_id: str,
    current_user: str = Depends(get_current_user),
):
    """Get conversation history for a thread"""
    try:
        if not await checkpointer.verify_thread_owner(thread_id, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")

        messages_data = await checkpointer.get_conversation_history(thread_id)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving history: {str(e)}"
        )


@app.delete("/history/{thread_id}", tags=["Chat"])
async def delete_conversation(
    thread_id: str,
    current_user: str = Depends(get_current_user),
):
    """Delete conversation history for a thread"""
    try:
        if not await checkpointer.verify_thread_owner(thread_id, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")

        deleted_count = await checkpointer.delete_thread(thread_id)

        return {
            "success": True,
            "message": f"Deleted {deleted_count} checkpoints for thread {thread_id}",
            "thread_id": thread_id,
            "deleted_count": deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting conversation: {str(e)}"
        )


# ─── Conversation Management ───────────────────────────────────────────

@app.get("/conversations", tags=["Conversations"])
async def list_conversations(current_user: str = Depends(get_current_user)):
    """List all conversations for the current user"""
    return await checkpointer.get_user_conversations(current_user)


@app.post("/conversations", tags=["Conversations"], status_code=status.HTTP_201_CREATED)
async def create_conversation(current_user: str = Depends(get_current_user)):
    """Create a new empty conversation and return its thread_id"""
    thread_id = str(uuid.uuid4())
    await checkpointer.create_empty_thread(thread_id, current_user)
    return {"thread_id": thread_id}


@app.patch("/conversations/{thread_id}", tags=["Conversations"])
async def rename_conversation(
    thread_id: str,
    req: RenameRequest,
    current_user: str = Depends(get_current_user),
):
    """Rename a conversation"""
    if not await checkpointer.verify_thread_owner(thread_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")

    await checkpointer.rename_thread(thread_id, req.title)
    return {"success": True, "thread_id": thread_id, "title": req.title}


# ─── Stats ──────────────────────────────────────────────────────────────

@app.get("/stats", tags=["Admin"])
async def get_stats(current_user: str = Depends(get_current_user)):
    """Get system statistics"""
    try:
        vector_stats = await asyncio.to_thread(vector_store.get_collection_stats)

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
