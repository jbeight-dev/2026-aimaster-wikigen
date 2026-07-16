import asyncio
import logging
import mimetypes
import os
import random
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import get_current_user
from ..errors import AppError
from ..ids import new_id
from ..models import SUPPORTED_FILE_EXTENSIONS, Document, File, Space, User, WikiMd
from ..schemas import (
    FileAnalyzeResponse,
    FileListResponse,
    FileResponse,
    FileSchema,
    WikiListResponse,
    WikiSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])

BUILDER_API_BASE_URL = os.getenv("builder_API_BASE_URL", "http://localhost:8002")
BUILDER_INGEST_URL = f"{BUILDER_API_BASE_URL}/builderapi/v1/ingest"

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "uploads"

ANALYSIS_STEPS = [
    "파일을 읽는 중이에요",
    "핵심 내용을 추출하는 중이에요",
    "내용을 요약하는 중이에요",
    "핵심 내용과 키워드를 뽑아내는 중이에요",
    "연관 문서를 탐색하는 중이에요",
    "내용을 검증하는 중이에요",
    "마무리하는 중이에요",
]

STEP_DELAY_SECONDS = 0.7
FAILURE_RATE = 0.15


def _get_file_or_404(db: Session, file_id: str) -> File:
    file = db.get(File, file_id)
    if not file or file.status == "deleted":
        raise AppError(404, "FILE_NOT_FOUND", "존재하지 않는 파일입니다.")
    return file


def _file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_storage_path(file_id: str, filename: str) -> Path:
    return STORAGE_DIR / file_id / filename


def _parse_builder_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _fetch_builder_document(client: httpx.AsyncClient, doc_id: str) -> dict | None:
    url = f"{BUILDER_API_BASE_URL}/builderapi/v1/documents/{doc_id}"
    logger.debug("fetching builder document doc_id=%s url=%s", doc_id, url)
    try:
        response = await client.get(url)
        response.raise_for_status()
        logger.info("fetched builder document doc_id=%s status=%s", doc_id, response.status_code)
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "builder document fetch returned error status for doc_id %s: %s",
            doc_id,
            exc.response.status_code,
        )
        return None
    except httpx.HTTPError:
        logger.exception("builder document fetch failed for doc_id %s", doc_id)
        return None


def _upsert_wikimd(db: Session, file: File, doc_id: str, payload: dict) -> None:
    document = payload["document"]
    row = db.get(WikiMd, doc_id)
    is_new = row is None
    if row is None:
        row = WikiMd(doc_id=doc_id)
        db.add(row)
    logger.info(
        "%s wikimd row doc_id=%s file_id=%s title=%s",
        "creating" if is_new else "updating",
        doc_id,
        file.file_id,
        document.get("title"),
    )
    row.file_id = file.file_id
    row.space_id = file.space_id
    row.title = document["title"]
    row.slug = document["slug"]
    row.doc_type = document.get("doc_type", "generic")
    row.summary = document["summary"]
    row.keywords = document.get("keywords", [])
    row.concepts = document.get("concepts", [])
    row.tags = document.get("tags", [])
    row.entities = document.get("entities", [])
    row.relations = document.get("relations", [])
    row.source = document.get("source", {})
    row.review_status = document.get("review_status", "draft")
    row.version = document.get("version", 1)
    row.reviewed_by = document.get("reviewed_by")
    row.builder_created_at = _parse_builder_dt(document.get("created_at"))
    row.builder_updated_at = _parse_builder_dt(document.get("updated_at"))
    row.body = payload["body"]


async def _fetch_and_persist_wikimd_docs(file: File, doc_ids: list[str]) -> None:
    if not doc_ids:
        logger.info("no doc_ids to fetch for file %s", file.file_id)
        return

    logger.info("fetching %d builder document(s) for file %s", len(doc_ids), file.file_id)
    fetched: list[tuple[str, dict]] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for doc_id in doc_ids:
            payload = await _fetch_builder_document(client, doc_id)
            if payload is not None:
                fetched.append((doc_id, payload))

    logger.info(
        "fetched %d/%d builder document(s) successfully for file %s",
        len(fetched),
        len(doc_ids),
        file.file_id,
    )
    if not fetched:
        return

    db = SessionLocal()
    try:
        for doc_id, payload in fetched:
            try:
                _upsert_wikimd(db, file, doc_id, payload)
                db.commit()
            except Exception:
                logger.exception("failed to persist wikimd row for doc_id %s", doc_id)
                db.rollback()
    finally:
        db.close()


async def _call_builder_ingest(file: File) -> None:
    path = _file_storage_path(file.file_id, file.name)
    if not path.exists():
        logger.warning("builder ingest skipped: no stored content for file %s", file.file_id)
        return

    content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    logger.info(
        "calling builder ingest for file %s (name=%s, content_type=%s) at %s",
        file.file_id,
        file.name,
        content_type,
        BUILDER_INGEST_URL,
    )
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with path.open("rb") as fh:
                response = await client.post(
                    BUILDER_INGEST_URL,
                    data={"file_id": file.file_id, "space_id": file.space_id},
                    files={"file": (file.name, fh, content_type)},
                )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("builder ingest call failed for file %s", file.file_id)
        return

    try:
        doc_ids = response.json().get("doc_ids", [])
    except ValueError:
        logger.exception("builder ingest response was not valid JSON for file %s", file.file_id)
        return

    logger.info(
        "builder ingest succeeded for file %s: status=%s doc_ids=%s",
        file.file_id,
        response.status_code,
        doc_ids,
    )
    await _fetch_and_persist_wikimd_docs(file, doc_ids)


def _build_document_from_wiki(file: File, entry: WikiMd) -> Document:
    sections = []
    if entry.concepts:
        sections.append({"type": "tags", "heading": "핵심 키워드", "tags": entry.concepts})
    sections.append(
        {
            "type": "text",
            "heading": "요약",
            "paragraphs": [entry.summary] if entry.summary else [],
        }
    )
    if entry.body:
        sections.append({"type": "markdown", "heading": "LLM Wiki", "content": entry.body})

    return Document(
        document_id=new_id("doc"),
        file_id=file.file_id,
        space_id=file.space_id,
        wiki_doc_id=entry.doc_id,
        title=entry.title,
        status="pending",
        version=entry.version,
        flags=[],
        sections=sections,
        related_document_ids=[],
        history=[{"label": "문서 생성됨 (분석 완료)", "time": _now_iso()}],
    )


async def _run_analysis_progress(file_id: str) -> None:
    logger.info("analysis progress started for file %s (%d steps)", file_id, len(ANALYSIS_STEPS))
    for index, message in enumerate(ANALYSIS_STEPS):
        await asyncio.sleep(STEP_DELAY_SECONDS)
        db = SessionLocal()
        try:
            file = db.get(File, file_id)
            if not file or file.status != "analyzing":
                logger.info(
                    "analysis progress aborted for file %s at step %d/%d (status=%s)",
                    file_id,
                    index + 1,
                    len(ANALYSIS_STEPS),
                    file.status if file else "missing",
                )
                return
            file.step_index = index
            file.step_message = message
            db.commit()
            logger.info(
                "file %s step %d/%d: %s", file_id, index + 1, len(ANALYSIS_STEPS), message
            )
        finally:
            db.close()
    logger.info("analysis progress finished for file %s", file_id)


def _finalize_analysis(file_id: str) -> None:
    db = SessionLocal()
    try:
        file = db.get(File, file_id)
        if not file or file.status != "analyzing":
            logger.info(
                "finalize skipped for file %s (status=%s)",
                file_id,
                file.status if file else "missing",
            )
            return

        if random.random() < FAILURE_RATE:
            logger.info("analysis randomly failed for file %s (FAILURE_RATE=%s)", file_id, FAILURE_RATE)
            file.status = "analysis_failed"
            db.commit()
            return

        wiki_entries = db.query(WikiMd).filter(WikiMd.file_id == file.file_id).all()
        if not wiki_entries:
            logger.warning("analysis failed for file %s: no wikimd entries were persisted", file_id)
            file.status = "analysis_failed"
            db.commit()
            return

        documents = [_build_document_from_wiki(file, entry) for entry in wiki_entries]
        document_id_by_wiki_doc_id = {
            entry.doc_id: doc.document_id for entry, doc in zip(wiki_entries, documents)
        }
        for entry, doc in zip(wiki_entries, documents):
            related_ids = []
            for relation in entry.relations:
                target_document_id = document_id_by_wiki_doc_id.get(relation.get("target"))
                if target_document_id and target_document_id not in related_ids:
                    related_ids.append(target_document_id)
            doc.related_document_ids = related_ids
            db.add(doc)

        file.status = "done"
        db.commit()
        logger.info(
            "analysis completed for file %s: created %d document(s)", file_id, len(documents)
        )
    finally:
        db.close()


@router.post("/spaces/{space_id}/files", response_model=FileListResponse, status_code=201)
async def upload_files(
    space_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    space = db.get(Space, space_id)
    if not space:
        raise AppError(404, "SPACE_NOT_FOUND", "존재하지 않는 Space입니다.")

    form = await request.form()
    uploads = form.getlist("files[]") or form.getlist("files")
    logger.info("received %d upload(s) for space %s", len(uploads), space_id)

    created: list[File] = []
    for upload in uploads:
        contents = await upload.read()
        ext = _file_extension(upload.filename or "")
        status = "idle" if ext in SUPPORTED_FILE_EXTENSIONS else "upload_failed"
        file = File(
            file_id=new_id("file"),
            space_id=space_id,
            name=upload.filename,
            size_bytes=len(contents),
            status=status,
        )
        db.add(file)
        created.append(file)

        if status == "idle":
            path = _file_storage_path(file.file_id, file.name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
            logger.info(
                "saved file %s '%s' (%d bytes) to %s",
                file.file_id,
                file.name,
                file.size_bytes,
                path,
            )
        else:
            logger.warning(
                "rejected upload '%s' for space %s: unsupported extension '%s'",
                upload.filename,
                space_id,
                ext,
            )

    db.commit()
    for file in created:
        db.refresh(file)

    return FileListResponse(items=[FileSchema.model_validate(f) for f in created])


@router.get("/spaces/{space_id}/files", response_model=FileListResponse)
def list_files(
    space_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    space = db.get(Space, space_id)
    if not space:
        raise AppError(404, "SPACE_NOT_FOUND", "존재하지 않는 Space입니다.")

    files = (
        db.query(File)
        .filter(File.space_id == space_id, File.status != "deleted")
        .order_by(File.created_at.desc())
        .all()
    )
    return FileListResponse(items=[FileSchema.model_validate(f) for f in files])


@router.get("/files/{file_id}", response_model=FileResponse)
def get_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = _get_file_or_404(db, file_id)
    return FileResponse(file=FileSchema.model_validate(file))


@router.post("/files/{file_id}/analyze", response_model=FileAnalyzeResponse, status_code=202)
async def analyze_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = _get_file_or_404(db, file_id)
    if file.status != "idle":
        raise AppError(400, "FILE_NOT_ANALYZABLE", "분석을 시작할 수 없는 상태입니다.")

    logger.info("starting analysis for file %s '%s'", file.file_id, file.name)
    file.status = "analyzing"
    file.step_index = 0
    file.step_message = ANALYSIS_STEPS[0]
    db.commit()
    await _run_analysis_progress(file.file_id)
    await _call_builder_ingest(file)
    _finalize_analysis(file.file_id)
    db.refresh(file)
    logger.info("analysis request finished for file %s: status=%s", file.file_id, file.status)

    return FileAnalyzeResponse(file_id=file.file_id, status=file.status)


@router.post("/files/{file_id}/retry", response_model=FileAnalyzeResponse, status_code=202)
async def retry_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = _get_file_or_404(db, file_id)
    if file.status != "analysis_failed":
        raise AppError(400, "FILE_NOT_ANALYZABLE", "재분석할 수 없는 상태입니다.")

    logger.info("retrying analysis for file %s '%s'", file.file_id, file.name)
    file.status = "analyzing"
    file.step_index = 0
    file.step_message = ANALYSIS_STEPS[0]
    db.commit()
    await _run_analysis_progress(file.file_id)
    await _call_builder_ingest(file)
    _finalize_analysis(file.file_id)
    db.refresh(file)
    logger.info("retry finished for file %s: status=%s", file.file_id, file.status)

    return FileAnalyzeResponse(file_id=file.file_id, status=file.status)


@router.get("/files/{file_id}/wiki", response_model=WikiListResponse)
def list_file_wiki(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = _get_file_or_404(db, file_id)
    entries = db.query(WikiMd).filter(WikiMd.file_id == file.file_id).all()
    return WikiListResponse(items=[WikiSchema.model_validate(e) for e in entries])


@router.delete("/files/{file_id}", status_code=204)
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = _get_file_or_404(db, file_id)
    file.status = "deleted"
    updated = (
        db.query(Document)
        .filter(Document.file_id == file.file_id)
        .update({"status": "deleted"}, synchronize_session=False)
    )
    db.commit()
    logger.info(
        "deleted file %s '%s' (%d associated document(s) marked deleted)",
        file.file_id,
        file.name,
        updated,
    )


@router.get("/files/{file_id}/stream")
async def stream_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = _get_file_or_404(db, file_id)
    payload = FileSchema.model_validate(file).model_dump_json()

    async def event_generator():
        yield f"data: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
