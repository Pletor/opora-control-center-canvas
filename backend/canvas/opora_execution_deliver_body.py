"""Tělo `POST /executions/{id}/deliver` a co z něj server odvodí bez modelu (zefektivneni-opory.md §3.2).

Čisté funkce kromě `card_commits` (čte git): ověření těla (422 s polem, tvarem a příkladem), poznámka
kroku bez `notes` z předmětů commitů karty (trailer `Opora-Node` nebo cesty karty, `commit_pairs`),
jinak `summary`, a `selfChecks` + běhy kontrol z položek `checks`.
"""
import re

from backend.canvas import commit_pairs
from backend.canvas.payload_errors import invalid, keys_problem
from backend.integrations import git_read

REQUIRED = {"project", "workspace", "summary"}
OPTIONAL = {"steps", "commit", "checks", "decisions", "close"}
STEP_STATUSES = ("done", "failed", "skipped")
CHECK_STATUSES = ("green", "red")
COMMIT = re.compile(r"[0-9a-f]{7,64}")
EXAMPLE = {"project": "PROJECT", "workspace": "draft", "summary": "Sekce hotová, testy zelené.",
           "steps": [{"stepId": "s1", "status": "done", "notes": "Komponenta a test."}],
           "commit": None, "checks": [{"name": "npm test", "status": "green", "output": "12 passed"}],
           "decisions": [], "close": True}
COMMIT_LIMIT = 50
NOTE_LIMIT = 4000


def _text(value, field, expected, limit=4000, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > limit or "\0" in value:
        raise invalid("deliver", field, "neplatná hodnota.", expected, EXAMPLE)
    return value


def validate_body(payload):
    """Normalizované tělo; neplatný tvar = InvalidPayload (422)."""
    problem = keys_problem(payload, REQUIRED, OPTIONAL)
    if problem:
        raise invalid("deliver", "body", problem,
                      "{project, workspace, summary, steps?, commit?, checks?, decisions?, close?}", EXAMPLE)
    body = {"project": payload["project"], "workspace": payload["workspace"],
            "summary": _text(payload["summary"], "summary", "neprázdný text do 4000 znaků"),
            "steps": [], "commit": payload.get("commit"), "checks": [], "close": payload.get("close", True),
            "decisions": payload.get("decisions", [])}
    steps = payload.get("steps", [])
    if not isinstance(steps, list) or len(steps) > 100:
        raise invalid("deliver", "steps", "má být pole.", "[{stepId, status: done|failed|skipped, notes?}]", EXAMPLE)
    seen = set()
    for item in steps:
        problem = keys_problem(item, {"stepId", "status"}, {"notes"})
        if problem or item["status"] not in STEP_STATUSES or not isinstance(item["stepId"], str) or item["stepId"] in seen:
            raise invalid("deliver", "steps[]", problem or "neplatný nebo opakovaný krok.",
                          "{stepId: ID kroku ze start.steps, status: done|failed|skipped, notes?}", EXAMPLE)
        seen.add(item["stepId"])
        notes = item.get("notes")
        if notes is not None:
            _text(notes, "steps[].notes", "text do 4000 znaků", empty=True)
        body["steps"].append({"stepId": item["stepId"], "status": item["status"], "notes": notes})
    if body["commit"] is not None and (not isinstance(body["commit"], str) or not COMMIT.fullmatch(body["commit"])):
        raise invalid("deliver", "commit", "není SHA.", "7–64 malých hex znaků, nebo null = git rev-parse HEAD", EXAMPLE)
    checks = payload.get("checks", [])
    if not isinstance(checks, list) or len(checks) > 30:
        raise invalid("deliver", "checks", "má být pole.", "[{name, status: green|red, output?}]", EXAMPLE)
    names = set()
    for item in checks:
        problem = keys_problem(item, {"name", "status"}, {"output"})
        if problem or item["status"] not in CHECK_STATUSES or item.get("name") in names:
            raise invalid("deliver", "checks[]", problem or "neplatný nebo opakovaný stav kontroly.",
                          "{name: příkaz, status: green|red, output?}", EXAMPLE)
        names.add(_text(item["name"], "checks[].name", "příkaz kontroly do 1000 znaků", limit=1000))
        output = item.get("output")
        if output is not None:
            _text(output, "checks[].output", "text do 4000 znaků", empty=True)
        body["checks"].append({"name": item["name"], "status": item["status"], "output": output})
    if type(body["close"]) is not bool:
        raise invalid("deliver", "close", "není bool.", "true (výchozí) nebo false", EXAMPLE)
    if not isinstance(body["decisions"], list):
        raise invalid("deliver", "decisions", "má být pole.", "[text rozhodnutí karty]", EXAMPLE)
    return body


def card_commits(root, node, graph_nodes, limit=COMMIT_LIMIT):
    """`[{sha, subject}]` posledních commitů HEAD, které patří kartě (trailer `Opora-Node` nebo její cesty)."""
    if not root:
        return []
    found = []
    for sha in git_read.recent(root, "HEAD", limit):
        info = git_read.commit_info(root, sha)
        if info is not None:
            found.append({"sha": info["sha"], "subject": info["subject"], "trailers": info["trailers"],
                          "paths": info["paths"], "branches": [], "task": None, "inMain": True, "date": info["date"]})
    pair = commit_pairs.pair_for_scope(scope={"kind": "node", "id": node}, spec_revision=0, spec_saved_at=None,
                                       workspace=None, commits=found,
                                       owned=commit_pairs.owned_paths(node, graph_nodes))
    subjects = {item["sha"]: item["subject"] for item in found}
    return [{"sha": sha, "subject": subjects[sha]} for sha in pair["gitCommits"]]


def step_results(body, commits, pinned):
    """`stepResults` pro výsledek: krok bez `notes` = předměty commitů karty, jinak `summary`."""
    known = {item["id"] for item in pinned or []}
    unknown = [item["stepId"] for item in body["steps"] if item["stepId"] not in known]
    if unknown:
        raise invalid("deliver", "steps[].stepId", "krok " + ", ".join(unknown) + " není v zadání běhu.",
                      "ID z start.steps: " + ", ".join(sorted(known)), EXAMPLE)
    derived = "; ".join(item["subject"] for item in commits)[:NOTE_LIMIT] or body["summary"]
    shas = [item["sha"][:40] for item in commits][:50]
    names = [item["name"][:500] for item in body["checks"]]
    out = []
    for item in body["steps"]:
        evidence = {"notes": item["notes"] if item["notes"] else derived}
        if shas:
            evidence["commits"] = shas
        if names:
            evidence["checks"] = names
        out.append({"stepId": item["stepId"], "status": item["status"], "evidence": evidence})
    return out


def _slug(name):
    slug = re.sub(r"[^a-z0-9_.:-]+", "-", name.lower()).strip("-")[:64]
    return slug if slug and slug[0].isalnum() else ("check-" + slug)[:64]


def self_checks(checks, head):
    """`selfChecks` výsledku z `checks` (jen s plným SHA hlavy a aspoň jednou kontrolou), jinak None."""
    if not checks or not head or len(head) != 40:
        return None
    items, names = [], set()
    for item in checks:
        name = _slug(item["name"])
        while name in names:
            name = (name[:60] + "-" + str(len(names)))[:64]
        names.add(name)
        green = item["status"] == "green"
        entry = {"name": name, "command": item["name"], "exitCode": 0 if green else 1,
                 "status": "passed" if green else "failed"}
        if item["output"]:
            entry["output"] = item["output"]
        items.append(entry)
    return {"headSha": head, "checks": items}


def check_runs(checks):
    """Pořadí zápisu běhů kontrol: zelené dřív, červené naposled, aby nejnovější běh karty (brána `local`)
    nikdy nepřekryl červený výsledek zeleným."""
    return sorted(checks, key=lambda item: item["status"] == "red")
