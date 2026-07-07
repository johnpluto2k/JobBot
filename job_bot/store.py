"""Vector store for semantic querying of the profile.

ChromaDB is optional: if it (or a compatible Python version) isn't available,
storage is skipped with a warning so the rest of the pipeline still runs.
"""

from __future__ import annotations

from . import config
from .models import MasterProfile


def _profile_chunks(profile: MasterProfile) -> list[tuple[str, str, dict]]:
    """Flatten the profile into (id, text, metadata) chunks for embedding."""
    chunks: list[tuple[str, str, dict]] = []

    for i, exp in enumerate(profile.experience):
        head = f"{exp.role or ''} at {exp.organization or ''}".strip()
        for j, b in enumerate(exp.bullets):
            chunks.append((f"exp-{i}-{j}", f"{head}: {b.text}",
                           {"section": "experience", "org": exp.organization or "",
                            "tags": ", ".join(b.keyword_tags)}))

    for i, lead in enumerate(profile.leadership):
        head = f"{lead.role or ''} at {lead.organization or ''}".strip()
        for j, b in enumerate(lead.bullets):
            chunks.append((f"lead-{i}-{j}", f"{head}: {b.text}",
                           {"section": "leadership", "org": lead.organization or ""}))

    for i, proj in enumerate(profile.projects):
        body = proj.description or ""
        body += " " + " ".join(b.text for b in proj.bullets)
        chunks.append((f"proj-{i}", f"{proj.name}: {body}".strip(),
                       {"section": "projects", "tech": ", ".join(proj.technologies)}))

    for i, edu in enumerate(profile.education):
        chunks.append((f"edu-{i}",
                       f"{edu.degree or ''} {edu.major or ''} at {edu.school or ''}. "
                       f"Coursework: {', '.join(edu.relevant_coursework)}",
                       {"section": "education"}))

    for i, sk in enumerate(profile.skills):
        chunks.append((f"skill-{i}", f"{sk.category} skills: {', '.join(sk.skills)}",
                       {"section": "skills", "category": sk.category}))

    return chunks


def store_profile(profile: MasterProfile) -> bool:
    """Embed profile chunks into a local ChromaDB collection. Returns success."""
    try:
        import chromadb
    except Exception as exc:
        print(f"  ! ChromaDB unavailable ({exc}); skipping vector store")
        return False

    chunks = _profile_chunks(profile)
    if not chunks:
        print("  ! no chunks to store")
        return False

    config.ensure_dirs()
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    collection = client.get_or_create_collection("master_profile")
    ids = [c[0] for c in chunks]
    # Replace existing ids to keep the store idempotent across runs.
    try:
        collection.delete(ids=ids)
    except Exception:
        pass
    collection.add(
        ids=ids,
        documents=[c[1] for c in chunks],
        metadatas=[c[2] for c in chunks],
    )
    print(f"  stored {len(chunks)} chunks in ChromaDB at {config.CHROMA_DIR}")
    return True


def query(text: str, n: int = 5):  # pragma: no cover - convenience helper
    import chromadb

    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    collection = client.get_or_create_collection("master_profile")
    return collection.query(query_texts=[text], n_results=n)
