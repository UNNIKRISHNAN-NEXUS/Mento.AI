# -*- coding: utf-8 -*-
"""
Mento.AI Notes Document & PDF Generator
Generates clean, academic-style DOCX and PDF documents using Times New Roman (12-14pt)
in pure black text. Includes bold unit/topic headings, source file & page references,
and the actual extracted notes from the uploaded study material.
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Any
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger("docx_generator")

# Pure Black Palette (Academic standard)
COLOR_BLACK = RGBColor(0, 0, 0)

def deduplicate_and_merge_chunks(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates and merges overlapping text chunks from the same source document.
    Preserves original reading order, page numbers, and formatting.
    """
    if not matches:
        return []
        
    cleaned_matches = []
    seen_texts = set()
    
    for match in matches:
        raw_text = match.get("text", "").strip()
        if not raw_text:
            continue
            
        # Normalize for duplicate detection
        normalized = " ".join(raw_text.split()[:25]) # first 25 words
        if normalized in seen_texts:
            continue
            
        seen_texts.add(normalized)
        
        # Check if this chunk can be merged with previous chunk if overlapping
        if cleaned_matches:
            prev = cleaned_matches[-1]
            if prev["source"] == match.get("source") and prev["page_number"] == match.get("page_number"):
                prev_text = prev["text"]
                prev_tail = prev_text[-100:].strip()
                curr_head = raw_text[:100].strip()
                
                overlap_len = 0
                for length in range(min(len(prev_tail), len(curr_head)), 15, -1):
                    if prev_tail.endswith(curr_head[:length]):
                        overlap_len = length
                        break
                        
                if overlap_len > 0:
                    merged_text = prev_text + raw_text[overlap_len:]
                    prev["text"] = merged_text
                    continue
                    
        cleaned_matches.append({
            "chunk_id": match.get("chunk_id", ""),
            "text": raw_text,
            "page_number": match.get("page_number", 1),
            "source": match.get("source", "Study Material"),
            "type": match.get("type", "digital"),
            "similarity_score": match.get("similarity_score", 1.0)
        })
        
    return cleaned_matches

def add_heading_times(doc, text: str, level: int, space_before: int = 14, space_after: int = 4):
    """Add a heading styled in Times New Roman Bold Pure Black."""
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    
    font_size = 15 if level == 1 else 13
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(font_size)
        run.font.color.rgb = COLOR_BLACK
        run.bold = True
        
    return p

def generate_docx(
    matched_results: List[Dict[str, Any]],
    output_path: str,
    title: str = "Extracted Study Notes",
    description: str = "Notes extracted and compiled by Mento.AI"
) -> bool:
    """
    Generate a clean DOCX document in Times New Roman (12-14pt) pure black.
    Includes unit headings, topic headings, source/page references, and actual extracted notes.
    """
    try:
        logger.info(f"Generating DOCX output at {output_path}...")
        doc = docx.Document()
        
        # Page Margins (1 inch all sides)
        for section in doc.sections:
            section.page_width = Inches(8.5)
            section.page_height = Inches(11.0)
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)
            
        # Set Normal style to Times New Roman 12pt Pure Black
        style_normal = doc.styles['Normal']
        style_normal.font.name = 'Times New Roman'
        style_normal.font.size = Pt(12)
        style_normal.font.color.rgb = COLOR_BLACK
        style_normal.paragraph_format.line_spacing = 1.15
        style_normal.paragraph_format.space_after = Pt(6)
        
        # Title Block
        title_p = doc.add_paragraph()
        title_p.paragraph_format.space_before = Pt(12)
        title_p.paragraph_format.space_after = Pt(4)
        title_run = title_p.add_run(f"MENTO.AI — {title.upper()}")
        title_run.font.name = 'Times New Roman'
        title_run.font.size = Pt(18)
        title_run.font.color.rgb = COLOR_BLACK
        title_run.bold = True
        
        # Subtitle / Source info
        desc_p = doc.add_paragraph()
        desc_p.paragraph_format.space_after = Pt(14)
        desc_run = desc_p.add_run(f"{description} | Generated on {datetime.now().strftime('%B %d, %Y')}")
        desc_run.font.name = 'Times New Roman'
        desc_run.font.size = Pt(10.5)
        desc_run.font.color.rgb = COLOR_BLACK
        desc_run.italic = True
        
        # Horizontal divider line
        div_p = doc.add_paragraph()
        div_p.paragraph_format.space_after = Pt(16)
        div_run = div_p.add_run("_________________________________________________________________________________")
        div_run.font.name = 'Times New Roman'
        div_run.font.size = Pt(9)
        div_run.font.color.rgb = COLOR_BLACK
        
        current_unit = None
        total_topics_added = 0
        
        for idx, result in enumerate(matched_results):
            raw_matches = result.get("matches", [])
            matches = deduplicate_and_merge_chunks(raw_matches)
            
            # Skip topics with no extractable text
            if not matches:
                continue
                
            total_topics_added += 1
            unit_name = result.get("unit", "General")
            
            # Unit Heading (15pt Bold Times New Roman)
            if unit_name != current_unit:
                current_unit = unit_name
                add_heading_times(doc, current_unit.upper(), level=1, space_before=18, space_after=6)
                
            # Topic Heading (13pt Bold Times New Roman)
            topic_number = result.get("hierarchy_number", "")
            topic_title = result.get("title", "")
            if topic_number and topic_number != "*":
                heading_text = f"Topic {topic_number}: {topic_title}"
            else:
                heading_text = f"Topic: {topic_title}"
                
            add_heading_times(doc, heading_text, level=2, space_before=12, space_after=4)
                
            # Excerpts (12pt Times New Roman, 1.15 line spacing)
            for m_idx, match in enumerate(matches):
                # Source and Page Reference
                p_meta = doc.add_paragraph()
                p_meta.paragraph_format.space_before = Pt(4)
                p_meta.paragraph_format.space_after = Pt(2)
                p_meta.paragraph_format.keep_with_next = True
                
                meta_run = p_meta.add_run(
                    f"Source: {match['source']} | Page: {match['page_number']}"
                )
                meta_run.font.name = 'Times New Roman'
                meta_run.font.size = Pt(10)
                meta_run.font.color.rgb = COLOR_BLACK
                meta_run.italic = True
                
                # Excerpt Body Text
                text_content = match["text"]
                paragraphs = text_content.split("\n\n")
                
                for text_block in paragraphs:
                    clean_block = text_block.strip()
                    if not clean_block:
                        continue
                    p_block = doc.add_paragraph()
                    p_block.paragraph_format.space_after = Pt(6)
                    p_block.paragraph_format.left_indent = Inches(0.15)
                    
                    run = p_block.add_run(clean_block)
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(12)
                    run.font.color.rgb = COLOR_BLACK

        if total_topics_added == 0:
            p_empty = doc.add_paragraph()
            p_empty.add_run("No notes content available for the selected topics.")
            
        doc.save(output_path)
        logger.info(f"DOCX successfully saved at {output_path} with {total_topics_added} topics.")
        return True
        
    except Exception as e:
        logger.error(f"Error generating DOCX document: {e}", exc_info=True)
        raise e

def generate_pdf(
    matched_results: List[Dict[str, Any]],
    output_path: str,
    title: str = "Extracted Study Notes",
    description: str = "Notes extracted and compiled by Mento.AI"
) -> bool:
    """
    Generate a clean PDF document using ReportLab in Times-Roman (12-14pt) pure black.
    Includes unit headings, topic headings, source/page references, and actual extracted notes.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        logger.info(f"Generating PDF output at {output_path}...")
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=72,
            rightMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        styles = getSampleStyleSheet()
        
        # Pure Black Times-Roman Styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontName='Times-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.black,
            spaceAfter=4
        )
        
        desc_style = ParagraphStyle(
            'DescStyle',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=10.5,
            leading=14,
            textColor=colors.black,
            spaceAfter=12
        )
        
        unit_style = ParagraphStyle(
            'UnitStyle',
            parent=styles['Heading1'],
            fontName='Times-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.black,
            spaceBefore=16,
            spaceAfter=6,
            keepWithNext=True
        )
        
        topic_style = ParagraphStyle(
            'TopicStyle',
            parent=styles['Heading2'],
            fontName='Times-Bold',
            fontSize=13,
            leading=17,
            textColor=colors.black,
            spaceBefore=10,
            spaceAfter=3,
            keepWithNext=True
        )
        
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=10,
            leading=13,
            textColor=colors.black,
            spaceBefore=3,
            spaceAfter=3,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=11.5,
            leading=15,
            textColor=colors.black,
            leftIndent=12,
            spaceAfter=6
        )
        
        story = []
        
        # Title Block
        story.append(Paragraph(f"MENTO.AI — {title.upper()}", title_style))
        story.append(Paragraph(f"{description} | Generated on {datetime.now().strftime('%B %d, %Y')}", desc_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=0, spaceAfter=14))
        
        current_unit = None
        total_topics_added = 0
        
        for result in matched_results:
            raw_matches = result.get("matches", [])
            matches = deduplicate_and_merge_chunks(raw_matches)
            
            if not matches:
                continue
                
            total_topics_added += 1
            unit_name = result.get("unit", "General")
            
            if unit_name != current_unit:
                current_unit = unit_name
                story.append(Paragraph(current_unit.upper(), unit_style))
                
            topic_number = result.get("hierarchy_number", "")
            topic_title = result.get("title", "")
            if topic_number and topic_number != "*":
                heading_text = f"Topic {topic_number}: {topic_title}"
            else:
                heading_text = f"Topic: {topic_title}"
                
            story.append(Paragraph(heading_text, topic_style))
                
            for match in matches:
                meta_text = f"Source: {match['source']} | Page: {match['page_number']}"
                story.append(Paragraph(meta_text, meta_style))
                
                paragraphs = match["text"].split("\n\n")
                for p_text in paragraphs:
                    clean_p = p_text.strip()
                    if not clean_p:
                        continue
                    # Escape XML characters for ReportLab Paragraph
                    safe_text = clean_p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(safe_text, body_style))
                    
        if total_topics_added == 0:
            story.append(Paragraph("No notes content available for the selected topics.", body_style))
            
        doc.build(story)
        logger.info(f"PDF successfully saved at {output_path} with {total_topics_added} topics.")
        return True
        
    except Exception as e:
        logger.error(f"Error generating PDF document: {e}", exc_info=True)
        raise e
