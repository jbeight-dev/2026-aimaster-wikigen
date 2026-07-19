import hashlib
import json
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
BUILDER_BUILD_URL = f"{BUILDER_API_BASE_URL}/builderapi/v1/build"

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "uploads"

BUILDER_STEP_MESSAGES = {
    "intake": "파일을 읽는 중이에요",
    "extract": "핵심 내용을 추출하는 중이에요",
    "structure": "내용을 구조화하는 중이에요",
    "translate": "번역하는 중이에요",
    "enrich": "핵심 키워드와 관계를 추출하는 중이에요",
    "metadata": "메타데이터를 정리하는 중이에요",
    "relations": "연관 문서를 탐색하는 중이에요",
    "verify": "내용을 검증하는 중이에요",
    "draft": "마무리하는 중이에요",
}

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


def _persist_built_documents(file: File, documents: list[dict]) -> None:
    # /build의 result 이벤트는 문서 본문(document/body)을 doc_id와 함께 바로 실어주므로,
    # /ingest 때처럼 GET /documents/{doc_id}로 다시 조회할 필요가 없다.
    if not documents:
        logger.info("no documents to persist for file %s", file.file_id)
        return

    db = SessionLocal()
    try:
        for entry in documents:
            doc_id = entry.get("doc_id")
            if not doc_id:
                logger.warning("skipping built document without doc_id for file %s", file.file_id)
                continue
            try:
                _upsert_wikimd(db, file, doc_id, entry)
                db.commit()
            except Exception:
                logger.exception("failed to persist wikimd row for doc_id %s", doc_id)
                db.rollback()
    finally:
        db.close()


def _update_analysis_step(file_id: str, *, index: int | None = None, message: str | None = None) -> None:
    db = SessionLocal()
    try:
        file = db.get(File, file_id)
        if not file or file.status != "analyzing":
            return
        if index is not None:
            file.step_index = index
        if message is not None:
            file.step_message = message
        db.commit()
    finally:
        db.close()


async def _iter_sse_events(response: httpx.Response):
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        try:
            yield json.loads(payload)
        except ValueError:
            logger.exception("failed to parse builder SSE payload: %s", payload)


async def _call_builder_build(file: File) -> None:
    path = _file_storage_path(file.file_id, file.name)
    if not path.exists():
        logger.warning("builder build skipped: no stored content for file %s", file.file_id)
        return

    content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    ext = _file_extension(file.name)
    ingest_filename = f"{file.file_id}.{ext}" if ext else file.file_id
    logger.info(
        "calling builder build for file %s (name=%s, ingest_filename=%s, content_type=%s) at %s",
        file.file_id,
        file.name,
        ingest_filename,
        content_type,
        BUILDER_BUILD_URL,
    )

    built_documents: list[dict] = []
    error_detail: str | None = None
    finished_steps = 0
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with path.open("rb") as fh:
                async with client.stream(
                    "POST",
                    BUILDER_BUILD_URL,
                    data={"file_id": file.file_id, "space_id": file.space_id},
                    files={"file": (ingest_filename, fh, content_type)},
                ) as response:
                    response.raise_for_status()
                    async for event in _iter_sse_events(response):
                        event_type = event.get("event")
                        if event_type == "start":
                            step = event.get("step", "")
                            logger.info("file %s builder step started: %s (%s)", file.file_id, step, event.get("detail"))
                            _update_analysis_step(file.file_id, message=BUILDER_STEP_MESSAGES.get(step, step))
                        elif event_type == "finish":
                            finished_steps += 1
                            logger.info(
                                "file %s builder step finished: %s (%ss)",
                                file.file_id,
                                event.get("step"),
                                event.get("elapsed"),
                            )
                            _update_analysis_step(file.file_id, index=finished_steps)
                        elif event_type == "result":
                            built_documents = event.get("documents", [])
                        elif event_type == "error":
                            error_detail = event.get("detail", "")
    except httpx.HTTPError:
        logger.exception("builder build call failed for file %s", file.file_id)
        return

    if error_detail is not None:
        logger.error("builder build reported failure for file %s: %s", file.file_id, error_detail)
        return

    logger.info(
        "builder build succeeded for file %s: doc_ids=%s",
        file.file_id,
        [entry.get("doc_id") for entry in built_documents],
    )
    _persist_built_documents(file, built_documents)


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

# Step1. 파일 업로드 시 호출
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
        checksum = hashlib.sha256(contents).hexdigest()
        ext = _file_extension(upload.filename or "")
        status = "uploaded" if ext in SUPPORTED_FILE_EXTENSIONS else "upload_failed"
        file = File(
            file_id=new_id("file"),
            space_id=space_id,
            name=upload.filename,
            size_bytes=len(contents),
            checksum=checksum,
            status=status,
        )
        db.add(file)
        created.append(file)

        if status == "uploaded":
            path = _file_storage_path(file.file_id, file.name)
            file.storage_path = str(path)
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

## Step2. 파일 분석 요청
@router.post("/files/{file_id}/analyze", response_model=FileAnalyzeResponse, status_code=202)
async def analyze_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file = _get_file_or_404(db, file_id)
    if file.status != "uploaded":
        raise AppError(400, "FILE_NOT_ANALYZABLE", "분석을 시작할 수 없는 상태입니다.")

    logger.info("starting analysis for file %s '%s'", file.file_id, file.name)
    file.status = "analyzing"
    file.step_index = 0
    file.step_message = BUILDER_STEP_MESSAGES["intake"]
    db.commit()
    ### Builder API 호출하여 분석 시작
    await _call_builder_build(file)
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
    file.step_message = BUILDER_STEP_MESSAGES["intake"]
    db.commit()
    await _call_builder_build(file)
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
