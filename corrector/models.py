from __future__ import annotations
from pydantic import BaseModel, Field


class Sentence(BaseModel):
    id: int
    text: str
    paragraph_id: int
    paragraph_order: int


class Correction(BaseModel):
    id: int = Field(description="Global sentence ID")
    corrected: str


class CorrectionResponse(BaseModel):
    corrections: list[Correction] = []
