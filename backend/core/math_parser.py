# -*- coding: utf-8 -*-
"""
Mento.AI Mathematical Parser & Symbol Normalizer
Detects mathematical equations, functions, symbols, and LaTeX notation.
Normalizes math syntax into clean Unicode math notation for DOCX and PDF documents.
"""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("math_parser")

# LaTeX to Unicode Symbol Mapping
LATEX_SYMBOL_MAP: Dict[str, str] = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\zeta": "ζ", r"\eta": "η", r"\theta": "θ",
    r"\iota": "ι", r"\kappa": "κ", r"\lambda": "λ", r"\mu": "μ",
    r"\nu": "ν", r"\xi": "ξ", r"\pi": "π", r"\rho": "ρ",
    r"\sigma": "σ", r"\tau": "τ", r"\phi": "φ", r"\chi": "χ",
    r"\psi": "ψ", r"\omega": "ω", r"\Delta": "Δ", r"\Theta": "Θ",
    r"\Lambda": "Λ", r"\Sigma": "Σ", r"\Phi": "Φ", r"\Omega": "Ω",
    r"\int": "∫", r"\sum": "∑", r"\prod": "∏", r"\sqrt": "√",
    r"\infty": "∞", r"\approx": "≈", r"\neq": "≠", r"\leq": "≤",
    r"\geq": "≥", r"\pm": "±", r"\partial": "∂", r"\nabla": "∇",
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\rightarrow": "→",
    r"\Rightarrow": "⇒", r"\in": "∈", r"\subset": "⊂", r"\cup": "∪",
    r"\cap": "∩", r"\forall": "∀", r"\exists": "∃"
}

# Superscripts and Subscripts
SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'x': 'ˣ', 'y': 'ʸ'
}

SUBSCRIPT_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ', 'n': 'ₙ', 'm': 'ₘ'
}

# Math Function Pattern
MATH_FUNCTIONS = [
    "sin", "cos", "tan", "cot", "sec", "csc", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "log", "ln", "exp", "lim", "max", "min",
    "arg", "det", "tr", "dim", "ker", "deg", "mod"
]

def is_math_expression(text: str) -> bool:
    """
    Check if a text paragraph contains mathematical notation or equations.
    """
    if not text:
        return False
        
    # Check for Unicode math symbols
    math_chars = "∫∑∏√∞≈≠≤≥±∂∇·×÷→⇒∈⊂∪∩∀∃αβγδθλμπσφωΔ"
    if any(ch in text for ch in math_chars):
        return True
        
    # Check for LaTeX commands
    if re.search(r"\\[a-zA-Z]+", text):
        return True
        
    # Check for math patterns (e.g. f(x) =, dy/dx, x^2 + y^2)
    patterns = [
        r"\b[a-zA-Z]\([a-zA-Z0-9,\s]+\)\s*=", # f(x) =
        r"d[yza-z]/d[xa-z]",                  # dy/dx
        r"\b(sin|cos|tan|log|ln|lim)\s*\(",    # sin(x), log(n)
        r"[a-zA-Z0-9_\.]+\^[0-9a-zA-Z]+",    # x^2, e^x
        r"\b\d+\s*[\+\-\*/\=]\s*\d+\b",      # 2 + 2 = 4
        r"\b\sqrt\{?[a-zA-Z0-9\s]+\}?"       # sqrt(x)
    ]
    
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
            
    return False

def convert_latex_to_unicode(text: str) -> str:
    """
    Convert LaTeX symbols, superscripts, and subscripts to clean Unicode math text.
    """
    if not text:
        return ""
        
    res = text
    
    # Replace LaTeX symbol commands
    for latex, uni in LATEX_SYMBOL_MAP.items():
        res = res.replace(latex, uni)
        
    # Convert sqrt{expr} -> √(expr)
    res = re.sub(r"\\?sqrt\{([^}]+)\}", r"√(\1)", res)
    res = re.sub(r"\\?sqrt\s*([a-zA-Z0-9]+)", r"√\1", res)
    
    # Convert frac{a}{b} -> (a/b)
    res = re.sub(r"\\?frac\{([^}]+)\}\{([^}]+)\}", r"(\1 / \2)", res)
    
    # Convert superscripts x^2, x^{10}
    def replace_sup(match):
        val = match.group(1) or match.group(2)
        sup_str = "".join(SUPERSCRIPT_MAP.get(ch, ch) for ch in val)
        return sup_str

    res = re.sub(r"\^\{([^}]+)\}", replace_sup, res)
    res = re.sub(r"\^([0-9a-zA-Z\+\-\=])", replace_sup, res)
    
    # Convert subscripts x_1, x_{ij}
    def replace_sub(match):
        val = match.group(1) or match.group(2)
        sub_str = "".join(SUBSCRIPT_MAP.get(ch, ch) for ch in val)
        return sub_str

    res = re.sub(r"_\{([^}]+)\}", replace_sub, res)
    res = re.sub(r"_([0-9a-zA-Z\+\-\=])", replace_sub, res)
    
    # Clean inline math delimiters $...$
    res = re.sub(r"\$([^$]+)\$", r"\1", res)
    
    return res

def format_math_text(text: str) -> str:
    """
    Normalize and format mathematical text for clean document presentation.
    """
    if not text:
        return ""
        
    # Convert LaTeX to Unicode
    formatted = convert_latex_to_unicode(text)
    
    # Clean double spaces or broken formatting (preserve newlines)
    formatted = re.sub(r"[ \t]+", " ", formatted).strip()
    
    return formatted
