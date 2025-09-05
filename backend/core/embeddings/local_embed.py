"""
Local Embedding System for AlsaniaMCP
Provides self-contained embedding functionality without external API dependencies
"""

import hashlib
import json
import logging
import os
import pickle
import re
from typing import List, Optional, Dict, Any
import numpy as np
from collections import Counter
import math

logger = logging.getLogger("alsaniamcp.embeddings")

class LocalEmbedding:
    """Local embedding system using TF-IDF and semantic features"""
    
    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
        self.vocabulary = {}
        self.idf_scores = {}
        self.cache_dir = "cache/embeddings"
        self.vocab_file = os.path.join(self.cache_dir, "vocabulary.json")
        self.idf_file = os.path.join(self.cache_dir, "idf_scores.json")
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load existing vocabulary and IDF scores
        self._load_vocabulary()
        self._load_idf_scores()
        
        # Semantic feature extractors
        self.semantic_patterns = {
            'question': [r'\?', r'\bwhat\b', r'\bhow\b', r'\bwhy\b', r'\bwhen\b', r'\bwhere\b', r'\bwho\b'],
            'action': [r'\b(do|make|create|build|run|execute|perform)\b'],
            'emotion': [r'\b(happy|sad|angry|excited|worried|confused|frustrated)\b'],
            'time': [r'\b(today|tomorrow|yesterday|now|later|soon|recently)\b'],
            'location': [r'\b(here|there|home|office|city|country)\b'],
            'technical': [r'\b(api|database|server|code|function|class|method)\b'],
            'memory': [r'\b(remember|recall|forget|store|save|retrieve)\b']
        }
    
    def _load_vocabulary(self):
        """Load vocabulary from cache"""
        try:
            if os.path.exists(self.vocab_file):
                with open(self.vocab_file, 'r') as f:
                    self.vocabulary = json.load(f)
                logger.info(f"Loaded vocabulary with {len(self.vocabulary)} terms")
        except Exception as e:
            logger.warning(f"Failed to load vocabulary: {e}")
            self.vocabulary = {}
    
    def _save_vocabulary(self):
        """Save vocabulary to cache"""
        try:
            with open(self.vocab_file, 'w') as f:
                json.dump(self.vocabulary, f)
        except Exception as e:
            logger.warning(f"Failed to save vocabulary: {e}")
    
    def _load_idf_scores(self):
        """Load IDF scores from cache"""
        try:
            if os.path.exists(self.idf_file):
                with open(self.idf_file, 'r') as f:
                    self.idf_scores = json.load(f)
                logger.info(f"Loaded IDF scores for {len(self.idf_scores)} terms")
        except Exception as e:
            logger.warning(f"Failed to load IDF scores: {e}")
            self.idf_scores = {}
    
    def _save_idf_scores(self):
        """Save IDF scores to cache"""
        try:
            with open(self.idf_file, 'w') as f:
                json.dump(self.idf_scores, f)
        except Exception as e:
            logger.warning(f"Failed to save IDF scores: {e}")
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization with normalization"""
        # Convert to lowercase and extract words
        text = text.lower()
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        # Split and filter empty strings
        tokens = [token.strip() for token in text.split() if token.strip()]
        return tokens
    
    def _extract_semantic_features(self, text: str) -> List[float]:
        """Extract semantic features from text"""
        features = []
        text_lower = text.lower()
        
        # Pattern-based features
        for pattern_type, patterns in self.semantic_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches
            features.append(min(score / 10.0, 1.0))  # Normalize to [0,1]
        
        # Text statistics features
        features.extend([
            len(text) / 1000.0,  # Text length (normalized)
            len(text.split()) / 100.0,  # Word count (normalized)
            len(set(text.split())) / len(text.split()) if text.split() else 0,  # Vocabulary diversity
            text.count('?') / 10.0,  # Question density
            text.count('!') / 10.0,  # Exclamation density
        ])
        
        return features
    
    def _compute_tf_idf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute TF-IDF scores for tokens"""
        # Term frequency
        tf = Counter(tokens)
        total_terms = len(tokens)
        
        tf_idf = {}
        for term, count in tf.items():
            tf_score = count / total_terms
            idf_score = self.idf_scores.get(term, 1.0)  # Default IDF of 1.0
            tf_idf[term] = tf_score * idf_score
        
        return tf_idf
    
    def _update_vocabulary(self, tokens: List[str]):
        """Update vocabulary with new tokens"""
        for token in tokens:
            if token not in self.vocabulary:
                self.vocabulary[token] = len(self.vocabulary)
        
        # Save updated vocabulary periodically
        if len(self.vocabulary) % 100 == 0:
            self._save_vocabulary()
    
    def _update_idf_scores(self, documents: List[List[str]]):
        """Update IDF scores based on document collection"""
        if not documents:
            return
        
        # Count document frequencies
        doc_freq = Counter()
        total_docs = len(documents)
        
        for doc_tokens in documents:
            unique_tokens = set(doc_tokens)
            for token in unique_tokens:
                doc_freq[token] += 1
        
        # Compute IDF scores
        for token, freq in doc_freq.items():
            self.idf_scores[token] = math.log(total_docs / freq)
        
        self._save_idf_scores()
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text using local methods"""
        try:
            # Tokenize text
            tokens = self._tokenize(text)
            
            # Update vocabulary
            self._update_vocabulary(tokens)
            
            # Extract semantic features
            semantic_features = self._extract_semantic_features(text)
            
            # Compute TF-IDF features
            tf_idf = self._compute_tf_idf(tokens)
            
            # Create embedding vector
            embedding = [0.0] * self.embedding_dim
            
            # Fill semantic features (first part of embedding)
            semantic_dim = min(len(semantic_features), self.embedding_dim // 4)
            for i in range(semantic_dim):
                embedding[i] = semantic_features[i]
            
            # Fill TF-IDF features (remaining part of embedding)
            tfidf_start = semantic_dim
            tfidf_dim = self.embedding_dim - tfidf_start
            
            # Map tokens to embedding dimensions using vocabulary indices
            for token, score in tf_idf.items():
                if token in self.vocabulary:
                    vocab_idx = self.vocabulary[token]
                    embed_idx = tfidf_start + (vocab_idx % tfidf_dim)
                    embedding[embed_idx] += score
            
            # Normalize embedding to unit vector
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Local embedding failed: {e}")
            # Return random normalized vector as fallback
            import random
            random.seed(hash(text) % (2**32))
            embedding = [random.gauss(0, 0.1) for _ in range(self.embedding_dim)]
            norm = math.sqrt(sum(x * x for x in embedding))
            return [x / norm for x in embedding] if norm > 0 else embedding

class EmbeddingManager:
    """Manages embedding generation with fallback options"""
    
    def __init__(self):
        self.local_embedder = LocalEmbedding()
        self.cache_dir = "cache/embeddings"
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_path(self, text: str) -> str:
        """Get cache file path for text"""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{text_hash}.pkl")
    
    def _load_from_cache(self, text: str) -> Optional[List[float]]:
        """Load embedding from cache"""
        try:
            cache_path = self._get_cache_path(text)
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    embedding = pickle.load(f)
                logger.debug(f"Loaded embedding from cache")
                return embedding
        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")
        return None
    
    def _save_to_cache(self, text: str, embedding: List[float]):
        """Save embedding to cache"""
        try:
            cache_path = self._get_cache_path(text)
            with open(cache_path, 'wb') as f:
                pickle.dump(embedding, f)
        except Exception as e:
            logger.warning(f"Failed to save to cache: {e}")
    
    def get_embedding(self, text: str, use_external: bool = False) -> List[float]:
        """Get embedding for text with caching and fallback"""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * 384
        
        # Check cache first
        cached_embedding = self._load_from_cache(text)
        if cached_embedding:
            return cached_embedding
        
        # Try external API if requested and available
        if use_external:
            external_embedding = self._get_external_embedding(text)
            if external_embedding:
                self._save_to_cache(text, external_embedding)
                return external_embedding
        
        # Use local embedding as primary method
        local_embedding = self.local_embedder.embed_text(text)
        self._save_to_cache(text, local_embedding)
        return local_embedding
    
    def _get_external_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from external API (OpenRouter) if available"""
        try:
            import requests
            
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return None
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers=headers,
                json={
                    "model": "text-embedding-ada-002",
                    "input": [text]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                embedding = data["data"][0]["embedding"]
                logger.info("Generated embedding using external API")
                return embedding
            else:
                logger.warning(f"External API failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"External embedding failed: {e}")
        
        return None

# Global embedding manager instance
embedding_manager = EmbeddingManager()

# Convenience functions for backward compatibility
def get_embedding(text: str, use_external: bool = False) -> List[float]:
    """Get embedding for text"""
    return embedding_manager.get_embedding(text, use_external)

def embed_text(text: str) -> List[float]:
    """Simple embedding function for backward compatibility"""
    return embedding_manager.get_embedding(text, use_external=False)
