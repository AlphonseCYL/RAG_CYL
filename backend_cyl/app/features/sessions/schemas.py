from pydantic import BaseModel


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


class DeleteSessionResponse(BaseModel):
    status: str = "success"
    message: str = "Session deleted successfully"
