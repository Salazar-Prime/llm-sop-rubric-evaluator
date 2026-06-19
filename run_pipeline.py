"""
Pipeline launcher — run all four steps in sequence from a single entry point.

Usage:
    python run_pipeline.py                        # run all steps (1 → 2 → 3 → 4)
    python run_pipeline.py --steps 1 2            # run only steps 1 and 2
    python run_pipeline.py --steps 2 --max-entries 5   # test with 5 entries
    python run_pipeline.py --steps 2 --start-index 50  # resume step 2 from row 50
    python run_pipeline.py --title "My Report"    # custom PDF title for step 4

Individual steps can also be run directly:
    python steps/step1_clean.py --help
    python steps/step2_evaluate.py --help
    python steps/step3_merge.py --help
    python steps/step4_report.py --help
"""

import argparse
import os
import sys
import traceback

# Always run relative to this file's directory (the project root),
# regardless of where the user invokes python from.
_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)

from utils.config import get as cfg
from steps.step1_clean import clean_sop_data
from steps.step2_evaluate import process_cleaned_data, load_json_schema
from steps.step3_merge import merge_evaluation_results
from steps.step4_report import generate_pdf_report


# ── Helpers ──────────────────────────────────────────────────────────────────

def _banner(n, label):
    print(f"\n{'─' * 60}")
    print(f"  Step {n}: {label}")
    print(f"{'─' * 60}")


def _done(n):
    print(f"  Step {n} complete ✓")


# ── Step runners ─────────────────────────────────────────────────────────────

def run_step1(args):
    _banner(1, "Clean SoP data")
    clean_sop_data(
        input_file=args.input,
        instruction_file=args.instructions,
        output_dir=args.output_dir,
        max_word_count_skip=args.max_word_count_skip,
    )
    _done(1)


def run_step2(args):
    _banner(2, "Evaluate SoPs via OpenAI")
    json_schema = load_json_schema()
    process_cleaned_data(
        input_file=os.path.join(args.output_dir, "cleanedData.xlsx"),
        json_schema=json_schema,
        model=args.model,
        output_dir=args.output_dir,
        start_index=args.start_index,
        max_entries=args.max_entries,
        program_name=cfg("programName", "the program"),
        institution=cfg("institution", "the institution"),
        reasoning_effort=args.reasoning_effort,
    )
    _done(2)


def run_step3(args):
    _banner(3, "Merge results onto roster")
    merge_evaluation_results(
        roster_csv=args.input,
        results_xlsx=os.path.join(args.output_dir, "combined_results.xlsx"),
        output_path=os.path.join(args.output_dir, "applicants_graded.xlsx"),
    )
    _done(3)


def run_step4(args):
    _banner(4, "Generate PDF report")
    generate_pdf_report(
        input_xlsx=os.path.join(args.output_dir, "applicants_graded.xlsx"),
        output_path=os.path.join(args.output_dir, "pdf_reports", "graded_sop_report.pdf"),
        report_title=args.title,
    )
    _done(4)


# ── Step registry ─────────────────────────────────────────────────────────────

STEPS = {
    1: run_step1,
    2: run_step2,
    3: run_step3,
    4: run_step4,
}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    output_dir = cfg("outputDir", "outputs")

    parser = argparse.ArgumentParser(
        description="SoP rubric-grading pipeline launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python run_pipeline.py                        run all four steps
  python run_pipeline.py --steps 1 2            run steps 1 and 2 only
  python run_pipeline.py --steps 2 --max-entries 5   test with 5 entries
  python run_pipeline.py --steps 2 --start-index 50  resume step 2 from row 50
        """,
    )

    # Which steps to run
    parser.add_argument(
        "--steps", nargs="+", type=int, choices=[1, 2, 3, 4],
        default=[1, 2, 3, 4],
        metavar="N",
        help="Steps to run, e.g. --steps 1 2 3 (default: all)",
    )

    # Step 1 options
    parser.add_argument("--input", default=cfg("inputCsv", "sample_data/applicants_sample.csv"),
                        help="Applicants CSV (step 1 input, also used by step 3 for the roster)")
    parser.add_argument("--instructions", default=cfg("instructionFile", "instructionSoP.txt"),
                        help="Instruction-removal text file (step 1)")
    parser.add_argument("--max-word-count-skip", type=int,
                        default=cfg("maxWordCountSkip", 1500),
                        help="Word count threshold for skipping flag (step 1)")

    # Step 2 options
    parser.add_argument("--model", default=cfg("openaiModel", "gpt-5.4-mini"),
                        help="OpenAI model name (step 2). GPT-5.x / o-series use "
                             "reasoning_effort; GPT-4.x and older use temperature/top_p.")
    parser.add_argument("--reasoning-effort",
                        default=cfg("reasoningEffort", "low"),
                        choices=["none", "low", "medium", "high", "xhigh"],
                        help="Reasoning effort for GPT-5.x / o-series models (default: low). "
                             "Ignored for GPT-4.x and older.")
    parser.add_argument("--start-index", type=int, default=0,
                        help="Row index to start from, for resuming (step 2)")
    parser.add_argument("--max-entries", type=int, default=None,
                        help="Maximum entries to evaluate; omit for all (step 2)")

    # Step 4 options
    parser.add_argument("--title", default=cfg("pdfReportTitle", "SoP Rubric Evaluation Report"),
                        help="Report title on the PDF cover page (step 4)")

    # Shared
    parser.add_argument("--output-dir", default=output_dir,
                        help=f"Output directory (default: {output_dir})")

    args = parser.parse_args()

    # Deduplicate and sort so steps always run in order even if user passes --steps 3 1
    steps_to_run = sorted(set(args.steps))

    print(f"\nRunning steps: {steps_to_run}")
    print(f"Output dir:    {args.output_dir}")

    failed = []
    for step_num in steps_to_run:
        try:
            STEPS[step_num](args)
        except Exception:
            print(f"\n  ERROR in Step {step_num}:")
            traceback.print_exc()
            failed.append(step_num)
            print(f"\n  Stopping pipeline — step {step_num} failed.")
            break

    print(f"\n{'─' * 60}")
    if failed:
        print(f"  Pipeline stopped at step {failed[0]}.")
        sys.exit(1)
    else:
        print(f"  All steps complete.")
