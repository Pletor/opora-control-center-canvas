"""Jedno vyhodnocení kuličky Linie (docs/navrhy/2026-11-06-linie-rebrand.md §2, §2a, §4). Bez gitu a bez modelu.

`axes(work, after_merge)` → pět os z dnešního záznamu `work`; `evaluate(work, after_merge, live)` → `{key, text, reason,
next, allowed, blocked}` podle tabulky §2a (první platné pravidlo vyhrává); `evidence(work, after_merge, pr)` → důkazy.
`after_merge` je sha nejnovějšího commitu větve, který začleněný merge neobsahuje (zjistí volající z gitu); HEAD je pak
on, jinak `headSha`. `live` = agent má ověřeně živou relaci (zdroj zatím není, takže wip je „probíhá (neověřeno)“).
"""
ACTIONS = ("accept", "merge", "attempt")
ALWAYS = ["block", "unblock"]  # §2a: block/unblock je povolen vždy


def _short(sha):
    return (sha or "-")[:7]


def _checks(work, head):
    """Stav kontrol pro HEAD; bez nich `missing` se sha posledních kontrol (jiná revize) nebo None."""
    found = [check for check in work.get("checks") or [] if check.get("sha") == head] if head else []
    if not found:
        older = (work.get("checks") or [])[-1:]
        return {"state": "missing", "sha": older[0].get("sha") if older else None, "src": "report"}
    statuses = {check.get("status") for check in found}
    state = "failed" if "red" in statuses else "running" if "pending" in statuses else "passed"
    return {"state": state, "sha": head, "src": "report"}


def axes(work, after_merge=None):
    work = work or {}
    head = after_merge or work.get("headSha")
    if after_merge:
        state, src = "in_progress", "git log"  # commit po začlenění, zatím bez hlášení
    elif head:
        state, src = "submitted", "linie report"
    elif work.get("runs"):
        state, src = "in_progress", "relace agenta"
    else:
        state, src = "not_started", None
    accepted, merged = work.get("acceptance"), work.get("merged")
    return {
        "work": {"state": state, "sha": head, "src": src},
        "checks": _checks(work, head),
        "acceptance": {"state": "pending" if not accepted else "accepted" if accepted.get("sha") == head else "stale",
                       "sha": (accepted or {}).get("sha"), "src": "záznam přijetí"},
        "integration": {"state": "merged" if merged else "none", "target": (merged or {}).get("target") or work.get(
            "target"), "sha": (merged or {}).get("sha"), "at": (merged or {}).get("at"),
            "mode": (merged or {}).get("mode"), "src": "merge log"},
        "deploy": {"envs": {}, "src": "událost prostředí"},
    }


def _rule(work, ax, live):
    """`(key, text, reason, next, allowed)` – pořadí přesně podle tabulky §2a (+ `deferred` před `todo`)."""
    head, h7 = ax["work"]["sha"], _short(ax["work"]["sha"])
    checks, acc, integ = ax["checks"], ax["acceptance"], ax["integration"]
    target = integ["target"] or "cíle"
    if work.get("blocked"):
        why = work["blocked"].get("reason") or ""
        return "blocked", "blokováno", f"ruční block: {why}", f"Člověk odblokuje ({why}).", ["unblock"]
    if integ["state"] == "merged" and ax["work"]["src"] != "git log":  # git log = commit po začlenění
        return ("merged", f"začleněno do {target}", f"integration.merged → {target} & žádný commit po začlenění",
                "Nasazení potvrdí prostředí; zatím nenasazeno, nevím.", [])
    if work.get("deferred"):
        return "deferred", "odloženo", "ruční odložení", "Odloženo; pokračuj přes resume.", ["resume"]
    if ax["work"]["state"] == "not_started":
        return ("todo", "nezačato", "work.not_started", f"Kancelář založí pokus na větvi {work.get('branch') or '?'}.",
                ["attempt"])
    if ax["work"]["state"] == "in_progress":
        if live:
            return "wip", "probíhá", "work.in_progress", "Agent odevzdá revizi (linie report).", []
        return ("wip", "probíhá (neověřeno)", "work.in_progress & bez živé relace",
                "Agent se přihlásí a odevzdá revizi (linie report).", [])
    if checks["state"] == "failed":
        return ("failed", f"kontroly selhaly {h7}", f"work.submitted & checks.failed({h7})",
                "Agent opraví a odevzdá novou revizi.", [])
    if checks["state"] == "missing" or checks["sha"] != head:
        why = (f"checks.sha {_short(checks['sha'])} ≠ HEAD {h7}" if checks["sha"] else f"checks.missing({h7})")
        step = f"CI ověří HEAD {h7}."
        if acc["state"] == "stale":
            step += f" Přijetí bylo pro starší {_short(acc['sha'])}; teprve pak nové přijetí."
        return "nocheck", f"chybí kontroly {h7}", f"work.submitted & {why}", step, []
    if checks["state"] == "running":
        return ("checking", f"ověřuje se {h7}", f"work.submitted & checks.running({h7})", f"Čekáme na CI pro {h7}.",
                [])
    if acc["state"] == "stale":
        return ("stale", f"přijato pro starší {_short(acc['sha'])}",
                f"checks.passed({h7}) & acceptance.accepted({_short(acc['sha'])} ≠ HEAD {h7})",
                f"Člověk znovu přijme HEAD {h7}.", ["accept"])
    if acc["state"] == "pending":
        return ("pending", f"čeká na přijetí {h7}", f"checks.passed({h7}) & acceptance.pending",
                f"Člověk rozhodne o přijetí {h7}.", ["accept"])
    reason = f"checks.passed({h7}) & acceptance.accepted({h7}) & integration.none"
    if (work.get("mergeAllowed") or {}).get("sourceSha") != head:  # služba bez povolení pro HEAD nezačlení (merge.py)
        return ("accepted", f"přijato {h7}, čeká na povolení začlenění", reason + " & mergeAllowed chybí",
                f"Člověk povolí začlenění do {target} (allow-merge).", [])
    return ("accepted", f"přijato {h7}, čeká na začlenění", reason,
            f"Služba začlení (merge) do {target} a znovu ověří.", ["merge"])


def evaluate(work, after_merge=None, live=False):
    work = work or {}
    ax = axes(work, after_merge)
    key, text, reason, step, allowed = _rule(work, ax, live)
    if after_merge:
        reason = f"nová revize po začlenění {_short(ax['integration']['sha'])} · " + reason
    blocked = {action: f"{reason} – {step}" for action in ACTIONS if action not in allowed}
    return {"key": key, "text": text, "reason": reason, "next": step,
            "allowed": allowed + [a for a in ALWAYS if a not in allowed], "blocked": blocked, "axes": ax}


def evidence(work, after_merge=None, pr=None):
    """Důkazy `{kind, ref, at, src}` z téhož záznamu; PR jen když ho volající přečetl."""
    work = work or {}
    found = [{"kind": "session", "ref": run.get("sessionId"), "at": run.get("startedAt"), "src": "agent-office"}
             for run in work.get("runs") or []]
    head = work.get("headSha")
    if head:
        mine = [check for check in work.get("checks") or [] if check.get("sha") == head]
        found.append({"kind": "commit", "ref": head, "at": mine[-1]["at"] if mine else None, "src": "linie report"})
        found += [{"kind": "check", "ref": f"{c['name']}={c['status']}@{head[:7]}", "at": c.get("at"), "src": "report"}
                  for c in mine]
    if work.get("acceptance"):
        found.append({"kind": "accept", "ref": work["acceptance"].get("sha"), "at": work["acceptance"].get("at"),
                      "src": "záznam přijetí"})
    if work.get("merged"):
        found.append({"kind": "merge", "ref": work["merged"].get("sha"), "at": work["merged"].get("at"),
                      "src": "merge log"})
    if after_merge:
        found.append({"kind": "commit", "ref": after_merge, "at": None, "src": "git log"})
    if pr and pr.get("number") is not None:
        found.append({"kind": "pr", "ref": f"#{pr['number']}", "url": pr.get("url"), "at": None, "src": "GitHub"})
    return found
