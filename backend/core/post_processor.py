# -*- coding: utf-8 -*-
"""
Mento.AI OCR & Text Post-Processor
Fixes OCR misspellings, mid-sentence line breaks, missing spaces, broken words,
hyphenated line wraps, and layout misalignments in extracted study materials.
"""

import re
import logging
from typing import List

from backend.core.heading_detector import is_valid_academic_heading

logger = logging.getLogger("post_processor")

# Common OCR Confusable Replacements (Word-level regexes)
OCR_WORD_REPLACEMENTS = [
    (r'\bThermodynam1cs\b', 'Thermodynamics'),
    (r'\bthermodynam1cs\b', 'thermodynamics'),
    (r'\bphys1cs\b', 'physics'),
    (r'\bPhys1cs\b', 'Physics'),
    (r'\bEquat1on\b', 'Equation'),
    (r'\bequat1on\b', 'equation'),
    (r'\bSolut1on\b', 'Solution'),
    (r'\bsolut1on\b', 'solution'),
    (r'\bcomp1ete\b', 'complete'),
    (r'\ba1so\b', 'also'),
    (r'\brnolecule\b', 'molecule'),
    (r'\brnolecules\b', 'molecules'),
    (r'\brnater\b', 'water'),
    (r'\brnodem\b', 'modern'),
    (r'\brnodel\b', 'model'),
    (r'\bteh\b', 'the'),
    (r'\badn\b', 'and'),
    (r'\bw/o\b', 'without'),
    (r'\bw/\b', 'with'),
    (r'\bb/w\b', 'between'),
    (r'\be\.g\.\b', 'e.g.,'),
    (r'\bi\.e\.\b', 'i.e.,'),
    (r'\bfig\.\b', 'Figure'),
    (r'\beq\.\b', 'Equation'),
]

def fix_ocr_spelling(text: str) -> str:
    """Correct common OCR letter substitution errors and common typos."""
    if not text:
        return ""
        
    # Apply word-level OCR fixes
    for pattern, replacement in OCR_WORD_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
        
    # Fix '1' substituted for 'l' inside alphabetical words (e.g. 'e1ement' -> 'element', 'ca1culate' -> 'calculate')
    def replace_1_with_l(match):
        word = match.group(0)
        # Only replace if surrounded by letters and not part of a math equation or number
        if re.search(r'[a-zA-Z]1[a-zA-Z]', word):
            return word.replace('1', 'l')
        return word
        
    text = re.sub(r'\b[a-zA-Z]*1[a-zA-Z]+\b', replace_1_with_l, text)
    
    # Fix '0' substituted for 'O' inside uppercase words of 4+ letters (e.g. 'PR0CESS' -> 'PROCESS')
    def replace_0_with_O(match):
        word = match.group(0)
        # Avoid math variables like X0Y or R0C
        if len(word) >= 4 and re.search(r'[A-Z]0[A-Z]', word):
            return word.replace('0', 'O')
        return word
        
    text = re.sub(r'\b[A-Z]{2,}0[A-Z]+\b', replace_0_with_O, text)
    
    return text

def unwrap_line_breaks(text: str) -> str:
    """
    Intelligently unwrap line breaks caused by OCR or PDF page margins.
    Joins lines that belong to the same sentence/paragraph.
    """
    if not text:
        return ""
        
    # 1. Fix hyphenated line breaks (e.g. "thermo-\n dynamic" -> "thermodynamic")
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    lines = text.splitlines()
    unwrapped_paragraphs: List[str] = []
    current_para: List[str] = []
    
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            if current_para:
                unwrapped_paragraphs.append(" ".join(current_para))
                current_para = []
            continue
            
        # Determine if this line is a structural heading, bullet point, or equation
        is_bullet = bool(re.match(r'^([\•\-\*\d+\.]|\([a-z0-9]+\))\s+', line))
        is_heading = is_valid_academic_heading(line)
        is_eq = bool(re.search(r'(=|→|⇒|∫|∑|∏|√|sin|cos|tan|log)\s', line))
        
        if is_bullet or is_heading or is_eq:
            if current_para:
                unwrapped_paragraphs.append(" ".join(current_para))
                current_para = []
            unwrapped_paragraphs.append(line)
            continue
            
        if not current_para:
            current_para.append(line)
        else:
            prev_line = current_para[-1]
            # If previous line ends with sentence punctuation (. ! ? :), start new paragraph line
            if prev_line[-1] in '.!?:;':
                unwrapped_paragraphs.append(" ".join(current_para))
                current_para = [line]
            else:
                # Mid-sentence line break -> join with space
                current_para.append(line)
                
    if current_para:
        unwrapped_paragraphs.append(" ".join(current_para))
        
    return "\n\n".join(unwrapped_paragraphs)

def clean_and_normalize_text(text: str) -> str:
    """
    Master post-processing pipeline for extracted text.
    Corrects spelling, unwraps line breaks, removes noise characters, and formats spacing.
    Preserves math equations, exponents, and subscript notations.
    """
    if not text:
        return ""
        
    # 1. Fix OCR spelling & character substitutions
    processed = fix_ocr_spelling(text)
    
    # 2. Unwrap line breaks & reassemble paragraphs
    processed = unwrap_line_breaks(processed)
    
    # 3. Clean up multiple spaces & misplaced punctuation spaces
    processed = re.sub(r'[ \t]{2,}', ' ', processed)
    processed = re.sub(r'\s+([,\.\?\!;\:])', r'\1', processed)
    processed = re.sub(r'\([ \t]+', '(', processed)
    processed = re.sub(r'[ \t]+\)', ')', processed)
    
    # 4. Remove isolated OCR noise characters (lone '|', '~', '¬', '¦') without removing '^' or '_'
    processed = re.sub(r'(?:\A|\s)[\|~¬¦](?=\s|\Z)', ' ', processed)
    
    # 5. Normalize paragraph spacing
    processed = re.sub(r'\n{3,}', '\n\n', processed)
    
    return processed.strip()
