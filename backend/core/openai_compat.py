"""
OpenAI API Compatibility Layer for AlsaniaMCP
Provides OpenAI-compatible endpoints that integrate with AlsaniaMCP's memory system
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import HTTPException
from pydantic import BaseModel, Field

from core.embeddings import embedding_manager
from core.auth import auth_manager

logger = logging.getLogger("alsaniamcp.openai_compat")

# OpenAI-compatible request/response models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")
    name: Optional[str] = Field(None, description="Optional name for the message")

class ChatCompletionRequest(BaseModel):
    model: str = Field(default="alsania-memory", description="Model to use")
    messages: List[ChatMessage] = Field(..., description="List of messages")
    max_tokens: Optional[int] = Field(default=1000, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=0.7, description="Sampling temperature")
    top_p: Optional[float] = Field(default=1.0, description="Nucleus sampling parameter")
    n: Optional[int] = Field(default=1, description="Number of completions")
    stream: Optional[bool] = Field(default=False, description="Stream response")
    stop: Optional[List[str]] = Field(default=None, description="Stop sequences")
    presence_penalty: Optional[float] = Field(default=0.0, description="Presence penalty")
    frequency_penalty: Optional[float] = Field(default=0.0, description="Frequency penalty")
    user: Optional[str] = Field(default=None, description="User identifier")

class EmbeddingRequest(BaseModel):
    model: str = Field(default="alsania-embedding", description="Embedding model")
    input: List[str] = Field(..., description="Input texts to embed")
    user: Optional[str] = Field(default=None, description="User identifier")

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int = 0
    total_tokens: int

class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Usage

class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: List[float]

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: Usage

class OpenAICompatibilityLayer:
    """OpenAI API compatibility layer"""
    
    def __init__(self):
        self.supported_models = {
            "alsania-memory": "AlsaniaMCP Memory-Enhanced Chat Model",
            "alsania-embedding": "AlsaniaMCP Local Embedding Model",
            "gpt-3.5-turbo": "AlsaniaMCP Memory-Enhanced Chat Model (GPT-3.5 Compatible)",
            "gpt-4": "AlsaniaMCP Memory-Enhanced Chat Model (GPT-4 Compatible)",
            "text-embedding-ada-002": "AlsaniaMCP Local Embedding Model (Ada-002 Compatible)"
        }
    
    def _count_tokens(self, text: str) -> int:
        """Simple token counting (approximation)"""
        # Rough approximation: 1 token ≈ 4 characters
        return max(1, len(text) // 4)
    
    def _search_memory_context(self, query: str, agent_namespace: str = None, limit: int = 5) -> List[Dict]:
        """Search memory for relevant context"""
        try:
            from memory.vector_store import VectorStore
            
            # Get embedding for query
            embedding = embedding_manager.get_embedding(query)
            
            # Search vector store
            vector_store = VectorStore()
            namespace = agent_namespace or "default"
            results = vector_store.search(embedding, top_k=limit, namespace=namespace)
            
            return results
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
            return []
    
    def _generate_response(self, messages: List[ChatMessage], memory_context: List[Dict], 
                          max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Generate response using memory context"""
        try:
            # Build context from memory
            context_parts = []
            if memory_context:
                context_parts.append("Relevant memories:")
                for i, memory in enumerate(memory_context[:3]):  # Use top 3 memories
                    context_parts.append(f"{i+1}. {memory.get('text', '')}")
                context_parts.append("")
            
            # Build conversation context
            conversation_parts = []
            for msg in messages[-5:]:  # Use last 5 messages
                conversation_parts.append(f"{msg.role}: {msg.content}")
            
            # Combine contexts
            full_context = "\n".join(context_parts + conversation_parts)
            
            # Generate simple response based on context
            last_message = messages[-1].content.lower() if messages else ""
            
            # Simple response generation based on patterns
            if "hello" in last_message or "hi" in last_message:
                response = "Hello! I'm AlsaniaMCP, an AI assistant with persistent memory. How can I help you today?"
            elif "remember" in last_message or "recall" in last_message:
                if memory_context:
                    response = f"I found {len(memory_context)} relevant memories. Here's what I remember: {memory_context[0].get('text', '')[:200]}..."
                else:
                    response = "I don't have any specific memories related to your query, but I'm ready to learn and remember new information."
            elif "?" in last_message:
                if memory_context:
                    response = f"Based on my memories, here's what I can tell you: {memory_context[0].get('text', '')[:300]}..."
                else:
                    response = "I don't have specific information about that in my memory, but I'd be happy to help you explore the topic further."
            else:
                response = "I understand. I've noted this information and will remember it for future conversations. Is there anything specific you'd like me to help you with?"
            
            # Store the conversation in memory
            try:
                from core.main import save_memory_entry, insert_vector
                from lib.secure_memory_id import secure_memory_id
                
                # Store user message
                user_mem_id = secure_memory_id()
                save_memory_entry(user_mem_id, last_message, "openai_compat_user")
                user_embedding = embedding_manager.get_embedding(last_message)
                insert_vector(user_embedding, {"memory_id": user_mem_id, "text": last_message, "source": "openai_compat_user"})
                
                # Store assistant response
                assistant_mem_id = secure_memory_id()
                save_memory_entry(assistant_mem_id, response, "openai_compat_assistant")
                assistant_embedding = embedding_manager.get_embedding(response)
                insert_vector(assistant_embedding, {"memory_id": assistant_mem_id, "text": response, "source": "openai_compat_assistant"})
                
            except Exception as e:
                logger.warning(f"Failed to store conversation in memory: {e}")
            
            return response
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return "I apologize, but I encountered an error while processing your request. Please try again."
    
    async def chat_completion(self, request: ChatCompletionRequest, api_key_info: Dict) -> ChatCompletionResponse:
        """Handle chat completion request"""
        try:
            # Validate model
            if request.model not in self.supported_models:
                raise HTTPException(status_code=400, detail=f"Model {request.model} not supported")
            
            # Get the last user message for memory search
            user_messages = [msg for msg in request.messages if msg.role == "user"]
            last_user_message = user_messages[-1].content if user_messages else ""
            
            # Determine agent namespace from API key
            agent_namespace = None
            if api_key_info.get('namespaces'):
                agent_namespace = api_key_info['namespaces'][0]
            
            # Search memory for context
            memory_context = self._search_memory_context(last_user_message, agent_namespace)
            
            # Generate response
            response_content = self._generate_response(
                request.messages, 
                memory_context, 
                request.max_tokens, 
                request.temperature
            )
            
            # Calculate token usage
            prompt_tokens = sum(self._count_tokens(msg.content) for msg in request.messages)
            completion_tokens = self._count_tokens(response_content)
            
            # Create response
            response = ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:29]}",
                created=int(time.time()),
                model=request.model,
                choices=[
                    ChatChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=response_content),
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def create_embeddings(self, request: EmbeddingRequest, api_key_info: Dict) -> EmbeddingResponse:
        """Handle embedding creation request"""
        try:
            # Validate model
            if request.model not in self.supported_models:
                raise HTTPException(status_code=400, detail=f"Model {request.model} not supported")
            
            # Generate embeddings
            embeddings_data = []
            total_tokens = 0
            
            for i, text in enumerate(request.input):
                embedding = embedding_manager.get_embedding(text, use_external=False)
                embeddings_data.append(
                    EmbeddingData(
                        index=i,
                        embedding=embedding
                    )
                )
                total_tokens += self._count_tokens(text)
            
            # Create response
            response = EmbeddingResponse(
                data=embeddings_data,
                model=request.model,
                usage=Usage(
                    prompt_tokens=total_tokens,
                    total_tokens=total_tokens
                )
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Embedding creation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def list_models(self) -> Dict[str, Any]:
        """List available models"""
        models = []
        for model_id, description in self.supported_models.items():
            models.append({
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "alsania",
                "permission": [],
                "root": model_id,
                "parent": None,
                "description": description
            })
        
        return {
            "object": "list",
            "data": models
        }

# Global compatibility layer instance
openai_compat = OpenAICompatibilityLayer()
