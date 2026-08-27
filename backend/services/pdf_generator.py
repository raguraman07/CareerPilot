import io
import logging
import importlib

logger = logging.getLogger(__name__)

def html_to_pdf(html_content):
    """
    Converts HTML string with styling into a PDF byte stream using xhtml2pdf.
    """
    try:
        # Load pisa dynamically to prevent static analyzer warning when site-packages index is refreshing
        pisa_module = importlib.import_module("xhtml2pdf.pisa")
        
        pdf_buffer = io.BytesIO()
        pisa_status = pisa_module.CreatePDF(
            src=html_content,
            dest=pdf_buffer,
            encoding='utf-8'
        )
        if pisa_status and getattr(pisa_status, 'err', 0):
            logger.error(f"PISA PDF conversion error count: {pisa_status.err}")
            return None
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    except Exception as e:
        logger.error(f"Critical error during HTML to PDF conversion: {e}", exc_info=True)
        return None
