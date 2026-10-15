from typing import Literal
from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    roots: list[str] = Field(min_length=1, max_length=32)
    mode: Literal["exact", "images", "videos"] = "exact"
    excluded_directories: list[str] = Field(default_factory=list, max_length=128)
    excluded_extensions: list[str] = Field(default_factory=list, max_length=128)
    include_hidden: bool = False


class ReviewRequest(BaseModel):
    keep_ids: list[str] | None = Field(default=None, min_length=1, max_length=10000)
    changes: dict[str, bool] = Field(default_factory=dict, max_length=200)


class PlanRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=1000)
    destination: Literal["trash", "quarantine"] = "trash"


class ExecuteRequest(BaseModel):
    plan_id: str
    token: str
    confirmed: bool = False


class RestoreRequest(BaseModel):
    confirmed: bool = False
