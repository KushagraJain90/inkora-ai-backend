import tempfile
from pathlib import Path

from app.services.conversion_service import build_word_document

transcription = """# Main Heading
Section Heading
This is a test paragraph.
- First item
- Second item
1. Numbered item
Name	Subject
A	Python

print("Hello Inkora")



"""

pages = [
{
"page_number": 1,
"transcription": transcription,
"visual_images": {},
}
]

output_path = (
Path(tempfile.gettempdir())
/ "inkora_conversion_test.docx"
)

build_word_document(pages, output_path)

print("DOCX generated:", output_path.is_file())
print("File size:", output_path.stat().st_size, "bytes")
print("Output:", output_path)
