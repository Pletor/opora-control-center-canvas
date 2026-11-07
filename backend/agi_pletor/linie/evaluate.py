"""Jedno vyhodnocení kuličky Linie (docs/navrhy/2026-11-06-linie-rebrand.md §2, §2a, §4). Bez gitu a bez modelu.

`axes(work, after_merge)` → pět os z dnešního záznamu `work`; `evaluate(work, after_merge, live)` → `{key, text, reason,
next, allowed, blocked}` podle tabulky §2a (první platné pravidlo vyhrává); `evidence(work, after_merge, pr)` → důkazy.
`after_merge` je skutečná špička větve, kterou hlášení nepokrývá (zjistí volající z gitu, `work.unreported`): po
začlenění nejnovější commit mimo merge, jinak špička ≠ `headSha`; HEAD je pak on, jinak `headSha`. `target_sha` je
dnešní špička cíle povolení; povolení platí jen pro tutéž dvojici HEAD → špička cíle. `live` = relace s explicitní vazbou na worktree a čerstvým heartbeat (work.py). `integration` je osa
z merge logu nebo z gitu/GitHubu (work.py, §5a); bez ní platí `work.merged` jako důkaz gitu (`src: git`, `mode: None`).
`deploy` = `{env: {sha, at, origin}}` z událostí prostředí, které revizi úkolu obsahují.
L7d (§7 bod 4): přijetí platí pro dvojici `(sha, cardRevision)`; jiná revize zadání karty při stejném sha = klíč
`stale_plan` hned za `stale`, `allowed: accept`.
"""
ACTIONS = ("accept", "allow_merge", "merge", "attempt", "resume", "unblock", "preview", "revoke_accept", "defer")
ALWAYS = ["block"]  # block vždy; unblock jen u blocked, resume jen u deferred (zadání L7a po oponentuře)


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


def _merged(work):
    merged = work.get("merged")
    return {"state": "merged" if merged else "none", "target": (merged or {}).get("target") or work.get("target"),
            "sha": (merged or {}).get("sha"), "at": (merged or {}).get("at"), "mode": None, "op": None,
            "src": "git" if merged else None}


def _acceptance(accepted, head, card_revision):
    """Přijetí platí pro dvojici (sha, cardRevision): stejné sha s jinou revizí zadání karty = `stale_plan` (L7d)."""
    if not accepted:
        return "pending"
    if accepted.get("sha") != head:
        return "stale"
    old = accepted.get("cardRevision")
    return "stale_plan" if old is not None and card_revision is not None and old != card_revision else "accepted"


def axes(work, after_merge=None, integration=None, deploy=None, card_revision=None):
    work = work or {}
    head = after_merge or work.get("headSha")
    integ = integration or _merged(work)
    if after_merge:  # commit na větvi bez hlášení (po začlenění, nebo nová špička nad nahlášenou revizí)
        state, src = "in_progress", "git log" if integ["state"] == "merged" else "git log · bez hlášení"
    elif head:
        state, src = "submitted", "linie report"
    elif work.get("runs"):
        state, src = "in_progress", "relace agenta"
    else:
        state, src = "not_started", None
    accepted = work.get("acceptance")
    return {
        "work": {"state": state, "sha": head, "src": src},
        "checks": _checks(work, head),
        "acceptance": {"state": _acceptance(accepted, head, card_revision), "sha": (accepted or {}).get("sha"),
                       "cardRevision": (accepted or {}).get("cardRevision"), "src": "záznam přijetí"},
        "integration": integ,
        "deploy": {"envs": deploy or {}, "src": "událost prostředí"},
    }


def _rule(work, ax, live, target_sha=None, card_revision=None):
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
    if acc["state"] == "stale_plan":
        return ("stale_plan", f"přijato {h7} pro starší zadání R{acc['cardRevision']}",
                f"checks.passed({h7}) & acceptance.accepted({h7}, R{acc['cardRevision']} ≠ karta R{card_revision})",
                f"Člověk potvrdí přijetí vůči nové revizi zadání (karta R{card_revision}).", ["accept"])
    if acc["state"] == "pending":
        return ("pending", f"čeká na přijetí {h7}", f"checks.passed({h7}) & acceptance.pending",
                f"Člověk rozhodne o přijetí {h7}.", ["accept"])
    if integ["state"] == "unconfirmed":  # started bez finished: merge se stejným op jen ověří výsledek v gitu (§5a)
        return ("accepted", f"začlenění {h7} zahájeno, výsledek neověřen",
                f"checks.passed({h7}) & acceptance.accepted({h7}) & integration.unconfirmed",
                f"Služba ověří výsledek v gitu (merge znovu s op {integ['op']}).", ["merge"])
    reason = f"checks.passed({h7}) & acceptance.accepted({h7}) & integration.none"
    allowed = work.get("mergeAllowed") or {}
    if allowed.get("sourceSha") != head:  # služba bez povolení pro HEAD nezačlení (merge.py)
        return ("accepted", f"přijato {h7}, čeká na povolení začlenění", reason + " & mergeAllowed chybí",
                f"Člověk povolí začlenění do {target} (allow-merge).", ["allow_merge"])
    if target_sha and allowed.get("targetSha") != target_sha:  # povolení platí jen pro špičku cíle v době povolení
        aim, moved = allowed.get("target") or target, f"{_short(allowed.get('targetSha'))} → {_short(target_sha)}"
        return ("accepted", f"přijato {h7}, cíl {aim} se posunul", reason + f" & mergeAllowed.targetSha ({moved})",
                f"Člověk povolí začlenění znovu (allow-merge do {aim}).", ["allow_merge"],
                {"merge": f"cíl {aim} se od povolení posunul ({moved})"})
    return ("accepted", f"přijato {h7}, čeká na začlenění", reason + " & mergeAllowed(HEAD)",
            f"Služba začlení (merge) do {target} a znovu ověří.", ["merge"], {"allow_merge": "už povoleno pro HEAD"})


def _side(key, ax):
    """Vedlejší akce mimo tabulku §2a: náhled HEAD, zrušení přijetí (platného i zastaralého) před začleněním,
    odložení (park) mimo merged."""
    found = []
    if ax["work"]["sha"] and key not in ("merged", "blocked"):
        found.append("preview")
    if ax["acceptance"]["state"] in ("accepted", "stale", "stale_plan") and ax["integration"]["state"] == "none":
        found.append("revoke_accept")
    if key != "merged":
        found.append("defer")
    return found


def evaluate(work, after_merge=None, live=False, integration=None, deploy=None, target_sha=None, card_revision=None):
    """`card_revision` = aktuální revize zadání karty plánu (plan_link), None = neznámá / bez karty."""
    work = work or {}
    ax = axes(work, after_merge, integration, deploy, card_revision)
    key, text, reason, step, allowed, *own = _rule(work, ax, live, target_sha, card_revision)
    if after_merge and ax["integration"]["state"] == "merged":
        reason = f"nová revize po začlenění {_short(ax['integration']['sha'])} · " + reason
    elif after_merge:
        reason = f"HEAD {_short(after_merge)} bez hlášení (hlášeno {_short(work.get('headSha'))}) · " + reason
    allowed = allowed + _side(key, ax)
    blocked = {action: f"{reason} – {step}" for action in ACTIONS if action not in allowed}
    blocked.update(*own)  # vlastní důvod pravidla (např. allow_merge „už povoleno pro HEAD“)
    if "preview" in blocked:
        blocked["preview"] = "bez HEAD není co spustit" if not ax["work"]["sha"] else f"{key}: náhled se nespouští"
    if "revoke_accept" in blocked:
        blocked["revoke_accept"] = f"acceptance.{ax['acceptance']['state']} & integration.{ax['integration']['state']}" \
            " – zrušit jde jen existující přijetí před začleněním"
    if "defer" in blocked:
        blocked["defer"] = "začleněno – není co odložit"
    return {"key": key, "text": text, "reason": reason, "next": step,
            "allowed": allowed + [a for a in ALWAYS if a not in allowed], "blocked": blocked, "axes": ax}


def evidence(work, after_merge=None, pr=None, integration=None):
    """Důkazy `{kind, ref, at, src}` z téhož záznamu; PR jen když ho volající přečetl."""
    work = work or {}
    integ = integration or _merged(work)
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
    if integ["state"] != "none":
        found.append({"kind": "merge", "ref": integ["sha"] or integ["op"], "at": integ["at"], "src": integ["src"]})
    if after_merge:
        found.append({"kind": "commit", "ref": after_merge, "at": None, "src": "git log"})
    if pr and pr.get("number") is not None:
        found.append({"kind": "pr", "ref": f"#{pr['number']}", "url": pr.get("url"), "at": None, "src": "GitHub"})
    return found
