"""LLM service with Groq and Ollama support"""

from typing import Dict, Any, List, Optional
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
    """LLM service supporting Groq and Ollama with structured outputs"""
    
    def __init__(self, provider: str = None):
        """Initialize LLM service
        
        Args:
            provider: LLM provider ('groq' or 'ollama')
        """
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
    
    def generate_with_groq(
        self,
        prompt: str,
        context: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> StructuredAnswer:
        """Generate response using Groq API
        
        Args:
            prompt: User query
            context: Retrieved context
            conversation_history: Previous conversation messages
            
        Returns:
            StructuredAnswer object
        """
        if not self.groq_client:
            raise ValueError("Groq client not initialized. Check GROQ_API_KEY.")
        
        # Build messages
        messages = []
        
        # System message
        system_message = {
            "role": "system",
            "content": """You are a helpful AI assistant specializing in dropshipping and service points platforms. 
Your role is to provide accurate, helpful information based on the provided context.

When answering:
1. Use the provided context to answer the question accurately
2. If the context doesn't contain enough information, say so honestly
3. Provide confidence score based on how well the context supports your answer
4. List the source filenames you used to generate the answer

Format your response as JSON with these fields:
- answer: Your detailed answer to the question
- confidence: A number between 0 and 1 indicating your confidence
- sources_used: List of source filenames used"""
        }
        messages.append(system_message)
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 3 exchanges
                messages.append(msg)
        
        # User message with context
        user_message = {
            "role": "user",
            "content": f"""Context from documents:
{context}

Question: {prompt}

Please provide a detailed answer based on the context above."""
        }
        messages.append(user_message)
        
        try:
            # Call Groq API
            response = self.groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            # Parse response
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
        """Generate response using Ollama
        
        Args:
            prompt: User query
            context: Retrieved context
            conversation_history: Previous conversation messages
            
        Returns:
            StructuredAnswer object
        """
        # Build messages
        messages = []
        
        # System message
        system_message = {
            "role": "system",
            "content": """You are a helpful AI assistant specializing in dropshipping and service points platforms. 
Provide accurate information based on the context. Format your response as JSON with: answer, confidence (0-1), and sources_used (list)."""
        }
        messages.append(system_message)
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 3 exchanges
                messages.append(msg)
        
        # User message
        user_message = {
            "role": "user",
            "content": f"""Context: {context}

Question: {prompt}

Respond in JSON format with answer, confidence, and sources_used fields."""
        }
        messages.append(user_message)
        
        try:
            # Call Ollama
            response = ollama.chat(
                model=self.ollama_model,
                messages=messages,
                options={
                    "temperature": 0.3,
                    "num_predict": 512
                },
                format="json"
            )
            
            # Parse response
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
        """Generate response using configured or specified provider
        
        Args:
            prompt: User query
            context: Retrieved context
            conversation_history: Previous conversation messages
            provider: Override default provider
            
        Returns:
            StructuredAnswer object
        """
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
            
            # Fallback to alternative provider
            if use_provider == "groq" and self.ollama_model:
                logger.info("Falling back to Ollama")
                return self.generate_with_ollama(prompt, context, conversation_history)
            elif use_provider == "ollama" and self.groq_client:
                logger.info("Falling back to Groq")
                return self.generate_with_groq(prompt, context, conversation_history)
            else:
                raise


# Global LLM service instance
_llm_service = None


def get_llm_service(provider: str = None) -> LLMService:
    """Get or create the global LLM service instance
    
    Args:
        provider: Optional provider override
        
    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(provider)
    return _llm_service
