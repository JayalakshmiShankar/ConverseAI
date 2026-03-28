from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    gender: str = Field(min_length=1, max_length=32)
    mobile_number: str = Field(min_length=5, max_length=32)


class ProfileOut(BaseModel):
    name: str
    date_of_birth: date
    gender: str
    mobile_number: str

