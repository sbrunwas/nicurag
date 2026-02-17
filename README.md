# NICU Guidelines RAG (V1)

Clinician-facing RAG system for NICU guidelines with:
- Streamlit Q&A UI
- Postgres + pgvector persistence
- Incremental ingestion from a recursive public Google Drive folder
- Selective OCR for low-text pages/slides
- Weekly + manual ingestion via GitHub Actions

## 1) Environment variables

Required:
- `DATABASE_URL`
- `OPENAI_API_KEY`

Optional:
- `DRIVE_PUBLIC_FOLDER_ID` (defaults to `1R6BzZ2UVA9ZECmHOwZFxyh3B7m7RYTmZ`)
- `INGEST_SINCE_DAYS` (default `8`)
- `EMBEDDING_DIM` (default `1536`)

## 2) Database initialization

```bash
python -c "from db.client import init_db; init_db()"
```

This initializes tables and indexes from `db/schema.sql`, substituting `__EMBEDDING_DIM__` using `EMBEDDING_DIM`.

## 3) Local ingestion

Install dependencies:

```bash
pip install -r requirements.txt
```

Run ingestion:

```bash
python -m ingest.ingest_runner --since-days 8
```

Useful flags:
- `--force-all`
- `--force-file-id <drive_file_id>`
- `--since-days <N>`

## 4) Run Streamlit locally

```bash
streamlit run app/streamlit_app.py
```

## Notes / TODOs

- `ingest/drive_sync.py` uses a public web scraping adapter for Drive listing/downloading.
  - TODO: replace with official Drive API adapter in V2.
- OCR is intentionally selective; current image heuristics are size-based only.
  - TODO: add better OCR candidate ranking and image pre-processing.
