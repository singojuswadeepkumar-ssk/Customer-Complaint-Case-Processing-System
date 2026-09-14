# AI-Powered Customer Complaint & Case Processing System

A production-oriented Python application that uses **Google Gemini** (via **LangChain**) to automatically process customer complaint documents, extract structured data, generate professional customer emails, produce management case summaries, and export a consolidated CSV report.

---

## Features

| Capability | Detail |
|---|---|
| **Multi-format ingestion** | TXT, PDF, DOCX |
| **Structured extraction** | 10-field Pydantic model validated by Gemini |
| **Customer email** | Professional, personalised, grounded response |
| **Management summary** | 5-section internal case report |
| **Parallel generation** | Email & summary generated concurrently per document |
| **CSV report** | One consolidated report for all processed files |
| **Robust error handling** | Corrupted / unsupported files skipped gracefully |
| **Structured logging** | Console + rotating file logs |

---

## Project Structure

```
AI-Powered-Complaint-System/
├── main.py                     # Entry-point
├── requirements.txt
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── logger.py               # Logging configuration
│   ├── models.py               # Pydantic schemas
│   ├── document_loader.py      # TXT / PDF / DOCX extraction
│   ├── llm_extraction.py       # Gemini structured extraction
│   ├── email_generator.py      # Customer email generation
│   ├── summary_generator.py    # Management summary generation
│   ├── workflow.py             # Pipeline orchestration
│   └── reporting.py            # File saving & CSV report
│
├── data/                       # ← Place complaint documents here
│   ├── complaint_001_billing.txt
│   ├── complaint_002_technical.txt
│   ├── complaint_003_delivery.txt
│   └── complaint_004_customer_service.txt
│
├── output/                     # Auto-created — generated outputs
│   ├── structured_data/        # *_structured.json  (one per complaint)
│   ├── customer_emails/        # *_email.txt        (one per complaint)
│   ├── case_summaries/         # *_summary.txt      (one per complaint)
│   └── final_report.csv        # Consolidated CSV of all results
│
├── logs/
│   └── app.log                 # Rotating application log
│
└── tests/
    ├── test_document_loader.py
    ├── test_models.py
    └── test_reporting.py
```

---

## Quick Start

### 1. Clone / download and enter the project directory

```bash
cd "AI Project"
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your Gemini API key

```bash
cp .env.example .env
# Edit .env and set your key:
# GOOGLE_API_KEY=your_actual_key_here
```

Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey).

### 5. Add complaint documents

Place `.txt`, `.pdf`, or `.docx` complaint files inside the `data/` folder.  
Four sample TXT complaints are already included.

### 6. Run the pipeline

```bash
python main.py
```

Optional flags:

```bash
python main.py --data path/to/docs --output path/to/results
```

---

## Output

After a successful run you will find:

| Path | Content |
|---|---|
| `output/structured_data/<name>_structured.json` | Validated Pydantic model as JSON |
| `output/customer_emails/<name>_email.txt` | Professional customer response email |
| `output/case_summaries/<name>_summary.txt` | Internal management case summary |
| `output/final_report.csv` | All complaints in one consolidated CSV |
| `logs/app.log` | Detailed run log |

---

## Extracted Fields (CSV columns)

| Field | Description |
|---|---|
| `source_file` | Original document filename |
| `customer_name` | Full customer name |
| `email` | Customer email |
| `phone_number` | Customer phone |
| `complaint_category` | Billing / Technical / Delivery / etc. |
| `issue_description` | Summary of the problem |
| `resolution_provided` | Resolution or action taken |
| `complaint_resolved` | Yes / No / Unknown |
| `escalation_required` | Yes / No / Unknown |
| `supporting_document_available` | Yes / No / Unknown |
| `overall_case_status` | Open / In Progress / Resolved / Escalated / Closed / Pending |

---

## Running Tests

```bash
pytest tests/ -v
# With coverage:
pytest tests/ -v --cov=src --cov-report=term-missing
```

> **Note:** LLM-dependent modules (`llm_extraction`, `email_generator`, `summary_generator`) require a real API key and are not covered by the unit tests (which test loaders, models, and reporting in isolation).

---

## Architecture

```
Document (TXT/PDF/DOCX)
        │
        ▼
  document_loader.py          ← Text extraction
        │
        ▼
  llm_extraction.py           ← Gemini structured JSON extraction → ComplaintRecord
        │
        ▼
  reporting.py                ← Save structured JSON → output/structured_data/
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
  email_generator.py              summary_generator.py
  (parallel thread)               (parallel thread)
        │                                  │
        ▼                                  ▼
  output/customer_emails/       output/case_summaries/
        │                                  │
        └─────────────────┬────────────────┘
                       ▼
                 reporting.py          ← final_report.csv
```

---

## Technologies

- **LangChain** — LLM chaining and prompt management
- **Google Gemini** (`gemini-3.1-flash-lite` + `gemini-3.5-flash-lite`, task-based) — Extraction, email, and summary generation
- **Pydantic v2** — Schema definition and runtime validation
- **PyMuPDF** — PDF text extraction
- **python-docx** — DOCX text extraction
- **Pandas** — CSV report generation
- **python-dotenv** — Environment variable management

---

## Model Strategy: Task-Based Dual-Model Assignment

The pipeline uses **two Gemini Lite models** with identical rate limits (15 RPM / 250K TPM / 500 requests-per-day each), assigned by **task** rather than round-robin:

| Task | Model | Rationale |
|---|---|---|
| Structured extraction | `gemini-3.1-flash-lite` | Internal/deterministic JSON output — normal outcome is sufficient |
| Management summary | `gemini-3.1-flash-lite` | Internal-facing report — normal outcome is sufficient |
| Customer email | `gemini-3.5-flash-lite` | Customer-facing communication — better tone/quality expected |

Every document uses the **same task → model mapping**, so extraction and summaries always run on `gemini-3.1-flash-lite`, while the customer-facing email always runs on `gemini-3.5-flash-lite`. Since both models share identical quotas, this costs nothing in terms of daily request budget while directing the stronger model specifically at the output customers actually see.

This is configured in [`src/llm_extraction.py`](src/llm_extraction.py) via `EXTRACTION_MODEL` / `SUMMARY_MODEL` / `EMAIL_MODEL`, and applied in [`src/workflow.py`](src/workflow.py) where three dedicated LLM instances are built once per pipeline run and passed to their respective task functions.

## Deployment

This project can be deployed to Azure two ways — see [`docs/AZURE_DEPLOYMENT.md`](docs/AZURE_DEPLOYMENT.md) for full step-by-step instructions:

- **Option A — Batch job (Azure Container Instance).** Deploys the CLI (`main.py`) as a run-to-completion container. No public URL; you upload files to an Azure File Share and download results via CLI. Best for scheduled/automated back-office processing.
- **Option B — Web app with a public URL (Azure Container Apps).** Deploys [`streamlit_app.py`](streamlit_app.py) — a browser UI wrapped around the same `run_pipeline()` — with public ingress. Gives you a shareable `https://...azurecontainerapps.io` link where anyone can upload complaint documents and see structured data, the generated email, the management summary, and the CSV report, with no CLI or API key needed on their end. Best for demos and evaluation.

### Future Consideration: Gemma as a High-Volume Fallback

Google AI Studio's free tier also exposes open-weight **Gemma** models (e.g. `gemma-4-26b`, `gemma-4-31b`) alongside Gemini. These are **not currently used** in this project, but are worth noting for future scaling:

| | Gemini `*-flash-lite` | Gemma 4 (26B/31B) |
|---|---|---|
| Requests/day | 500 | **14,400** (~28x more) |
| Tokens/minute | 250,000 | 16,000 (~15x less) |
| Requests/minute | 15 | 30 |
| Structured JSON reliability | High (tuned for schema-following & tool use) | Lower (smaller open models are less consistent at strict JSON adherence) |
| Multimodal | Yes | Text-only |

**Why we're not using Gemma yet:** `extract_complaint_data()` depends on the LLM reliably returning valid JSON that matches our Pydantic `ComplaintRecord` schema. Gemma's weaker structured-output reliability makes it a riskier default choice for extraction — a bad JSON parse would cascade into failed emails and summaries for that document.

**Where it could help later:**
- **High-volume scaling** — if daily complaint volume exceeds what the two Gemini Lite models can handle combined (~1,000 requests/day across both), Gemma's 14,400/day ceiling gives significant headroom.
- **Rate-limit fallback** — routing a task to Gemma only when a Gemini call fails with a `429 RESOURCE_EXHAUSTED` error, rather than failing the document outright.
- **Lower-stakes tasks first** — if adopted, Gemma would be a better fit for the management summary (internal-only, less schema-strict) before extraction (needs strict JSON) or the customer email (needs strong tone/quality).

If complaint volume grows and this becomes worth pursuing, the model constants in [`src/llm_extraction.py`](src/llm_extraction.py) are the single place to introduce a Gemma fallback path.

---

## License

MIT
