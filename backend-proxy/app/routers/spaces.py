from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..errors import AppError
from ..ids import new_id
from ..models import Document, File, Space, User
from ..schemas import SpaceCreateRequest, SpaceListResponse, SpaceResponse, SpaceSchema

router = APIRouter(prefix="/spaces", tags=["spaces"])


def _space_to_schema(db: Session, space: Space) -> SpaceSchema:
    file_count = db.query(func.count(File.file_id)).filter(
        File.space_id == space.space_id, File.status != "deleted"
    ).scalar()
    document_count = db.query(func.count(Document.document_id)).filter(
        Document.space_id == space.space_id, Document.status != "deleted"
    ).scalar()
    approved_count = (
        db.query(func.count(Document.document_id))
        .filter(Document.space_id == space.space_id, Document.status == "approved")
        .scalar()
    )
    return SpaceSchema(
        space_id=space.space_id,
        name=space.name,
        description=space.description,
        owner_id=space.owner_id,
        file_count=file_count,
        document_count=document_count,
        approved_count=approved_count,
        created_at=space.created_at,
    )


def _list_spaces_with_counts(db: Session, owner_id: str) -> list[SpaceSchema]:
    file_counts_sq = (
        db.query(
            File.space_id.label("space_id"),
            func.count(File.file_id).label("file_count"),
        )
        .filter(File.status != "deleted")
        .group_by(File.space_id)
        .subquery()
    )
    doc_counts_sq = (
        db.query(
            Document.space_id.label("space_id"),
            func.sum(case((Document.status != "deleted", 1), else_=0)).label("document_count"),
            func.sum(case((Document.status == "approved", 1), else_=0)).label("approved_count"),
        )
        .group_by(Document.space_id)
        .subquery()
    )
    rows = (
        db.query(
            Space,
            func.coalesce(file_counts_sq.c.file_count, 0),
            func.coalesce(doc_counts_sq.c.document_count, 0),
            func.coalesce(doc_counts_sq.c.approved_count, 0),
        )
        .outerjoin(file_counts_sq, file_counts_sq.c.space_id == Space.space_id)
        .outerjoin(doc_counts_sq, doc_counts_sq.c.space_id == Space.space_id)
        .filter(Space.owner_id == owner_id)
        .order_by(Space.created_at.desc())
        .all()
    )
    return [
        SpaceSchema(
            space_id=space.space_id,
            name=space.name,
            description=space.description,
            owner_id=space.owner_id,
            file_count=file_count,
            document_count=doc_count,
            approved_count=approved_count,
            created_at=space.created_at,
        )
        for space, file_count, doc_count, approved_count in rows
    ]


def _get_space_or_404(db: Session, space_id: str) -> Space:
    space = db.get(Space, space_id)
    if not space:
        raise AppError(404, "SPACE_NOT_FOUND", "존재하지 않는 Space입니다.")
    return space


@router.post("", response_model=SpaceResponse, status_code=201)
def create_space(
    body: SpaceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.name or not body.name.strip():
        raise AppError(400, "SPACE_NAME_REQUIRED", "Space 이름을 입력해주세요.")

    space = Space(
        space_id=new_id("spc"),
        name=body.name,
        description=body.description,
        owner_id=current_user.user_id,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return SpaceResponse(space=_space_to_schema(db, space))


@router.get("", response_model=SpaceListResponse)
def list_spaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SpaceListResponse(items=_list_spaces_with_counts(db, current_user.user_id))


@router.get("/{space_id}", response_model=SpaceResponse)
def get_space(
    space_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    space = _get_space_or_404(db, space_id)
    return SpaceResponse(space=_space_to_schema(db, space))


@router.delete("/{space_id}", status_code=204)
def delete_space(
    space_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    space = _get_space_or_404(db, space_id)
    db.delete(space)
    db.commit()


@router.delete("", status_code=204)
def delete_all_spaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Space).delete()
    db.commit()
