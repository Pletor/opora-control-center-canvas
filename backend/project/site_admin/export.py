"""Export design systému pro dělníka (kontrakt Správy webu §4): složka `design/` jako zip.

`design/tokens.css`, `tokens.json`, `components.css`, `README.md` (generuje `compile.py` z uložené revize),
`design/fonts/…` a `design/assets/<skupina>/…` (soubory z `site/`). Kancelář ji rozbalí do worktree jen ke čtení.
"""

import io
import zipfile

from backend.project.site_admin import compile as compiled
from backend.project.site_admin import store


def export_zip(service, project):
    """`(revize, bajty zipu)` uložené revize."""
    # shortcut: zip se skládá v paměti (assety do 10 MB, nejvýš 5000), při velkých webech streamovat po souborech.
    with service.lock_for(project):
        document = store.read(service, project)
        root = store.site_dir(service, project)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, text in (("tokens.css", compiled.tokens_css(document)), ("tokens.json", compiled.tokens_json(document)),
                               ("components.css", compiled.components_css(document)), ("README.md", compiled.readme(document))):
                archive.writestr(f"design/{name}", text)
            for folder in ("fonts", "assets"):
                for path in sorted((root / folder).rglob("*")) if (root / folder).is_dir() else []:
                    if path.is_file():
                        archive.write(path, "design/" + path.relative_to(root).as_posix())
    return document["revision"], buffer.getvalue()
