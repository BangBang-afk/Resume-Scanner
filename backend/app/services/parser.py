"""Resume bytes -> text + parse_quality. Stdlib-first, optional deps."""
from __future__ import annotations


def _quality_for_text(text: str) -> float:
    if not text or not text.strip():
        return 0.2
    stripped = text.strip()
    if len(stripped) < 50:
        return 0.4
    # garbled heuristic: very low whitespace ratio means binary/garbled
    spaces = text.count(" ")
    if len(text) > 0 and spaces / max(len(text), 1) < 0.05:
        return 0.3
    if "�" in text:
        return 0.4
    return 0.95


def parse_txt(content: bytes) -> tuple[str, float]:
    for enc in ("utf-8", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except Exception:
            text = ""
    return text, _quality_for_text(text)


def parse_pdf(content: bytes) -> tuple[str, float]:
    try:
        import pdfplumber  # type: ignore
        import io

        text_parts: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts)
        if text.strip():
            return text, _quality_for_text(text)
    except Exception:
        pass
    # OCR fallback stub: no tesseract here, mark low quality
    try:
        text = content.decode("latin-1", errors="ignore")
    except Exception:
        text = ""
    # if PDF header only / binary, treat as scanned
    if text.strip().startswith("%PDF") or len(text.strip()) < 50:
        return text, 0.3
    return text, _quality_for_text(text)


def parse_docx(content: bytes) -> tuple[str, float]:
    try:
        import docx  # type: ignore
        import io

        doc = docx.Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs)
        return text, _quality_for_text(text)
    except Exception:
        try:
            text = content.decode("latin-1", errors="ignore")
        except Exception:
            text = ""
        return text, 0.4


def parse_file(filename: str, content: bytes) -> tuple[str, float]:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return parse_pdf(content)
    if name.endswith(".docx"):
        return parse_docx(content)
    return parse_txt(content)
