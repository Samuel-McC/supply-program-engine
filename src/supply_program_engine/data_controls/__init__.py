def build_entity_export(*args, **kwargs):
    from supply_program_engine.data_controls.exports import build_entity_export as _build_entity_export

    return _build_entity_export(*args, **kwargs)


def retention_run_once(*args, **kwargs):
    from supply_program_engine.data_controls.retention import run_once as _run_once

    return _run_once(*args, **kwargs)


def create_subject_request(*args, **kwargs):
    from supply_program_engine.data_controls.subject_requests import create_subject_request as _create_subject_request

    return _create_subject_request(*args, **kwargs)


def update_subject_request_status(*args, **kwargs):
    from supply_program_engine.data_controls.subject_requests import (
        update_subject_request_status as _update_subject_request_status,
    )

    return _update_subject_request_status(*args, **kwargs)


def active_suppressions_for_entity(*args, **kwargs):
    from supply_program_engine.data_controls.suppression import (
        active_suppressions_for_entity as _active_suppressions_for_entity,
    )

    return _active_suppressions_for_entity(*args, **kwargs)


def record_suppression(*args, **kwargs):
    from supply_program_engine.data_controls.suppression import record_suppression as _record_suppression

    return _record_suppression(*args, **kwargs)


__all__ = [
    "active_suppressions_for_entity",
    "build_entity_export",
    "create_subject_request",
    "record_suppression",
    "retention_run_once",
    "update_subject_request_status",
]
