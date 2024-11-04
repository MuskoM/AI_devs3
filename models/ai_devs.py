from typing import Any
from pydantic import BaseModel

class AiDevsAnswer(BaseModel):
    task: str
    apikey: str
    answer: str | list | dict[str, Any]

class AiDevsResponse(BaseModel):
    code: int
    message: str | Any

