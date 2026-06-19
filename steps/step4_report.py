"""
Step 4 of 4 — Generate a PDF report from the graded applicant data.

Reads outputs/applicants_graded.xlsx (from step3_merge.py) and writes a
paginated PDF with a title page, table of contents, and one section per
evaluated applicant showing their SoP text and a rubric score table.

Run independently:
    python steps/step4_report.py
    python steps/step4_report.py --title "Summer 2025 SoP Evaluation"
    python steps/step4_report.py --input outputs/applicants_graded.xlsx --output outputs/report.pdf

Or via the pipeline launcher (recommended):
    python run_pipeline.py --steps 4
"""

import os
import sys

# Resolve the project root (publish_v2/) regardless of where this file lives,
# so that relative paths to config, data, and outputs always work correctly.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from utils.config import get as cfg


# Each entry: (display label, score column name, rationale column name).
# If you change the rubric criteria, update this list and jsonSchema.json together.
METRICS = [
    ("Drive & Curiosity",   "score_drive_curiosity",     "rationale_drive_curiosity"),
    ("Career Alignment",    "score_career_alignment",    "rationale_career_alignment"),
    ("Relevant Experience", "score_relevant_experience", "rationale_relevant_experience"),
]


class _DocTemplate(SimpleDocTemplate):
    """SimpleDocTemplate subclass that registers TOC entries for Title-styled paragraphs."""

    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        self.toc = TableOfContents()
        toc_style = ParagraphStyle(
            fontName="Helvetica",
            fontSize=10,
            name="TOCHeading0",
            leftIndent=20,
            firstLineIndent=-20,
            spaceBefore=1,
            spaceAfter=1,
            leading=16,
        )
        self.toc.dotsMinLevel = 0
        self.toc.levelStyles = [toc_style]

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "Title":
            key = "h1-%s" % self.seq.nextf("heading1")
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page, key))


def _create_student_section(row, styles):
    """Build the list of ReportLab flowables for a single applicant's section."""
    justified = ParagraphStyle("Justified", parent=styles["BodyText"], alignment=4)
    content = []

    # Section heading (also registers a TOC entry via afterFlowable)
    name = f"{row['first_name']} {row['last_name']} - {row['guid']}"
    content.append(Paragraph(name, styles["Title"]))
    content.append(Spacer(1, 12))

    # SoP text with word count and total score
    total = int(row["total_score"]) if pd.notna(row.get("total_score")) else 0
    max_score = len(METRICS) * 3          # derived from rubric size, not hardcoded
    wc = int(row["word_count"]) if pd.notna(row.get("word_count")) else 0
    content.append(Paragraph(
        f"<b>Statement of Purpose | ({wc} words | {total} out of {max_score})</b>",
        styles["Heading2"],
    ))
    content.append(Paragraph(str(row["cleaned_sop"]), justified))
    content.append(Spacer(1, 12))

    # Rubric score table
    table_data = [[
        Paragraph(f"<b>Metric &amp; Score<br/>Total: {total}/{max_score}</b>", styles["BodyText"]),
        Paragraph("<b>Rationale</b>", styles["BodyText"]),
    ]]
    for metric_name, score_col, rationale_col in METRICS:
        score_val = row.get(score_col)
        score_int = int(score_val) if pd.notna(score_val) else 0
        table_data.append([
            Paragraph(f"{metric_name}<br />{score_int}/3", styles["BodyText"]),
            Paragraph(str(row.get(rationale_col, "")), styles["BodyText"]),
        ])

    col1 = 510 * 0.20
    col2 = 510 * 0.80
    table = Table(table_data, colWidths=[col1, col2])
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    content.append(table)
    content.append(Spacer(1, 12))

    # ── EXTENSION POINT ───────────────────────────────────────────────────────
    # Add additional per-applicant report sections here.
    # Append any ReportLab flowable to `content` before the PageBreak.
    # Examples:
    #   content.append(build_score_chart(row))
    #   content.append(build_comparison_table(row, cohort_avg))
    #   content.append(Paragraph("Reviewer notes: ...", styles["BodyText"]))
    # ─────────────────────────────────────────────────────────────────────────

    content.append(PageBreak())
    return content


def generate_pdf_report(input_xlsx, output_path, report_title):
    df = pd.read_excel(input_xlsx)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = _DocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    pdf_content = []

    # ── Title page ────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=36, spaceAfter=30, alignment=1, leading=50,
    )
    date_style = ParagraphStyle(
        "DateStyle", parent=styles["Normal"],
        fontSize=14, alignment=1, spaceAfter=30,
    )
    pdf_content.append(Spacer(1, 100))
    pdf_content.append(Paragraph(report_title, title_style))
    pdf_content.append(Spacer(1, 30))
    pdf_content.append(Paragraph(datetime.now().strftime("%B %d, %Y"), date_style))
    pdf_content.append(PageBreak())

    # ── Table of contents ─────────────────────────────────────────────────────
    toc_title_style = ParagraphStyle(
        "TOCTitle", parent=styles["Heading1"],
        fontSize=14, spaceAfter=20, spaceBefore=10, alignment=1,
    )
    pdf_content.append(Paragraph("TABLE OF CONTENTS", toc_title_style))
    pdf_content.append(Spacer(1, 10))
    pdf_content.append(doc.toc)
    pdf_content.append(PageBreak())

    # ── Per-applicant sections ────────────────────────────────────────────────
    # Guard against the model column being absent (e.g. if step2 produced no results)
    if "model" not in df.columns:
        print("No 'model' column found — no evaluated entries to report.")
        return

    # Keep original row order from the graded file; filter to evaluated entries only
    evaluated = df[pd.notna(df["model"])]
    for _, row in evaluated.iterrows():
        pdf_content.extend(_create_student_section(row, styles))

    doc.multiBuild(pdf_content)
    print(f"PDF report generated: {output_path}")
    print(f"Total students: {len(evaluated)}")


if __name__ == "__main__":
    os.chdir(_ROOT)  # ensure relative paths resolve from project root when run directly

    output_dir = cfg("outputDir", "outputs")
    default_title = cfg("pdfReportTitle", "SoP Rubric Evaluation Report")
    parser = argparse.ArgumentParser(description="Step 4 of 4: Generate PDF report")
    parser.add_argument("--input",  default=os.path.join(output_dir, "applicants_graded.xlsx"),
                        help="Graded applicants Excel file from step3_merge.py")
    parser.add_argument("--output", default=os.path.join(output_dir, "pdf_reports", "graded_sop_report.pdf"),
                        help="Output PDF path")
    parser.add_argument("--title",  default=default_title,
                        help="Report title shown on the cover page")
    args = parser.parse_args()

    generate_pdf_report(args.input, args.output, args.title)
