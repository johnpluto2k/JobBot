"""Lightweight text utilities: tokenization, TF-IDF cosine, keyword matching.

Pure-Python so it runs anywhere (no torch/spaCy wheels needed on new Pythons).
If sentence-transformers is installed it is used for content similarity; the
TF-IDF cosine is the always-available fallback.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.&/-]*")

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "with", "as", "at",
    "by", "is", "are", "be", "will", "you", "your", "our", "we", "their", "this", "that",
    "from", "it", "they", "have", "has", "had", "but", "not", "all", "can", "may", "who",
    "which", "what", "such", "into", "across", "within", "while", "than", "then", "also",
    "including", "etc", "ability", "able", "work", "working", "experience", "role", "team",
    "skills", "strong", "excellent", "responsibilities", "requirements", "qualifications",
    "preferred", "required", "plus", "years", "year", "degree", "candidate", "candidates",
    "join", "help", "looking", "seeking", "support", "new", "other", "more", "must",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def _tf(tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    # sublinear term frequency damps long documents
    return {t: 1.0 + math.log(c) for t, c in counts.items()}


def tfidf_cosine(text_a: str, text_b: str) -> float:
    """Cosine similarity of two texts using sublinear TF and a simple IDF over
    the two-document corpus. Returns 0..1."""
    a, b = tokenize(text_a), tokenize(text_b)
    if not a or not b:
        return 0.0
    tf_a, tf_b = _tf(a), _tf(b)
    vocab = set(tf_a) | set(tf_b)
    # idf: a term in both docs is less distinctive than one in a single doc
    idf = {t: math.log(2 / (1 + (t in tf_a) + (t in tf_b)) + 1) + 1.0 for t in vocab}
    va = {t: tf_a.get(t, 0.0) * idf[t] for t in vocab}
    vb = {t: tf_b.get(t, 0.0) * idf[t] for t in vocab}
    dot = sum(va[t] * vb[t] for t in vocab)
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def content_similarity(text_a: str, text_b: str) -> float:
    """Best-available similarity. Tries sentence-transformers, falls back to
    TF-IDF cosine."""
    try:  # optional upgrade if the heavy dep happens to be installed
        from sentence_transformers import SentenceTransformer, util

        model = _get_st_model()
        if model is not None:
            emb = model.encode([text_a, text_b], convert_to_tensor=True, normalize_embeddings=True)
            return float(util.cos_sim(emb[0], emb[1]).item())
    except Exception:
        pass
    return tfidf_cosine(text_a, text_b)


_ST_MODEL = None


def _get_st_model():  # pragma: no cover - only runs if dep present
    global _ST_MODEL
    if _ST_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer

            _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _ST_MODEL = False
    return _ST_MODEL or None


def contains_phrase(haystack_low: str, phrase: str) -> bool:
    """Word-boundary-ish containment for an alias phrase."""
    phrase = phrase.strip().lower()
    if not phrase:
        return False
    if not re.search(r"[a-z0-9]", phrase[0]):  # alias is padded (e.g. ' r ')
        return phrase in haystack_low
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", haystack_low) is not None
