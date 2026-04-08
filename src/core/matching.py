import numpy as np
from sentence_transformers import SentenceTransformer


def compute_match_score(resume_text: str, jd_text: str, model: SentenceTransformer) -> int:
    """
    Compute a 0–100 match score between resume text and a job description.

    Uses cosine similarity on sentence-transformer embeddings.
    Raw similarity typically clusters in 0.2–0.8, so we rescale:
        score = clamp((raw - 0.2) / 0.6 * 100, 0, 100)
    """
    if not resume_text or not jd_text:
        return 0

    embeddings = model.encode([resume_text, jd_text])
    a, b = embeddings[0], embeddings[1]

    # Cosine similarity
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0
    raw_sim = float(dot / norm)

    # Rescale from [0.2, 0.8] → [0, 100]
    score = int((raw_sim - 0.2) / 0.6 * 100)
    return max(0, min(100, score))
