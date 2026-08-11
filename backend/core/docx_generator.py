# -*- coding: utf-8 -*-
"""
Mento.AI Notes Document & PDF Generator
Generates clean, academic-style DOCX and PDF documents using Times New Roman (12-14pt)
in pure black text without colors, shaded callout boxes, or cover statistics tables.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger("docx_generator")

# Pure Black Palette (Zero Colors)
COLOR_BLACK = RGBColor(0, 0, 0)

def add_heading_times(doc, text: str, level: int, space_before: int = 12, space_after: int = 4):
    """Add a heading styled in Times New Roman 14pt Bold Pure Black."""
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(14)
        run.font.color.rgb = COLOR_BLACK
        run.bold = True
        
    return p

def generate_docx(
    matched_results: List[Dict[str, Any]],
    output_path: str,
    title: str = "Extracted Syllabus Notes",
    description: str = "Notes extracted and compiled by Mento.AI"
):
    """
    Generate a clean DOCX document in Times New Roman (12-14pt) pure black.
    Includes only bold topic headings and the matched text excerpts underneath.
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
        title_run = title_p.add_run(title)
        title_run.font.name = 'Times New Roman'
        title_run.font.size = Pt(16)
        title_run.font.color.rgb = COLOR_BLACK
        title_run.bold = True
        
        # Subtitle / Source info
        desc_p = doc.add_paragraph()
        desc_p.paragraph_format.space_after = Pt(18)
        desc_run = desc_p.add_run(f"{description} | Generated on {datetime.now().strftime('%B %d, %Y')}")
        desc_run.font.name = 'Times New Roman'
        desc_run.font.size = Pt(10.5)
        desc_run.font.color.rgb = COLOR_BLACK
        desc_run.italic = True
        
        # Horizontal divider line
        div_p = doc.add_paragraph()
        div_p.paragraph_format.space_after = Pt(18)
        div_run = div_p.add_run("_________________________________________________________________________________")
        div_run.font.name = 'Times New Roman'
        div_run.font.size = Pt(9)
        div_run.font.color.rgb = COLOR_BLACK
        
        # Main Content Generation
        current_unit = None
        
        for idx, result in enumerate(matched_results):
            unit_name = result.get("unit", "General")
            
            # Unit Heading (14pt Bold Times New Roman)
            if unit_name != current_unit:
                current_unit = unit_name
                add_heading_times(doc, current_unit.upper(), level=1, space_before=16, space_after=6)
                
            # Topic Heading (14pt Bold Times New Roman)
            topic_number = result.get("hierarchy_number", "")
            topic_title = result.get("title", "")
            heading_text = f"{topic_number} {topic_title}".strip() if topic_number else topic_title
            
            add_heading_times(doc, heading_text, level=2, space_before=12, space_after=4)
            
            matches = result.get("matches", [])
            
            if not matches:
                continue
                
            # Excerpts (12pt Times New Roman, 1.15 line spacing)
            for m_idx, match in enumerate(matches):
                # Metadata line
                p_meta = doc.add_paragraph()
                p_meta.paragraph_format.space_before = Pt(4)
                p_meta.paragraph_format.space_after = Pt(2)
                p_meta.paragraph_format.keep_with_next = True
                
                meta_run = p_meta.add_run(
                    f"[Source: {match['source']} | Page {match['page_number']}]"
                )
                meta_run.font.name = 'Times New Roman'
                meta_run.font.size = Pt(10)
                meta_run.font.color.rgb = COLOR_BLACK
                meta_run.italic = True
                
                # Excerpt Body Text
                text_content = match["text"]
                paragraphs = text_content.split("\n\n")
                
                for text_block in paragraphs:
                    p_block = doc.add_paragraph()
                    p_block.paragraph_format.space_after = Pt(6)
                    p_block.paragraph_format.left_indent = Inches(0.2)
                    
                    run = p_block.add_run(text_block.strip())
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(12)
                    run.font.color.rgb = COLOR_BLACK

        doc.save(output_path)
        logger.info(f"DOCX successfully saved at {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating DOCX document: {e}")
        raise e

def generate_pdf(
    matched_results: List[Dict[str, Any]],
    output_path: str,
    title: str = "Extracted Syllabus Notes",
    description: str = "Notes extracted and compiled by Mento.AI"
):
    """
    Generate a clean PDF document using ReportLab in Times-Roman (12-14pt) pure black.
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
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True
        )
        
        topic_style = ParagraphStyle(
            'TopicStyle',
            parent=styles['Heading2'],
            fontName='Times-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.black,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True
        )
        
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=10,
            leading=13,
            textColor=colors.black,
            spaceBefore=4,
            spaceAfter=2,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=12,
            leading=16,
            textColor=colors.black,
            leftIndent=14,
            spaceAfter=6
        )
        
        story = []
        
        # Title Block
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"{description} | Generated on {datetime.now().strftime('%B %d, %Y')}", desc_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=0, spaceAfter=14))
        
        current_unit = None
        
        for result in matched_results:
            unit_name = result.get("unit", "General")
            
            if unit_name != current_unit:
                current_unit = unit_name
                story.append(Paragraph(current_unit.upper(), unit_style))
                
            topic_number = result.get("hierarchy_number", "")
            topic_title = result.get("title", "")
            heading_text = f"{topic_number} {topic_title}".strip() if topic_number else topic_title
            
            story.append(Paragraph(heading_text, topic_style))
            
            matches = result.get("matches", [])
            
            if not matches:
                continue
                
            for match in matches:
                meta_text = f"[Source: {match['source']} | Page {match['page_number']}]"
                story.append(Paragraph(meta_text, meta_style))
                
                paragraphs = match["text"].split("\n\n")
                for p_text in paragraphs:
                    # Escape XML characters for ReportLab Paragraph
                    safe_text = p_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(safe_text.strip(), body_style))
                    
        doc.build(story)
        logger.info(f"PDF successfully saved at {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating PDF document: {e}")
        raise e
