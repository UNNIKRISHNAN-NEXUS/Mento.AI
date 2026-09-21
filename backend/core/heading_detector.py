# -*- coding: utf-8 -*-
"""
Mento.AI Structure-Aware Academic Heading & Topic Detector
Detects meaningful academic section headers, numbered topics, and chapter titles.
Strictly filters out stopwords, random OCR fragments, narrative sentences, and metadata.
Preserves page-level granularity so no source page or paragraph is lost.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("heading_detector")

# Domain-specific words that are NEVER valid as STANDALONE (single-word) headings
INVALID_STANDALONE_WORDS = {
    "note", "example", "figure", "table",
    "definition", "introduction", "summary", "conclusion",
    "chapter", "unit", "section", "module", "part", "page",
    "author", "university", "dr", "prof"
}

# Grammatical stopwords/connectors that are NEVER valid as first word of ANY heading
INVALID_FIRST_WORDS = {
    "the", "and", "where", "which", "using", "this", "following", "therefore",
    "because", "is", "are", "with", "from", "that", "for", "about", "then",
    "such", "each", "between", "during", "also", "can", "could", "would",
    "should", "will", "shall", "may", "might", "must", "has", "have", "had",
    "been", "being", "do", "does", "did", "done", "etc", "viz", "ie", "eg",
    "i.e", "e.g", "al", "et", "below", "above", "given"
}

INVALID_SINGLE_WORDS = INVALID_STANDALONE_WORDS | INVALID_FIRST_WORDS

SENTENCE_STARTERS = [
    r"^(the|a|an)\s+[a-z]",
    r"^there\s+(are|is|were|was)\b",
    r"^this\s+(method|technique|approach|signal|system|paper|chapter|section|is|can|will|has)\b",
    r"^these\s+(methods|signals|systems|techniques|are|were)\b",
    r"^as\s+(shown|seen|discussed|mentioned|stated|described|defined)\b",
    r"^it\s+(can|is|was|should|may|will|has)\b",
    r"^in\s+(order|this|the|addition|contrast|general|other|such)\b",
    r"^we\s+(have|can|see|define|observe|obtain|note|find)\b",
    r"^let\s+us\b",
    r"^consider\s+(the|a|an)\b",
    r"^refer\s+to\b",
    r"^for\s+(example|instance)\b",
    r"^note\s+that\b",
    r"^according\s+to\b",
    r"^because\s+of\b",
    r"^which\s+(is|are|means|shows|conveys)\b",
    r"^where\s+[a-zA-Z]",
    r"^following\s+(are|is|the)\b",
    r"^on\s+the\s+other\s+hand\b",
    r"^hence\b",
    r"^thus\b",
]

NUMBERED_HEADING_PATTERN = re.compile(
    r'^(?:(?:UNIT|MODULE|CHAPTER|PART|SECTION|SEM)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)[:\-\.\u2013\u2014\s]+)?'
    r'(\d+(?:\.\d+)*\.?|[A-Z]\.|\b[IVXLCDM]+\.?)\s+(.+)$',
    re.IGNORECASE
)

UNIT_CHAPTER_ONLY_PATTERN = re.compile(
    r'^(?:(UNIT|MODULE|CHAPTER|PART|SECTION|SEM)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN))[:\-\.\u2013\u2014\s]*(.*)$',
    re.IGNORECASE
)

def is_valid_academic_heading(line: str) -> bool:
    """
    Evaluates whether a text line is a genuine academic section or topic heading.
    """
    if not line:
        return False
        
    s = line.strip()
    if len(s) < 3 or len(s) > 85:
        return False
        
    if s.endswith(('.', ',', ';', '?', '!')):
        return False
        
    if any(op in s for op in ['=', '≈', '≠', '≤', '≥', '→', '⇒', '∫', '∑', '∏', '±']):
        return False
        
    u_match = UNIT_CHAPTER_ONLY_PATTERN.match(s)
    if u_match:
        sub_title = u_match.group(3).strip()
        sub_clean = re.sub(r'^[\u2013\u2014\:\-\.\s]+', '', sub_title).strip()
        if sub_clean:
            if len(sub_clean) >= 3:
                return True
        else:
            return True
            
    m = NUMBERED_HEADING_PATTERN.match(s)
    hierarchy_num = ""
    core_text = s
    if m:
        hierarchy_num = m.group(2).strip()
        core_text = m.group(3).strip()
        
    core_clean = re.sub(r'^[#*\-•\d\.\s\(\)\:\/]+', '', core_text).strip()
    if len(core_clean) < 3:
        return False
        
    core_lower = core_clean.lower()
    words = core_clean.split()
    
    if len(words) == 1:
        if core_lower in INVALID_SINGLE_WORDS:
            return False
        if len(core_clean) < 4 or not core_clean[0].isupper():
            return False
            
    for pat in SENTENCE_STARTERS:
        if re.search(pat, core_lower):
            return False
            
    narrative_verb_patterns = [
        r"\b(is|are|was|were)\s+(defined|represented|used|calculated|shown|given|obtained|categorized|described|conveyed)\b",
        r"\bcan\s+be\s+(used|seen|calculated|obtained|modeled|classified)\b",
        r"\bconveys\s+information\b",
        r"\bplays\s+an?\s+important\s+role\b",
        r"\bconsists\s+of\b",
        r"\brefers\s+to\b",
        r"\b(include|includes|including|such as|as follows|given by|namely)\b"
    ]
    for vp in narrative_verb_patterns:
        if re.search(vp, core_lower):
            return False
            
    if len(words) > 8:
        return False
        
    boilerplate = [
        "copyright", "rights reserved", "page ", "university", "department",
        "author", "isbn", "http", "www.", "@", "email", "all rights",
        "lecture notes", "syllabus", "course code", "semester"
    ]
    if any(bp in core_lower for bp in boilerplate):
        return False
        
    if m and len(words) >= 1:
        return True
        
    if not core_clean[0].isupper():
        return False
        
    first_word = words[0].lower()
    prepositions_and_conjunctions = {
        "into", "from", "with", "at", "by", "for", "of", "on", "in",
        "where", "when", "which", "and", "or", "but", "so", "as", "if",
        "that", "then", "than", "such", "also", "thus", "hence", "therefore",
        "while", "after", "before", "during", "since", "until"
    }
    if first_word in prepositions_and_conjunctions or first_word in INVALID_FIRST_WORDS:
        return False
        
    capitalized_count = sum(1 for w in words if w and w[0].isupper())
    required_cap = max(1, (len(words) + 1) // 2)
    if capitalized_count < required_cap:
        return False
    
    if any(len(w) >= 4 and w.lower() not in INVALID_FIRST_WORDS for w in words):
        return True
            
    return False

def clean_heading_title(line: str) -> Tuple[str, str]:
    """
    Extracts clean heading title and hierarchy number.
    Returns: (clean_title, hierarchy_number)
    """
    s = line.strip()
    u_match = UNIT_CHAPTER_ONLY_PATTERN.match(s)
    if u_match:
        unit_type = u_match.group(1).split()[0].title()
        unit_num = u_match.group(2).strip()
        unit_title = u_match.group(3).strip()
        title_clean = re.sub(r'^[\u2013\u2014\:\-\.\s]+', '', unit_title).strip()
        prefix = f"{unit_type} {unit_num}"
        if title_clean:
            return title_clean, prefix
        return prefix, prefix

    m = NUMBERED_HEADING_PATTERN.match(s)
    if m:
        hierarchy = m.group(2).strip().rstrip('.')
        title = m.group(3).strip()
        title_clean = re.sub(r'^[:\-\.\s]+', '', title).strip()
        return title_clean, hierarchy
        
    clean = re.sub(r'^[#*\-•\d\.\s\(\)\:\/]+', '', s).strip()
    clean = re.sub(r'[:\s]+$', '', clean)
    return clean, ""

def segment_into_sections(
    raw_blocks: List[Dict[str, Any]],
    doc_source: str
) -> List[Dict[str, Any]]:
    """
    Segments document blocks into coherent logical sections.
    Preserves exact page numbers per paragraph so no source pages or paragraphs are collapsed.
    """
    sections = []
    current_heading = None
    current_hierarchy = ""
    current_page = 1
    current_type = "digital"
    current_paragraphs = []
    current_images = []
    current_tables = []
    seen_img_ids = set()
    section_counter = 1
    
    def save_current_section():
        nonlocal current_heading, current_hierarchy, current_paragraphs, current_images, current_tables, seen_img_ids, current_page, current_type, section_counter
        if not current_paragraphs and not current_images and not current_tables:
            return
            
        text_content = "\n\n".join(current_paragraphs).strip()
        if len(text_content) < 10 and not current_images and not current_tables:
            current_paragraphs = []
            current_images = []
            current_tables = []
            seen_img_ids = set()
            return
            
        title = current_heading or f"Section Notes (Page {current_page})"
        full_ctx = f"{current_hierarchy} {title}".strip() if current_hierarchy else title
        section_imgs = list(current_images)
        section_tabs = list(current_tables)
        
        # Sub-divide if section is excessively long (>1200 chars) while preserving page context
        if len(text_content) > 1200:
            sub_chunks = []
            cur_sub = []
            cur_sub_len = 0
            for p in current_paragraphs:
                cur_sub.append(p)
                cur_sub_len += len(p)
                if cur_sub_len >= 800:
                    sub_chunks.append("\n\n".join(cur_sub))
                    cur_sub = []
                    cur_sub_len = 0
            if cur_sub:
                sub_chunks.append("\n\n".join(cur_sub))
                
            for s_idx, s_text in enumerate(sub_chunks):
                sec_id = f"{doc_source}_sec_{section_counter}_{s_idx+1}"
                chunk_imgs = section_imgs if s_idx == 0 else []
                chunk_tabs = section_tabs if s_idx == 0 else []
                sections.append({
                    "chunk_id": sec_id,
                    "section_id": sec_id,
                    "heading": title,
                    "hierarchy_number": current_hierarchy,
                    "full_context": full_ctx,
                    "page_number": current_page,
                    "source": doc_source,
                    "type": current_type,
                    "paragraphs": current_paragraphs,
                    "text": s_text,
                    "images": chunk_imgs,
                    "tables": chunk_tabs,
                    "is_structured_section": bool(current_heading)
                })
            section_counter += 1
        else:
            sec_id = f"{doc_source}_sec_{section_counter}"
            sections.append({
                "chunk_id": sec_id,
                "section_id": sec_id,
                "heading": title,
                "hierarchy_number": current_hierarchy,
                "full_context": full_ctx,
                "page_number": current_page,
                "source": doc_source,
                "type": current_type,
                "paragraphs": list(current_paragraphs),
                "text": text_content,
                "images": section_imgs,
                "tables": section_tabs,
                "is_structured_section": bool(current_heading)
            })
            section_counter += 1
            
        current_paragraphs = []
        current_images = []
        current_tables = []
        seen_img_ids = set()
        
    last_page_seen = 1
    
    for block in raw_blocks:
        page_num = block.get("page_number", 1)
        b_type = block.get("type", "digital")
        text = block.get("text", "").strip()
        block_imgs = block.get("images", [])
        block_tabs = block.get("tables", [])
        
        # If page number changed and we don't have an explicit structured heading spanning it,
        # save the previous page's section to preserve page boundary granularity!
        if page_num != last_page_seen and not current_heading and (current_paragraphs or current_images or current_tables):
            save_current_section()
            current_page = page_num
            
        last_page_seen = page_num
        
        for img in block_imgs:
            img_key = img.get("image_id") or img.get("path")
            if img_key and img_key not in seen_img_ids:
                seen_img_ids.add(img_key)
                current_images.append(img)
                
        for tab in block_tabs:
            current_tables.append(tab)
        
        if not text:
            continue
            
        lines = text.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
                
            if is_valid_academic_heading(line_str):
                save_current_section()
                clean_title, hierarchy = clean_heading_title(line_str)
                current_heading = clean_title
                current_hierarchy = hierarchy
                current_page = page_num
                current_type = b_type
            else:
                if not current_paragraphs:
                    current_page = page_num
                    current_type = b_type
                current_paragraphs.append(line_str)
                
    save_current_section()
    return sections
