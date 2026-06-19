"""
Step 1 of 4 — Clean applicant SoP data.

Reads a CSV of applicants, strips embedded instruction text (fuzzy-matched
against instructionSoP.txt), counts words, and writes a cleaned Excel file
to outputs/cleanedData.xlsx.

Run independently:
    python steps/step1_clean.py
    python steps/step1_clean.py --input my_applicants.csv --output-dir outputs

Or via the pipeline launcher (recommended):
    python run_pipeline.py --steps 1

Required CSV columns: first_name, last_name, guid, statement_of_purpose
Output feeds into: step2_evaluate.py
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

from utils.cleanString import cleanString, getInstructionInJson
from utils.config import get as cfg
from utils.utils import setupLogger


def clean_sop_data(input_file, instruction_file, output_dir, max_word_count_skip=None):
    if max_word_count_skip is None:
        max_word_count_skip = cfg("maxWordCountSkip", 1500)

    os.makedirs(output_dir, exist_ok=True)
    logger = setupLogger(os.path.join(output_dir, "logs"), "step1_clean.log")

    json_instructions = getInstructionInJson(instruction_file)

    df = pd.read_csv(input_file, encoding="utf-8")

    columns = ["first_name", "last_name", "guid", "original_sop",
               "cleaned_sop", "word_count", "logs", "skipped"]
    cleaned_data = pd.DataFrame(columns=columns)

    for index, row in df.iterrows():
        try:
            sop = row["statement_of_purpose"]

            # ── EXTENSION POINT ───────────────────────────────────────────────────
            # Add additional pre-processing steps here before the main clean pass.
            # Each step should be a function with signature (text: str) -> str.
            # Example:
            #   sop = strip_html_tags(sop)
            #   sop = normalize_unicode(sop)
            # ─────────────────────────────────────────────────────────────────────

            cleaned_sop, word_count, logs = cleanString(sop, json_instructions)
            skipped = word_count > max_word_count_skip

            cleaned_data.loc[len(cleaned_data)] = {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "guid": row["guid"],
                "original_sop": sop,
                "cleaned_sop": cleaned_sop,
                "word_count": word_count,
                "logs": "; ".join(logs),
                "skipped": skipped,
            }

            logger.info(f"Processed row {index}: {row['first_name']} {row['last_name']} ({word_count} words)")
            if logs:
                logger.info(f"  Cleaning actions: {'; '.join(logs)}")
        except Exception as e:
            logger.error(f"Error processing row {index}: {e}")

    output_path = os.path.join(output_dir, "cleanedData.xlsx")
    cleaned_data.to_excel(output_path, index=False)
    logger.info(f"Cleaning complete. Results saved to {output_path}")

    total = len(cleaned_data)
    skipped_count = int(cleaned_data["skipped"].sum())
    logger.info(f"Total processed: {total} | Marked for review (>{max_word_count_skip} words): {skipped_count}")


if __name__ == "__main__":
    os.chdir(_ROOT)  # ensure relative paths resolve from project root when run directly

    parser = argparse.ArgumentParser(description="Step 1 of 4: Clean SoP data")
    parser.add_argument("--input", default=cfg("inputCsv", "sample_data/applicants_sample.csv"),
                        help="Path to applicants CSV")
    parser.add_argument("--instructions", default=cfg("instructionFile", "instructionSoP.txt"),
                        help="Path to instruction-removal text file")
    parser.add_argument("--output-dir", default=cfg("outputDir", "outputs"),
                        help="Output directory (default: outputs/)")
    parser.add_argument("--max-word-count-skip", type=int,
                        default=cfg("maxWordCountSkip", 1500),
                        help="Flag entries with more words than this threshold")
    args = parser.parse_args()

    clean_sop_data(args.input, args.instructions, args.output_dir, args.max_word_count_skip)
