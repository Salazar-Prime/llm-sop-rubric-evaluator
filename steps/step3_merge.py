"""
Step 3 of 4 — Merge evaluation results onto the original applicant roster.

Joins outputs/combined_results.xlsx (from step2_evaluate.py) onto the original
applicants CSV by guid and writes outputs/applicants_graded.xlsx.

All original roster columns are preserved in their original order; evaluation
columns are appended after them, followed by total_score.

Run independently:
    python steps/step3_merge.py
    python steps/step3_merge.py --roster my_applicants.csv --output outputs/graded.xlsx

Or via the pipeline launcher (recommended):
    python run_pipeline.py --steps 3

Output feeds into: step4_report.py
"""

import os
import sys

# Resolve the project root (publish_v2/) regardless of where this file lives,
# so that relative paths to config, data, and outputs always work correctly.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse

import pandas as pd

from utils.config import get as cfg


# Evaluation columns expected from step2_evaluate.py output.
# Order here determines the column order in the output file.
SCORE_COLS = [
    "score_drive_curiosity",
    "score_career_alignment",
    "score_relevant_experience",
]

RESULT_COLS = [
    "cleaned_sop",
    "word_count",
    "skipped",
    "model",
    *SCORE_COLS,
    "rationale_drive_curiosity",
    "rationale_career_alignment",
    "rationale_relevant_experience",
]


def merge_evaluation_results(roster_csv, results_xlsx, output_path):
    original_df = pd.read_csv(roster_csv, encoding="utf-8")
    results_df = pd.read_excel(results_xlsx)

    # Only pull result columns that are actually present (defensive against partial runs)
    available_result_cols = [c for c in RESULT_COLS if c in results_df.columns]

    merged_df = pd.merge(
        original_df,
        results_df[["guid"] + available_result_cols],
        on="guid",
        how="left",
    )

    # Calculate total score from whichever score columns are present
    present_score_cols = [c for c in SCORE_COLS if c in merged_df.columns]
    merged_df["total_score"] = merged_df[present_score_cols].sum(axis=1)

    # ── EXTENSION POINT ───────────────────────────────────────────────────────
    # Add custom post-merge logic here before the file is saved.
    # Examples:
    #   merged_df = flag_borderline_scores(merged_df)
    #   merged_df = add_percentile_rank(merged_df, score_col="total_score")
    #   merged_df = apply_tiebreaker(merged_df)
    # ─────────────────────────────────────────────────────────────────────────

    # Column order: all original roster columns first (preserving any extra
    # fields the caller's CSV may have), then evaluation columns, total_score last.
    eval_cols = [c for c in available_result_cols if c not in original_df.columns]
    final_cols = list(original_df.columns) + eval_cols + ["total_score"]
    final_cols = [c for c in final_cols if c in merged_df.columns]  # drop any missing
    merged_df = merged_df[final_cols]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    merged_df.to_excel(output_path, index=False)
    print(f"Merged results saved to {output_path}")

    evaluated = int(merged_df["model"].notna().sum()) if "model" in merged_df.columns else 0
    print(f"\nMerge statistics:")
    print(f"  Original records:    {len(original_df)}")
    print(f"  Evaluated records:   {len(results_df)}")
    print(f"  Successfully merged: {evaluated}")
    print(f"  Without evaluations: {len(merged_df) - evaluated}")


if __name__ == "__main__":
    os.chdir(_ROOT)  # ensure relative paths resolve from project root when run directly

    output_dir = cfg("outputDir", "outputs")
    parser = argparse.ArgumentParser(description="Step 3 of 4: Merge evaluation results")
    parser.add_argument("--roster", default=cfg("inputCsv", "sample_data/applicants_sample.csv"),
                        help="Original applicants CSV (same file used in step1_clean.py)")
    parser.add_argument("--results", default=os.path.join(output_dir, "combined_results.xlsx"),
                        help="Combined results Excel from step2_evaluate.py")
    parser.add_argument("--output", default=os.path.join(output_dir, "applicants_graded.xlsx"),
                        help="Output path for the merged graded file")
    args = parser.parse_args()

    merge_evaluation_results(args.roster, args.results, args.output)
