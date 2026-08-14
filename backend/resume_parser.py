import os
import logging
import PyPDF2
import docx

logger = logging.getLogger(__name__)

def parse_pdf(filepath):
    """
    Extract text and page count from a PDF file using PyPDF2.
    """
    text = []
    pages = 0
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            pages = len(reader.pages)
            for page_num in range(pages):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
    except Exception as e:
        logger.error(f"Error parsing PDF {filepath}: {e}")
        raise ValueError(f"Failed to parse PDF file: {str(e)}")
        
    return {
        "text": "\n".join(text),
        "pages": pages,
        "file_type": "pdf"
    }

def parse_docx(filepath):
    """
    Extract text and page count estimate from a DOCX file using python-docx.
    """
    text = []
    try:
        doc = docx.Document(filepath)
        for para in doc.paragraphs:
            if para.text.strip():
                text.append(para.text)
        
        # Also extract tables text
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    text.append(" | ".join(row_text))
                    
    except Exception as e:
        logger.error(f"Error parsing DOCX {filepath}: {e}")
        raise ValueError(f"Failed to parse DOCX file: {str(e)}")
        
    # Docx does not have a formal pagination structure stored natively, 
    # we default to 1 page or estimate based on word count. 
    # Let's return pages=1 for docx (standard practice since we don't render it).
    return {
        "text": "\n".join(text),
        "pages": 1,
        "file_type": "docx"
    }

def parse_resume(filepath):
    """
    Auto-detects format from extension and extracts text.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pdf':
        return parse_pdf(filepath)
    elif ext in ['.docx', '.doc']:
        return parse_docx(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}")