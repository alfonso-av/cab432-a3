from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class LoginSchema(BaseModel):
    username: str
    password: str

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    message: str

class JobCreate(BaseModel):
    input_file_id: str
    preset: str = "veryslow"
    crf: int = Field(23, ge=0, le=51)
    resolution: Optional[str] = None
    threads: Optional[int] = 0

class JobStatusResponse(BaseModel):
    id: str
    status: str
    owner: str
    input_file_id: str
    output_ready: bool
    output_path: Optional[str]
    params: Dict[str, Any]
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    log_tail: Optional[str]
