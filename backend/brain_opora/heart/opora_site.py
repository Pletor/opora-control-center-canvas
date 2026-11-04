"""Design systém webu jako nástroj srdce (`opora_heart.py site`, kontrakt Správy webu §4).

Jen standardní knihovna. Nástroj sem předá sám sebe (`tool`): `call` s tokenem srdce, `Failure`, `env`.
- `show [--tokens]` vypíše shrnutí design systému projektu (`GET /api/site-admin/summary`: titulek, témata, počty
  tokenů, styly, komponenty, stav nastavení, čekající návrhy); `--tokens` přidá celý `tokens.json`;
- `propose --file F [--note N]` podá návrh změny `{title?, settings?, design?}` (`POST /api/site-admin/proposals`).
  Dokument se nemění: návrh přijme nebo zamítne člověk na stránce Správa webu. Nový návrh nahradí čekající.
Dávka srdce (`command.py`) soubor kopíruje do `brain/` vedle `opora_heart.py`.
"""
import json
from pathlib import Path


def show(tool, with_tokens):
    query = {"project": tool.env("OPORA_PROJECT")}
    out = tool.call("GET", "/api/site-admin/summary", query=query)
    return {**out, "tokensJson": tool.call("GET", "/api/site-admin/tokens.json", query=query)} if with_tokens else out


def propose(tool, path, note):
    try:
        changes = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise tool.Failure({"error": f"Soubor návrhu {path} nejde přečíst: {error}", "code": "site_file",
                            "hint": "Soubor je JSON {title?, settings?: {část: …}, design?: {tokens?, readme?, …}}; "
                                    "uvedená část nahradí uloženou celou."}) from None
    body = {"project": tool.env("OPORA_PROJECT"), "changes": changes, **({"note": note} if note else {})}
    found = tool.call("POST", "/api/site-admin/proposals", body)
    return {"proposalId": found["id"], "baseRevision": found["baseRevision"], "diffTotal": found["diffTotal"],
            "diff": found["diff"][:20], "notes": found["notes"],
            "next": "návrh přijme nebo zamítne člověk na stránce Správa webu"}


def site(args, tool):
    return show(tool, args.tokens) if args.action == "show" else propose(tool, args.file, args.note)
