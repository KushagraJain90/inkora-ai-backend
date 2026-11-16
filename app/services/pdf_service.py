
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.evaluation_models import EvaluationResponse


def build_evaluation_pdf(
    question: str,
    student_answer: str,
    result: EvaluationResponse,
    output_path: Path,
) -> None:
    """Create a standalone evaluation PDF using ReportLab."""

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="InkoraTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        alignment=TA_CENTER,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="InkoraSection",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        spaceBefore=10,
        spaceAfter=5,
        textColor=colors.HexColor("#243B53"),
    ))

    styles.add(ParagraphStyle(
        name="InkoraBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13,
        spaceAfter=5,
        wordWrap="CJK",
    ))

    styles.add(ParagraphStyle(
        name="InkoraSmall",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#52606D"),
        spaceAfter=3,
    ))

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="Inkora AI Academic Answer Evaluation",
        author="Inkora AI",
    )

    story = [
        Paragraph("Inkora AI", styles["InkoraTitle"]),
        Paragraph(
            "Academic Answer Evaluation Report",
            styles["Heading1"],
        ),
        Spacer(1, 3 * mm),
    ]

    def add_section(title: str, body: str) -> None:
        story.append(
            Paragraph(escape(title), styles["InkoraSection"])
        )

        safe_body = escape(body or "").replace("\n", "<br/>")

        story.append(
            Paragraph(
                safe_body if safe_body else "—",
                styles["InkoraBody"],
            )
        )

    add_section("Question", question)

    if result.evaluation_status == "evaluated":

        marks = (
            f"{result.marks_awarded:g} / "
            f"{result.total_marks:g}"
        )

        story.append(
            Paragraph(
                f"<b>Marks awarded:</b> {escape(marks)}",
                styles["Heading2"],
            )
        )

        add_section("Score rationale", result.score_rationale)

        if result.scoring_breakdown:

            story.append(
                Paragraph(
                    "Scoring breakdown",
                    styles["InkoraSection"],
                )
            )

            rows = [
                ["Criterion", "Awarded", "Possible", "Comment"]
            ]

            for item in result.scoring_breakdown:
                rows.append([
                    Paragraph(
                        escape(item.criterion),
                        styles["InkoraSmall"],
                    ),
                    f"{item.marks_awarded:g}",
                    f"{item.marks_possible:g}",
                    Paragraph(
                        escape(item.comment),
                        styles["InkoraSmall"],
                    ),
                ])

            table = Table(
                rows,
                colWidths=[
                    39 * mm,
                    17 * mm,
                    17 * mm,
                    89 * mm,
                ],
                repeatRows=1,
            )

            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#EAF0F6")),
                ("TEXTCOLOR", (0, 0), (-1, 0),
                 colors.HexColor("#102A43")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("GRID", (0, 0), (-1, -1),
                 0.4, colors.HexColor("#CBD2D9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))

            story.append(table)

        feedback_sections = [
            ("Strengths", result.feedback.strengths),
            (
                "Missing or weak points",
                result.feedback.missing_or_weak_points,
            ),
            ("Improvements", result.feedback.improvements),
            (
                "Ways to gain more marks",
                result.feedback.ways_to_gain_more_marks,
            ),
        ]

        for title, items in feedback_sections:
            story.append(
                Paragraph(title, styles["InkoraSection"])
            )

            if items:
                for item in items:
                    story.append(
                        Paragraph(
                            "• " + escape(item),
                            styles["InkoraBody"],
                        )
                    )
            else:
                story.append(
                    Paragraph(
                        "No specific points identified.",
                        styles["InkoraBody"],
                    )
                )

    else:
        add_section(
            "Evaluation needs clarification",
            result.clarification_needed or result.score_rationale,
        )

        add_section("Details", result.score_rationale)

    add_section(
        "Student answer (transcribed text)",
        student_answer or "[blank answer]",
    )

    story.append(Spacer(1, 5 * mm))

    story.append(
        Paragraph(
            "Generated by Inkora AI. Review the feedback alongside "
            "your course requirements.",
            styles["InkoraSmall"],
        )
    )

    document.build(story)
