# -*- coding: utf-8 -*-
"""
Mento.AI Semantic Matcher & Topic Detection Engine
Uses SBERT (Sentence-Transformers) + FAISS when available,
or fast TF-IDF N-gram Cosine Similarity for lightweight serverless environments.
Matches syllabus topics to study material chunks, and identifies 'Other Topics'
present in the study material that were not part of the syllabus.
"""

import re
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple

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

def extract_candidate_headings_from_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts candidate section headers and topic titles from study material chunks.
    Identifies patterns like:
      - '1.1 Classification of Signals'
      - 'Chapter 3: Filters'
      - 'Z-Transform'
      - 'Types of Systems:'
    """
    candidates = []
    seen_titles = set()
    
    HEADING_PATTERNS = [
        re.compile(r'^(?:UNIT|MODULE|CHAPTER|PART|SECTION)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE)[:\-\.\s\s]+(.*)$', re.IGNORECASE),
        re.compile(r'^(\d+(?:\.\d+)+)\.?\s+([A-Z].*)$'), # 1.1 Topic or 1.1.1 Subtopic
        re.compile(r'^([A-Z][a-zA-Z0-9\s\-\(\)\/\,\&]{3,65}):\s*$'), # Title with colon
    ]
    
    for chunk in chunks:
        lines = chunk["text"].splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str or len(line_str) < 3 or len(line_str) > 80:
                continue
                
            title_found = None
            hierarchy_num = ""
            
            for pat in HEADING_PATTERNS:
                m = pat.match(line_str)
                if m:
                    if len(m.groups()) == 2:
                        hierarchy_num = m.group(1).strip()
                        title_found = m.group(2).strip()
                    elif len(m.groups()) == 1:
                        title_found = m.group(1).strip()
                    break
                    
            # Check for uppercase or titlecase short heading line
            if not title_found:
                if (line_str.isupper() and 4 <= len(line_str) <= 60 and not line_str.endswith('.')):
                    title_found = line_str.title()
                elif (re.match(r'^[A-Z][a-zA-Z0-9\s\-]{3,50}$', line_str) and not line_str.endswith('.')):
                    # Short title case line
                    words = line_str.split()
                    if 1 <= len(words) <= 7 and not any(w.lower() in ["the", "this", "and", "or", "in", "with", "from"] for w in [words[0]]):
                        title_found = line_str
                        
            if title_found and len(title_found) >= 3:
                norm_key = title_found.lower().strip()
                if norm_key not in seen_titles and not any(kw in norm_key for kw in ["page", "figure", "table", "university", "author", "isbn"]):
                    seen_titles.add(norm_key)
                    candidates.append({
                        "title": title_found,
                        "hierarchy_number": hierarchy_num,
                        "chunk_id": chunk["chunk_id"],
                        "chunk": chunk
                    })
                    
    return candidates

def _extract_other_topics(
    chunks: List[Dict[str, Any]],
    matched_chunk_ids: Set[str],
    topics: List[Dict[str, Any]],
    model=None
) -> List[Dict[str, Any]]:
    """
    Identifies and structures non-syllabus topics found in the study material.
    """
    candidate_headings = extract_candidate_headings_from_chunks(chunks)
    other_topics = []
    other_topic_idx = 1
    covered_chunk_ids = set(matched_chunk_ids)
    
    # Calculate similarity of candidate headings to syllabus topics
    if candidate_headings and topics:
        syllabus_titles = [t["full_context"].lower() for t in topics]
        
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        cand_titles = [c["title"].lower() for c in candidate_headings]
        all_txts = cand_titles + syllabus_titles
        
        try:
            vec = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
            mat = vec.fit_transform(all_txts)
            c_mat = mat[:len(cand_titles)]
            s_mat = mat[len(cand_titles):]
            sims = cosine_similarity(c_mat, s_mat) # [num_cand, num_syl]
        except Exception:
            sims = np.zeros((len(cand_titles), len(syllabus_titles)))
            
        for i, cand in enumerate(candidate_headings):
            max_syl_sim = float(np.max(sims[i])) if len(syllabus_titles) > 0 else 0.0
            
            # If this heading is NOT strongly similar to any syllabus topic (< 0.40), it is an Other Topic!
            if max_syl_sim < 0.40:
                cand_chunk = cand["chunk"]
                
                # Check if this heading chunk is already covered or has other matching chunks
                topic_chunks = [cand_chunk]
                covered_chunk_ids.add(cand_chunk["chunk_id"])
                
                # Find other chunks mentioning this topic title
                title_keywords = [w.lower() for w in cand["title"].split() if len(w) > 3]
                if title_keywords:
                    for c in chunks:
                        if c["chunk_id"] not in covered_chunk_ids:
                            c_text_lower = c["text"].lower()
                            if all(kw in c_text_lower for kw in title_keywords):
                                topic_chunks.append(c)
                                covered_chunk_ids.add(c["chunk_id"])
                                
                matches_list = []
                for tc in topic_chunks:
                    matches_list.append({
                        "chunk_id": tc["chunk_id"],
                        "text": tc["text"],
                        "page_number": tc["page_number"],
                        "type": tc["type"],
                        "source": tc["source"],
                        "score": 1.0,
                        "similarity_score": 1.0,
                        "confidence_pct": 100.0
                    })
                    
                other_topics.append({
                    "topic_id": f"other_topic_{other_topic_idx}",
                    "title": cand["title"],
                    "unit": "Other Topics Found in Study Material",
                    "section": "",
                    "hierarchy_number": cand["hierarchy_number"],
                    "full_context": f"Other Topics > {cand['title']}",
                    "is_other_topic": True,
                    "similarity_score": 1.0,
                    "confidence_pct": 100.0,
                    "source_chunks": [tc["chunk_id"] for tc in topic_chunks],
                    "matches": matches_list
                })
                other_topic_idx += 1
                
    # Check for remaining unmatched chunks not assigned to syllabus or candidate headings
    remaining_unmatched = [c for c in chunks if c["chunk_id"] not in covered_chunk_ids]
    if remaining_unmatched:
        # Group remaining chunks by source file or into thematic blocks
        for chunk in remaining_unmatched:
            # Extract first meaningful heading or line from chunk
            first_lines = [l.strip() for l in chunk["text"].splitlines() if len(l.strip()) >= 4]
            title_name = first_lines[0][:60] if first_lines else f"Additional Study Notes ({chunk['source']} Page {chunk['page_number']})"
            # Clean up title
            title_name = re.sub(r'^[#*\-•\d\.\s]+', '', title_name).strip()
            if not title_name:
                title_name = f"Additional Notes ({chunk['source']} Page {chunk['page_number']})"
                
            other_topics.append({
                "topic_id": f"other_topic_{other_topic_idx}",
                "title": title_name,
                "unit": "Other Topics Found in Study Material",
                "section": "General Notes",
                "hierarchy_number": "*",
                "full_context": f"Other Topics > {title_name}",
                "is_other_topic": True,
                "similarity_score": 0.85,
                "confidence_pct": 85.0,
                "source_chunks": [chunk["chunk_id"]],
                "matches": [{
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "page_number": chunk["page_number"],
                    "type": chunk["type"],
                    "source": chunk["source"],
                    "score": 0.85,
                    "similarity_score": 0.85,
                    "confidence_pct": 85.0
                }]
            })
            other_topic_idx += 1
            covered_chunk_ids.add(chunk["chunk_id"])
            
    return other_topics

def _match_with_tfidf(
    topics: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    similarity_threshold: float,
    top_k: int
) -> Dict[str, Any]:
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
    
    syllabus_results = []
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
            
            if score >= effective_threshold or (rank == 0 and score > 0.04):
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
        syllabus_results.append({
            "topic_id": topic["topic_id"],
            "title": topic["title"],
            "unit": topic["unit"],
            "section": topic.get("section", ""),
            "hierarchy_number": topic.get("hierarchy_number", ""),
            "full_context": topic["full_context"],
            "is_other_topic": False,
            "similarity_score": topic_matches[0]["similarity_score"] if topic_matches else 0.0,
            "confidence_pct": topic_matches[0]["confidence_pct"] if topic_matches else 0.0,
            "source_chunks": [m["chunk_id"] for m in topic_matches],
            "matches": topic_matches
        })

    # Detect Other Topics from study material
    other_topics = _extract_other_topics(chunks, matched_chunk_ids, topics)
    
    # Combined list for backward compatibility
    combined_topics = syllabus_results + other_topics
    
    # Chunks map
    chunks_map = {c["chunk_id"]: c for c in chunks}
    
    coverage = compute_coverage_audit(syllabus_results)
    
    return {
        "syllabus_topics": syllabus_results,
        "other_topics": other_topics,
        "topics": combined_topics,
        "chunks": chunks_map,
        "coverage": coverage
    }

def match_syllabus_to_document(
    topics: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    similarity_threshold: float = 0.35,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Perform semantic search to match syllabus topics to document chunks.
    Uses SBERT + FAISS if available, otherwise fast TF-IDF.
    Returns structured syllabus_topics, other_topics, chunks_map, and coverage report.
    """
    if not topics or not chunks:
        logger.warning("Empty topics or chunks provided for matching.")
        return {
            "syllabus_topics": [],
            "other_topics": [],
            "topics": [],
            "chunks": {},
            "coverage": compute_coverage_audit([])
        }
        
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
    scores, indices = index.search(topic_embeddings, k=min(top_k, len(chunks)))
    
    # 5. Compile results
    syllabus_results = []
    matched_chunk_ids = set()
    
    for i, topic in enumerate(topics):
        topic_matches = []
        for rank in range(min(top_k, len(chunks))):
            score = float(scores[i][rank])
            idx = int(indices[i][rank])
            
            # FAISS can return -1 if there aren't enough elements
            if idx == -1:
                continue
                
            if score >= similarity_threshold or (rank == 0 and score >= 0.22):
                matched_chunk = chunks[idx]
                matched_chunk_ids.add(matched_chunk["chunk_id"])
                display_score = round(score, 4)
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
        
        # Sort matches by similarity score descending
        topic_matches.sort(key=lambda x: x["score"], reverse=True)
        
        syllabus_results.append({
            "topic_id": topic["topic_id"],
            "title": topic["title"],
            "unit": topic["unit"],
            "section": topic.get("section", ""),
            "hierarchy_number": topic.get("hierarchy_number", ""),
            "full_context": topic["full_context"],
            "is_other_topic": False,
            "similarity_score": topic_matches[0]["similarity_score"] if topic_matches else 0.0,
            "confidence_pct": topic_matches[0]["confidence_pct"] if topic_matches else 0.0,
            "source_chunks": [m["chunk_id"] for m in topic_matches],
            "matches": topic_matches
        })
        
    # 6. Detect Other Topics from study material
    other_topics = _extract_other_topics(chunks, matched_chunk_ids, topics, model=model)
    
    combined_topics = syllabus_results + other_topics
    chunks_map = {c["chunk_id"]: c for c in chunks}
    coverage = compute_coverage_audit(syllabus_results)
    
    logger.info(f"Syllabus matching complete: {len(syllabus_results)} syllabus topics, {len(other_topics)} other topics detected.")
    
    return {
        "syllabus_topics": syllabus_results,
        "other_topics": other_topics,
        "topics": combined_topics,
        "chunks": chunks_map,
        "coverage": coverage
    }

def compute_coverage_audit(matched_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes coverage metrics comparing syllabus topics against study material matches.
    Identifies covered topics vs missing topics.
    """
    # Only calculate coverage on syllabus topics (not other_topics)
    syl_topics = [t for t in matched_results if not t.get("is_other_topic", False)]
    if not syl_topics:
        syl_topics = matched_results
        
    total_topics = len(syl_topics)
    covered_topics = []
    missing_topics = []
    total_excerpts = 0
    
    for item in syl_topics:
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
