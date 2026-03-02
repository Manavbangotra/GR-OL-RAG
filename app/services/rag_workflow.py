"""LangGraph RAG workflow with state management and streaming support"""

from typing import TypedDict, List, Dict, Any, Generator
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver
import logging

from app.services.vector_store import get_vector_store
from app.services.llm_service import get_llm_service
from app.models.schemas import StructuredAnswer, SourceDocument

logger = logging.getLogger(__name__)


# Define the state schema
class RAGState(TypedDict):
    """State for RAG workflow"""
    query: str
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: Dict[str, Any]
    conversation_history: List[Dict[str, str]]
    thread_id: str
    llm_provider: str
    top_k: int


class RAGWorkflow:
    """LangGraph-based RAG workflow with streaming support"""

    def __init__(
        self,
        checkpointer: BaseCheckpointSaver = None,
        llm_provider: str = None
    ):
        self.checkpointer = checkpointer
        self.vector_store = get_vector_store()
        self.llm_service = get_llm_service(llm_provider)

        # Build the graph
        self.graph = self._build_graph()

        logger.info("Initialized RAG workflow")

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(RAGState)

        workflow.add_node("process_query", self.process_query)
        workflow.add_node("retrieve_documents", self.retrieve_documents)
        workflow.add_node("format_context", self.format_context)
        workflow.add_node("generate_answer", self.generate_answer)

        workflow.set_entry_point("process_query")
        workflow.add_edge("process_query", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "format_context")
        workflow.add_edge("format_context", "generate_answer")
        workflow.add_edge("generate_answer", END)

        return workflow.compile()

    def process_query(self, state: RAGState) -> RAGState:
        query = state["query"].strip()
        logger.info(f"Processing query: {query[:100]}...")
        return {**state, "query": query}

    def retrieve_documents(self, state: RAGState) -> RAGState:
        query = state["query"]
        top_k = state.get("top_k", 5)
        logger.info(f"Retrieving top {top_k} documents...")
        results = self.vector_store.search(query, top_k=top_k)
        logger.info(f"Retrieved {len(results)} documents")
        return {**state, "retrieved_docs": results}

    def format_context(self, state: RAGState) -> RAGState:
        docs = state["retrieved_docs"]
        if not docs:
            context = "No relevant documents found."
        else:
            context_parts = []
            for i, doc in enumerate(docs, 1):
                filename = doc["metadata"].get("filename", "Unknown")
                content = doc["content"]
                context_parts.append(f"[Source {i}: {filename}]\n{content}\n")
            context = "\n".join(context_parts)

        logger.info(f"Formatted context: {len(context)} characters")
        return {**state, "context": context}

    def generate_answer(self, state: RAGState) -> RAGState:
        query = state["query"]
        context = state["context"]
        conversation_history = state.get("conversation_history", [])
        llm_provider = state.get("llm_provider")

        logger.info("Generating answer with LLM...")

        structured_answer = self.llm_service.generate(
            prompt=query,
            context=context,
            conversation_history=conversation_history,
            provider=llm_provider
        )

        updated_history = conversation_history.copy()
        updated_history.append({"role": "user", "content": query})
        updated_history.append({"role": "assistant", "content": structured_answer.answer})

        logger.info(f"Generated answer with confidence: {structured_answer.confidence}")

        return {
            **state,
            "answer": structured_answer.model_dump(),
            "conversation_history": updated_history
        }

    # ── Synchronous run (existing) ──────────────────────────────────────

    def run(
        self,
        query: str,
        thread_id: str = None,
        llm_provider: str = None,
        top_k: int = 5,
        user_id: str = None,
        title: str = None,
    ) -> Dict[str, Any]:
        """Run the full RAG workflow (blocking)."""
        # Load previous state if thread_id provided
        conversation_history = []
        is_first_message = True
        if thread_id and self.checkpointer:
            previous_state = self.checkpointer.load_state(thread_id)
            if previous_state:
                conversation_history = previous_state.get("conversation_history", [])
                if conversation_history:
                    is_first_message = False

        initial_state = {
            "query": query,
            "retrieved_docs": [],
            "context": "",
            "answer": {},
            "conversation_history": conversation_history,
            "thread_id": thread_id or "default",
            "llm_provider": llm_provider,
            "top_k": top_k
        }

        try:
            result = self.graph.invoke(initial_state)

            if thread_id and self.checkpointer:
                self.checkpointer.save_state(
                    thread_id,
                    result,
                    user_id=user_id,
                    title=title if is_first_message else None,
                )

            return {
                "query": result["query"],
                "answer": result["answer"].get("answer", ""),
                "confidence": result["answer"].get("confidence", 0.0),
                "sources": self._format_sources(result["retrieved_docs"]),
                "thread_id": thread_id
            }

        except Exception as e:
            logger.error(f"Error running RAG workflow: {e}")
            raise

    # ── Streaming run (NEW) ─────────────────────────────────────────────

    def run_stream(
        self,
        query: str,
        thread_id: str = None,
        llm_provider: str = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Run retrieval + context steps (blocking), return context needed for streaming.

        Returns a dict with:
          - context: formatted context string
          - conversation_history: loaded history
          - sources: list of SourceDocument
          - retrieved_docs: raw docs (for state save)
          - is_first_message: bool
        """
        conversation_history = []
        is_first_message = True

        # load_state is now async — callers must handle this before calling run_stream
        # We accept pre-loaded conversation_history via a separate method

        initial_state = {
            "query": query,
            "retrieved_docs": [],
            "context": "",
            "answer": {},
            "conversation_history": conversation_history,
            "thread_id": thread_id or "default",
            "llm_provider": llm_provider,
            "top_k": top_k,
        }

        # Run only retrieval + formatting (no LLM call)
        state = self.process_query(initial_state)
        state = self.retrieve_documents(state)
        state = self.format_context(state)

        return {
            "context": state["context"],
            "sources": self._format_sources(state["retrieved_docs"]),
            "retrieved_docs": state["retrieved_docs"],
            "query": state["query"],
        }

    def stream_tokens(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None,
        llm_provider: str = None,
    ) -> Generator[str, None, None]:
        """Stream LLM tokens for the given query and context."""
        yield from self.llm_service.stream(
            prompt=query,
            context=context,
            conversation_history=conversation_history,
            provider=llm_provider,
        )

    def _format_sources(self, docs: List[Dict[str, Any]]) -> List[SourceDocument]:
        sources = []
        for doc in docs:
            sources.append(SourceDocument(
                content=doc["content"][:500],
                filename=doc["metadata"].get("filename", "Unknown"),
                page=doc["metadata"].get("page"),
                score=doc["score"]
            ))
        return sources


# Global workflow instance
_workflow = None


def get_rag_workflow(checkpointer: BaseCheckpointSaver = None) -> RAGWorkflow:
    global _workflow
    if _workflow is None:
        _workflow = RAGWorkflow(checkpointer=checkpointer)
    return _workflow
