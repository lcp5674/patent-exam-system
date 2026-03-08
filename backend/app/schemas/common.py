"""通用 Schema"""
from pydantic import BaseModel
from typing import Optional, Generic, TypeVar

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class DeleteResponse(BaseModel):
    id: int
    deleted: bool = True


class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
