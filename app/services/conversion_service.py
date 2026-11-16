
import io
import re
import subprocess
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from fastapi import HTTPException
from google.genai import types
from PIL import Image

from app.core.config import BASE_DIR, BATCH_SIZE, LIBREOFFICE_PATH, MODEL_NAME
from app.models.ocr_models import ConversionBatchResponse


def crop_visual_region(image_bytes: bytes, region) -> bytes:
    """Slightly enlarge the crop while keeping its center unchanged."""

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
        width, height = image.size

        # Original Gemini coordinates
        x1 = round(region.x_min * width)
        y1 = round(region.y_min * height)
        x2 = round(region.x_max * width)
        y2 = round(region.y_max * height)

        # Keep coordinates within the image boundaries
        x1 = max(0, min(width, x1))
        y1 = max(0, min(height, y1))
        x2 = max(0, min(width, x2))
        y2 = max(0, min(height, y2))

        if x2 <= x1 or y2 <= y1:
            raise ValueError(
                f"Invalid crop coordinates for {region.region_id}"
            )

        # Expand by 5% on each side
        crop_width = x2 - x1
        crop_height = y2 - y1

        pad_x = round(crop_width * 0.05)
        pad_y = round(crop_height * 0.05)

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(width, x2 + pad_x)
        y2 = min(height, y2 + pad_y)

        cropped = image.crop((x1, y1, x2, y2))

        output = io.BytesIO()
        cropped.save(output, format="PNG")
        return output.getvalue()



def insert_visual_image(document, image_bytes: bytes) -> None:
    """Insert a centered visual into the Word document."""

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(
        io.BytesIO(image_bytes),
        width=Inches(5.8),
    )



def add_transcription_to_docx(
    document,
    transcription,
    visual_images=None,
):
    """Format headings, lists, tables, code and paragraphs in Word."""

    visual_images = visual_images or {}
    lines = transcription.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index].strip()

        # Replace visual markers with cropped images.
        visual_match = re.fullmatch(
            r"\[\[VISUAL:([A-Za-z0-9_-]+)\]\]",
            line,
        )

        if visual_match:
            visual_id = visual_match.group(1)
            image_bytes = visual_images.get(visual_id)

            if image_bytes is None:
                raise ValueError(
                    f"Missing cropped image for {visual_id}"
                )

            insert_visual_image(document, image_bytes)
            index += 1
            continue

        if not line:
            index += 1
            continue

        # Preserve code and pseudocode inside Markdown fences.
        if line.startswith("```"):
            index += 1
            code_lines = []

            while index < len(lines):
                candidate = lines[index].rstrip("\r")

                if candidate.strip().startswith("```"):
                    index += 1
                    break

                code_lines.append(candidate)
                index += 1

            code_paragraph = document.add_paragraph()
            code_paragraph.paragraph_format.space_after = Pt(6)
            code_paragraph.paragraph_format.line_spacing = 1.0

            for line_number, code_line in enumerate(code_lines):
                run = code_paragraph.add_run(code_line)
                run.font.name = "Consolas"
                run.font.size = Pt(9)

                if line_number < len(code_lines) - 1:
                    run.add_break()

            continue

        # Markdown-style tables.
        if line.startswith("|") and "|" in line[1:]:
            table_lines = []

            while index < len(lines):
                candidate = lines[index].strip()

                if not candidate.startswith("|"):
                    break

                table_lines.append(candidate)
                index += 1

            rows = []

            for table_line in table_lines:
                cells = [
                    cell.strip()
                    for cell in table_line.strip("|").split("|")
                ]

                # Skip Markdown table separator rows.
                if cells and all(
                    re.fullmatch(
                        r":?-{3,}:?",
                        cell.replace(" ", ""),
                    )
                    for cell in cells
                ):
                    continue

                rows.append(cells)

            if rows:
                column_count = max(len(row) for row in rows)

                table = document.add_table(
                    rows=0,
                    cols=column_count,
                )
                table.style = "Table Grid"

                for row_index, values in enumerate(rows):
                    cells = table.add_row().cells

                    for col_index, value in enumerate(values):
                        cells[col_index].text = value

                        if row_index == 0:
                            for run in cells[col_index].paragraphs[0].runs:
                                run.bold = True

            continue

        # Headings.
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)

        if heading:
            document.add_heading(
                heading.group(2),
                level=len(heading.group(1)),
            )
            index += 1
            continue

        # Bulleted lists.
        if re.match(r"^[-*•]\s+", line):
            text = re.sub(r"^[-*•]\s+", "", line)
            document.add_paragraph(text, style="List Bullet")
            index += 1
            continue

        # Numbered lists.
        if re.match(r"^\d+[.)]\s+", line):
            text = re.sub(r"^\d+[.)]\s+", "", line)
            document.add_paragraph(text, style="List Number")
            index += 1
            continue

        # Regular paragraphs: join wrapped lines into continuous flow.
        paragraph_lines = [line]
        index += 1

        while index < len(lines):
            next_line = lines[index].strip()

            if not next_line:
                break

            if (
                next_line.startswith(("|", "```")) or re.match(r"^#{1,3}\s+", next_line) or re.match(r"^[-*•]\s+", next_line) or re.match(r"^\d+[.)]\s+", next_line) or re.fullmatch(r"\[\[VISUAL:[A-Za-z0-9_-]+\]\]", next_line)
            ):
                break

            paragraph_lines.append(next_line)
            index += 1

        document.add_paragraph(" ".join(paragraph_lines))


def build_word_document(page_results, output_path):
    """Build the complete editable Word document."""

    document = Document()

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for page in page_results:
        # Preserve continuous flow between uploaded pages.
        add_transcription_to_docx(
            document,
            page["transcription"],
            page.get("visual_images", {}),
        )

    document.save(output_path)
    

CONVERSION_PROMPT_PATH = (
    BASE_DIR / "app" / "prompts" / "conversion_prompt.txt"
)


def transcribe_conversion_batch(image_data, gemini_client):
    """Transcribe one batch of images using Gemini."""

    if not CONVERSION_PROMPT_PATH.is_file():
        raise HTTPException(
            status_code=500,
            detail="The conversion prompt file is missing.",
        )

    prompt = CONVERSION_PROMPT_PATH.read_text(encoding="utf-8")

    image_parts = [
        types.Part.from_bytes(
            data=data,
            mime_type=mime_type,
        )
        for data, mime_type in image_data
    ]

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, *image_parts],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ConversionBatchResponse,
            ),
        )

        if not response.text:
            raise HTTPException(
                status_code=502,
                detail="Gemini returned an empty transcription.",
            )

        parsed = ConversionBatchResponse.model_validate_json(
            response.text
        )

        expected = list(range(1, len(image_data) + 1))
        actual = [item.page_number for item in parsed.pages]

        if len(parsed.pages) != len(image_data) or actual != expected:
            raise HTTPException(
                status_code=502,
                detail="OCR returned an invalid batch response.",
            )

        return parsed

    except HTTPException:
        raise

    except (ValueError, TypeError) as error:
        print(
            f"Conversion response validation failed: "
            f"{type(error).__name__}: {error}"
        )
        raise HTTPException(
            status_code=502,
            detail="Gemini returned an invalid conversion response.",
        ) from error

    except Exception as error:
        print(
            f"Conversion provider request failed: "
            f"{type(error).__name__}: {error}"
        )
        raise HTTPException(
            status_code=502,
            detail="Document transcription failed. Check backend logs.",
        ) from error

def process_conversion_page(item, original_image_bytes):
    """Validate visual markers and crop their corresponding image regions."""

    visual_images = {}

    region_ids = {
        region.region_id for region in item.visual_regions
    }

    if len(region_ids) != len(item.visual_regions):
        raise HTTPException(
            status_code=502,
            detail="Gemini returned duplicate visual region IDs.",
        )

    markers = re.findall(
        r"(?m)^\[\[VISUAL:([A-Za-z0-9_-]+)\]\]$",
        item.transcription,
    )

    if len(markers) != len(set(markers)):
        raise HTTPException(
            status_code=502,
            detail="Gemini returned duplicate visual markers.",
        )

    if set(markers) != region_ids:
        raise HTTPException(
            status_code=502,
            detail=(
                "Visual markers and crop regions do not match. "
                "Please retry the conversion."
            ),
        )

    for region in item.visual_regions:
        try:
            visual_images[region.region_id] = crop_visual_region(
                original_image_bytes,
                region,
            )
        except Exception as error:
            print(
                f"Visual cropping failed for {region.region_id}: "
                f"{type(error).__name__}"
            )
            raise HTTPException(
                status_code=502,
                detail="Could not crop an equation or diagram.",
            ) from error

    return {
        "transcription": item.transcription,
        "visual_images": visual_images,
    }


def process_conversion_pages(image_data, gemini_client):
    """Process all uploaded pages in sequential batches."""

    page_results = []

    for batch_start in range(0, len(image_data), BATCH_SIZE):
        batch = image_data[
            batch_start:batch_start + BATCH_SIZE
        ]

        parsed = transcribe_conversion_batch(
            batch,
            gemini_client,
        )

        for item in parsed.pages:
            original_image_bytes = batch[item.page_number - 1][0]

            processed = process_conversion_page(
                item,
                original_image_bytes,
            )

            page_results.append({
                "page_number": batch_start + item.page_number,
                "transcription": processed["transcription"],
                "visual_images": processed["visual_images"],
            })

    return page_results


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path, profile_path: Path):
    """Convert a Word document to PDF using LibreOffice."""

    command = [
        str(LIBREOFFICE_PATH),
        f"-env:UserInstallation={profile_path.as_uri()}",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(docx_path.parent),
        str(docx_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

        if (
            result.returncode != 0
            or not pdf_path.is_file()
            or pdf_path.stat().st_size == 0
        ):
            print(
                "LibreOffice conversion failed:",
                result.returncode,
                result.stderr[:1000],
            )

            raise HTTPException(
                status_code=500,
                detail="Could not generate the PDF document.",
            )

    except subprocess.TimeoutExpired as error:
        raise HTTPException(
            status_code=504,
            detail="PDF conversion timed out.",
        ) from error



def create_conversion_zip(docx_path: Path, pdf_path: Path) -> bytes:
    """Package the generated Word and PDF documents into a ZIP archive."""

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(
            docx_path,
            arcname=docx_path.name,
        )
        archive.write(
            pdf_path,
            arcname=pdf_path.name,
        )

    return zip_buffer.getvalue()
