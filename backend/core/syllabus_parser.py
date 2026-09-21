# -*- coding: utf-8 -*-
"""
Mento.AI Syllabus Parser
Parses structural and flat topics from a syllabus file (PDF, DOCX, TXT).
Detects units, modules, and sub-topics, building a list of searchable topics.
"""

import os
import re
import logging
from typing import List, Dict, Any
from backend.core.parser import parse_document

logger = logging.getLogger("syllabus_parser")

# Regex to detect Units, Modules, or Chapters
UNIT_PATTERN = re.compile(
    r"^(?:UNIT|MODULE|CHAPTER|PART|SECTION|SEM)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)[:\-\.\s\s]+(.*)$",
    re.IGNORECASE
)

# Regex to detect bullet points or numbered lists
TOPIC_PATTERN = re.compile(
    r"^[\s]*[-*•+]\s*(.*)$"  # Bullets like -, *, •
    r"|^[\s]*(\d+(?:\.\d+)*)\.?\s*(.*)$"  # Numbered like 1., 1.1, 1.1.1
    r"|^[\s]*([a-zA-Z])\)\s*(.*)$"  # Letters like a), b)
)

def parse_syllabus(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse a syllabus document and extract a list of topics.
    Captures hierarchical metadata (e.g. Unit / Module headers) to enrich matching.
    """
    try:
        # Read raw text directly for text files, or via parser for PDF/DOCX
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                full_text = f.read()
        else:
            chunks = parse_document(file_path)
            full_text = "\n".join([chunk["text"] for chunk in chunks])
            
        lines = full_text.splitlines()
        
        topics = []
        current_unit = "General"
        current_section = ""
        
        topic_index = 1
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
                
            # Check for Unit/Module header
            unit_match = UNIT_PATTERN.match(line_str)
            if unit_match:
                unit_num = unit_match.group(1).strip()
                unit_title = unit_match.group(2).strip()
                current_unit = f"Unit {unit_num}: {unit_title}"
                current_section = ""  # Reset section on new unit
                logger.info(f"Detected syllabus section: {current_unit}")
                continue
                
            # Check if it's a section header (e.g., ends with colon or contains explicit section keywords)
            if line_str.endswith(":") or (line_str.isupper() and 10 <= len(line_str) <= 60 and any(kw in line_str for kw in ["UNIT", "MODULE", "CHAPTER", "SECTION", "PART", "CONTENTS", "SYLLABUS", "TOPICS"])):
                if not any(kw in line_str for kw in ["SYLLABUS", "CONTENT", "TOPICS", "COURSE"]):
                    current_section = line_str.rstrip(":")
                continue
                
            # Match standard topic patterns (bullet, numbered)
            bullet_match = re.match(r"^[-*•+]\s*(.+)$", line_str)
            num_match = re.match(r"^(\d+(?:\.\d+)*)\.?\s*(.+)$", line_str)
            letter_match = re.match(r"^([a-zA-Z\d]+)\)\s*(.+)$", line_str)
            
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
            elif 2 <= len(line_str) <= 120:
                # Fallback: if it's a simple line, not too long, treat it as a topic
                topic_title = line_str
                
            if topic_title and len(topic_title) >= 2:
                # If topic_title contains comma or semicolon separated terms, expand them into individual topics
                sub_titles = [t.strip() for t in re.split(r'[,;]+', topic_title) if len(t.strip()) >= 2]
                if not sub_titles:
                    sub_titles = [topic_title]
                    
                for sub_t in sub_titles:
                    context_parts = [current_unit]
                    if current_section:
                        context_parts.append(current_section)
                    if hierarchy_number:
                        context_parts.append(hierarchy_number)
                    context_parts.append(sub_t)
                    
                    full_context = " > ".join(context_parts)
                    
                    topics.append({
                        "topic_id": f"topic_{topic_index}",
                        "title": sub_t,
                        "unit": current_unit,
                        "section": current_section,
                        "hierarchy_number": hierarchy_number,
                        "full_context": full_context
                    })
                    topic_index += 1
                
        # If no structured topics were found (e.g., simple list of lines),
        # treat all non-empty lines (length >= 2 chars) as topics
        if not topics:
            logger.info("No structured list patterns found in syllabus. Using line/phrase fallback.")
            for line in lines:
                line_str = line.strip()
                if len(line_str) >= 2:
                    topics.append({
                        "topic_id": f"topic_{topic_index}",
                        "title": line_str[:120],
                        "unit": "General",
                        "section": "",
                        "hierarchy_number": "",
                        "full_context": f"General > {line_str[:120]}"
                    })
                    topic_index += 1
                    
        # If still empty (e.g. single block of text or comma-separated list), split by commas, semicolons, or periods
        if not topics and full_text.strip():
            logger.info("Splitting unstructured syllabus by punctuation...")
            phrases = [p.strip() for p in re.split(r'[,;\.\n]+', full_text) if len(p.strip()) >= 2]
            for p in phrases:
                topics.append({
                    "topic_id": f"topic_{topic_index}",
                    "title": p[:120],
                    "unit": "General",
                    "section": "",
                    "hierarchy_number": "",
                    "full_context": f"General > {p[:120]}"
                })
                topic_index += 1

        # Absolute fail-safe guarantee: Never return empty list
        if not topics:
            raw_title = full_text.strip()[:100] if full_text.strip() else "General Syllabus & Notes"
            logger.info(f"Using absolute fail-safe topic: {raw_title}")
            topics.append({
                "topic_id": "topic_1",
                "title": raw_title,
                "unit": "General",
                "section": "",
                "hierarchy_number": "",
                "full_context": f"General > {raw_title}"
            })

        logger.info(f"Extracted {len(topics)} topics from syllabus.")
        return topics
        
    except Exception as e:
        logger.error(f"Error parsing syllabus {file_path}: {e}")
        # Fail-safe catch-all
        return [{
            "topic_id": "topic_1",
            "title": "General Syllabus & Extracted Notes",
            "unit": "General",
            "section": "",
            "hierarchy_number": "",
            "full_context": "General > General Syllabus & Extracted Notes"
        }]
