import pdfplumber
import docx
from typing import Optional

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts raw text content cleanly from PDF files."""
    text_content = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
    return "\n".join(text_content)

def extract_text_from_docx(file_path: str) -> str:
    """Extracts clean text content from Microsoft Word DOCX files."""
    doc = docx.Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)

def parse_resume_file(file_path: str) -> str:
    """Auto-detects file type and extracts readable text."""
    lower_path = file_path.lower()
    if lower_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif lower_path.endswith(".docx") or lower_path.endswith(".doc"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported resume format: {file_path}. Please supply a PDF or DOCX.")
