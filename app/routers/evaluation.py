
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.core.gemini import client
from app.models.evaluation_models import (
    EvaluationCriterion,
    EvaluationFeedback,
    EvaluationResponse,
)
from app.services.evaluation_service import (
    MAX_EVALUATION_ANSWER_PAGES,
    evaluate_answer,
    read_and_validate_image,
    transcribe_evaluation_images,
    validate_evaluation_result,
)
from app.services.pdf_service import build_evaluation_pdf

router = APIRouter(prefix="/api", tags=["Evaluation"])


@router.post("/evaluate")
async def evaluate_academic_answer(
    question_text: str | None = Form(default=None),
    question_image: Annotated[UploadFile | None, File()] = None,
    student_answer_text: str | None = Form(default=None),
    student_answer_images: Annotated[list[UploadFile] | None, File()] = None,
    total_marks: float = Form(..., gt=0),
    academic_level: str = Form(..., min_length=1, max_length=100),
    degree_field: str = Form(..., min_length=1, max_length=200),
):
    """
    Evaluate one academic answer and return the generated PDF.
    Accept exactly one question input and one answer input.
    """

    if client is None:
        raise HTTPException(
            status_code=500,
            detail="Gemini API key is not configured on the server.",
        )

    if not math.isfinite(total_marks) or total_marks <= 0:
        raise HTTPException(
            status_code=400,
            detail="total_marks must be a finite number greater than zero.",
        )

    if not academic_level.strip() or not degree_field.strip():
        raise HTTPException(
            status_code=400,
            detail="Academic level and degree field cannot be blank.",
        )

    question_text = (question_text or "").strip()

    has_typed_answer_input = student_answer_text is not None
    student_answer_text = student_answer_text or ""
    student_answer_images = student_answer_images or []

    if bool(question_text) == (question_image is not None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one question input: question_text or question_image.",
        )

    if has_typed_answer_input and student_answer_images:
        raise HTTPException(
            status_code=400,
            detail="Use only one answer input: student_answer_text or student_answer_images.",
        )

    if len(student_answer_images) > MAX_EVALUATION_ANSWER_PAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Upload no more than {MAX_EVALUATION_ANSWER_PAGES} answer pages.",
        )

    image_data = []
    question_image_index = None
    answer_image_start = None

    try:
        # Read question image first, followed by answer pages.
        if question_image is not None:
            image_data.append(
                await read_and_validate_image(
                    question_image,
                    "Question image",
                )
            )
            question_image_index = len(image_data) - 1

        if student_answer_images:
            answer_image_start = len(image_data)

            for page_number, upload in enumerate(
                student_answer_images,
                start=1,
            ):
                image_data.append(
                    await read_and_validate_image(
                        upload,
                        f"Answer page {page_number}",
                    )
                )

        # Transcribe all images in batches.
        if image_data:
            all_transcriptions = transcribe_evaluation_images(
                image_data,
                client,
            )

            if question_image_index is not None:
                question_text = all_transcriptions[
                    question_image_index
                ].strip()

            if answer_image_start is not None:
                student_answer_text = "\n\n".join(
                    f"[Page {index + 1}]\n{page_text.strip()}"
                    for index, page_text in enumerate(
                        all_transcriptions[answer_image_start:]
                    )
                ).strip()

        if not question_text:
            raise HTTPException(
                status_code=400,
                detail="The question could not be transcribed. Please provide a clearer image.",
            )

        # Detect genuinely blank image-based answers.
        if student_answer_images and student_answer_text.strip():
            answer_page_texts = (
                [
                    page_text.strip()
                    for page_text in all_transcriptions[
                        answer_image_start:
                    ]
                ]
                if answer_image_start is not None
                else []
            )

            if answer_page_texts and all(
                text.lower() in {
                    "[blank page]",
                    "[no readable text]",
                    "",
                }
                for text in answer_page_texts
            ):
                student_answer_text = ""

        student_answer_text = student_answer_text.strip()

        # Blank answers receive zero marks without another Gemini call.
        if not student_answer_text:
            evaluation = EvaluationResponse(
                evaluation_status="evaluated",
                marks_awarded=0.0,
                total_marks=total_marks,
                score_rationale=(
                    "No assessable answer content was provided, "
                    "so no marks can be awarded."
                ),
                feedback_summary=(
                    "No answer content was provided. Submit an answer "
                    "to receive content-specific feedback."
                ),
                clarification_needed=None,
                scoring_breakdown=[
                    EvaluationCriterion(
                        criterion="Answer content",
                        marks_awarded=0.0,
                        marks_possible=total_marks,
                        comment="No assessable answer content was provided.",
                    )
                ],
                feedback=EvaluationFeedback(
                    strengths=[],
                    missing_or_weak_points=[
                        "No answer content was provided to assess."
                    ],
                    improvements=[
                        "Submit an answer that directly addresses the question."
                    ],
                    ways_to_gain_more_marks=[
                        "Provide relevant explanations, steps, or examples as required by the question."
                    ],
                ),
            )

            validate_evaluation_result(evaluation, total_marks)

        else:
            # Evaluate the answer using Gemini.
            evaluation = evaluate_answer(
                question_text=question_text,
                student_answer_text=student_answer_text,
                total_marks=total_marks,
                academic_level=academic_level,
                degree_field=degree_field,
                gemini_client=client,
            )

        # Generate the evaluation PDF.
        with tempfile.TemporaryDirectory(
            prefix="inkora_evaluation_"
        ) as temp_dir:

            pdf_path = Path(temp_dir) / "Inkora_AI_Evaluation.pdf"

            build_evaluation_pdf(
                question_text,
                student_answer_text,
                evaluation,
                pdf_path,
            )

            pdf_bytes = pdf_path.read_bytes()

            if not pdf_bytes.startswith(b"%PDF") or len(pdf_bytes) < 500:
                raise HTTPException(
                    status_code=500,
                    detail="The evaluation PDF could not be generated.",
                )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        headers = {
            "Content-Disposition": (
                f'attachment; filename="Inkora_AI_Evaluation_{timestamp}.pdf"'
            ),
            "X-Evaluation-Status": evaluation.evaluation_status,
            "X-Total-Marks": str(
                evaluation.total_marks
                if evaluation.total_marks is not None
                else ""
            ),
            "X-Marks-Awarded": (
                "0"
                if not student_answer_text
                else str(
                    evaluation.marks_awarded
                    if evaluation.marks_awarded is not None
                    else ""
                )
            ),
            "X-Feedback-Summary": quote(
                evaluation.feedback_summary or evaluation.score_rationale,
                safe="",
            ),
            "X-Score-Rationale": quote(
                evaluation.score_rationale or "",
                safe="",
            ),
            "Access-Control-Expose-Headers": (
                "Content-Disposition, X-Evaluation-Status, X-Total-Marks, "
                "X-Marks-Awarded, X-Feedback-Summary, X-Score-Rationale"
            ),
        }

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers=headers,
        )

    except HTTPException:
        raise

    except Exception as error:
        print(
            f"Academic evaluation failed: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=502,
            detail="Academic evaluation failed. Check the backend logs and try again.",
        ) from error

    finally:
        if question_image is not None:
            await question_image.close()

        for upload in student_answer_images:
            await upload.close()
