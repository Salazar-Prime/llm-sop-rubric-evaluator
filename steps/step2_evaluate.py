"""
Step 2 of 4 — Evaluate cleaned SoPs via OpenAI structured outputs.

Reads outputs/cleanedData.xlsx (from step1_clean.py), sends each SoP to the
OpenAI API using the rubric in systemPromptv2.txt and schema in jsonSchema.json,
saves a per-applicant JSON under outputs/jsonOutputs/, and writes the combined
scores and rationales to outputs/combined_results.xlsx.

Run independently:
    python steps/step2_evaluate.py
    python steps/step2_evaluate.py --max-entries 5      # limit for testing
    python steps/step2_evaluate.py --start-index 50     # resume a partial run

Or via the pipeline launcher (recommended):
    python run_pipeline.py --steps 2

Output feeds into: step3_merge.py
"""

import os
import sys

# Resolve the project root (publish_v2/) regardless of where this file lives,
# so that relative paths to config, data, and outputs always work correctly.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse
import json

import pandas as pd

from utils.config import get as cfg
from utils.openaiApi import getResponse
from utils.utils import setupLogger


# Column name → path inside the JSON evaluation object returned by the API.
# If you change the rubric criteria, update these dicts and jsonSchema.json together.
SCORE_COLS = {
    "score_drive_curiosity":      ("research_motivation", "drive_and_curiosity", "score"),
    "score_career_alignment":     ("research_motivation", "career_alignment", "score"),
    "score_relevant_experience":  ("readiness", "relevant_experience", "score"),
}

RATIONALE_COLS = {
    "rationale_drive_curiosity":      ("research_motivation", "drive_and_curiosity", "rationale"),
    "rationale_career_alignment":     ("research_motivation", "career_alignment", "rationale"),
    "rationale_relevant_experience":  ("readiness", "relevant_experience", "rationale"),
}


def _extract(evaluation, path):
    obj = evaluation
    for key in path[:-1]:
        obj = obj[key]
    return obj[path[-1]]


def load_json_schema(schema_path="jsonSchema.json"):
    with open(schema_path, "r") as f:
        return json.load(f)


def merge_response(response, row, df, model):
    evaluation = response["response"]["evaluation"]
    row_index = row.name
    df.at[row_index, "model"] = model
    for col, path in {**SCORE_COLS, **RATIONALE_COLS}.items():
        df.at[row_index, col] = _extract(evaluation, path)
    return df


def process_cleaned_data(input_file, json_schema, model, output_dir,
                         start_index=0, max_entries=None,
                         program_name=None, institution=None,
                         reasoning_effort="low"):
    json_out_dir = os.path.join(output_dir, "jsonOutputs")
    os.makedirs(json_out_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "logs"), exist_ok=True)

    logger = setupLogger(os.path.join(output_dir, "logs"), "step2_evaluate.log")

    combined_output = os.path.join(output_dir, "combined_results.xlsx")
    df = pd.read_excel(input_file)

    if os.path.exists(combined_output):
        combined_df = pd.read_excel(combined_output)
        logger.info(f"Resuming from existing {combined_output}")
    else:
        combined_df = df.copy()

    end_index = len(df) if max_entries is None else min(start_index + max_entries, len(df))
    processed = 0

    for index, row in df.iloc[start_index:end_index].iterrows():
        logger.info(f"Processing {row['first_name']} {row['last_name']}")
        try:
            response = getResponse(
                row["cleaned_sop"], json_schema, model=model,
                program_name=program_name, institution=institution,
                reasoning_effort=reasoning_effort,
            )

            guid = str(row["guid"]).replace("/", "_")
            json_path = os.path.join(json_out_dir,
                                     f"{row['first_name']}_{row['last_name']}_{guid}.json")
            with open(json_path, "w") as f:
                json.dump(response, f, indent=4)

            ev = response["response"]["evaluation"]
            scores = " - ".join(str(_extract(ev, p)) for p in SCORE_COLS.values())
            logger.info(f"  Scores: {scores}")

            combined_df = merge_response(response, row, combined_df, model)
            processed += 1

            # Save intermittently so a crash doesn't lose all progress
            if processed % 10 == 0:
                combined_df.to_excel(combined_output, index=False)
                logger.info(f"Intermediate save after {processed} entries")

        except Exception as e:
            logger.error(f"Error processing {row['first_name']} {row['last_name']}: {e}")

    combined_df.to_excel(combined_output, index=False)
    logger.info(f"Done. Processed {processed} entries. Results: {combined_output}")


if __name__ == "__main__":
    os.chdir(_ROOT)  # ensure relative paths resolve from project root when run directly

    parser = argparse.ArgumentParser(description="Step 2 of 4: Evaluate SoPs via OpenAI")
    parser.add_argument("--input", default=os.path.join(cfg("outputDir", "outputs"), "cleanedData.xlsx"),
                        help="Path to cleaned data Excel file (output of step1_clean.py)")
    parser.add_argument("--model", default=cfg("openaiModel", "gpt-4o"),
                        help="OpenAI model name")
    parser.add_argument("--output-dir", default=cfg("outputDir", "outputs"),
                        help="Output directory (default: outputs/)")
    parser.add_argument("--start-index", type=int, default=0,
                        help="Row index to start from — use to resume a partial run")
    parser.add_argument("--max-entries", type=int, default=None,
                        help="Maximum number of entries to process (omit to process all)")
    args = parser.parse_args()

    program_name = cfg("programName", "the program")
    institution = cfg("institution", "the institution")
    reasoning_effort = cfg("reasoningEffort", "low")

    json_schema = load_json_schema()
    process_cleaned_data(
        args.input, json_schema, args.model, args.output_dir,
        start_index=args.start_index,
        max_entries=args.max_entries,
        program_name=program_name,
        institution=institution,
        reasoning_effort=reasoning_effort,
    )
