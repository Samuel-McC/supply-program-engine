from __future__ import annotations

from dataclasses import dataclass

from supply_program_engine.auth.models import SessionPrincipal


@dataclass(frozen=True)
class PermissionContext:
    operator_can_review: bool
    operator_can_approve: bool
    operator_can_send: bool
    operator_can_manage_data_controls: bool
    operator_can_run_admin_actions: bool


def can_review(operator: SessionPrincipal | None) -> bool:
    return bool(operator and operator.has_any_role("reviewer", "approver", "sender", "admin"))


def can_approve(operator: SessionPrincipal | None) -> bool:
    return bool(operator and operator.has_any_role("approver", "admin"))


def can_send(operator: SessionPrincipal | None) -> bool:
    return bool(operator and operator.has_any_role("sender", "admin"))


def can_manage_data_controls(operator: SessionPrincipal | None) -> bool:
    return bool(operator and operator.has_any_role("admin"))


def can_run_admin_actions(operator: SessionPrincipal | None) -> bool:
    return bool(operator and operator.has_any_role("admin"))


def permission_context(operator: SessionPrincipal | None) -> PermissionContext:
    return PermissionContext(
        operator_can_review=can_review(operator),
        operator_can_approve=can_approve(operator),
        operator_can_send=can_send(operator),
        operator_can_manage_data_controls=can_manage_data_controls(operator),
        operator_can_run_admin_actions=can_run_admin_actions(operator),
    )
