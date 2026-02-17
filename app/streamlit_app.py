from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

import streamlit as st
from openai import OpenAI

# Ensure repo-root imports (e.g., db.client) work in Streamlit cloud/runtime
# where the script can be executed with app/ as the working directory.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db.client import get_conn, get_embedding_dim


@st.cache_resource
def openai_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is required")
    return OpenAI(api_key=key)


def embed_query(query: str) -> list[float]:
    response = openai_client().embeddings.create(model="text-embedding-3-small", input=[query])
    return response.data[0].embedding


def fetch_folder_prefixes() -> list[str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT folder_path FROM chunks WHERE folder_path IS NOT NULL AND folder_path <> ''")
            rows = [row[0] for row in cur.fetchall()]
    prefixes = set()
    for path in rows:
        current = []
        for part in path.split("/"):
            current.append(part)
            prefixes.add("/".join(current))
    return sorted(prefixes)


def retrieval(query_embedding: list[float], top_k: int, folder_filter: str | None):
    where = ""
    params = [query_embedding, top_k]
    if folder_filter:
        where = "WHERE folder_path = %s OR folder_path LIKE %s"
        params = [query_embedding, folder_filter, f"{folder_filter}/%", top_k]

    sql = f"""
        SELECT doc_title, folder_path, doc_modified_time, doc_url, source_type,
               page_or_slide, text_origin, text,
               (embedding <=> %s::vector) AS distance
        FROM chunks
        {where}
        ORDER BY distance
        LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return rows


def status_summary() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(last_ingested_at), COUNT(*) FILTER (WHERE status='indexed'), COUNT(*) FILTER (WHERE status='failed') FROM documents")
            row = cur.fetchone()
    return {
        "last_ingest": row[0],
        "indexed": row[1],
        "failed": row[2],
    }


def build_context(rows) -> str:
    blocks = []
    for i, row in enumerate(rows, start=1):
        doc_title, folder_path, modified_time, doc_url, source_type, page_or_slide, text_origin, text, _ = row
        blocks.append(
            f"[Source {i}]\n"
            f"Title: {doc_title}\n"
            f"Location: {source_type} {page_or_slide}\n"
            f"Folder: {folder_path}\n"
            f"Last Updated: {modified_time}\n"
            f"URL: {doc_url}\n"
            f"Text Origin: {text_origin}\n"
            f"Content:\n{text}\n"
        )
    return "\n".join(blocks)


def generate_answer(question: str, context: str) -> str:
    system_prompt = (
        "You are a NICU guideline assistant. Use only the retrieved context. "
        "Cite sources inline using [Source X]. "
        "If context is insufficient, say you are uncertain and recommend checking the source guideline."
    )
    response = openai_client().chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"},
        ],
    )
    return response.choices[0].message.content or "No answer generated."


def main() -> None:
    st.set_page_config(page_title="NICU Guidelines Assistant", layout="wide")
    st.title("NICU Guidelines RAG Assistant")
    st.warning("May be incorrect — verify in the linked guideline before acting.")

    with st.sidebar:
        st.header("Filters & Status")
        folders = fetch_folder_prefixes()
        folder_filter = st.selectbox("Folder filter", options=[""] + folders, format_func=lambda x: x or "All folders")
        show_context = st.toggle("Show retrieved context", value=False)
        top_k = st.slider("Top-k chunks", min_value=3, max_value=15, value=6)

        summary = status_summary()
        st.caption(f"Last ingestion: {summary['last_ingest']}")
        st.caption(f"Indexed documents: {summary['indexed']}")
        st.caption(f"Failed documents: {summary['failed']}")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask a NICU guideline question...")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving guidelines..."):
            query_emb = embed_query(question)
            rows = retrieval(query_emb, top_k=top_k, folder_filter=folder_filter or None)
            context = build_context(rows)
            answer = generate_answer(question, context)

        st.markdown(answer)
        st.subheader("Sources used")
        grouped = defaultdict(list)
        for row in rows:
            grouped[row[0]].append(row)

        for title, doc_rows in grouped.items():
            first = doc_rows[0]
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.markdown(f"- Slide/Page: {', '.join(str(r[5]) for r in doc_rows)}")
                st.markdown(f"- Folder path: {first[1]}")
                st.markdown(f"- Last updated: {first[2]}")
                st.markdown(f"- Text origin: {', '.join(sorted(set(r[6] for r in doc_rows)))}")
                st.link_button("Open source guideline", first[3])

        if show_context:
            with st.expander("Show retrieved context"):
                st.code(context)

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    # Side-effect call so import failures appear early for misconfigured embeddings.
    _ = get_embedding_dim()
    main()
