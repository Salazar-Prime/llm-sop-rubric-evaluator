# llm-sop-rubric-evaluator

Automated rubric-based scoring of Statements of Purpose (SoPs) using OpenAI structured outputs.
The pipeline cleans raw applicant text, sends each SoP to an LLM with a 6-criterion rubric, merges
scores back onto the applicant roster, and generates a paginated PDF report.

---

## Overview

The rubric covers three dimensions, each with two sub-criteria scored 0–3 (18 points total):

| Dimension | Sub-criterion |
|-----------|---------------|
| **Passion** | Motivation for Scientific Research |
| | Initiative |
| **Clarity of Purpose** | Program Expectations and Benefits |
| | Alignment with Future Endeavors and Career Direction |
| **Resilience** | Reflection on Learning through Experience |
| | Problem Solving |

---

## Prerequisites

- Python 3.8+
- An OpenAI API key with access to structured outputs (`gpt-4o` or later)

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/Salazar-Prime/llm-sop-rubric-evaluator.git
cd llm-sop-rubric-evaluator
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 3. Configure the program
cp config.example.json config.json
# Edit config.json: set programName, institution, and optionally openaiModel

# 4. Run on sample data (2 entries, minimal API cost)
python run_pipeline.py --max-entries 2
```

Outputs land in `outputs/` (see [Outputs](#outputs) below).

---

## Input format

The applicant CSV must have these columns:

| Column | Description |
|--------|-------------|
| `first_name` | Applicant first name |
| `last_name` | Applicant last name |
| `guid` | Unique identifier (any string) |
| `statement_of_purpose` | Full SoP text (may contain embedded prompt questions) |

Point `config.json → inputCsv` at your file, or pass `--input` to each script directly.

### Removing embedded prompt questions

`instructionSoP.txt` lists the prompt questions that applicants sometimes copy verbatim into
their essays. `step1_clean.py` uses fuzzy matching to strip these sequences automatically.
Edit the file to match your program's actual prompt wording.

---

## Customizing the rubric

1. **Edit `systemPromptv2.txt`** — the `{program_name}` and `{institution}` placeholders are
   filled automatically from `config.json` at runtime. Change the score descriptions to match
   your program's criteria.

2. **Edit `jsonSchema.json`** — if you add or rename rubric criteria, keep the field names in
   `jsonSchema.json` in sync with the column mappings at the top of `step2_evaluate.py`
   (`SCORE_COLS` / `RATIONALE_COLS`) and the `METRICS` list at the top of `step4_report.py`.

---

## Running each step independently

All scripts accept `--help` for full flag documentation.

```bash
# All steps at once (recommended)
python run_pipeline.py
python run_pipeline.py --max-entries 5        # limit API calls for testing
python run_pipeline.py --steps 2 --start-index 50   # resume step 2 from row 50

# Or run individual steps directly
python steps/step1_clean.py --input data/myApplicants.csv
python steps/step2_evaluate.py --model gpt-4o --max-entries 50
python steps/step3_merge.py --roster data/myApplicants.csv
python steps/step4_report.py --title "Summer 2025 SoP Report"
```

---

## Outputs

| File | Description |
|------|-------------|
| `outputs/cleanedData.xlsx` | Cleaned SoPs with word counts and skipped flags |
| `outputs/jsonOutputs/*.json` | Raw LLM response per applicant |
| `outputs/combined_results.xlsx` | Cleaned data + all scores and rationales |
| `outputs/applicants_graded.xlsx` | Original roster merged with scores and total |
| `outputs/pdf_reports/graded_sop_report.pdf` | Paginated PDF with TOC, SoP text, and score table per applicant |
| `outputs/logs/` | Rotating log files for each pipeline step |

Entries where `word_count > maxWordCountSkip` (default 1500) are flagged `skipped=True`
and still sent to the LLM unless you filter them out before Step 2.

---

## Cost note

Each SoP call uses approximately 800–1 500 prompt tokens and ~300 completion tokens with
`gpt-4o`. Use `--max-entries 2` when testing. If an API call fails, the script logs the
error and continues; re-run with `--start-index N` to resume from where it stopped
(existing `combined_results.xlsx` is preserved and updated incrementally).

---

## License

MIT — see `LICENSE`.

---

## Acknowledgments

Rubric developed for the Purdue EURO / SURF undergraduate research program.
