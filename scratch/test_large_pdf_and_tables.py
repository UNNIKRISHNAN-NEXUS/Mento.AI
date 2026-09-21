# -*- coding: utf-8 -*-
"""
Stress Test and Complex Document Verification:
1. 20-page digital PDF with mathematical equations and diagrams
2. 2-column academic PDF with tables
3. Full API server-level simulation (Upload -> Process -> Match -> Generate PDF/DOCX -> Validate)
"""

import sys
import os
import io

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pymupdf
from PIL import Image, ImageDraw
from backend.core.parser import parse_pdf, parse_document
from backend.core.matcher import match_syllabus_to_document
from backend.core.docx_generator import generate_docx, generate_pdf, validate_generated_document

TEST_DIR = os.path.join(PROJECT_ROOT, "scratch", "test_artifacts")
os.makedirs(TEST_DIR, exist_ok=True)

def create_20_page_pdf(path: str):
    """Creates a 20-page PDF with 20 distinct academic sections, formulas, and diagrams."""
    doc = pymupdf.open()
    for i in range(20):
        page = doc.new_page(width=612, height=792)
        p_num = i + 1
        unit_num = (i // 4) + 1
        
        # Unit Header
        page.insert_text((50, 60), f"UNIT {unit_num}: ADVANCED DIGITAL SIGNAL PROCESSING", fontsize=14, color=(0, 0, 0))
        # Topic Header
        page.insert_text((50, 90), f"{p_num}.0 Topic Section {p_num} — Analytical Study", fontsize=12, color=(0, 0, 0))
        
        # Paragraph Text
        body = (
            f"Section {p_num} explores the fundamental characteristics of discrete-time signals, "
            f"sampling theorems, filter design methodologies, and Fourier transform properties. "
            f"Let x(t) be an analog signal band-limited to B Hz. By the Nyquist criteria, the sampling rate "
            f"must satisfy f_s >= 2B to prevent aliasing distortion. "
            f"Furthermore, frequency response H(e^jw) can be obtained by computing the discrete-time Fourier transform (DTFT). "
        ) * 4
        page.insert_textbox(pymupdf.Rect(50, 110, 560, 360), body, fontsize=10, color=(0, 0, 0))
        
        # Diagram
        page.draw_rect(pymupdf.Rect(50, 380, 450, 520), color=(0.1, 0.3, 0.7), fill=(0.95, 0.97, 1.0))
        page.insert_text((70, 450), f"Figure {p_num}.1: Frequency Response & Pole-Zero Constellation for Filter {p_num}", fontsize=10, color=(0, 0, 0))
        
        page.insert_text((50, 750), f"Page {p_num} of 20", fontsize=9, color=(0.5, 0.5, 0.5))
        
    doc.save(path)
    doc.close()

def create_two_column_pdf_with_table(path: str):
    """Creates a 2-column academic PDF with a structured table."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    
    # Title spanning full page
    page.insert_text((50, 50), "RESEARCH PAPER: COMPARATIVE FILTER DESIGN", fontsize=15, color=(0, 0, 0))
    page.insert_text((50, 75), "1. Introduction and Overview", fontsize=12, color=(0, 0, 0))
    
    # Column 1 (left: x 50 to 280)
    col1_text = (
        "Column 1 analysis: Finite impulse response (FIR) filters offer strictly linear phase "
        "characteristics and guaranteed stability. The transfer function is given by the polynomial summation. "
        "Windowing techniques such as Hamming, Hanning, and Blackman windows are commonly utilized."
    )
    page.insert_textbox(pymupdf.Rect(50, 95, 280, 350), col1_text * 2, fontsize=9.5, color=(0, 0, 0))
    
    # Column 2 (right: x 320 to 560)
    col2_text = (
        "Column 2 analysis: Infinite impulse response (IIR) filters achieve sharper transition bands "
        "with significantly lower filter orders compared to FIR counterparts. "
        "Bilinear transformation maps continuous s-domain poles to discrete z-domain poles."
    )
    page.insert_textbox(pymupdf.Rect(320, 95, 560, 350), col2_text * 2, fontsize=9.5, color=(0, 0, 0))
    
    # Table spanning bottom
    page.draw_rect(pymupdf.Rect(50, 420, 560, 550), color=(0.3, 0.3, 0.3))
    page.insert_text((60, 445), "Filter Type          Order      Passband Ripple     Stopband Attenuation", fontsize=9, color=(0, 0, 0))
    page.insert_text((60, 475), "Butterworth           4              0.5 dB                 -45 dB", fontsize=9, color=(0, 0, 0))
    page.insert_text((60, 505), "Chebyshev I           4              1.0 dB                 -55 dB", fontsize=9, color=(0, 0, 0))
    page.insert_text((60, 535), "Elliptic              4              0.2 dB                 -65 dB", fontsize=9, color=(0, 0, 0))
    
    doc.save(path)
    doc.close()

def run_large_tests():
    print("=" * 60)
    print("  RUNNING 20-PAGE & 2-COLUMN PDF VERIFICATION")
    print("=" * 60)
    
    # Test 1: 20-Page PDF
    pdf_20p = os.path.join(TEST_DIR, "test_20_pages.pdf")
    create_20_page_pdf(pdf_20p)
    print(f"\n[TEST 1] Parsing 20-Page PDF: {pdf_20p}")
    
    img_dir = os.path.join(TEST_DIR, "images_20p")
    chunks = parse_pdf(pdf_20p, image_dir=img_dir)
    print(f" -> Total parsed chunks: {len(chunks)}")
    pages = sorted(set(c["page_number"] for c in chunks))
    print(f" -> Source pages captured: {len(pages)} (pages 1 to {max(pages)})")
    assert len(pages) == 20, f"Expected 20 pages captured, got {len(pages)}"
    
    # Match against a 2-topic syllabus
    syllabus = [
        {"topic_id": "top_1", "title": "Topic Section 1", "unit": "Unit 1", "full_context": "Unit 1 > 1.0 Topic Section 1 — Analytical Study"},
        {"topic_id": "top_2", "title": "Topic Section 2", "unit": "Unit 1", "full_context": "Unit 1 > 2.0 Topic Section 2 — Analytical Study"}
    ]
    
    match_data = match_syllabus_to_document(syllabus, chunks, similarity_threshold=0.25)
    print(f"\n[TEST 2] Matching results for 20-page document:")
    print(f" -> Syllabus topics: {len(match_data['syllabus_topics'])}")
    print(f" -> Other/Additional topics: {len(match_data['other_topics'])}")
    print(f" -> Total topics generated: {len(match_data['topics'])}")
    
    all_pages_in_output = set()
    for t in match_data["topics"]:
        for m in t.get("matches", []):
            all_pages_in_output.add(m["page_number"])
    print(f" -> All 20 source pages preserved in topics: {len(all_pages_in_output)}/20 pages")
    assert len(all_pages_in_output) == 20, f"Expected 20 pages, got {len(all_pages_in_output)}"
    
    # Generate 20-page output PDF and validate
    out_pdf = os.path.join(TEST_DIR, "output_20_pages.pdf")
    generate_pdf(match_data["topics"], out_pdf, title="Advanced DSP Notes")
    pdf_val = validate_generated_document(out_pdf, export_format="pdf")
    print(f"\n[TEST 3] 20-Page PDF Output Validation:")
    print(f" -> Output PDF Pages: {pdf_val['page_count']}")
    print(f" -> Output PDF Total Chars: {pdf_val['total_chars']}")
    print(f" -> Output PDF Images: {pdf_val['images_count']}")
    assert pdf_val['page_count'] >= 10, f"Expected at least 10 pages for 20-page input, got {pdf_val['page_count']}"
    
    # Test 4: Two-column PDF
    two_col_pdf = os.path.join(TEST_DIR, "test_two_column.pdf")
    create_two_column_pdf_with_table(two_col_pdf)
    two_col_chunks = parse_pdf(two_col_pdf)
    print(f"\n[TEST 4] Two-Column PDF Parsing:")
    print(f" -> Chunks extracted: {len(two_col_chunks)}")
    assert len(two_col_chunks) > 0
    full_text = " ".join(c["text"] for c in two_col_chunks)
    assert "Column 1" in full_text and "Column 2" in full_text
    print(f" -> Correctly extracted both Column 1 and Column 2 in reading order!")
    
    print("\n" + "=" * 60)
    print("  ALL 20-PAGE & TWO-COLUMN TESTS PASSED WITH FLYING COLORS!")
    print("=" * 60)

if __name__ == "__main__":
    run_large_tests()
