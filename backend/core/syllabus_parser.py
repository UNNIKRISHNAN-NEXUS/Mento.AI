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
        # Re-use our parser to extract page chunks from the syllabus
        chunks = parse_document(file_path)
        full_text = "\n".join([chunk["text"] for chunk in chunks])
        lines = full_text.split("\n")
        
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
                
            # Check if it's a major heading (e.g., all uppercase and moderately short)
            if line_str.isupper() and len(line_str) < 80 and not line_str.startswith("-"):
                # If it's a new main header
                if any(kw in line_str for kw in ["SYLLABUS", "CONTENT", "TOPICS", "COURSE", "OBJECTIVE", "OUTCOME"]):
                    continue
                current_section = line_str
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
            elif 5 <= len(line_str) <= 100:
                # Fallback: if it's a simple line, not too long, treat it as a topic
                # provided it doesn't look like a standard paragraph
                topic_title = line_str
                
            if topic_title and len(topic_title) > 3:
                # Build context-aware search title
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
                
        # If no structured topics were found (e.g., simple list of lines),
        # treat all non-empty lines between 10 and 150 characters as topics
        if not topics:
            logger.info("No structured list patterns found in syllabus. Using raw line fallback.")
            for i, line in enumerate(lines):
                line_str = line.strip()
                if 10 <= len(line_str) <= 120:
                    topics.append({
                        "topic_id": f"topic_{topic_index}",
                        "title": line_str,
                        "unit": "General",
                        "section": "",
                        "hierarchy_number": "",
                        "full_context": f"General > {line_str}"
                    })
                    topic_index += 1
                    
        logger.info(f"Extracted {len(topics)} topics from syllabus.")
        return topics
        
    except Exception as e:
        logger.error(f"Error parsing syllabus {file_path}: {e}")
        raise e
