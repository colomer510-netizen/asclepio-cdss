import os
import asyncio
import re
from uuid import UUID
import asyncpg
from pgvector.asyncpg import register_vector
from sentence_transformers import SentenceTransformer

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "paraphrase-multilingual-mpnet-base-v2")
DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/asclepio_cdss")


class MedicalLiteratureIngestor:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        print(f"[*] Cargando modelo de vectorización: {model_name}...")
        self.embedder = SentenceTransformer(model_name)

    @staticmethod
    def detect_chapter(page_text: str, current_chapter: str) -> str:
        lines = [line.strip() for line in page_text.split("\n") if line.strip()]
        for line in lines[:5]:
            if re.match(r"^(CAPÍTULO|CAPITULO|SECCIÓN|PROTOCOLO|PARTE)\s+\d+", line, re.IGNORECASE):
                return line[:200]
        return current_chapter

    @staticmethod
    def chunk_page_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
        clean_text = re.sub(r"\s+", " ", text).strip()
        if not clean_text:
            return []
        
        chunks = []
        start = 0
        text_length = len(clean_text)
        
        while start < text_length:
            end = min(start + max_chars, text_length)
            if end < text_length:
                last_period = clean_text.rfind(". ", start, end)
                if last_period != -1 and (last_period - start) > (max_chars // 2):
                    end = last_period + 1
            
            chunks.append(clean_text[start:end].strip())
            if end == text_length:
                break
            start = max(0, end - overlap)
            
        return chunks

    async def ingest_pdf(
        self,
        pool: asyncpg.Pool,
        pdf_path: str,
        title: str,
        authors: list[str],
        publication_year: int,
        branch: str,  # 'convencional_alopatica', 'natural_fitoterapia', 'protocolo_enfermeria', 'investigacion_clinica'
        isbn_or_doi: str,
        evidence_level: str,
        source_institution: str,
    ) -> UUID:
        if fitz is None:
            raise RuntimeError("PyMuPDF (pymupdf) no está instalado. Ejecute: pip install pymupdf")

        doc_pdf = fitz.open(pdf_path)
        current_chapter = "Introducción / General"
        chunks_to_insert = []

        async with pool.acquire() as conn, conn.transaction():
            document_id: UUID = await conn.fetchval(
                """
                INSERT INTO medical_literature (
                    title, authors, publication_year, branch, 
                    isbn_or_doi, evidence_level, source_institution
                )
                VALUES ($1, $2, $3, $4::medicine_branch, $5, $6, $7)
                ON CONFLICT (isbn_or_doi) DO UPDATE SET title = EXCLUDED.title
                RETURNING document_id;
                """,
                title, authors, publication_year, branch,
                isbn_or_doi, evidence_level, source_institution
            )

            print(f"[*] Procesando '{title}' (ID: {document_id}) - {len(doc_pdf)} páginas...")

            for page_index in range(len(doc_pdf)):
                page = doc_pdf[page_index]
                page_number = page_index + 1
                raw_text = page.get_text("text")
                
                current_chapter = self.detect_chapter(raw_text, current_chapter)
                page_chunks = self.chunk_page_text(raw_text)

                for idx, chunk_text in enumerate(page_chunks):
                    section_ref = f"Pág. {page_number} - Frag. {idx + 1}"
                    chunks_to_insert.append(
                        (document_id, current_chapter, page_number, section_ref, chunk_text)
                    )

            texts_only = [item[4] for item in chunks_to_insert]
            print(f"[*] Generando embeddings para {len(texts_only)} fragmentos...")
            embeddings = self.embedder.encode(texts_only, normalize_embeddings=True, show_progress_bar=True)

            records_with_vectors = [
                (
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                    embeddings[i].tolist(),
                )
                for i, item in enumerate(chunks_to_insert)
            ]

            await conn.executemany(
                """
                INSERT INTO literature_chunks (
                    document_id, chapter_title, page_number, 
                    section_reference, content_text, embedding
                )
                VALUES ($1, $2, $3, $4, $5, $6);
                """,
                records_with_vectors,
            )

        doc_pdf.close()
        print(f"[✔] Ingesta completada con éxito: {len(records_with_vectors)} fragmentos indexados.")
        return document_id


async def main():
    pool = await asyncpg.create_pool(DB_DSN, init=register_vector)
    _ingestor = MedicalLiteratureIngestor()
    print("[✔] Ingestor de literatura médica listo.")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
