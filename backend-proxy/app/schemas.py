from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


def iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- User ----


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str


class UserListResponse(BaseModel):
    items: list[UserSchema]


class SwitchUserRequest(BaseModel):
    user_id: str


class SwitchUserResponse(BaseModel):
    token: str
    user: UserSchema


class MeResponse(BaseModel):
    user: UserSchema


# ---- Space ----


class SpaceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    space_id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    file_count: int
    document_count: int
    approved_count: int
    created_at: datetime

    @field_serializer("created_at")
    def _ser_created_at(self, dt: datetime) -> str:
        return iso_z(dt)


class SpaceCreateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SpaceResponse(BaseModel):
    space: SpaceSchema


class SpaceListResponse(BaseModel):
    items: list[SpaceSchema]


# ---- File ----


class FileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    space_id: str
    name: str
    size_bytes: int
    storage_path: Optional[str] = None
    checksum: Optional[str] = None
    status: str
    step_index: int
    step_message: Optional[str] = None
    created_at: datetime

    @field_serializer("created_at")
    def _ser_created_at(self, dt: datetime) -> str:
        return iso_z(dt)


class FileResponse(BaseModel):
    file: FileSchema


class FileListResponse(BaseModel):
    items: list[FileSchema]


class FileUploadResponse(BaseModel):
    items: list[FileSchema]


class FileAnalyzeResponse(BaseModel):
    file_id: str
    status: str


# ---- Document ----


class DocumentSection(BaseModel):
    type: str
    heading: str
    paragraphs: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[dict[str, Any]]] = None
    content: Optional[str] = None


class DocumentHistoryEntry(BaseModel):
    label: str
    time: str


class DocumentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    file_id: str
    space_id: str
    title: str
    status: str
    version: int
    reject_reason: Optional[str] = None
    flags: list[str] = []
    sections: list[DocumentSection] = []
    related_document_ids: list[str] = []
    history: list[DocumentHistoryEntry] = []


class DocumentResponse(BaseModel):
    document: DocumentSchema


class DocumentListResponse(BaseModel):
    items: list[DocumentSchema]


class DocumentRejectRequest(BaseModel):
    reason: Optional[str] = None


class DocumentUpdateRequest(BaseModel):
    sections: list[DocumentSection]


class VerifyFinding(BaseModel):
    claim: str
    grounded: bool
    evidence: Optional[str] = None
    severity: str


class VerifyValueChange(BaseModel):
    kind: str
    original_value: str
    changed_value: str
    evidence: Optional[str] = None


class VerifyRelationSuggestion(BaseModel):
    action: str
    type: str
    target: str
    confidence: float
    rationale: str
    status: str = "proposed"


class VerificationReport(BaseModel):
    doc_id: str
    verdict: str
    score: float
    attempt: int
    faithfulness: list[VerifyFinding] = []
    completeness: list[str] = []
    value_changes: list[VerifyValueChange] = []
    schema_issues: list[str] = []
    relations: list[VerifyRelationSuggestion] = []


class DocumentVerifyResponse(BaseModel):
    report: VerificationReport


# ---- Wiki ----


class WikiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc_id: str
    file_id: str
    space_id: str
    title: str
    slug: str
    doc_type: str
    summary: str
    keywords: list[str] = []
    concepts: list[str] = []
    tags: list[str] = []
    entities: list[Any] = []
    relations: list[Any] = []
    review_status: str
    version: int
    body: str
    builder_created_at: Optional[datetime] = None
    builder_updated_at: Optional[datetime] = None

    @field_serializer("builder_created_at", "builder_updated_at")
    def _ser_builder_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return iso_z(dt) if dt else None


class WikiListResponse(BaseModel):
    items: list[WikiSchema]


# ---- Chat ----


class ChatMessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str
    space_id: str
    role: str
    text: str
    source_document_ids: list[str] = []
    created_at: datetime

    @field_serializer("created_at")
    def _ser_created_at(self, dt: datetime) -> str:
        return iso_z(dt)


class ChatMessageCreateRequest(BaseModel):
    text: str


class ChatMessageCreateResponse(BaseModel):
    user_message: ChatMessageSchema
    assistant_message: ChatMessageSchema


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageSchema]


# ---- Error ----


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
