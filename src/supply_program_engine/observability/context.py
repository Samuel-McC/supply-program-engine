from __future__ import annotations


def span_attributes(
    *,
    correlation_id: str | None = None,
    entity_id: str | None = None,
    event_type: str | None = None,
    task_type: str | None = None,
    provider_name: str | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    attributes: dict[str, object] = {}

    if correlation_id:
        attributes["correlation_id"] = correlation_id
    if entity_id:
        attributes["entity_id"] = entity_id
    if event_type:
        attributes["event_type"] = event_type
    if task_type:
        attributes["task_type"] = task_type
    if provider_name:
        attributes["provider_name"] = provider_name
    if extra:
        for key, value in extra.items():
            if value is not None:
                attributes[key] = value

    return attributes
