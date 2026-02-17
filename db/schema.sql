CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  drive_file_id TEXT PRIMARY KEY,
  name TEXT,
  mime_type TEXT,
  folder_path TEXT,
  modified_time TIMESTAMPTZ,
  content_hash TEXT NULL,
  status TEXT CHECK (status IN ('indexed','failed','partial')),
  last_ingested_at TIMESTAMPTZ,
  error TEXT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id UUID PRIMARY KEY,
  drive_file_id TEXT REFERENCES documents(drive_file_id) ON DELETE CASCADE,
  doc_title TEXT,
  folder_path TEXT,
  doc_modified_time TIMESTAMPTZ,
  doc_url TEXT,
  source_type TEXT CHECK (source_type IN ('ppt_slide','pdf_page')),
  page_or_slide INT,
  text_origin TEXT CHECK (text_origin IN ('native_text','ocr')),
  text TEXT,
  embedding VECTOR(__EMBEDDING_DIM__),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_drive_file_id ON chunks(drive_file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_folder_path ON chunks(folder_path);
CREATE INDEX IF NOT EXISTS idx_documents_folder_path ON documents(folder_path);

-- Requires ANALYZE after substantial inserts.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat
ON chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
