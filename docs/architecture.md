# Architecture — Automated Literature Review

> **Current Phase: 1 — Research Corpus & PDF Processing**
> Components marked *[Phase N]* are not yet implemented.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Developer Laptop                                               │
│                                                                 │
│  ┌──────────────┐        ┌──────────────────────────────────┐  │
│  │  Browser     │        │  Python Virtual Environment      │  │
│  │  :3000       │◄──────►│                                  │  │
│  └──────────────┘        │  ┌────────────┐                  │  │
│                          │  │  Next.js   │  :3000           │  │
│                          │  │  Frontend  │                  │  │
│                          │  └─────┬──────┘                  │  │
│                          │        │ HTTP / REST              │  │
│                          │  ┌─────▼──────┐                  │  │
│                          │  │  FastAPI   │  :8000           │  │
│                          │  │  Backend   │                  │  │
│                          │  └─────┬──────┘                  │  │
│                          │        │                          │  │
│                          │  ┌─────▼──────────────────────┐  │  │
│                          │  │  LangGraph Orchestrator     │  │  │
│                          │  │  [Phase 2]                  │  │  │
│                          │  └─────┬──────────────────────-┘  │  │
│                          │        │                           │  │
│                          │  ┌─────▼──────────────────────┐   │  │
│                          │  │  Specialized Agents         │   │  │
│                          │  │  [Phase 2]                  │   │  │
│                          │  │                             │   │  │
│                          │  │  PDF Parser                 │   │  │
│                          │  │  Summarizer                 │   │  │
│                          │  │  Comparator                 │   │  │
│                          │  │  Gap Identifier             │   │  │
│                          │  │  Citation Verifier          │   │  │
│                          │  └─────┬───────────────────────┘   │  │
│                          │        │                            │  │
│                          │  ┌─────▼──────────────────────┐    │  │
│                          │  │  PostgreSQL + pgvector      │    │  │
│                          │  │  literature_review_dev      │    │  │
│                          │  └────────────────────────────┘    │  │
│                          └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Detail

### Frontend — Next.js 14

| Property     | Value                         |
|--------------|-------------------------------|
| Framework    | Next.js 14 (App Router)       |
| Language     | TypeScript                    |
| Port         | 3000                          |
| Phase 0 UI   | Health-check status display   |

**Phase 0 scope:** Minimal status page that polls `/health` and `/health/db`
every 15 seconds and displays connection state.

**Future phases will add:**
- PDF upload and corpus management UI
- Per-paper summary view
- Multi-paper comparison table
- Research gap display
- Downloadable report interface

**Environment variable:**
```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

### Backend — FastAPI

| Property    | Value                          |
|-------------|--------------------------------|
| Framework   | FastAPI 0.109+                 |
| Server      | Uvicorn with reload            |
| Language    | Python 3.11+                   |
| Port        | 8000                           |

**Phase 0 endpoints:**

| Route         | Method | Description               |
|---------------|--------|---------------------------|
| `/health`     | GET    | Backend liveness check    |
| `/health/db`  | GET    | Database connectivity     |
| `/docs`       | GET    | Swagger UI                |
| `/redoc`      | GET    | ReDoc UI                  |

**Phase 1 endpoint (implemented):**

| Route            | Method | Description                            |
|------------------|--------|----------------------------------------|
| `/papers/upload` | POST   | PDF ingestion → papers + chunks rows   |

**CORS:** Configured for development to allow `localhost:3000`.
Production CORS must be explicitly restricted before deployment.

**Future phases will add:**
- `GET /papers/{id}/summary` — Paper summary retrieval
- `POST /analysis/compare` — Multi-paper comparison
- `GET /analysis/gaps` — Research gap identification
- `POST /reports/generate` — Report export

---

## Ingestion Pipeline — [Phase 1]

```
PDF bytes
   │  POST /papers/upload (backend/api/papers.py)
   ▼
Validate (PDF-only, size, safe filename) ──400 on failure
   ▼
store_pdf() → data/raw/{uuid}_{safe}.pdf
   ▼
ingestion/parser.py  PyMuPDFParser (import fitz)
   ├── page_count + per-page text (page numbers preserved)
   └── PDF metadata (title / author / year)
   ▼
ingestion/chunker.py  SectionChunker
   ├── deterministic section headings (or "Unknown")
   └── fixed-size, page-safe chunks (word-boundary aligned)
   ▼
ingestion/service.py  persist_paper()
   ▼
PostgreSQL  papers + chunks rows   (created by scripts/init_db.py)
```

Design notes:
- The parser is behind the `PDFParser` protocol in `ingestion/parser.py` so it
  can be swapped for GROBID / Marker in a later phase without touching the rest
  of the pipeline.
- Processing is synchronous in Phase 1; `IngestionService.ingest` is the seam
  for a future job queue.
- No LLM, embeddings, or vector retrieval are part of Phase 1.

---

### LangGraph Orchestrator — [Phase 2]

LangGraph manages the multi-agent workflow as a directed graph.

Planned graph topology:

```
Upload PDF
    │
    ▼
PDF Parser Node ──────────────────────────────┐
    │                                         │
    ▼                                         │
Chunker / Embedder Node                       │
    │                                         │
    ▼                                         │
Summarization Node                            │
    │                                         │
    ▼                                         ▼
Comparison Node ◄──── (multi-paper input) ────┘
    │
    ▼
Gap Identification Node
    │
    ▼
Citation Verification Node
    │
    ▼
Report Generation Node
```

Each node is an independent Python class with:
- A defined input schema (Pydantic model)
- A defined output schema (Pydantic model)
- Unit-testable logic isolated from the graph

---

### Specialized Agents — [Phase 2]

| Agent                  | Responsibility                                   |
|------------------------|--------------------------------------------------|
| PDF Parser             | Extract text, sections, figures, references      |
| Summarizer             | Generate per-paper structured summaries          |
| Comparator             | Identify similarities and differences            |
| Gap Identifier         | Surface unstudied areas and open questions       |
| Citation Verifier      | Validate cited papers exist and are accurate     |
| Report Generator       | Produce a structured literature review document  |

All agents will be implemented under `agents/`.

---

### Database — PostgreSQL + pgvector

| Property      | Value                              |
|---------------|------------------------------------|
| Database      | PostgreSQL 14+                     |
| Extension     | pgvector 0.5+ (optional Phase 0)   |
| Dev database  | `literature_review_dev`            |
| ORM           | SQLAlchemy 2.0                     |
| Connection    | Managed via `DATABASE_URL` env var |

**Phase 0:** Connection verified. No application schema existed yet.

**Phase 1 (implemented):**
- `papers` table — metadata (title, authors, year, doi, source_url) +
  storage reference (filename, storage_path) + page_count, extracted_at
- `chunks` table — page-aware text chunks (paper_id FK, page_number, section,
  chunk_index, text) for evidence / citation traceability

**Phase 3 (retrieval) will add:**
- `embeddings` table — vector columns using pgvector
- Similarity search functions

#### papers table (Phase 1)

| Column        | Type         | Notes                                  |
|---------------|--------------|----------------------------------------|
| id            | INTEGER PK   | Autoincrement                          |
| title         | VARCHAR(512) | Falls back to filename when missing    |
| authors       | JSON         | List of author names (nullable)        |
| year          | INTEGER      | From PDF creation date (nullable)      |
| doi           | VARCHAR(512) | Nullable                               |
| source_url    | VARCHAR(1024)| Nullable                               |
| filename      | VARCHAR(512) | Original upload name (sanitised)       |
| storage_path  | VARCHAR(1024)| data/raw/{uuid}_{safe}.pdf              |
| page_count    | INTEGER      | Nullable                               |
| extracted_at  | TIMESTAMP    | When the PDF was parsed                |
| created_at    | TIMESTAMP    | Default now                            |
| updated_at    | TIMESTAMP    | Auto-updates on change                 |

#### chunks table (Phase 1)

| Column       | Type         | Notes                                  |
|--------------|--------------|----------------------------------------|
| id           | INTEGER PK   | Autoincrement                          |
| paper_id     | INTEGER FK   | → papers.id, ON DELETE CASCADE         |
| page_number  | INTEGER      | 1-based source page (traceability)     |
| section      | VARCHAR(128) | Detected section or `Unknown`          |
| chunk_index  | INTEGER      | Zero-based deterministic order         |
| text         | TEXT         | Chunk body (no source text lost)       |
| created_at   | TIMESTAMP    | Default now                            |

The schema is created via `scripts/init_db.py` (idempotent) and never at
application import time, preserving the lazy database behaviour.

#### pgvector

pgvector enables vector similarity search required for semantic retrieval.

To install pgvector on PostgreSQL:

```sql
-- Inside your database:
CREATE EXTENSION IF NOT EXISTS vector;
```

If pgvector is unavailable in Phase 0, the project continues without it.
The extension is required only when embedding generation is introduced in Phase 3.

**Installation guides:**
- Docker: use `pgvector/pgvector` image
- Ubuntu/Debian: `apt install postgresql-14-pgvector`
- macOS (Homebrew): `brew install pgvector`
- Windows: Build from source or use Docker

---

## Data Flow — Full Pipeline (Future)

```
Researcher uploads PDF
        │
        ▼
FastAPI receives file
        │
        ▼
PDF Parser Agent
  └── Extract raw text
  └── Detect sections (Abstract, Methods, Results, etc.)
  └── Extract bibliography
        │
        ▼
Chunker / Embedder
  └── Split into overlapping chunks
  └── Generate embeddings via LLM
  └── Store in PostgreSQL (pgvector)
        │
        ▼
Summarization Agent
  └── Generate structured per-section summaries
  └── Store in PostgreSQL
        │
        ▼
(Repeat for each paper)
        │
        ▼
Comparison Agent
  └── Cross-paper theme analysis
  └── Methodology comparison
        │
        ▼
Gap Identification Agent
  └── Surface unstudied areas
  └── Identify conflicting findings
        │
        ▼
Citation Verifier
  └── Validate references
  └── Flag missing or incorrect citations
        │
        ▼
Report Generator
  └── Produce structured Markdown/PDF report
        │
        ▼
FastAPI returns report to frontend
        │
        ▼
User downloads / views report
```

---

## Environment Variables Reference

| Variable                  | Required | Description                            |
|---------------------------|----------|----------------------------------------|
| `APP_ENV`                 | Yes      | `development` or `production`          |
| `BACKEND_PORT`            | Yes      | FastAPI server port (default: 8000)    |
| `BACKEND_URL`             | No       | Full backend URL for scripts           |
| `FRONTEND_PORT`           | No       | Next.js port (default: 3000)           |
| `FRONTEND_URL`            | No       | Full frontend URL for CORS config      |
| `DATABASE_URL`            | Yes      | PostgreSQL connection string           |
| `DB_HOST`                 | Yes      | PostgreSQL host                        |
| `DB_PORT`                 | Yes      | PostgreSQL port (default: 5432)        |
| `DB_NAME`                 | Yes      | Database name                          |
| `DB_USER`                 | Yes      | Database user                          |
| `DB_PASSWORD`             | Yes      | Database password                      |
| `NEXT_PUBLIC_BACKEND_URL` | No       | Backend URL exposed to browser         |
| `PGVECTOR_ENABLED`        | No       | Set to `true` when pgvector available  |
| `PDF_STORAGE_DIR`         | No       | Upload directory (default: `data/raw`) |
| `MAX_UPLOAD_MB`           | No       | Max upload size in MB (default: 50)    |
| `OPENAI_API_KEY`          | Phase 2  | LLM API key                            |
| `LLM_MODEL`               | Phase 2  | Model identifier (e.g., `gpt-4`)       |

---

## Security Notes

- Never commit `.env` — it is excluded via `.gitignore`
- Never commit `frontend/.env.local` — also excluded
- All secrets must be passed via environment variables
- CORS is permissive in development; must be restricted for production
- LLM API keys belong in `.env` only — never in source code
