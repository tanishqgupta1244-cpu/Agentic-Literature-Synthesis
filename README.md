# Automated Literature Review

An AI-powered system that analyzes multiple research papers using specialized
agents for summarization, comparison, gap identification, citation verification,
and report generation. Orchestrated with LangGraph.

---

## Current Phase

```
Current Phase : Phase 1
Status        : Research Corpus & PDF Processing
```

Phase 1 builds the reliable PDF → structured, page-aware research data →
PostgreSQL ingestion pipeline (parsing, section detection, deterministic
chunking, papers + chunks persistence).

> **Note:** The Phase 1 implementation is complete and fully unit-tested.
> End-to-end ingestion against PostgreSQL requires PostgreSQL 14+ to be
> installed and configured (see "Phase 1 — Setup" below). Until then, the
> database-dependent acceptance items are BLOCKED on the local machine.

---

## Planned Architecture

```
Browser
   │
   ▼
Next.js Frontend  (localhost:3000)
   │
   ▼
FastAPI Backend   (localhost:8000)
   │
   ▼
LangGraph Orchestrator          ← Phase 2
   │
   ├── PDF Parsing Agent        ← Phase 1
   ├── Summarization Agent      ← Phase 2
   ├── Comparison Agent         ← Phase 2
   ├── Gap Identification Agent ← Phase 2
   └── Citation Verifier        ← Phase 2
          │
          ▼
   PostgreSQL + pgvector        ← Phase 0 (connection) / Phase 1 (schema)
```

See `docs/architecture.md` for the full design.

---

## Project Structure

```
project-root/
├── backend/               FastAPI application
│   ├── api/               Route handlers (health, papers)
│   ├── config/            Database config, settings
│   ├── models.py          SQLAlchemy ORM (papers, chunks)
│   └── main.py            Application entry point
│
├── frontend/              Next.js application
│   └── src/
│       ├── app/           App Router pages and layouts
│       ├── components/    Shared UI components
│       ├── hooks/         Custom React hooks
│       └── lib/           API client utilities
│
├── agents/                LangGraph agents (Phase 2+)
├── ingestion/             Document ingestion pipeline (Phase 1)
│   ├── parser.py          PDF parser abstraction (PyMuPDF)
│   ├── models.py          Parsed paper / chunk pydantic models
│   ├── chunker.py         Section detection + deterministic chunking
│   └── service.py         Pipeline orchestration (store → parse → chunk → save)
├── evaluation/            Evaluation metrics (future)
│
├── data/
│   ├── raw/               Raw PDF files (git-ignored)
│   ├── processed/         Processed documents (git-ignored)
│   └── test_corpus/       Sample papers for testing (tracked)
│
├── tests/
│   ├── unit/              Fast tests, no external dependencies
│   └── integration/       Tests requiring live database
│
├── scripts/
│   ├── init_db.py         Create papers + chunks tables (Phase 1)
│   ├── setup_check.py     Verify environment before first run
│   └── health_check.py    Check the live running stack
│
├── docs/
│   ├── architecture.md    System design and component overview
│   └── git_workflow.md    Branch strategy and commit conventions
│
├── .env.example           Environment variable template
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Requirements

| Requirement    | Version   | Notes                            |
|----------------|-----------|----------------------------------|
| Python         | 3.11+     | 3.12 works, 3.11 is the baseline |
| Node.js        | 18+       | Required for frontend only       |
| npm            | 9+        | Bundled with Node.js             |
| PostgreSQL     | 14+       | Local or Docker                  |
| pgvector       | 0.5+      | Optional in Phase 0              |

---

## Setup — Step by Step

### 1. Clone the repository

```bash
git clone <repository-url>
cd "Agentic Research Aanlyzer"
```

### 2. Create a Python virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
# Copy the template
cp .env.example .env

# Open .env and fill in your values:
#   DATABASE_URL — your PostgreSQL connection string
#   DB_USER, DB_PASSWORD — your database credentials
```

`.env` is listed in `.gitignore` and will never be committed.

Minimum required values in `.env`:

```dotenv
APP_ENV=development
BACKEND_PORT=8000
FRONTEND_PORT=3000
FRONTEND_URL=http://localhost:3000
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/literature_review_dev
DB_HOST=localhost
DB_PORT=5432
DB_NAME=literature_review_dev
DB_USER=<your-db-user>
DB_PASSWORD=<your-db-password>
```

### 5. Create the PostgreSQL database

Connect to PostgreSQL and run:

```sql
CREATE USER reviewer WITH PASSWORD 'your_secure_password';
CREATE DATABASE literature_review_dev OWNER reviewer;

-- Optional: enable pgvector if installed
\c literature_review_dev
CREATE EXTENSION IF NOT EXISTS vector;
```

Or using `psql` from the command line:

```bash
psql -U postgres -c "CREATE USER reviewer WITH PASSWORD 'your_secure_password';"
psql -U postgres -c "CREATE DATABASE literature_review_dev OWNER reviewer;"
```

### 6. Verify your environment (pre-startup check)

```bash
python scripts/setup_check.py
```

Expected output:

```
====================================================
  Automated Literature Review — Setup Check
====================================================

[1] Python
  Python version               [ OK ]  (3.12.0)

[2] Python Dependencies
  fastapi                      [ OK ]
  uvicorn                      [ OK ]
  ...

[3] Environment Configuration
  .env file                    [ OK ]  (found)
  DATABASE_URL                 [ OK ]  (***)
  APP_ENV                      [ OK ]  (development)
  BACKEND_PORT                 [ OK ]  (8000)

[4] Project Structure
  backend                      [ OK ]
  frontend                     [ OK ]
  ...

[5] PostgreSQL
  PostgreSQL connection        [ OK ]  (SELECT 1 succeeded)

[6] Node.js / npm (frontend)
  node                         [ OK ]  (v20.x.x)
  npm                          [ OK ]  (10.x.x)
```

### 7. Start the backend

```bash
# From the project root, with virtual environment activated:
uvicorn backend.main:app --reload --port 8000
```

The backend is ready when you see:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 8. Install frontend dependencies

```bash
cd frontend
npm install
```

### 9. Start the frontend

```bash
# Still inside the frontend/ directory:
npm run dev
```

The frontend is ready when you see:

```
▲ Next.js 14.x.x
- Local: http://localhost:3000
```

### 10. Open the application

Open your browser and navigate to:

```
http://localhost:3000
```

You should see:

```
Automated Literature Review
AI-powered research paper analysis — Phase 0

System Status
Backend   ●  Connected
Database  ●  Connected
```

### 11. Run the full stack health check

With both backend and frontend running:

```bash
python scripts/health_check.py
```

---

## Health Endpoints

| Endpoint       | Method | Description                              |
|----------------|--------|------------------------------------------|
| `/health`      | GET    | Confirms the backend process is running  |
| `/health/db`   | GET    | Confirms PostgreSQL connection is live   |
| `/papers/upload` | POST | Upload + ingest a research PDF (Phase 1) |
| `/docs`        | GET    | Interactive API documentation (Swagger)  |
| `/redoc`       | GET    | Alternative API documentation            |

### Example responses

`GET /health`
```json
{ "status": "ok" }
```

`GET /health/db`
```json
{ "status": "ok", "database": "connected" }
```

---

## Phase 1 — Research Corpus & PDF Processing

### Overview

Phase 1 delivers the document-ingestion foundation:

```
PDF → Upload → PyMuPDF extraction → metadata + pages + text →
section detection → deterministic chunking → PostgreSQL (papers + chunks)
```

Everything is **deterministic** — no LLMs, no embeddings, no vector search.
Page numbers are preserved end-to-end for future citation traceability.

### Pipeline components

| Module | Responsibility |
|--------|----------------|
| `ingestion/parser.py` | PDF parsing abstraction + PyMuPDF implementation. Swappable later for GROBID / Marker. |
| `ingestion/models.py` | Typed pydantic models (`ParsedPaper`, `PaperChunk`, ...). |
| `ingestion/chunker.py` | Deterministic section headings + fixed-size, page-safe chunking. |
| `ingestion/service.py` | Store PDF → parse → chunk → persist in one synchronous pipeline. |
| `backend/models.py` | SQLAlchemy ORM for `papers` and `chunks`. |
| `scripts/init_db.py` | Create the `papers` / `chunks` tables (idempotent). |

### 1. Install PostgreSQL 14+

- **Windows:** installer from https://www.postgresql.org/download/windows/
- **macOS (Homebrew):** `brew install postgresql@16`
- **Ubuntu/Debian:** `sudo apt install postgresql postgresql-contrib`
- **Docker:** `docker run --name litreview-pg -e POSTGRES_PASSWORD=... -p 5432:5432 -d postgres:16`

Start the service, then:

```bash
psql -U postgres -c "CREATE USER reviewer WITH PASSWORD 'your_secure_password';"
psql -U postgres -c "CREATE DATABASE literature_review_dev OWNER reviewer;"
```

### 2. Configure `.env`

```bash
cp .env.example .env
```

Fill in your PostgreSQL credentials. The important Phase 1 keys:

```dotenv
DATABASE_URL=postgresql://reviewer:password@localhost:5432/literature_review_dev
PDF_STORAGE_DIR=data/raw
MAX_UPLOAD_MB=50
```

`DATABASE_URL` must be plain `postgresql://…` — the backend normalises it to the
`postgresql+psycopg://` driver automatically.

### 3. Install Python dependencies (incl. PyMuPDF)

```bash
pip install -r requirements.txt
```

PyMuPDF is pinned in `requirements.txt` and imports as `import fitz`.

### 4. Initialise the schema

```bash
python scripts/init_db.py
```

Creates the `papers` and `chunks` tables. Safe to re-run.

### 5. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 6. Upload endpoint

| Property    | Value                                        |
|-------------|----------------------------------------------|
| Endpoint    | `POST /papers/upload`                        |
| Content type| `multipart/form-data`, field name `file`     |
| Success     | `201`                                        |

**Example request (curl):**

```bash
curl -X POST http://localhost:8000/papers/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@data/test_corpus/your_paper.pdf"
```

**Example response (201):**

```json
{
  "paper_id": 1,
  "filename": "your_paper.pdf",
  "page_count": 12,
  "chunks_created": 42,
  "status": "processed"
}
```

**Error responses:**

| Status | Meaning                                          |
|--------|--------------------------------------------------|
| 400    | Not a PDF, empty file, oversized file, bad name  |
| 422    | File is not a readable PDF (malformed/corrupt)   |
| 500    | Failed to persist to the database                |

Interactive docs: `http://localhost:8000/docs`.

### 7. Tests

```bash
# Unit tests (no database required) — includes parser, chunker,
# validation, upload endpoint (SQLite), ORM/FK tests
pytest tests/unit/ -v

# Integration tests (require running PostgreSQL)
pytest tests/integration/ -v -m integration

# Full suite
pytest -v
```

Integration tests auto-skip when PostgreSQL is unreachable. The Phase 0
connection test in `tests/integration/test_database.py` asserts a live
connection and will fail (by design) when PostgreSQL is down — it is not part
of the unit suite.

### 8. Test corpus

- `data/test_corpus/` — the *initial testing corpus* of 15–20 papers.
  It is tracked in Git and is **not** the final limit of the system.
- `data/raw/` — uploaded PDFs, git-ignored.
- `data/processed/` — reserved for processed artifacts, git-ignored.

Workflow: smoke-test with **2–3 representative PDFs** first, then run the
full 15–20 paper corpus. Unit tests use small PDFs generated programmatically
at test time — never real papers.

### Known parser limitations (Phase 1)

- Section detection is a simple, deterministic heading matcher: headings must
  appear as their own text lines and match known labels, otherwise the section
  is `Unknown`.
- Scanned/image-only PDFs (no embedded text) extract no text.
- Metadata (title/author/year) is read from the PDF file itself; when missing
  the title falls back to the filename and authors/year stay empty. No LLM is
  used to infer metadata.
- Chunking is fixed-size on character boundaries (word-boundary aware); it is
  not semantic and does not overlap.
- Real-world slightly-malformed PDFs are accepted only if they still carry a
  `%PDF` header and a `%%EOF` trailer; truncated files are rejected.
- GROBID and Marker are documented alternatives for a later phase; the
  `PDFParser` abstraction in `ingestion/parser.py` is the replacement seam.

---

## Running Tests

### Unit tests (no database required)

```bash
pytest tests/unit/ -v
```

### Integration tests (requires running PostgreSQL)

```bash
pytest tests/integration/ -v -m integration
```

### All tests

```bash
pytest -v
```

---

## Development Workflow

```
feature branch
      │
      ▼
  implement
      │
      ▼
  pytest tests/unit/
      │
      ▼
  open pull request → dev
      │
      ▼
   review + merge
      │
      ▼
  sprint review → main
```

Full branch strategy and commit conventions are documented in
`docs/git_workflow.md`.

### Quick reference

```bash
# Start new work
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name

# Commit
git add <files>
git commit -m "feat(backend): add new endpoint"

# Push and open PR
git push -u origin feature/your-feature-name
```

---

## Troubleshooting

**`DATABASE_URL is not set` on startup**
→ You have not created or activated your `.env` file.
Run `cp .env.example .env` and fill in your credentials.

**`connection refused` on `/health/db`**
→ PostgreSQL is not running, or the credentials in `.env` are wrong.
Start PostgreSQL and verify `DATABASE_URL`.

**`ModuleNotFoundError: No module named 'fastapi'`**
→ Your virtual environment is not activated.
Run `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (macOS/Linux).

**`npm: command not found`**
→ Node.js is not installed or not on your PATH.
Install Node.js 18+ from https://nodejs.org.

**Frontend shows `Backend: Error`**
→ The FastAPI backend is not running.
Start it with `uvicorn backend.main:app --reload --port 8000`.

---

## Phase Roadmap

| Phase | Name                          | Status         |
|-------|-------------------------------|----------------|
| 0     | Environment & Foundation      | ✅ Complete     |
| 1     | Research Corpus & PDF Parsing | In progress (code complete; DB verification pending) |
| 2     | Agents & Orchestration        | Not started    |
| 3     | Retrieval & Vector Search     | Not started    |
| 4     | Report Generation             | Not started    |
| 5     | Evaluation & Frontend         | Not started    |
