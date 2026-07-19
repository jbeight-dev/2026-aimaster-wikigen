from pydantic import BaseModel


class HistoryTurn(BaseModel):
    role: str
    text: str


class ChatRequest(BaseModel):
    space_id: str
    user_id: str
    question: str
    history: list[HistoryTurn] = []


class Source(BaseModel):
    document_id: str
    title: str
    score: float
    heading: str = ""


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = []


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
