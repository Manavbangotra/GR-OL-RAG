"""LLM service with Groq and Ollama support (sync + streaming)"""

from typing import Dict, Any, List, Optional, Generator
import logging
import json

# Groq
from groq import Groq

# Ollama
import ollama

from app.config import settings
from app.models.schemas import StructuredAnswer

logger = logging.getLogger(__name__)


class LLMService:
    """LLM service supporting Groq and Ollama with structured outputs and streaming"""

    def __init__(self, provider: str = None):
        self.provider = provider or settings.default_llm_provider

        # Initialize Groq client if needed
        if self.provider == "groq" or settings.groq_api_key:
            try:
                self.groq_client = Groq(api_key=settings.groq_api_key)
                logger.info("Initialized Groq client")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")
                self.groq_client = None
        else:
            self.groq_client = None

        # Ollama settings
        self.ollama_base_url = settings.ollama_base_url
        self.ollama_model = settings.ollama_model

        logger.info(f"LLM service initialized with provider: {self.provider}")

    # ── Helper: build message list ──────────────────────────────────────

    def _build_messages(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None,
        for_json: bool = True,
    ) -> List[Dict[str, str]]:
        """Build the messages array for LLM calls."""
        json_instruction = (
            "\n\nFormat your response as JSON with these fields:\n"
            "- answer: Your detailed answer to the question\n"
            "- confidence: A number between 0 and 1 indicating your confidence\n"
            "- sources_used: List of source filenames used"
            if for_json
            else ""
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant specializing in dropshipping and service points platforms. "
                    "Your role is to provide accurate, helpful information based on the provided context.\n\n"
                    "When answering:\n"
                    "1. Use the provided context to answer the question accurately\n"
                    "2. If the context doesn't contain enough information, say so honestly\n"
                    "3. Provide confidence score based on how well the context supports your answer\n"
                    "4. List the source filenames you used to generate the answer"
                    + json_instruction
                ),
            }
        ]

        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(msg)

        messages.append({
            "role": "user",
            "content": (
                f"Context from documents:\n{context}\n\n"
                f"Question: {prompt}\n\n"
                "Please provide a detailed answer based on the context above."
            ),
        })

        return messages

    # ── Synchronous generation (existing) ───────────────────────────────

    def generate_with_groq(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> StructuredAnswer:
        if not self.groq_client:
            raise ValueError("Groq client not initialized. Check GROQ_API_KEY.")

        messages = self._build_messages(prompt, context, conversation_history, for_json=True)

        try:
            response = self.groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            return StructuredAnswer(
                answer=result.get("answer", ""),
                confidence=float(result.get("confidence", 0.5)),
                sources_used=result.get("sources_used", [])
            )

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def generate_with_ollama(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> StructuredAnswer:
        messages = self._build_messages(prompt, context, conversation_history, for_json=True)

        try:
            response = ollama.chat(
                model=self.ollama_model,
                messages=messages,
                options={
                    "temperature": 0.3,
                    "num_predict": 512
                },
                format="json"
            )

            content = response['message']['content']
            result = json.loads(content)

            return StructuredAnswer(
                answer=result.get("answer", ""),
                confidence=float(result.get("confidence", 0.5)),
                sources_used=result.get("sources_used", [])
            )

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    def generate(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None,
        provider: str = None
    ) -> StructuredAnswer:
        use_provider = provider or self.provider

        try:
            if use_provider == "groq":
                return self.generate_with_groq(prompt, context, conversation_history)
            elif use_provider == "ollama":
                return self.generate_with_ollama(prompt, context, conversation_history)
            else:
                raise ValueError(f"Unknown provider: {use_provider}")
        except Exception as e:
            logger.error(f"Error with {use_provider}, attempting fallback...")

            if use_provider == "groq" and self.ollama_model:
                logger.info("Falling back to Ollama")
                return self.generate_with_ollama(prompt, context, conversation_history)
            elif use_provider == "ollama" and self.groq_client:
                logger.info("Falling back to Groq")
                return self.generate_with_groq(prompt, context, conversation_history)
            else:
                raise

    # ── Streaming generation (NEW) ──────────────────────────────────────

    def stream_with_groq(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None,
    ) -> Generator[str, None, None]:
        """Stream tokens from Groq API."""
        if not self.groq_client:
            raise ValueError("Groq client not initialized. Check GROQ_API_KEY.")

        messages = self._build_messages(prompt, context, conversation_history, for_json=False)

        try:
            stream = self.groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                temperature=0.3,
                max_tokens=1024,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

        except Exception as e:
            logger.error(f"Groq streaming error: {e}")
            raise

    def stream_with_ollama(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None,
    ) -> Generator[str, None, None]:
        """Stream tokens from Ollama."""
        messages = self._build_messages(prompt, context, conversation_history, for_json=False)

        try:
            stream = ollama.chat(
                model=self.ollama_model,
                messages=messages,
                options={
                    "temperature": 0.3,
                    "num_predict": 512,
                },
                stream=True,
            )

            for chunk in stream:
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token

        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise

    def stream(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None,
        provider: str = None,
    ) -> Generator[str, None, None]:
        """Stream tokens from configured or specified provider with fallback."""
        use_provider = provider or self.provider

        try:
            if use_provider == "groq":
                yield from self.stream_with_groq(prompt, context, conversation_history)
            elif use_provider == "ollama":
                yield from self.stream_with_ollama(prompt, context, conversation_history)
            else:
                raise ValueError(f"Unknown provider: {use_provider}")
        except Exception as e:
            logger.error(f"Streaming error with {use_provider}, attempting fallback...")

            if use_provider == "groq" and self.ollama_model:
                logger.info("Falling back to Ollama streaming")
                yield from self.stream_with_ollama(prompt, context, conversation_history)
            elif use_provider == "ollama" and self.groq_client:
                logger.info("Falling back to Groq streaming")
                yield from self.stream_with_groq(prompt, context, conversation_history)
            else:
                raise


# Global LLM service instance
_llm_service = None


def get_llm_service(provider: str = None) -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(provider)
    return _llm_service
