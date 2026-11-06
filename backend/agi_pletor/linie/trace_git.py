"""Gitová půlka vodotisku (docs/navrhy/2026-11-06-linie-vodotisk-cesty.md): commity a místa v kódu k značce `OP-XXXXXX`.

Značka je tvrzení, git je důkaz: commit se značkou na větvi úkolu nad `baseSha` je `verified`, jinde `claimed`, commit bez
značky na větvi úkolu `inferred`. Komentář v kódu je `verified`, jen když soubor změnil některý verified commit úkolu.
"""
import re
from datetime import datetime

from backend.agi_pletor.linie.commit import TRAILER
from backend.agi_pletor.linie.work import ancestor
from backend.integrations.gitio import git

TIMEOUT = 15
FORMAT = "--format=%H%x1f%cI%x1f%an%x1f%s%x1f%b%x1e"
SYMBOL = re.compile(r"^\s*(?:export\s+(?:default\s+)?(?:async\s+)?(?:const|function|class)|async\s+def|def|class|function)"
                    r"\s+(\w+)")


def _git(root, *args):
    return git(root, *args, timeout=TIMEOUT, optional=True) or ""


def _log(root, *args):
    records = [r.strip("\n") for r in _git(root, "log", *args, FORMAT).split("\x1e") if r.strip()]
    for record in records:
        sha, at, author, title, body = (record.split("\x1f", 4) + [""])[:5]
        trailers = {kind.lower(): value for kind, value in TRAILER.findall(body)}
        yield {"sha": sha.strip(), "sha7": sha.strip()[:7], "title": title, "at": at, "author": author,
               "trailers": {"mark": trailers.get("mark"), "node": (trailers.get("node") or "").split("@")[0] or None,
                            "execution": trailers.get("execution")}}


def commits(root, mark, work):
    """Commity značky seřazené od nejstaršího; `paths` (jen u verified) slouží kódu, ne odpovědi."""
    found = {c["sha"]: c | {"marked": True} for c in _log(root, "--all", "--grep=" + mark)}
    for c in _log(root, f"{work['baseSha']}..{work['branch']}"):
        found.setdefault(c["sha"], c | {"marked": False})
    out = []
    for c in found.values():
        sha = c["sha"]
        c["branches"] = _git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)", "--contains", sha).split()
        on_branch = work["branch"] in c["branches"] and not ancestor(root, sha, work["baseSha"])
        c["status"] = ("verified" if on_branch else "claimed") if c["marked"] else "inferred"
        c["paths"] = _git(root, "show", "--name-only", "--format=", sha).split() if c["status"] == "verified" else []
        out.append(c)
    return sorted(out, key=lambda c: datetime.fromisoformat(c["at"].replace("Z", "+00:00")))


def code(root, mark, head, verified_paths):
    """Řádky se značkou ve stromu `head` (nezávisí na worktree), s krokem a nejbližším symbolem nad nimi."""
    if not head:
        return []
    step, places = re.compile(re.escape(mark) + r"\.(\d+)"), []
    for line in _git(root, "grep", "-n", "-F", "-e", mark, head, "--").splitlines():
        path, number, text = line[len(head) + 1:].split(":", 2) if line.startswith(head + ":") else (None, None, None)
        if path is None or not number.isdigit():
            continue
        source = _git(root, "show", f"{head}:{path}").splitlines()
        symbol = next((m.group(1) for row in reversed(source[:int(number) - 1]) if (m := SYMBOL.match(row))), None)
        found = step.search(text)
        places.append({"path": path, "line": int(number), "text": text.strip(), "step": int(found.group(1)) if found else None,
                       "symbol": symbol, "status": "verified" if path in verified_paths else "claimed"})
    return places
