"""Stav kuličky Linie odvozený z `work` ticketu (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §2). Bez gitu a modelu.

`state(work, target_sha=None)` → `{state, label, next}`. Pořadí pravidel: začleněno, blokováno, odloženo, zastaralé
přijetí nebo povolení (jiné SHA než headSha, nebo jiná špička cíle, když ji volající zná), bez commitu otevřeno,
kontroly pro headSha nejsou všechny zelené = čeká na ověření, platné přijetí = hotovo, ještě nezačleněno, jinak otevřeno.
"""

LABELS = {"open": "otevřeno", "awaiting_checks": "čeká na ověření", "blocked": "blokováno", "deferred": "odloženo",
          "accepted_unmerged": "hotovo, ještě nezačleněno", "merged": "začleněno", "stale": "zastaralé přijetí"}


def checks_for(work, sha):
    """Kontroly k jednomu SHA; starší kontroly k jinému SHA zůstávají jen v historii pole."""
    return [check for check in work.get("checks") or [] if check.get("sha") == sha]


def green(work):
    """Všechny kontroly pro headSha zelené (a aspoň jedna)."""
    found = checks_for(work, work.get("headSha"))
    return bool(found) and all(check.get("status") == "green" for check in found)


def _state(work, target_sha):
    head, accepted, allowed = work.get("headSha"), work.get("acceptance"), work.get("mergeAllowed")
    if work.get("merged"):
        return "merged", "Hotovo, nic dalšího."
    if work.get("blocked"):
        return "blocked", f"Vyřeš blokaci ({work['blocked'].get('reason', '')}), pak resume."
    if work.get("deferred"):
        return "deferred", "Odloženo; pokračuj přes resume."
    if (accepted and accepted.get("sha") != head) or (allowed and allowed.get("sourceSha") != head):
        return "stale", "Přijetí platí pro jiné SHA; člověk přijme aktuální revizi znovu."
    if allowed and target_sha and allowed.get("targetSha") != target_sha:
        return "stale", f"Cíl {allowed.get('target')} se od povolení posunul; člověk povolí začlenění znovu."
    if not head:
        return "open", f"Pracuj na větvi {work.get('branch')} a po commitu pošli report."
    if not green(work):
        return "awaiting_checks", f"Pošli report se zelenými kontrolami pro {head[:7]}."
    if not accepted:
        return "open", f"Člověk přijme revizi {head[:7]}."
    if not allowed:
        return "accepted_unmerged", f"Člověk povolí začlenění do {work.get('target') or 'cíle'}."
    return "accepted_unmerged", f"Začlenit službou (merge) do {allowed.get('target')}."


def state(work, target_sha=None):
    name, step = _state(work or {}, target_sha)
    return {"state": name, "label": LABELS[name], "next": step}
