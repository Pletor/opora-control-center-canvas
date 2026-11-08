"""Linie jako git-flow obrázek (kontrakt §5): svislé linie main / develop / pracovní větve s commity.

`graph(root, folder, accepted)` → `{lanes: [{name, role, parent, sha, base, commits, acceptance, preview, pr}], active}`.
Commity linie jsou nejstarší první; `base` je merge-base s rodičem (odbočení). Git přes `integrations.gitio.git`,
chyba gitu je `ValueError`. Přijetí `accepted` = `{větev: work.acceptance}` z ticketů (routa). PR z `gh` je jen doplněk: chybí-li gh nebo selže, `pr` je `null`.
"""
import json
import shutil
import subprocess
import threading
import time
from datetime import UTC, datetime

from backend.agi_pletor.linie import branches, gitsnap, previews, tree

TIMEOUT = branches.TIMEOUT
FORMAT = "--format=%H%x1f%P%x1f%cI%x1f%s"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _commits(root, *args):
    out = gitsnap.frozen(root, "log", FORMAT, *args, optional=False)  # argumenty z plných SHA se pamatují
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


PR_SEEN = {}  # repozitář → (monotonic, prs) pro graf
PR_TTL = 60


def recent_prs(root):
    """`gh_prs` nejvýš jednou za minutu a nikdy v cestě požadavku (gh trvá ~1 s): obnoví se na pozadí, do té doby
    poslední známé PR (první požadavek bez PR)."""
    seen = PR_SEEN.get(str(root))
    if seen is None or time.monotonic() - seen[0] > PR_TTL:
        seen = PR_SEEN[str(root)] = (time.monotonic(), seen[1] if seen else {})
        threading.Thread(target=lambda: PR_SEEN.__setitem__(str(root), (time.monotonic(), gh_prs(root))),
                         daemon=True).start()
    return seen[1]


def graph(root, folder, accepted=None, *, pr_lookup=recent_prs, running=None):
    """`running` = `previews.status(folder)`, když ho volající už přečetl."""
    with gitsnap.scope():
        return _graph(root, folder, accepted, pr_lookup, running)


def _graph(root, folder, accepted, pr_lookup, running):
    stamps_args = ("for-each-ref", "refs/heads", "--format=%(refname:short)\t%(committerdate:unix)")
    unmerged_args = ("for-each-ref", "--no-merged", "main", "refs/heads", "--format=%(refname:short)")
    gitsnap.warm(root, [*branches.reads(root), stamps_args, unmerged_args])  # nezávislé gity souběžně
    found = branches.summary(root)
    rows = {b["name"]: b for b in found["branches"]}
    if "main" not in rows:
        raise ValueError("Repozitář nemá větev main.")
    stamps = gitsnap.read(root, *stamps_args, optional=False)
    when = {name: int(at) for name, _, at in (line.partition("\t") for line in stamps.splitlines()) if at.isdigit()}
    unmerged = set(gitsnap.read(root, *unmerged_args, optional=False).splitlines())
    accepted = accepted or {}
    running = {p.get("branch"): p for p in (previews.status(folder) if running is None else running)}
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
    names = [n for n in tree.order(rows) if n in ("main", "develop") or n in work]
    sha = {name: row["sha"] for name, row in rows.items()}  # jména → SHA z téhož čtení: výstup gitu se pamatuje
    pair = {n: (sha.get(rows[n]["parent"]) or rows[n]["parent"], sha[n]) for n in names if n != "main"}
    gitsnap.prefetch(root, [("merge-base", *pair[n]) for n in pair])
    bases = {n: gitsnap.frozen(root, "merge-base", *pair[n], optional=False) for n in pair}
    span = {n: ("-n", "31", sha[n], "--not", bases[n] + "^@") if n == "develop" else ("-n", "30", "..".join(pair[n]))
            for n in pair}
    gitsnap.prefetch(root, [("log", FORMAT, *span[n]) for n in span] + [("log", FORMAT, "-n", "8", sha["main"])])
    for name in names:
        row = rows[name]
        if name == "main":
            base, commits = None, _commits(root, "-n", "8", sha["main"])
        else:
            # develop i s odbočným commitem (`base^@` vyloučí jen jeho rodiče); pracovní větev jen rodič..větev
            base, commits = bases[name], _commits(root, *span[name])
        lanes.append({"name": name, "role": row["role"], "parent": row["parent"], "sha": row["sha"], "base": base,
                      "commits": commits, "acceptance": stamped(accepted.get(name), row["sha"]),
                      "preview": running.get(name), "pr": prs.get(name)})
    active = max(sorted(work), key=lambda name: when.get(name, 0), default=None)
    return {"lanes": lanes, "active": active}
