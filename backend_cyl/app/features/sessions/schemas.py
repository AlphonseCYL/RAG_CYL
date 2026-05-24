from pydantic import BaseModel


class SessionResponse(BaseModel):
    session_id: str
    status: str = "success"
    message: str = "Session created successfully"

