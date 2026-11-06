"""Hook SessionStart Claude Code: zapíše `<cwd>/.opora/session.json`, ze kterého `linie.py task` vezme relaci.

Čte JSON ze stdin (`session_id`, `transcript_path`, `cwd`). Nikdy nespadne a vždy skončí kódem 0, start relace neblokuje.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main(raw):
    data = json.loads(raw)
    cwd = Path(data.get("cwd") or ".")
    path = cwd / ".opora" / "session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sessionId": data.get("session_id"), "transcriptPath": data.get("transcript_path"),
                                "at": datetime.now(timezone.utc).isoformat()}, indent=2), "utf-8")
    # duplikát 4 řádků z linie.remember: .opora/ se necommituje (lokální info/exclude)
    out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--git-path", "info/exclude"], capture_output=True,
                         text=True, encoding="utf-8", check=False).stdout.strip()
    exclude = cwd / out if out else None
    if exclude:
        known = exclude.read_text("utf-8") if exclude.is_file() else ""
        if ".opora/" not in known:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            exclude.write_text(known + "\n.opora/\n", "utf-8")


if __name__ == "__main__":
    try:
        main(sys.stdin.read())
    except Exception:  # noqa: BLE001 - hook nesmí blokovat start relace
        pass
    sys.exit(0)
