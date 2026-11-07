"""JSON soubory Linie v datovém kořeni služby (merge log, nasazení, cache PR): čtení a atomická změna pod zámkem."""
import json
import threading
from pathlib import Path

LOCK = threading.Lock()  # čtení-změna-zápis z více vláken serveru


def read(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def update(path, default, change):
    """`change(hodnota) → nová hodnota`; zapíše celý soubor, nebo nic. Vrací novou hodnotu."""
    path = Path(path)
    with LOCK:
        value = change(read(path, default))
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        return value
