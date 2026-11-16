
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.core.config import (
    ALLOWED_TYPES,
    LIBREOFFICE_PATH,
    MAX_CONVERSION_PAGES,
    MAX_FILE_SIZE,
)
from app.core.gemini import client
from app.services.conversion_service import (
    build_word_document,
    convert_docx_to_pdf,
    create_conversion_zip,
    process_conversion_pages,
)

router = APIRouter(prefix="/api", tags=["Conversion"])


@router.post("/convert")
async def convert_handwritten_document(
    pages: Annotated[list[UploadFile], File()],
):
    """Convert handwritten pages into editable DOCX and PDF files."""

    if client is None:
        raise HTTPException(
            status_code=500,
            detail="Gemini API key is not configured on the server.",
        )

    if not 1 <= len(pages) <= MAX_CONVERSION_PAGES:
        raise HTTPException(
            status_code=400,
            detail="Upload between 1 and 100 pages per conversion.",
        )

    if not Path(LIBREOFFICE_PATH).is_file():
        raise HTTPException(
            status_code=500,
            detail="LibreOffice was not found on the server.",
        )

    try:
        # Validate all uploaded images before calling Gemini.
        image_data = []

        for index, page in enumerate(pages, start=1):
            if page.content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail=f"Page {index} must be JPEG, PNG, or WebP.",
                )

            data = await page.read()

            if not data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Page {index} is empty.",
                )

            if len(data) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Page {index} exceeds the 10 MB limit.",
                )

            image_data.append((data, page.content_type))

        # Transcribe and process all pages in batches.
        page_results = process_conversion_pages(
            image_data,
            client,
        )

        with tempfile.TemporaryDirectory(
            prefix="inkora_conversion_"
        ) as temp_dir:

            temp_path = Path(temp_dir)

            docx_path = temp_path / "Inkora_AI_Converted.docx"
            pdf_path = temp_path / "Inkora_AI_Converted.pdf"
            profile_path = temp_path / "libreoffice_profile"

            # Generate the complete Word document.
            build_word_document(
                page_results,
                docx_path,
            )

            # Convert the Word document into PDF.
            convert_docx_to_pdf(
                docx_path,
                pdf_path,
                profile_path,
            )

            # Package both documents into a ZIP archive.
            zip_content = create_conversion_zip(
                docx_path,
                pdf_path,
            )

            return Response(
                content=zip_content,
                media_type="application/zip",
                headers={
                    "Content-Disposition":
                        'attachment; filename="Inkora_AI_Converted.zip"',
                    "X-Page-Count": str(len(page_results)),
                },
            )

    except HTTPException:
        raise

    except Exception as error:
        print(
            "Document conversion failed:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=502,
            detail="Document conversion failed. Check the backend logs.",
        ) from error

    finally:
        for page in pages:
            await page.close()
