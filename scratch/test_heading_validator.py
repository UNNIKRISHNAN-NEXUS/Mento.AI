# -*- coding: utf-8 -*-
"""Test Heading Detection and Validation Rules."""

import re

# Stopwords & single generic words that can never be standalone headings
INVALID_SINGLE_WORDS = {
    "the", "and", "where", "which", "using", "this", "following", "therefore",
    "note", "example", "figure", "table", "because", "is", "are", "with", "from",
    "that", "for", "about", "then", "such", "each", "between", "during", "signal",
    "system", "method", "equation", "property", "value", "type", "types", "form",
    "case", "point", "output", "input", "result", "characteristics", "function",
    "definition", "introduction", "summary", "conclusion", "chapter", "unit",
    "section", "module", "part", "page", "author", "university", "dr", "prof",
    "also", "can", "could", "would", "should", "will", "shall", "may", "might",
    "must", "has", "have", "had", "been", "being", "do", "does", "did", "done"
}

# Common narrative sentence starters that must never become headings
SENTENCE_STARTERS = [
    r"^(the|a|an)\s+[a-z]",
    r"^there\s+(are|is|were|was)\b",
    r"^this\s+(method|technique|approach|signal|system|is|can|will|has)\b",
    r"^these\s+(methods|signals|systems|are)\b",
    r"^as\s+(shown|seen|discussed|mentioned|stated|described)\b",
    r"^it\s+(can|is|was|should|may|will)\b",
    r"^in\s+(order|this|the|addition|contrast|general|other)\b",
    r"^we\s+(have|can|see|define|observe|obtain|note)\b",
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
]

NUMBERED_HEADING_PATTERN = re.compile(
    r'^(?:(?:UNIT|MODULE|CHAPTER|PART|SECTION)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)[:\-\.\s\s]+)?'
    r'(\d+(?:\.\d+)*|[A-Z]\.|\b[IVXLCDM]+\.)\s+(.+)$',
    re.IGNORECASE
)

def is_valid_academic_heading(line: str) -> bool:
    if not line:
        return False
    s = line.strip()
    if len(s) < 3 or len(s) > 85:
        return False
        
    # Check if sentence-like punctuation at the end
    if s.endswith(('.', ',', ';', ':', '?', '!')):
        # Only allowed if it's "1." or "Chapter 1:" with text after, not ending with a period/comma
        return False
        
    # Strip numbering to analyze core text
    core_text = s
    m = NUMBERED_HEADING_PATTERN.match(s)
    if m:
        core_text = m.group(3).strip()
        
    # Clean core text
    core_clean = re.sub(r'^[#*\-•\d\.\s\(\)\:\/]+', '', core_text).strip()
    if len(core_clean) < 3:
        return False
        
    core_lower = core_clean.lower()
    
    # Check single invalid words
    words = core_clean.split()
    if len(words) == 1:
        if core_lower in INVALID_SINGLE_WORDS:
            return False
        # If single word, must be at least 4 letters, capitalized, and not in stop words
        if len(core_clean) < 4 or not core_clean[0].isupper():
            return False
            
    # Check narrative sentence starters
    for pat in SENTENCE_STARTERS:
        if re.search(pat, core_lower):
            return False
            
    # Check for excessive sentence-like verbs
    narrative_verb_patterns = [
        r"\b(is|are|was|were)\s+(defined|represented|used|calculated|shown|given|obtained|categorized|described)\b",
        r"\bcan\s+be\s+(used|seen|calculated|obtained|modeled)\b",
        r"\bconveys\s+information\b"
    ]
    for vp in narrative_verb_patterns:
        if re.search(vp, core_lower):
            return False
            
    # Sentence word count limit
    if len(words) > 8:
        return False
        
    # Check metadata / boilerplate
    boilerplate = ["copyright", "rights reserved", "page ", "university", "department", "author", "isbn", "http", "www.", "@"]
    if any(bp in core_lower for bp in boilerplate):
        return False
        
    # Check valid structure:
    # 1. Was explicitly numbered (e.g. "1.1 Classification of Signals")
    if m and len(words) >= 1:
        return True
        
    # 2. Capitalized academic heading (e.g. "Fourier Transform", "Z-Transform", "IIR Filters")
    first_word = words[0]
    if len(words) == 1 and first_word.lower() in INVALID_SINGLE_WORDS:
        return False
        
    if core_clean.isupper() or core_clean.istitle() or any(w[0].isupper() for w in words):
        # Must have at least one substantial noun/concept word (>= 4 letters)
        if any(len(w) >= 4 for w in words):
            return True
            
    return False

test_bad = [
    "the", "where", "following", "and", "signal", "which", "using", "is", "characteristics",
    "The signal is represented", "There are two types", "This method can be used",
    "A signal is a function that conveys information about the state or behavior of a physical system.",
    "Page 12 of 45", "Department of Electrical Engineering", "Copyright 2026. All rights reserved."
]

test_good = [
    "1. Introduction to Signals",
    "2. Classification of Signals",
    "3. Continuous-Time Signals",
    "4. Discrete-Time Signals",
    "5. Periodic and Aperiodic Signals",
    "6. Energy and Power Signals",
    "7. Fourier Transform",
    "8. Sampling Theorem",
    "Z-Transform",
    "Noise Reduction Techniques",
    "IIR Filters",
    "Window Functions",
    "UNIT 1: SIGNALS AND SYSTEMS"
]

print("--- Testing BAD Candidates (Should all be False) ---")
for b in test_bad:
    res = is_valid_academic_heading(b)
    print(f"[{'PASS' if not res else 'FAIL'}] '{b}' -> {res}")
    assert not res, f"Expected False for '{b}'"

print("\n--- Testing GOOD Candidates (Should all be True) ---")
for g in test_good:
    res = is_valid_academic_heading(g)
    print(f"[{'PASS' if res else 'FAIL'}] '{g}' -> {res}")
    assert res, f"Expected True for '{g}'"

print("\nALL HEADING VALIDATION TESTS PASSED!")
