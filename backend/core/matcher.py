# -*- coding: utf-8 -*-
"""
Mento.AI Semantic Matcher
Uses SBERT (Sentence-Transformers) + FAISS when available,
or fast TF-IDF N-gram Cosine Similarity for lightweight serverless environments.
Matches syllabus topics to the best relevant study material chunks.
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger("matcher")

_MODEL_INSTANCE = None
SBERT_AVAILABLE = False
FAISS_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    import sentence_transformers
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False

def get_embedding_model():
    """Lazy load SBERT model for embedding generation if available."""
    global _MODEL_INSTANCE
    if not SBERT_AVAILABLE or not FAISS_AVAILABLE:
        return None
        
    if _MODEL_INSTANCE is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading SBERT model (all-MiniLM-L6-v2)...")
            _MODEL_INSTANCE = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("SBERT model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer: {e}. Falling back to TF-IDF matching.")
            return None
    return _MODEL_INSTANCE

def _match_with_tfidf(
    topics: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    similarity_threshold: float,
    top_k: int
) -> List[Dict[str, Any]]:
    """
    High-speed, lightweight TF-IDF n-gram cosine matching for serverless deployment.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    chunk_texts = [c["text"] for c in chunks]
    topic_texts = [t["full_context"] for t in topics]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),
        sublinear_tf=True,
        token_pattern=r'(?u)\b[\w-]+\b'
    )
    
    all_texts = chunk_texts + topic_texts
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    
    num_chunks = len(chunks)
    chunk_vecs = tfidf_matrix[:num_chunks]
    topic_vecs = tfidf_matrix[num_chunks:]

    sim_matrix = cosine_similarity(topic_vecs, chunk_vecs)
    
    matched_results = []
    matched_chunk_ids = set()

    for i, topic in enumerate(topics):
        topic_matches = []
        topic_sims = sim_matrix[i]
        
        # Rank chunks by score
        ranked_indices = np.argsort(-topic_sims)
        
        # Adaptive threshold for TF-IDF
        effective_threshold = min(similarity_threshold, 0.15)
        
        for rank in range(min(top_k, len(ranked_indices))):
            idx = int(ranked_indices[rank])
            score = float(topic_sims[idx])
            
            if score >= effective_threshold or rank == 0 and score > 0.05:
                matched_chunk = chunks[idx]
                matched_chunk_ids.add(matched_chunk["chunk_id"])
                # Scale TF-IDF score into 0-1 range for UI display
                display_score = min(round(score * 1.5, 4), 0.99)
                topic_matches.append({
                    "chunk_id": matched_chunk["chunk_id"],
                    "text": matched_chunk["text"],
                    "page_number": matched_chunk["page_number"],
                    "type": matched_chunk["type"],
                    "source": matched_chunk["source"],
                    "score": display_score,
                    "similarity_score": display_score,
                    "confidence_pct": round(display_score * 100, 1)
                })

        topic_matches.sort(key=lambda x: x["score"], reverse=True)
        matched_results.append({
            "topic_id": topic["topic_id"],
            "title": topic["title"],
            "unit": topic["unit"],
            "section": topic["section"],
            "hierarchy_number": topic["hierarchy_number"],
            "full_context": topic["full_context"],
            "matches": topic_matches
        })

    # Preserve unmatched chunks
    unmatched_chunks = [c for c in chunks if c["chunk_id"] not in matched_chunk_ids]
    if unmatched_chunks:
        uncategorized_matches = []
        for chunk in unmatched_chunks:
            uncategorized_matches.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "page_number": chunk["page_number"],
                "type": chunk["type"],
                "source": chunk["source"],
                "score": 0.5,
                "similarity_score": 0.5,
                "confidence_pct": 50.0
            })
        matched_results.append({
            "topic_id": "topic_uncategorized_notes",
            "title": "Extracted Study Notes (Uncategorized / Additional Notes)",
            "unit": "Extracted Notes & Handwritten Materials",
            "section": "General",
            "hierarchy_number": "*",
            "full_context": "Additional extracted study materials and handwritten notes",
            "matches": uncategorized_matches
        })

    return matched_results

def match_syllabus_to_document(
    topics: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    similarity_threshold: float = 0.35,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Perform semantic search to match syllabus topics to document chunks.
    Uses SBERT + FAISS if available, otherwise fast TF-IDF.
    """
    if not topics or not chunks:
        logger.warning("Empty topics or chunks provided for matching.")
        return []
        
    model = get_embedding_model()
    if model is None or not FAISS_AVAILABLE:
        logger.info("Using lightweight TF-IDF semantic matcher for serverless execution.")
        return _match_with_tfidf(topics, chunks, similarity_threshold, top_k)
        
    import faiss
    
    # 1. Embed study material chunks
    logger.info(f"Embedding {len(chunks)} document chunks with SBERT...")
    chunk_texts = [chunk["text"] for chunk in chunks]
    chunk_embeddings = model.encode(chunk_texts, show_progress_bar=False, convert_to_numpy=True)
    
    # Normalize for cosine similarity
    faiss.normalize_L2(chunk_embeddings)
    
    # 2. Build FAISS index
    dimension = chunk_embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(chunk_embeddings)
    logger.info("FAISS vector index built successfully.")
    
    # 3. Embed syllabus topics
    logger.info(f"Embedding {len(topics)} syllabus topics...")
    topic_texts = [topic["full_context"] for topic in topics]
    topic_embeddings = model.encode(topic_texts, show_progress_bar=False, convert_to_numpy=True)
    faiss.normalize_L2(topic_embeddings)
    
    # 4. Search index
    logger.info(f"Running vector similarity search (top_k={top_k}, threshold={similarity_threshold})...")
    scores, indices = index.search(topic_embeddings, k=top_k)
    
    # 5. Compile results
    matched_results = []
    matched_chunk_ids = set()
    
    for i, topic in enumerate(topics):
        topic_matches = []
        for rank in range(top_k):
            score = float(scores[i][rank])
            idx = int(indices[i][rank])
            
            # FAISS can return -1 if there aren't enough elements
            if idx == -1:
                continue
                
            if score >= similarity_threshold:
                matched_chunk = chunks[idx]
                matched_chunk_ids.add(matched_chunk["chunk_id"])
                topic_matches.append({
                    "chunk_id": matched_chunk["chunk_id"],
                    "text": matched_chunk["text"],
                    "page_number": matched_chunk["page_number"],
                    "type": matched_chunk["type"],
                    "source": matched_chunk["source"],
                    "score": round(score, 4),
                    "similarity_score": round(score, 4),  # alias for frontend compatibility
                    "confidence_pct": round(score * 100, 1)
                })
        
        # Sort matches by similarity score descending
        topic_matches.sort(key=lambda x: x["score"], reverse=True)
        
        matched_results.append({
            "topic_id": topic["topic_id"],
            "title": topic["title"],
            "unit": topic["unit"],
            "section": topic["section"],
            "hierarchy_number": topic["hierarchy_number"],
            "full_context": topic["full_context"],
            "matches": topic_matches
        })
        
    # 6. Preserve unmatched chunks (e.g. handwritten OCR or notes that didn't meet topic threshold)
    unmatched_chunks = [c for c in chunks if c["chunk_id"] not in matched_chunk_ids]
    if unmatched_chunks:
        logger.info(f"Preserving {len(unmatched_chunks)} unmatched study/handwritten note chunks...")
        uncategorized_matches = []
        for chunk in unmatched_chunks:
            uncategorized_matches.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "page_number": chunk["page_number"],
                "type": chunk["type"],
                "source": chunk["source"],
                "score": 0.5,
                "similarity_score": 0.5,
                "confidence_pct": 50.0
            })
            
        matched_results.append({
            "topic_id": "topic_uncategorized_notes",
            "title": "Extracted Study Notes (Uncategorized / Additional Notes)",
            "unit": "Extracted Notes & Handwritten Materials",
            "section": "General",
            "hierarchy_number": "*",
            "full_context": "Additional extracted study materials and handwritten notes",
            "matches": uncategorized_matches
        })
        
    logger.info("Syllabus-to-document matching completed.")
    return matched_results

def compute_coverage_audit(matched_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes coverage metrics comparing syllabus topics against study material matches.
    Identifies covered topics vs missing topics.
    """
    total_topics = len(matched_results)
    covered_topics = []
    missing_topics = []
    total_excerpts = 0
    
    for item in matched_results:
        matches = item.get("matches", [])
        match_count = len(matches)
        total_excerpts += match_count
        
        topic_info = {
            "topic_id": item.get("topic_id"),
            "title": item.get("title"),
            "unit": item.get("unit"),
            "hierarchy_number": item.get("hierarchy_number"),
            "match_count": match_count
        }
        
        if match_count > 0:
            covered_topics.append(topic_info)
        else:
            missing_topics.append(topic_info)
            
    matched_count = len(covered_topics)
    missing_count = len(missing_topics)
    coverage_pct = round((matched_count / total_topics * 100), 1) if total_topics > 0 else 0.0
    
    return {
        "total_topics": total_topics,
        "matched_topics_count": matched_count,
        "missing_topics_count": missing_count,
        "coverage_percentage": coverage_pct,
        "total_excerpts": total_excerpts,
        "covered_topics": covered_topics,
        "missing_topics": missing_topics
    }

