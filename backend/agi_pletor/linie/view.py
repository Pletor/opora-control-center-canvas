"""Jeden souhrn Linie pro Velín (`GET /api/pletor/linie/`, kontrakt §5).

Zdroj, který selže (git, registr), vrátí ve své sekci `{error}`; souhrn nikdy nepadá.
"""
from backend.agi_pletor.dashboard.heart_view import safe
from backend.agi_pletor.linie import acceptance, branches, previews
from backend.agi_pletor.linie.graph import stamped

# shortcut: ochrana main/develop na GitHubu se živě neověřuje (zjištěno ručně 2026-11-06: protection 404,
# rulesets prázdné); po M4 číst z `gh api`.
ENFORCEMENT = "nevynuceno"


def linie_view(folder, root, accepted=None):
    """`{main, develop, server, deployed, branches, previews, enforcement}`; větve nesou přijetí (`accepted` =
    `{větev: work.acceptance}` z ticketů) a náhled."""
    git = safe(lambda: branches.summary(root))
    accepted, deployed = accepted or {}, acceptance.read_deployed(folder)
    running = safe(lambda: previews.status(folder))
    by_branch = {p.get("branch"): p for p in running} if isinstance(running, list) else {}
    if "error" in git:
        return {"main": git, "develop": None, "server": git, "deployed": deployed, "branches": [],
                "previews": running, "enforcement": ENFORCEMENT}
    rows = []
    for branch in git["branches"]:
        acceptance_row = stamped(accepted.get(branch["name"]), branch["sha"])
        rows.append({**branch, "acceptance": acceptance_row, "preview": by_branch.get(branch["name"])})
    return {"main": git["main"], "develop": git["develop"], "server": git["server"],
            "deployed": deployed, "branches": rows, "previews": running, "enforcement": ENFORCEMENT}
