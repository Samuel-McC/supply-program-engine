from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


OperatorRole = Literal["reviewer", "approver", "sender", "admin"]


class OperatorUser(BaseModel):
    username: str
    display_name: str
    password_hash: str
    roles: list[OperatorRole] = Field(default_factory=list)


class SessionPrincipal(BaseModel):
    username: str
    display_name: str
    roles: list[OperatorRole] = Field(default_factory=list)
    issued_at: int
    expires_at: int
    csrf_key: str

    def has_any_role(self, *roles: OperatorRole) -> bool:
        if "admin" in self.roles:
            return True
        if not roles:
            return True
        return any(role in self.roles for role in roles)
