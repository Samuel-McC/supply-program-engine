from __future__ import annotations

from typing import Any


def render_template(template: str, context: dict[str, Any]) -> str:
    """
    Very small merge-field renderer.

    Example:
        "Hi {{ company_name }}" -> "Hi Acme Inc"
    """
    rendered = template

    for key, value in context.items():
        placeholder = "{{ " + key + " }}"
        rendered = rendered.replace(placeholder, str(value if value is not None else ""))

    return rendered
