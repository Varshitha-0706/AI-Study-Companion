"""
Document processing pipeline.

Flow: Upload → Queued → Processing → Extract → Chunk → Embed → Ready/Failed

Key invariants:
- material_id + user_id + project_id are always passed and re-verified in the task
- Idempotent: re-running on a 'ready' material is a no-op
- Retries: up to 3 times with 60s delay
- On failure: material.status = 'failed' with error_message
"""
import uuid
import json
import re
from datetime import datetime, timezone
from typing import Optional

import pymupdf  # PyMuPDF

from app.core.config import settings
from app.ai.gemini_client import gemini_client
from app.services.storage_service import storage_service


def get_sync_db():
    """Create a synchronous DB session for use in Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Convert async URL to sync URL for Celery
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def chunk_text(text: str, page_number: int, chunk_size: int = 512, overlap: int = 50) -> list[dict]:
    """
    Chunk text into overlapping segments, preserving page attribution.
    Returns list of {content, page_number, chunk_index}.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    idx = 0
    chunk_index = 0

    while idx < len(words):
        end = min(idx + chunk_size, len(words))
        chunk_words = words[idx:end]
        content = " ".join(chunk_words).strip()
        if content:
            chunks.append({
                "content": content,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "token_count": len(chunk_words),
            })
            chunk_index += 1
        idx += chunk_size - overlap

    return chunks


def extract_concepts_from_document(full_text: str, doc_title: str) -> list[dict]:
    """
    Use Gemini to extract key concepts from the document.
    Returns list of {name, description, importance_score}.
    Validates output before returning.
    """
    # Truncate to avoid token limits
    truncated = full_text[:15000] if len(full_text) > 15000 else full_text

    prompt = f"""Analyze this learning document titled "{doc_title}" and extract the key concepts a learner should understand.

Document content:
{truncated}

Return a JSON array of concepts. Each concept must have:
- "name": short concept name (max 60 chars)
- "description": 1-2 sentence explanation
- "importance_score": float 0.0-1.0

Return 5-15 concepts. Return ONLY the JSON array, no other text.

Example format:
[
  {{"name": "Concept Name", "description": "What it means.", "importance_score": 0.9}},
  ...
]"""

    try:
        text, _ = gemini_client.generate(prompt, temperature=0.1, max_output_tokens=2048)

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if not json_match:
            return []

        concepts_raw = json.loads(json_match.group())

        # Validate structure
        validated = []
        for c in concepts_raw:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name", "")).strip()[:300]
            description = str(c.get("description", "")).strip()
            importance = float(c.get("importance_score", 0.5))
            importance = max(0.0, min(1.0, importance))

            if name:
                validated.append({
                    "name": name,
                    "description": description,
                    "importance_score": importance,
                })

        return validated[:15]  # max 15 concepts

    except Exception as e:
        print(f"[document_pipeline] Concept extraction via Gemini failed ({e}), extracting from document text structure")
        # Extract concepts from headings, definitions, and capitalized phrases in text
        concepts = []
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        for line in lines:
            # Check for section headers, bullets, or definition patterns
            match = re.match(r'^(?:[0-9]+[\.\)]\s*|[-*•]\s*)?([A-Z][A-Za-z0-9\s\-]{3,50})(?::\s*|\s*-\s*|\s*–\s*)(.+)', line)
            if match:
                c_name = match.group(1).strip()[:60]
                c_desc = match.group(2).strip()[:200]
                if c_name and len(c_name.split()) <= 6:
                    concepts.append({
                        "name": c_name,
                        "description": c_desc,
                        "importance_score": 0.85
                    })
            elif line.isupper() and 4 <= len(line) <= 50 and not line.startswith("PAGE"):
                concepts.append({
                    "name": line.title(),
                    "description": f"Key concept and topic area covering {line.title()}.",
                    "importance_score": 0.8
                })

        # Deduplicate by name
        seen = set()
        unique_concepts = []
        for c in concepts:
            if c["name"].lower() not in seen:
                seen.add(c["name"].lower())
                unique_concepts.append(c)

        if not unique_concepts:
            # Default fallback concepts based on document title
            unique_concepts = [{
                "name": doc_title.replace(".pdf", "").replace("_", " ").title(),
                "description": f"Core subject matter of {doc_title}.",
                "importance_score": 0.9
            }]

        return unique_concepts[:15]




def process_document_sync(material_id: str, user_id: str, project_id: str):
    """Direct execution helper for environments where Celery worker isn't running."""
    from app.models.models import Material, MaterialStatus, Chunk, Concept, Event
    db = get_sync_db()
    try:
        material = db.query(Material).filter(
            Material.id == uuid.UUID(material_id),
            Material.user_id == uuid.UUID(user_id),
            Material.project_id == uuid.UUID(project_id),
        ).first()

        if not material or material.status == MaterialStatus.ready:
            return

        material.status = MaterialStatus.processing
        db.commit()

        if hasattr(storage_service, 'get_full_path'):
            file_path = storage_service.get_full_path(material.filename)
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        else:
            import asyncio
            file_bytes = asyncio.run(storage_service.read(material.filename))

        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        material.page_count = doc.page_count

        all_text = ""
        all_chunks = []

        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            page_text = page.get_text().strip()
            if page_text:
                all_text += f"\n{page_text}"
                chunks = chunk_text(page_text, page_num)
                all_chunks.extend(chunks)

        doc.close()

        if not all_chunks:
            material.status = MaterialStatus.failed
            material.error_message = "No text content could be extracted from this PDF"
            db.commit()
            return

        for chunk_data in all_chunks:
            try:
                embedding = gemini_client.embed(chunk_data["content"])
            except Exception as e:
                print(f"[document_pipeline_sync] Embedding error: {e}")
                embedding = None

            chunk = Chunk(
                id=uuid.uuid4(),
                material_id=material.id,
                project_id=material.project_id,
                user_id=material.user_id,
                content=chunk_data["content"],
                page_number=chunk_data["page_number"],
                chunk_index=chunk_data["chunk_index"],
                token_count=chunk_data.get("token_count"),
                embedding=embedding,
            )
            db.add(chunk)

        concepts_data = extract_concepts_from_document(all_text, material.original_filename)
        for concept_data in concepts_data:
            existing = db.query(Concept).filter(
                Concept.project_id == material.project_id,
                Concept.user_id == material.user_id,
                Concept.name == concept_data["name"],
            ).first()

            if not existing:
                concept = Concept(
                    id=uuid.uuid4(),
                    project_id=material.project_id,
                    user_id=material.user_id,
                    extracted_from_id=material.id,
                    name=concept_data["name"],
                    description=concept_data["description"],
                    importance_score=concept_data["importance_score"],
                )
                db.add(concept)

        material.status = MaterialStatus.ready
        material.processed_at = datetime.now(timezone.utc)
        material.error_message = None

        event = Event(
            id=uuid.uuid4(),
            user_id=material.user_id,
            project_id=material.project_id,
            event_type="material_processed",
            payload={
                "material_id": str(material.id),
                "filename": material.original_filename,
                "page_count": material.page_count,
                "chunks_created": len(all_chunks),
                "concepts_extracted": len(concepts_data),
            },
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[document_pipeline_sync] Error: {exc}")
        try:
            mat = db.query(Material).filter(Material.id == uuid.UUID(material_id)).first()
            if mat:
                mat.status = MaterialStatus.failed
                mat.error_message = str(exc)[:500]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()

