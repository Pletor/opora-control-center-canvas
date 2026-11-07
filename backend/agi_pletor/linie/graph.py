"""Linie jako git-flow obrázek (kontrakt §5): svislé linie main / develop / pracovní větve s commity.

`graph(root, folder, accepted)` → `{lanes: [{name, role, parent, sha, base, commits, acceptance, preview, pr}], active}`.
Commity linie jsou nejstarší první; `base` je merge-base s rodičem (odbočení). Git přes `integrations.gitio.git`,
chyba gitu je `ValueError`. Přijetí `accepted` = `{větev: work.acceptance}` z ticketů (routa). PR z `gh` je jen doplněk: chybí-li gh nebo selže, `pr` je `null`.
"""
import json
import shutil
import subprocess
from datetime import UTC, datetime

from backend.agi_pletor.linie import branches, previews, tree
from backend.integrations.gitio import git

TIMEOUT = branches.TIMEOUT
FORMAT = "--format=%H%x1f%P%x1f%cI%x1f%s"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _commits(root, *args):
    out = git(root, "log", FORMAT, *args, timeout=TIMEOUT)
    rows = []
    for line in reversed(out.splitlines()):
        sha, parents, at, title = line.split("\x1f", 3)
        rows.append({"sha": sha, "sha7": sha[:7], "title": title, "parents": parents.split(),
                     "at": datetime.fromisoformat(at).astimezone(UTC).isoformat().replace("+00:00", "Z")})
    return rows


def stamped(stored, head):
    """Záznam přijetí s `valid`: zkrácené sha (7+) platí jako předpona plné hlavy větve; jinak None."""
    if not isinstance(stored, dict):
        return None
    return {**stored, "valid": bool(stored.get("sha")) and head.startswith(stored["sha"])}


def gh_lookup(root):
    """`{prs: {větev: {number, state, url, base}}, ok, error}` z posledních PR. Repozitář bez PR je `ok: True`
    s prázdným `prs`; chybějící gh nebo chyba čtení je `ok: False` s důvodem (výpadek, ne „žádné PR“)."""
    gh = shutil.which("gh")
    if not gh:
        return {"prs": {}, "ok": False, "error": "gh není nainstalované"}
    # shortcut: jedno volání na posledních 200 PR místo `--head` na větev; starší větve PR neukážou.
    command = [gh, "pr", "list", "--state", "all", "--limit", "200", "--json", "number,state,url,baseRefName,headRefName"]
    try:
        out = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=10,
                             check=True, creationflags=NO_WINDOW).stdout
        rows = json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        return {"prs": {}, "ok": False, "error": type(error).__name__}
    if not isinstance(rows, list):
        return {"prs": {}, "ok": False, "error": "neočekávaná odpověď gh"}
    prs = {}
    for row in rows:  # gh vrací nejnovější první; ten vyhrává
        prs.setdefault(row.get("headRefName"), {"number": row.get("number"), "state": row.get("state"),
                                                "url": row.get("url"), "base": row.get("baseRefName")})
    return {"prs": prs, "ok": True, "error": None}


def gh_prs(root):
    """Jen `prs` z `gh_lookup` pro doplňky (graf, detail commitu, cesta), kde výpadek = PR neukázat."""
    return gh_lookup(root)["prs"]


def graph(root, folder, accepted=None, *, pr_lookup=gh_prs):
    found = branches.summary(root)
    rows = {b["name"]: b for b in found["branches"]}
    if "main" not in rows:
        raise ValueError("Repozitář nemá větev main.")
    stamps = git(root, "for-each-ref", "refs/heads", "--format=%(refname:short)\t%(committerdate:unix)",
                 timeout=TIMEOUT)
    when = {name: int(at) for name, _, at in (line.partition("\t") for line in stamps.splitlines()) if at.isdigit()}
    unmerged = set(git(root, "for-each-ref", "--no-merged", "main", "refs/heads", "--format=%(refname:short)",
                       timeout=TIMEOUT).splitlines())
    accepted = accepted or {}
    running = {p.get("branch"): p for p in previews.status(folder)}
    # shortcut: aktivní téma = nesloučené větve mladší než špička main (poslední přijaté vydání);
    # po M2 nahradí vazba na ticket.
    work = {name for name, row in rows.items() if row["role"] in branches.ROLES and name in unmerged
            and when.get(name, 0) > when.get("main", 0)}
    work |= {name for name in rows if name not in ("main", "develop") and (name in accepted or name in running)}
    for name in list(work):  # předci až ke kořeni musí mít vlastní linii, jinak odbočení nemá kam
        parent = rows[name]["parent"]
        while parent in rows and parent not in ("main", "develop") and parent not in work:
            work.add(parent)
            parent = rows[parent]["parent"]

    prs = pr_lookup(root)
    lanes = []
    for name in [n for n in tree.order(rows) if n in ("main", "develop") or n in work]:
        row = rows[name]
        if name == "main":
            base, commits = None, _commits(root, "-n", "8", "main")
        else:
            base = git(root, "merge-base", row["parent"], name, timeout=TIMEOUT)
            # develop i s odbočným commitem (`base^@` vyloučí jen jeho rodiče); pracovní větev jen rodič..větev
            commits = (_commits(root, "-n", "31", name, "--not", base + "^@") if name == "develop"
                       else _commits(root, "-n", "30", f"{row['parent']}..{name}"))
        lanes.append({"name": name, "role": row["role"], "parent": row["parent"], "sha": row["sha"], "base": base,
                      "commits": commits, "acceptance": stamped(accepted.get(name), row["sha"]),
                      "preview": running.get(name), "pr": prs.get(name)})
    active = max(sorted(work), key=lambda name: when.get(name, 0), default=None)
    return {"lanes": lanes, "active": active}
