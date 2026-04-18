#!/usr/bin/env python3
"""
Convert Markdown roadmap to PDF format using ReportLab
"""

import markdown
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, blue, red, green
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import re
import os
import sys


class PDFConverter:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.custom_styles = {}
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom styles for the PDF"""
        # Title style
        self.custom_styles['title'] = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#2c3e50'),
            alignment=TA_CENTER,
            borderWidth=0,
            borderColor=HexColor('#3498db'),
            borderPadding=5
        )

        # Heading 1 style
        self.custom_styles['heading1'] = ParagraphStyle(
            'CustomHeading1',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
            spaceBefore=20,
            textColor=HexColor('#34495e'),
            borderWidth=0,
            borderColor=HexColor('#95a5a6'),
            borderPadding=3
        )

        # Heading 2 style
        self.custom_styles['heading2'] = ParagraphStyle(
            'CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15,
            textColor=HexColor('#34495e')
        )

        # Code style
        self.custom_styles['code'] = ParagraphStyle(
            'Code',
            parent=self.styles['Code'],
            fontSize=9,
            textColor=HexColor('#333333'),
            backgroundColor=HexColor('#f8f9fa'),
            borderWidth=1,
            borderColor=HexColor('#e9ecef'),
            borderPadding=3,
            leftIndent=20
        )

        # Normal text style
        self.custom_styles['normal'] = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            textColor=black
        )

    def parse_markdown_elements(self, content):
        """Parse markdown content into PDF elements"""
        elements = []
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Headers
            if line.startswith('# '):
                text = line[2:].strip()
                elements.append(Paragraph(text, self.custom_styles['title']))
                elements.append(Spacer(1, 20))
            elif line.startswith('## '):
                text = line[3:].strip()
                elements.append(
                    Paragraph(text, self.custom_styles['heading1']))
                elements.append(Spacer(1, 12))
            elif line.startswith('### '):
                text = line[4:].strip()
                elements.append(
                    Paragraph(text, self.custom_styles['heading2']))
                elements.append(Spacer(1, 8))

            # Tables
            elif '|' in line and i + 1 < len(lines) and '|' in lines[i + 1]:
                table_data = []
                # Parse table header
                header = [cell.strip() for cell in line.split('|')[1:-1]]
                table_data.append(header)
                i += 1
                # Skip separator line
                if i < len(lines) and '|' in lines[i] and '-' in lines[i]:
                    i += 1
                # Parse table rows
                while i < len(lines) and '|' in lines[i]:
                    row = [cell.strip() for cell in lines[i].split('|')[1:-1]]
                    if row:
                        table_data.append(row)
                    i += 1

                if table_data:
                    table = Table(table_data, repeatRows=1)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f2f2f2')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ffffff')),
                        ('GRID', (0, 0), (-1, -1), 1, HexColor('#dddddd')),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('TOPPADDING', (0, 1), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                    ]))
                    elements.append(table)
                    elements.append(Spacer(1, 12))
                continue

            # Code blocks
            elif line.startswith('```'):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1

                code_text = '\n'.join(code_lines)
                # Escape HTML entities and format for ReportLab
                code_text = code_text.replace('&', '&amp;').replace(
                    '<', '&lt;').replace('>', '&gt;')
                elements.append(Paragraph(
                    f'<font name="Courier">{code_text}</font>', self.custom_styles['code']))
                elements.append(Spacer(1, 12))

            # Lists
            elif line.startswith(('- ') or ('* ')):
                list_items = []
                while i < len(lines) and (lines[i].strip().startswith('- ') or lines[i].strip().startswith('* ')):
                    item_text = lines[i].strip()[2:].strip()
                    list_items.append(f"â¢ {item_text}")
                    i += 1

                for item in list_items:
                    elements.append(
                        Paragraph(item, self.custom_styles['normal']))
                elements.append(Spacer(1, 6))
                continue

            # Blockquotes
            elif line.startswith('> '):
                quote_text = line[2:].strip()
                elements.append(
                    Paragraph(f'<i>{quote_text}</i>', self.custom_styles['normal']))
                elements.append(Spacer(1, 6))

            # Regular paragraphs
            else:
                # Handle inline code
                line = re.sub(
                    r'`([^`]+)`', r'<font name="Courier" color="#333333" backColor="#f8f9fa">\1</font>', line)
                # Handle bold text
                line = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', line)
                # Handle italic text
                line = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', line)

                elements.append(Paragraph(line, self.custom_styles['normal']))
                elements.append(Spacer(1, 6))

            i += 1

        return elements

    def convert_to_pdf(self, md_file_path, output_pdf_path=None):
        """Convert markdown file to PDF"""
        if output_pdf_path is None:
            output_pdf_path = md_file_path.replace('.md', '.pdf')

        try:
            # Read markdown file
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: File '{md_file_path}' not found.")
            return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False

        # Create PDF document
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )

        # Parse markdown content
        elements = self.parse_markdown_elements(content)

        try:
            # Build PDF
            doc.build(elements)

            print(
                f"Successfully converted '{md_file_path}' to '{output_pdf_path}'")
            print(f"PDF file size: {os.path.getsize(output_pdf_path):,} bytes")
            return True

        except Exception as e:
            print(f"Error generating PDF: {e}")
            return False


def main():
    """Main function"""
    md_file = "STRATEGY_ROADMAP.md"

    if not os.path.exists(md_file):
        print(f"Error: '{md_file}' not found in current directory.")
        sys.exit(1)

    print(f"Converting {md_file} to PDF...")
    converter = PDFConverter()
    success = converter.convert_to_pdf(md_file)

    if success:
        pdf_file = md_file.replace('.md', '.pdf')
        print(f"\nPDF generated successfully: {pdf_file}")
        print(
            f"You can now open the PDF file to view your roadmap in a professional format.")
    else:
        print("\nFailed to generate PDF. Please check the error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
