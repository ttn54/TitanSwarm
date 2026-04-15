import re
import numpy as np
from sentence_transformers import SentenceTransformer

# Tokens shorter than this are treated as stop-words and ignored in keyword matching
_MIN_TOKEN_LEN = 3


def _keyword_overlap_score(resume_text: str, jd_text: str) -> int:
    """
    Extract alphanumeric tokens (≥3 chars) from the JD and compute
    what fraction of them appear in the resume.
    Returns 0–100.
    """
    def _tokens(text: str) -> set[str]:
        return {t.lower() for t in re.findall(r'[A-Za-z0-9#+]+', text) if len(t) >= _MIN_TOKEN_LEN}

    jd_tokens = _tokens(jd_text)
    if not jd_tokens:
        return 0
    resume_tokens = _tokens(resume_text)
    overlap = len(jd_tokens & resume_tokens)
    return int(overlap / len(jd_tokens) * 100)


def compute_match_score(resume_text: str, jd_text: str, model: SentenceTransformer) -> int:
    """
    Hybrid 0–100 match score:
        50% semantic cosine similarity (sentence-transformer embeddings)
        50% keyword overlap (fraction of JD tokens present in resume)

    Semantic component rescales raw cosine from [0.2, 0.8] → [0, 100].
    """
    if not resume_text or not jd_text:
        return 0

    # ── Semantic component ──────────────────────────────────────────────────
    embeddings = model.encode([resume_text, jd_text])
    a, b = embeddings[0], embeddings[1]
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    raw_sim = float(dot / norm) if norm > 0 else 0.0
    semantic_score = int((raw_sim - 0.2) / 0.6 * 100)
    semantic_score = max(0, min(100, semantic_score))

    # ── Keyword overlap component ───────────────────────────────────────────
    kw_score = _keyword_overlap_score(resume_text, jd_text)

    # ── Hybrid ─────────────────────────────────────────────────────────────
    score = int(0.5 * semantic_score + 0.5 * kw_score)
    return max(0, min(100, score))
