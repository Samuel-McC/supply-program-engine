from __future__ import annotations

import re
from dataclasses import dataclass


_WHITESPACE_RE = re.compile(r"\s+")

_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("unsubscribe", ("unsubscribe", "stop", "opt out")),
    ("not_interested", ("not interested", "no thanks", "remove me")),
    ("out_of_office", ("out of office", "away until")),
    ("interested", ("interested", "let's talk", "send details", "pricing", "call me")),
)


@dataclass(frozen=True)
class ClassificationResult:
    classification: str
    matched_phrase: str | None = None


def normalize_reply_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.lower()).strip()


def reply_snippet(text: str, limit: int = 160) -> str:
    normalized = _WHITESPACE_RE.sub(" ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def classify_reply(text: str) -> ClassificationResult:
    normalized = normalize_reply_text(text)

    for classification, phrases in _RULES:
        for phrase in phrases:
            if phrase in normalized:
                return ClassificationResult(classification=classification, matched_phrase=phrase)

    return ClassificationResult(classification="unknown")
