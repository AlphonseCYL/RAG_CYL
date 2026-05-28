from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class SessionResponse(BaseModel):
    session_id: str
    status: str = "success"
    message: str = "Session created successfully"


class SessionItem(BaseModel):
    session_id: str
    name: str
    created_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionItem]
    status: str = "success"
    message: str = "Sessions loaded successfully"


class MessageItem(BaseModel):
    id: int
    session_id: str
    user_question: str
    model_answer: str
    documents: list[dict] | str
    recommended_questions: list[str] | str
    think: str
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageItem]
    status: str = "success"
    message: str = "Messages loaded successfully"


class DeleteSessionResponse(BaseModel):
    status: str = "success"
    message: str = "Session deleted successfully"
