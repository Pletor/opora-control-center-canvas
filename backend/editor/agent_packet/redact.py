"""Minimální, samostatný redaktor známých vzorů tajemství v uživatelském textu.

Pokrývá známé tvary tokenů (zejména fine-grained `github_pat_`) a zůstává
samostatný: podklady redigují jen text, ne klíče,
takže záměrné číselné čítače (např. cache_read_tokens) tudy vůbec neprocházejí.
"""

import re

REDACTED = "[REDACTED]"

_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"github_pat_[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.]{10,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|password|passwd|access[_-]?key|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+_.\-]{8,}['\"]?"
    ),
]


def redact_text(value):
    """Nahradí známé vzory tajemství v netroubém uživatelském textu, beze změny délky sémantiky."""
    if not isinstance(value, str) or not value:
        return value
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result
