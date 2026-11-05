"""Rozdělí text na věty podle `.`, `!` a `?` (bez znalosti zkratek): {"text"} → {"sentences": [...]}."""
import re


def run(vstup: dict) -> dict:
    parts = re.findall(r"[^.!?]+[.!?]*", vstup.get("text", ""))
    return {"sentences": [part.strip() for part in parts if part.strip()]}
