from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}


def validate_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF, TXT, and DOCX are supported in E-Mode.",
        )
    return suffix


def normalize_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_upload(file: UploadFile) -> str:
    suffix = validate_upload(file)
    payload = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Uploaded file exceeds the 5 MB limit")

    if suffix == ".txt":
        raw_text = _extract_txt_text(payload)
    elif suffix == ".docx":
        raw_text = _extract_docx_text(payload)
    else:
        raw_text = _extract_pdf_text(payload)

    normalized = normalize_text(raw_text)
    if not normalized:
        raise HTTPException(status_code=400, detail="The uploaded file does not contain readable text")
    return normalized


def _extract_txt_text(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def _extract_docx_text(payload: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=400, detail="Unable to read the DOCX file") from exc

    root = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        joined = "".join(parts).strip()
        if joined:
            paragraphs.append(joined)
    return "\n".join(paragraphs)


def _extract_pdf_text(payload: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="PDF support is unavailable until backend dependencies are installed",
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(payload))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pragma: no cover - parser-specific failures
        raise HTTPException(status_code=400, detail="Unable to extract text from the PDF file") from exc
    return "\n".join(page for page in pages if page.strip())


def select_relevant_context(
    material_text: str,
    *,
    topic: str,
    instructions: str,
    latest_message: str,
    max_chunks: int = 5,
    chunk_size: int = 1200,
) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", material_text) if part.strip()]
    chunks = list(_chunk_paragraphs(paragraphs, chunk_size=chunk_size))
    if not chunks:
        return material_text[: chunk_size * max_chunks]

    keywords = _keywords(" ".join([topic, instructions, latest_message]))
    if not keywords:
        return "\n\n".join(chunks[:max_chunks])

    scored = sorted(
        ((chunk, _score_chunk(chunk, keywords)) for chunk in chunks),
        key=lambda item: item[1],
        reverse=True,
    )
    selected = [chunk for chunk, score in scored[:max_chunks] if score > 0]
    if not selected:
        selected = chunks[:max_chunks]
    return "\n\n".join(selected)


def _chunk_paragraphs(paragraphs: Iterable[str], *, chunk_size: int) -> Iterable[str]:
    bucket: list[str] = []
    current_length = 0
    for paragraph in paragraphs:
        if current_length and current_length + len(paragraph) > chunk_size:
            yield "\n\n".join(bucket)
            bucket = []
            current_length = 0
        bucket.append(paragraph)
        current_length += len(paragraph)
    if bucket:
        yield "\n\n".join(bucket)


def _keywords(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Zа-яА-Я0-9]{3,}", value.lower())}


def _score_chunk(chunk: str, keywords: set[str]) -> int:
    lowered = chunk.lower()
    return sum(lowered.count(keyword) for keyword in keywords)
