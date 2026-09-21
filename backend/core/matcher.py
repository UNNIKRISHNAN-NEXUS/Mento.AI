# -*- coding: utf-8 -*-
"""
Mento.AI Semantic Matcher & Topic Detection Engine
Uses multi-layer matching:
1. Exact Keyword / Heading Match
2. SBERT Vector Embeddings + FAISS / TF-IDF N-gram Cosine Similarity
3. Section & Page-Level Continuity

Maps syllabus topic indexes directly to real study material paragraphs, equations, tables, and images.
Guarantees zero content loss by preserving all remaining source pages and sections.
"""

import re
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple

from backend.core.heading_detector import is_valid_academic_heading, clean_heading_title

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

def extract_keywords(text: str) -> Set[str]:
    """Extract significant lowercase keywords from a topic or heading string."""
    if not text:
        return set()
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "unit", "module",
        "chapter", "section", "part", "general", "notes", "study", "material",
        "introduction", "overview", "basics", "concept", "concepts", "types",
        "definition", "about", "into", "their", "have", "been", "using"
    }
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    return {w for w in words if w not in stopwords}

def compute_keyword_overlap_score(topic_title: str, chunk_text: str, chunk_heading: str = "") -> float:
    """Computes keyword overlap score between topic title and chunk content."""
    t_words = extract_keywords(topic_title)
    if not t_words:
        return 0.0
        
    c_words = extract_keywords(f"{chunk_heading} {chunk_text}")
    if not c_words:
        return 0.0
        
    overlap = t_words.intersection(c_words)
    overlap_ratio = len(overlap) / float(len(t_words))
    
    # Exact substring boost
    clean_t = re.sub(r'[^a-zA-Z0-9\s]', ' ', topic_title.lower()).strip()
    clean_c = re.sub(r'[^a-zA-Z0-9\s]', ' ', f"{chunk_heading} {chunk_text}".lower())
    
    exact_boost = 0.0
    if len(clean_t) >= 4 and clean_t in clean_c:
        exact_boost = 0.4
    elif chunk_heading and clean_t in clean_heading_title(chunk_heading)[0].lower():
        exact_boost = 0.5
        
    return min(1.0, overlap_ratio * 0.6 + exact_boost)

def extract_candidate_headings_from_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts candidate section headers and topic titles from study material chunks.
    Only allows meaningful academic headings.
    """
    candidates = []
    seen_titles = set()
    
    for chunk in chunks:
        if chunk.get("is_structured_section") and chunk.get("heading"):
            heading = chunk["heading"].strip()
            hierarchy = chunk.get("hierarchy_number", "").strip()
            if is_valid_academic_heading(heading) and heading.lower() not in seen_titles:
                seen_titles.add(heading.lower())
                candidates.append({
                    "title": heading,
                    "hierarchy_number": hierarchy,
                    "chunk_id": chunk["chunk_id"],
                    "chunk": chunk
                })
                
        lines = chunk.get("text", "").splitlines()
        for line in lines:
            line_str = line.strip()
            if not is_valid_academic_heading(line_str):
                continue
                
            clean_title, hierarchy_num = clean_heading_title(line_str)
            norm_key = clean_title.lower().strip()
            if norm_key in seen_titles:
                continue
            if not is_valid_academic_heading(clean_title) and not hierarchy_num:
                continue
                
            seen_titles.add(norm_key)
            candidates.append({
                "title": clean_title,
                "hierarchy_number": hierarchy_num,
                "chunk_id": chunk["chunk_id"],
                "chunk": chunk
            })
            
    return candidates

def _extract_other_topics(
    chunks: List[Dict[str, Any]],
    matched_chunk_ids: Set[str],
    topics: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    Identifies non-syllabus topics found in the study material.
    """
    candidate_headings = extract_candidate_headings_from_chunks(chunks)
    other_topics = []
    other_topic_idx = 1
    covered_chunk_ids = set(matched_chunk_ids)
    
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
            sims = cosine_similarity(c_mat, s_mat)
        except Exception:
            sims = np.zeros((len(cand_titles), len(syllabus_titles)))
            
        for i, cand in enumerate(candidate_headings):
            max_syl_sim = float(np.max(sims[i])) if len(syllabus_titles) > 0 else 0.0
            
            # If not already covered by syllabus topics
            if max_syl_sim < 0.40 and cand["chunk"]["chunk_id"] not in covered_chunk_ids:
                cand_chunk = cand["chunk"]
                topic_chunks = [cand_chunk]
                covered_chunk_ids.add(cand_chunk["chunk_id"])
                
                cand_heading_lower = cand["title"].lower()
                for c in chunks:
                    if c["chunk_id"] not in covered_chunk_ids:
                        if c.get("heading", "").lower() == cand_heading_lower:
                            topic_chunks.append(c)
                            covered_chunk_ids.add(c["chunk_id"])
                                
                matches_list = []
                for tc in topic_chunks:
                    matches_list.append({
                        "chunk_id": tc["chunk_id"],
                        "text": tc.get("text", ""),
                        "page_number": tc.get("page_number", 1),
                        "type": tc.get("type", "digital"),
                        "source": tc.get("source", "Study Material"),
                        "images": tc.get("images", []),
                        "tables": tc.get("tables", []),
                        "score": 1.0,
                        "similarity_score": 1.0,
                        "confidence_pct": 100.0
                    })
                    
                src_pages = sorted(set(tc.get("page_number", 1) for tc in topic_chunks))
                total_chars = sum(len(tc.get("text", "")) for tc in topic_chunks)
                
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
                    "source_pages": src_pages,
                    "source_text_chars": total_chars,
                    "source_chunks": [tc["chunk_id"] for tc in topic_chunks],
                    "matches": matches_list
                })
                other_topic_idx += 1
                
    return other_topics, covered_chunk_ids

def _group_remaining_unmatched_chunks(
    chunks: List[Dict[str, Any]],
    covered_chunk_ids: Set[str]
) -> List[Dict[str, Any]]:
    """
    CRITICAL ZERO DATA LOSS HANDLER:
    Gathers all remaining chunks that were not claimed by syllabus topics or explicit other topics.
    Groups them by source document and page numbers so 100% of material is retained.
    """
    remaining_chunks = [c for c in chunks if c["chunk_id"] not in covered_chunk_ids]
    if not remaining_chunks:
        return []

    grouped_by_page: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
    for c in remaining_chunks:
        key = (c.get("source", "Study Material"), c.get("page_number", 1))
        if key not in grouped_by_page:
            grouped_by_page[key] = []
        grouped_by_page[key].append(c)

    additional_topics = []
    add_idx = 1
    
    for (src, p_num), p_chunks in sorted(grouped_by_page.items(), key=lambda item: (item[0][0], item[0][1])):
        matches_list = []
        for c in p_chunks:
            matches_list.append({
                "chunk_id": c["chunk_id"],
                "text": c.get("text", ""),
                "page_number": c.get("page_number", p_num),
                "type": c.get("type", "digital"),
                "source": src,
                "images": c.get("images", []),
                "tables": c.get("tables", []),
                "score": 0.85,
                "similarity_score": 0.85,
                "confidence_pct": 85.0
            })
            
        topic_title = f"Section Notes — Page {p_num} ({src})"
        total_chars = sum(len(c.get("text", "")) for c in p_chunks)
        additional_topics.append({
            "topic_id": f"add_topic_{add_idx}",
            "title": topic_title,
            "unit": "Additional Source Notes & Material",
            "section": "",
            "hierarchy_number": str(p_num),
            "full_context": f"Additional Notes > {topic_title}",
            "is_other_topic": True,
            "similarity_score": 0.85,
            "confidence_pct": 85.0,
            "source_pages": [p_num],
            "source_text_chars": total_chars,
            "source_chunks": [c["chunk_id"] for c in p_chunks],
            "matches": matches_list
        })
        add_idx += 1

    return additional_topics

def match_syllabus_to_document(
    topics: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    similarity_threshold: float = 0.25,
    top_k: int = 25
) -> Dict[str, Any]:
    """
    Perform multi-layer semantic search to map syllabus topics to real study material content.
    Combines:
    1. Keyword/heading match
    2. SBERT embedding cosine similarity (or TF-IDF)
    3. Section continuity
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
    use_sbert = (model is not None and FAISS_AVAILABLE)
    
    chunk_texts = [
        f"{chunk.get('heading', '')} {chunk.get('text', '')}".strip() if chunk.get('heading') else chunk.get("text", "")
        for chunk in chunks
    ]
    topic_texts = [topic["full_context"] for topic in topics]
    
    sim_matrix = None
    
    if use_sbert:
        try:
            chunk_embeddings = model.encode(chunk_texts, show_progress_bar=False, convert_to_numpy=True)
            topic_embeddings = model.encode(topic_texts, show_progress_bar=False, convert_to_numpy=True)
            
            faiss.normalize_L2(chunk_embeddings)
            faiss.normalize_L2(topic_embeddings)
            
            sim_matrix = np.dot(topic_embeddings, chunk_embeddings.T)
        except Exception as emb_err:
            logger.warning(f"SBERT embedding computation failed: {emb_err}. Using TF-IDF.")
            use_sbert = False

    if sim_matrix is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        vectorizer = TfidfVectorizer(ngram_range=(1, 3), sublinear_tf=True, token_pattern=r'(?u)\b[\w-]+\b')
        all_txts = chunk_texts + topic_texts
        mat = vectorizer.fit_transform(all_txts)
        c_mat = mat[:len(chunks)]
        t_mat = mat[len(chunks):]
        sim_matrix = cosine_similarity(t_mat, c_mat)

    syllabus_results = []
    matched_chunk_ids = set()
    
    effective_thresh = min(similarity_threshold, 0.20)

    for i, topic in enumerate(topics):
        topic_matches = []
        topic_title = topic["title"]
        topic_sims = sim_matrix[i]
        
        # Rank chunks by score
        ranked_indices = np.argsort(-topic_sims)
        
        for rank in range(min(top_k, len(chunks))):
            idx = int(ranked_indices[rank])
            sem_score = float(topic_sims[idx])
            chunk = chunks[idx]
            
            # Compute keyword overlap score
            kw_score = compute_keyword_overlap_score(topic_title, chunk.get("text", ""), chunk.get("heading", ""))
            
            # Combined hybrid score (boosted by keyword match)
            combined_score = max(sem_score, kw_score, (sem_score * 0.5 + kw_score * 0.5))
            
            # Match condition: hybrid score >= threshold, or strong keyword presence, or top-1 best match if above minimal baseline
            if combined_score >= effective_thresh or kw_score >= 0.35 or (rank == 0 and combined_score >= 0.10):
                matched_chunk_ids.add(chunk["chunk_id"])
                display_score = min(round(float(combined_score), 4), 0.99)
                topic_matches.append({
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk.get("text", ""),
                    "page_number": chunk.get("page_number", 1),
                    "type": chunk.get("type", "digital"),
                    "source": chunk.get("source", "Study Material"),
                    "images": chunk.get("images", []),
                    "tables": chunk.get("tables", []),
                    "score": display_score,
                    "similarity_score": display_score,
                    "confidence_pct": round(display_score * 100, 1)
                })

        # Sort matches by page number and score
        topic_matches.sort(key=lambda x: (x["page_number"], -x["score"]))
        
        src_pages = sorted(set(m["page_number"] for m in topic_matches))
        src_chars = sum(len(m.get("text", "")) for m in topic_matches)
        
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
            "source_pages": src_pages,
            "source_text_chars": src_chars,
            "source_chunks": [m["chunk_id"] for m in topic_matches],
            "matches": topic_matches
        })

    # Detect other topics & retain 100% of study material
    other_topics, covered_chunk_ids = _extract_other_topics(chunks, matched_chunk_ids, topics)
    additional_notes = _group_remaining_unmatched_chunks(chunks, covered_chunk_ids)
    all_other_topics = other_topics + additional_notes
    
    combined_topics = syllabus_results + all_other_topics
    chunks_map = {c["chunk_id"]: c for c in chunks}
    coverage = compute_coverage_audit(syllabus_results)
    
    return {
        "syllabus_topics": syllabus_results,
        "other_topics": all_other_topics,
        "topics": combined_topics,
        "chunks": chunks_map,
        "coverage": coverage
    }

def compute_coverage_audit(matched_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes coverage metrics comparing syllabus topics against study material matches."""
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
