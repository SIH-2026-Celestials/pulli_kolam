"""Pydantic request/response models for /api/v1/auth/*. Plain primitives
in responses only -- never a password or password_hash field, by
construction (UserPublic simply has no such field to accidentally
serialize)."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("display_name")
    @classmethod
    def _valid_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Display name is required.")
        if len(v) > 100:
            raise ValueError("Display name must be 100 characters or fewer.")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserPublic(BaseModel):
    id: int
    email: str
    display_name: str
    created_at: str
    last_login_at: str | None = None
