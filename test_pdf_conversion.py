
import tempfile
from pathlib import Path

from app.core.config import LIBREOFFICE_PATH
from app.services.conversion_service import (
    build_word_document,
    convert_docx_to_pdf,
)

temp_dir = Path(tempfile.gettempdir()) / "inkora_pdf_test"
temp_dir.mkdir(exist_ok=True)

docx_path = temp_dir / "test_document.docx"
pdf_path = temp_dir / "test_document.pdf"
profile_path = temp_dir / "libreoffice_profile"

pages = [
    {
        "page_number": 1,
        "transcription": "# Inkora AI PDF Test\n\nPDF conversion is working.",
        "visual_images": {},
    }
]

build_word_document(pages, docx_path)

convert_docx_to_pdf(
    docx_path,
    pdf_path,
    profile_path,
)

print("LibreOffice path:", LIBREOFFICE_PATH)
print("DOCX exists:", docx_path.is_file())
print("PDF generated:", pdf_path.is_file())
print("PDF size:", pdf_path.stat().st_size, "bytes")
print("PDF output:", pdf_path)
