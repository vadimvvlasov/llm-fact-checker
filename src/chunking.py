import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-Я0-9])")


def split_sentences(text: str) -> list[str]:
    """Lightweight regex sentence splitter (no nltk download needed)."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def chunk_text(text: str, sentences_per_chunk: int = 4, overlap: int = 1) -> list[str]:
    """Sentence-level chunking with a sliding window and overlap."""
    sentences = split_sentences(text)
    if not sentences:
        return []

    step = max(sentences_per_chunk - overlap, 1)
    chunks = []
    for start in range(0, len(sentences), step):
        window = sentences[start : start + sentences_per_chunk]
        if not window:
            continue
        chunks.append(" ".join(window))
        if start + sentences_per_chunk >= len(sentences):
            break
    return chunks
