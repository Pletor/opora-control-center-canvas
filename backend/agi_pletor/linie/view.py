"""Jeden souhrn Linie pro Velín (`GET /api/pletor/linie/`, kontrakt §5).

Zdroj, který selže (git, registr), vrátí ve své sekci `{error}`; souhrn nikdy nepadá.
"""
from backend.agi_pletor.dashboard.heart_view import safe
from backend.agi_pletor.linie import acceptance, branches, previews

# shortcut: ochrana main/develop na GitHubu se živě neověřuje (zjištěno ručně 2026-11-06: protection 404,
# rulesets prázdné); po M4 číst z `gh api`.
ENFORCEMENT = "nevynuceno"


def linie_view(folder, root):
    """`{main, develop, server, deployed, branches, previews, enforcement}`; větve nesou přijetí a náhled."""
    git = safe(lambda: branches.summary(root))
    accepted = acceptance.read(folder)
    running = safe(lambda: previews.status(folder))
    by_branch = {p.get("branch"): p for p in running} if isinstance(running, list) else {}
    if "error" in git:
        return {"main": git, "develop": None, "server": git, "deployed": accepted["deployed"], "branches": [],
                "previews": running, "enforcement": ENFORCEMENT}
    rows = []
    for branch in git["branches"]:
        stored = accepted["branches"].get(branch["name"])
        acceptance_row = None
        if isinstance(stored, dict):  # zkrácené sha (7+) platí jako předpona plného
            acceptance_row = {**stored, "valid": bool(stored.get("sha")) and branch["sha"].startswith(stored["sha"])}
        rows.append({**branch, "acceptance": acceptance_row, "preview": by_branch.get(branch["name"])})
    return {"main": git["main"], "develop": git["develop"], "server": git["server"],
            "deployed": accepted["deployed"], "branches": rows, "previews": running, "enforcement": ENFORCEMENT}
