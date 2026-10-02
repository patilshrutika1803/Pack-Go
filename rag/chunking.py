from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    source: str
    filename: str
    document_id: str


@dataclass(frozen=True)
class TextChunk:
    text: str
    page: int
    chunk_index: int
    source: str
    filename: str
    document_id: str


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and chunk_overlap must be smaller than chunk_size")
    text = " ".join(text.split())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - chunk_overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def chunk_pages(pages: list[PageText], chunk_size: int = 500, chunk_overlap: int = 60) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for page in pages:
        for text in _split_text(page.text, chunk_size, chunk_overlap):
            chunks.append(TextChunk(text, page.page, len(chunks), page.source, page.filename, page.document_id))
    return chunks