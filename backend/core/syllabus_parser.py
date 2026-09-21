# -*- coding: utf-8 -*-
"""
Mento.AI Syllabus Parser
Parses structural and flat topics from a syllabus file (PDF, DOCX, TXT).
Preserves line-by-line structure to accurately detect:
- Units / Modules / Chapters
- Numbered Topics (e.g. 1. Sampling, 1.1 Fourier Transform)
- Bullet Points (e.g. • Energy Signals, - Modulation)
- Subtopics and course sections
"""

import os
import re
import logging
from typing import List, Dict, Any
import pymupdf
from docx import Document as DocxDocument

from backend.core.ocr_engine import extract_text_from_pixmap, OCR_AVAILABLE

logger = logging.getLogger("syllabus_parser")

UNIT_PATTERN = re.compile(
    r"^(?:UNIT|MODULE|CHAPTER|PART|SECTION|SEM)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)[:\-\.\s\s]+(.*)$",
    re.IGNORECASE
)

BULLET_PATTERN = re.compile(r"^[-*•+]\s*(.+)$")
NUMBERED_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\.?\s*(.+)$")
LETTER_PATTERN = re.compile(r"^([a-zA-Z\d]+)\)\s*(.+)$")

def extract_raw_syllabus_text(file_path: str) -> str:
    """
    Extracts raw text preserving line breaks and outline formatting.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
            
    elif ext == ".pdf":
        text_lines = []
        doc = pymupdf.open(file_path)
        for i in range(len(doc)):
            page = doc.load_page(i)
            native_text = page.get_text("text") or ""
            alpha_chars = sum(1 for c in native_text if c.isalnum())
            
            if alpha_chars >= 30:
                text_lines.append(native_text)
            elif OCR_AVAILABLE:
                pix = page.get_pixmap(dpi=200)
                ocr_text = extract_text_from_pixmap(pix)
                text_lines.append(ocr_text)
            else:
                text_lines.append(native_text)
        doc.close()
        return "\n".join(text_lines)
        
    elif ext == ".docx":
        try:
            doc = DocxDocument(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception:
            pass
            
    return ""

def parse_syllabus(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse a syllabus document into a structured list of searchable topic dictionaries.
    """
    try:
        raw_text = extract_raw_syllabus_text(file_path)
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        
        topics = []
        current_unit = "General"
        current_section = ""
        topic_index = 1
        
        for line_str in lines:
            # 1. Check for Unit/Module/Chapter header
            unit_match = UNIT_PATTERN.match(line_str)
            if unit_match:
                unit_num = unit_match.group(1).strip()
                unit_title = unit_match.group(2).strip()
                current_unit = f"Unit {unit_num}: {unit_title}" if unit_title else f"Unit {unit_num}"
                current_section = ""
                continue
                
            # 2. Check for section header
            if line_str.endswith(":") or (line_str.isupper() and 8 <= len(line_str) <= 60 and any(kw in line_str for kw in ["UNIT", "MODULE", "CHAPTER", "SECTION", "PART", "CONTENTS", "SYLLABUS", "TOPICS"])):
                if not any(kw in line_str for kw in ["SYLLABUS", "CONTENT", "TOPICS", "COURSE"]):
                    current_section = line_str.rstrip(":")
                continue
                
            # Ignore document title banners like "COURSE SYLLABUS: EC8352 SIGNALS AND SYSTEMS"
            if re.match(r'^(?:COURSE|SYLLABUS|CURRICULUM|OUTLINE|LECTURE)\b', line_str, re.IGNORECASE) and len(line_str) <= 60:
                continue
                
            # 3. Match bullet / numbered / letter topics
            bullet_match = BULLET_PATTERN.match(line_str)
            num_match = NUMBERED_PATTERN.match(line_str)
            letter_match = LETTER_PATTERN.match(line_str)
            
            topic_title = ""
            hierarchy_number = ""
            
            if bullet_match:
                topic_title = bullet_match.group(1).strip()
            elif num_match:
                hierarchy_number = num_match.group(1).strip()
                topic_title = num_match.group(2).strip()
            elif letter_match:
                hierarchy_number = letter_match.group(1).strip()
                topic_title = letter_match.group(2).strip()
            elif 3 <= len(line_str) <= 100:
                topic_title = line_str
                
            if topic_title and len(topic_title) >= 2:
                # Add topic
                context_parts = [current_unit]
                if current_section:
                    context_parts.append(current_section)
                if hierarchy_number:
                    context_parts.append(hierarchy_number)
                context_parts.append(topic_title)
                
                full_context = " > ".join(context_parts)
                
                topics.append({
                    "topic_id": f"topic_{topic_index}",
                    "title": topic_title,
                    "unit": current_unit,
                    "section": current_section,
                    "hierarchy_number": hierarchy_number,
                    "full_context": full_context
                })
                topic_index += 1
                
        # Fallback if no structured topics found
        if not topics:
            for line_str in lines:
                if len(line_str) >= 3 and not re.match(r'^(?:COURSE|SYLLABUS)\b', line_str, re.IGNORECASE):
                    topics.append({
                        "topic_id": f"topic_{topic_index}",
                        "title": line_str[:100],
                        "unit": "General",
                        "section": "",
                        "hierarchy_number": "",
                        "full_context": f"General > {line_str[:100]}"
                    })
                    topic_index += 1
                    
        if not topics:
            raw_title = raw_text.strip()[:80] if raw_text.strip() else "General Syllabus Topics"
            topics.append({
                "topic_id": "topic_1",
                "title": raw_title,
                "unit": "General",
                "section": "",
                "hierarchy_number": "",
                "full_context": f"General > {raw_title}"
            })

        logger.info(f"Syllabus parsed: {len(topics)} topics successfully extracted.")
        return topics
        
    except Exception as e:
        logger.error(f"Error parsing syllabus {file_path}: {e}")
        return [{
            "topic_id": "topic_1",
            "title": "General Syllabus Topics",
            "unit": "General",
            "section": "",
            "hierarchy_number": "",
            "full_context": "General > General Syllabus Topics"
        }]
