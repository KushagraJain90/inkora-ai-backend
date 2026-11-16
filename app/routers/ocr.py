
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from google.genai import types

from app.core.config import ALLOWED_TYPES, MAX_FILE_SIZE
from app.core.gemini import client
from app.services.ocr_service import transcribe_handwritten_pages

router = APIRouter(prefix="/api", tags=["OCR"])


@router.post("/ocr")
async def recognize_handwriting(
    pages: Annotated[list[UploadFile], File()],
):
    """Transcribe between one and four handwritten page images."""

    if client is None:
        raise HTTPException(
            status_code=500,
            detail="Gemini API key is not configured on the server.",
        )

    if not 1 <= len(pages) <= 4:
        raise HTTPException(
            status_code=400,
            detail="Upload between 1 and 4 pages per request.",
        )

    image_parts = []

    try:
        for index, page in enumerate(pages, start=1):
            if page.content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail=f"Page {index} must be JPEG, PNG, or WebP.",
                )

            image_bytes = await page.read()

            if not image_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Page {index} is empty.",
                )

            if len(image_bytes) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Page {index} exceeds the 10 MB limit.",
                )

            image_parts.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=page.content_type,
                )
            )

        parsed = transcribe_handwritten_pages(
            image_parts,
            client,
        )

        return {
            "page_count": len(parsed.pages),
            "batch_request_count": 1,
            "pages": [
                item.model_dump()
                for item in parsed.pages
            ],
        }

    finally:
        for page in pages:
            await page.close()
