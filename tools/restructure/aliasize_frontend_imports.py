"""Přepíše relativní importy v src/**/*.{ts,tsx} na alias @/<cesta od src>."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
IMP = re.compile(r"""(from\s*|import\s*|import\(\s*)(['"])(\.{1,2}/[^'"]+)\2""")

def to_alias(file: Path, spec: str) -> str:
    target = (file.parent / spec).resolve()
    rel = target.relative_to(SRC).as_posix()
    return f"@/{rel}"

changed = 0
for path in list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")):
    text = path.read_bytes().decode("utf-8")
    new = IMP.sub(lambda m, path=path: f"{m.group(1)}{m.group(2)}{to_alias(path, m.group(3))}{m.group(2)}", text)
    if new != text:
        path.write_bytes(new.encode("utf-8"))
        changed += 1
print(f"rewritten files: {changed}")
