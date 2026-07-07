import re

_SPLIT_CANDIDATE_RE = re.compile(r"[.!?]\s+(?=[A-ZА-Я0-9])")

_ABBREVIATIONS = {
    "vol", "no", "p", "pp", "fig", "figs", "eq", "eqs", "cf",
    "dr", "mr", "mrs", "ms", "prof", "st", "jr", "sr",
    "e.g", "i.e", "etc", "et al", "approx",
}


def split_sentences(text: str) -> list[str]:
    """Lightweight regex sentence splitter (no nltk download needed).

    Skips split points where the word before the punctuation is a known
    abbreviation (vol., no., pp., ...) so citations like "vol. 276, no. 4"
    stay in one sentence instead of being torn apart.
    """
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []

    sentences: list[str] = []
    start = 0
    for m in _SPLIT_CANDIDATE_RE.finditer(text):
        split_pos = m.end()
        prev_word = text[start:m.start() + 1].rsplit(None, 1)[-1].rstrip(".!?").lower()
        if prev_word in _ABBREVIATIONS:
            continue
        sentences.append(text[start:split_pos].strip())
        start = split_pos
    sentences.append(text[start:].strip())
    return [s for s in sentences if s]


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
