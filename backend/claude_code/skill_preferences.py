"""Které skills má Opora při práci s Claude Code vynechat. Uloženo v datovém kořeni jako JSON."""

import json
from pathlib import Path

FILE_NAME = "claude-code-skills.json"
MAX_DISABLED = 2000


class SkillPreferences:
    def __init__(self, data_root: Path):
        self.path = Path(data_root) / FILE_NAME

    def disabled(self) -> list[str]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items = raw.get("disabledSkills") if isinstance(raw, dict) else None
        if not isinstance(items, list):
            return []
        return sorted({item for item in items if isinstance(item, str) and item})

    def save_disabled(self, items) -> list[str]:
        if not isinstance(items, list) or len(items) > MAX_DISABLED:
            raise ValueError("Očekáván seznam identifikátorů skills.")
        clean = set()
        for item in items:
            if not isinstance(item, str) or not item or len(item) > 200 or ":" not in item:
                raise ValueError("Neplatný identifikátor skillu.")
            clean.add(item)
        result = sorted(clean)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"disabledSkills": result}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        return result
