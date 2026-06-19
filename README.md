# llm-sop-rubric-evaluator

Automated rubric-based scoring of Statements of Purpose (SoPs) using OpenAI structured outputs.
The pipeline cleans raw applicant text, sends each SoP to an LLM with a 3-criterion rubric, merges
scores back onto the applicant roster, and generates a paginated PDF report.

---

## Overview

The rubric is defined in `systemPromptv2.txt`. It covers two dimensions with three sub-criteria,
each scored 0–3 (9 points total). Fractional scores are allowed for borderline cases. Each score
must be supported by a rationale with citations from the SoP.

| Dimension | Sub-criterion | Question |
|-----------|---------------|----------|
| **Research Motivation** | Drive and Curiosity | Why does the applicant want to do research? |
| | Career Alignment | How does this program connect to the applicant's future goals? |
| **Readiness** | Relevant Experience | What preparation has the applicant done beyond mandatory coursework? |

### Score anchors

**Drive and Curiosity**

| Score | Description |
|-------|-------------|
| 0 | No clear motivation mentioned. The applicant gives no indication of what drives their interest in research. |
| 1 | Mentions interest in research but gives no personal context or story behind it. |
| 2 | Describes a specific experience or observation that sparked their interest in research. |
| 3 | Articulates a compelling personal story with clear intellectual curiosity and identifies a specific question or problem they want to explore. |

**Career Alignment**

| Score | Description |
|-------|-------------|
| 0 | No future goals or connection to the program are mentioned. |
| 1 | Mentions future goals OR the program, but does not connect the two. |
| 2 | Connects the program to a stated career goal in general terms. |
| 3 | Describes a specific career path (e.g. PhD, industry R&D) and explains precisely how this program advances it. |

**Relevant Experience**

| Score | Description |
|-------|-------------|
| 0 | No relevant coursework, projects, or activities mentioned. |
| 1 | Lists coursework only; nothing beyond mandatory requirements. |
| 2 | Describes at least one activity beyond coursework (e.g. project, internship, club, volunteer work). |
| 3 | Demonstrates a consistent, self-directed track record of seeking out research or technical experience across multiple contexts. |

---

## Prerequisites

- Python 3.8+ (default version tested: **3.11.7**)
- An OpenAI API key with access to structured outputs
- Default model: **`gpt-5.4-mini`** (configurable in `config.json` or via `--model`)

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
# Edit config.json: set programName, institution, openaiModel, etc.

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

Point `config.json → inputCsv` at your file, or pass `--input` to the pipeline or step 1 directly.

### Removing embedded prompt questions

`instructionSoP.txt` lists the prompt questions that applicants sometimes copy verbatim into
their essays. Step 1 uses fuzzy matching to strip these sequences automatically.
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

## Pipeline launcher (`run_pipeline.py`)

`run_pipeline.py` runs one or more steps in order from a single entry point. Run
`python run_pipeline.py --help` for the full flag list.

```
usage: run_pipeline.py [-h] [--steps N [N ...]] [--input INPUT]
                       [--instructions INSTRUCTIONS]
                       [--max-word-count-skip MAX_WORD_COUNT_SKIP]
                       [--model MODEL]
                       [--reasoning-effort {none,low,medium,high,xhigh}]
                       [--start-index START_INDEX] [--max-entries MAX_ENTRIES]
                       [--title TITLE] [--output-dir OUTPUT_DIR]

SoP rubric-grading pipeline launcher

options:
  -h, --help            show this help message and exit
  --steps N [N ...]     Steps to run, e.g. --steps 1 2 3 (default: all)
  --input INPUT         Applicants CSV (step 1 input, also used by step 3 for the roster)
  --instructions INSTRUCTIONS
                        Instruction-removal text file (step 1)
  --max-word-count-skip MAX_WORD_COUNT_SKIP
                        Word count threshold for skipping flag (step 1)
  --model MODEL         OpenAI model name (step 2). GPT-5.x / o-series use
                        reasoning_effort; GPT-4.x and older use temperature/top_p.
  --reasoning-effort {none,low,medium,high,xhigh}
                        Reasoning effort for GPT-5.x / o-series models (default: low).
                        Ignored for GPT-4.x and older.
  --start-index START_INDEX
                        Row index to start from, for resuming (step 2)
  --max-entries MAX_ENTRIES
                        Maximum entries to evaluate; omit for all (step 2)
  --title TITLE         Report title on the PDF cover page (step 4)
  --output-dir OUTPUT_DIR
                        Output directory (default: outputs)

examples:
  python run_pipeline.py                        run all four steps
  python run_pipeline.py --steps 1 2            run steps 1 and 2 only
  python run_pipeline.py --steps 2 --max-entries 5   test with 5 entries
  python run_pipeline.py --steps 2 --start-index 50  resume step 2 from row 50
```

### Common invocations

```bash
python run_pipeline.py                        # all steps (1 → 2 → 3 → 4)
python run_pipeline.py --max-entries 5        # limit API calls for testing
python run_pipeline.py --steps 2 --start-index 50   # resume step 2 from row 50
python run_pipeline.py --title "Summer 2025 SoP Report"   # custom PDF title
```

---

## Pipeline steps

### Step 1 — Clean SoP data (`steps/step1_clean.py`)

Reads the applicants CSV, strips embedded instruction text (fuzzy-matched against
`instructionSoP.txt`), counts words, and writes `outputs/cleanedData.xlsx`.

```
usage: step1_clean.py [-h] [--input INPUT] [--instructions INSTRUCTIONS]
                      [--output-dir OUTPUT_DIR]
                      [--max-word-count-skip MAX_WORD_COUNT_SKIP]

Step 1 of 4: Clean SoP data

options:
  --input INPUT         Path to applicants CSV
  --instructions INSTRUCTIONS
                        Path to instruction-removal text file
  --output-dir OUTPUT_DIR
                        Output directory (default: outputs/)
  --max-word-count-skip MAX_WORD_COUNT_SKIP
                        Flag entries with more words than this threshold
```

```bash
python steps/step1_clean.py --input data/myApplicants.csv
python run_pipeline.py --steps 1
```

**Output:** `outputs/cleanedData.xlsx` → feeds Step 2

---

### Step 2 — Evaluate SoPs via OpenAI (`steps/step2_evaluate.py`)

Sends each cleaned SoP to the OpenAI API using the rubric in `systemPromptv2.txt` and schema in
`jsonSchema.json`. Saves a per-applicant JSON under `outputs/jsonOutputs/` and writes combined
scores and rationales to `outputs/combined_results.xlsx`.

```
usage: step2_evaluate.py [-h] [--input INPUT] [--model MODEL]
                         [--output-dir OUTPUT_DIR] [--start-index START_INDEX]
                         [--max-entries MAX_ENTRIES]

Step 2 of 4: Evaluate SoPs via OpenAI

options:
  --input INPUT         Path to cleaned data Excel file (output of step1_clean.py)
  --model MODEL         OpenAI model name
  --output-dir OUTPUT_DIR
                        Output directory (default: outputs/)
  --start-index START_INDEX
                        Row index to start from — use to resume a partial run
  --max-entries MAX_ENTRIES
                        Maximum number of entries to process (omit to process all)
```

```bash
python steps/step2_evaluate.py --model gpt-5.4-mini --max-entries 50
python run_pipeline.py --steps 2 --start-index 50
```

**Output:** `outputs/jsonOutputs/*.json`, `outputs/combined_results.xlsx` → feeds Step 3

---

### Step 3 — Merge results onto roster (`steps/step3_merge.py`)

Joins `combined_results.xlsx` onto the original applicants CSV by `guid`. All original roster
columns are preserved; evaluation columns and `total_score` are appended.

```
usage: step3_merge.py [-h] [--roster ROSTER] [--results RESULTS] [--output OUTPUT]

Step 3 of 4: Merge evaluation results

options:
  --roster ROSTER       Original applicants CSV (same file used in step1_clean.py)
  --results RESULTS     Combined results Excel from step2_evaluate.py
  --output OUTPUT       Output path for the merged graded file
```

```bash
python steps/step3_merge.py --roster data/myApplicants.csv
python run_pipeline.py --steps 3
```

**Output:** `outputs/applicants_graded.xlsx` → feeds Step 4

---

### Step 4 — Generate PDF report (`steps/step4_report.py`)

Reads the graded Excel file and writes a paginated PDF with a title page, table of contents,
and one section per evaluated applicant (SoP text plus rubric score table).

```
usage: step4_report.py [-h] [--input INPUT] [--output OUTPUT] [--title TITLE]

Step 4 of 4: Generate PDF report

options:
  --input INPUT         Graded applicants Excel file from step3_merge.py
  --output OUTPUT       Output PDF path
  --title TITLE         Report title shown on the cover page
```

```bash
python steps/step4_report.py --title "Summer 2025 SoP Report"
python run_pipeline.py --steps 4
```

**Output:** `outputs/pdf_reports/graded_sop_report.pdf`

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

Each SoP call uses roughly 800–1 500 prompt tokens and ~300 completion tokens with
`gpt-5.4-mini`. Use `--max-entries 2` when testing. If an API call fails, the script logs the
error and continues; re-run with `--start-index N` to resume from where it stopped
(existing `combined_results.xlsx` is preserved and updated incrementally).

---

## License

MIT — see `LICENSE`.

---

## Acknowledgments

Rubric developed for the Purdue EURO / SURF undergraduate research program.
