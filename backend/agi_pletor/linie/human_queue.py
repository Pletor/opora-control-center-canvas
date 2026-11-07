"""„Čeká na tebe“ (docs/navrhy/2026-11-06-linie-rebrand.md §6, §7 bod 7, L7g): fronta člověka a jedna akce.

`order(balls, rows)` → `queues.human[]` boardu: kuličky fronty `humanDecisions` (přijetí, povolení, začlenění,
odblokování) a k nim kuličky, které člověk už přijal, ale teď čekají na kontroly nebo novou revizi (řádek říká proč,
tlačítko nemá). Pořadí počítá služba: vůz, na který čeká jiný vůz fronty (jeho cíl je větev jiného vozu), první; pak
zdola nahoru po stromu (hlubší řádek dřív); pak stáří. Každý řádek nese větu „začlení X do Y, pak bude na řadě Z“ a
nejvýš jednu akci, odvozenou z `allowed` téhož `evaluate`.

`accept_merge(...)` = `POST /work/{id}/accept-merge`: jen kroky, které `evaluate` ještě povoluje, `accept` →
`allow_merge` → `merge` nad stávajícími funkcemi (žádná nová evidence). Zastaví se na prvním odmítnutí a vrátí 409 s
větou pro člověka a jedinou opravou v `hint`. Idempotence podle `op` (UUID) je ta z `merge`; nové kliknutí = nové op.
"""
from backend.agi_pletor.linie import idempotency, merge
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.work import WorkError
from backend.brain_opora.determinism.gate_payloads import GateError

WAITING = {"nocheck", "failed", "checking", "wip"}  # přijato dřív, teď čeká na kontroly / novou revizi
LABEL = {"stale": "Znovu přijmout špičku a začlenit", "stale_plan": "Znovu přijmout a začlenit"}
STEP = {"accept": "Přijetí", "allow_merge": "Povolení začlenění", "merge": "Začlenění"}
# kód 409 → (věta pro člověka, jediná oprava)
SAY = {
    "head_moved": ("na větvi je jiná revize, než jakou jsi viděl", "Načti frontu znovu a přijmi aktuální špičku."),
    "action_not_allowed": ("pravidlo Linie tento krok teď nepovoluje", "Řádek po načtení řekne, na co čeká."),
    "no_acceptance": ("revize není přijatá", "Klikni znovu: nejdřív se přijme špička."),
    "not_allowed": ("začlenění není povolené, nebo báze úkolu ještě není v cíli",
                    "Nejdřív začleň vůz, na který tento čeká (výš ve frontě)."),
    "target_moved": ("cíl se mezi povolením a začleněním posunul", "Klikni znovu: povolí se pro novou špičku cíle."),
    "target_missing": ("cílová větev v repozitáři není", "Zadej cíl kuličky v detailu."),
    "target_not_parent": ("cíl není rodič větve", "Povol začlenění do rodiče v detailu kuličky."),
    "checks_missing": ("pro tuto revizi chybí kontroly", "Kontroly dodá agent (linie report --check)."),
    "checks_failed": ("kontroly této revize nejsou zelené", "Agent opraví a pošle novou revizi."),
    "merge_conflict": ("větev nejde čistě začlenit (konflikt)", "Agent sloučí cíl do větve a pošle novou revizi."),
    "push_failed": ("push do originu selhal, nic se nezapsalo", "Ověř přístup k originu a klikni znovu."),
    "merge_not_done": ("předchozí začlenění v gitu neproběhlo", "Klikni znovu (nová operace)."),
    "op_conflict": ("operace patří jinému úkolu", "Klikni znovu (nová operace)."),
}


def _target(ball):
    return (ball.get("mergeAllowed") or {}).get("target") or ball["axes"]["integration"]["target"] or "?"


def _member(ball):
    key = ball["summary"]["key"]
    return "humanDecisions" in ball["queues"] or (key in WAITING and bool(ball.get("acceptance"))
                                                  and ball["axes"]["integration"]["state"] == "none")


def _action(ball):
    allowed, key = ball["allowed"], ball["summary"]["key"]
    if "unblock" in allowed:
        return {"kind": "unblock", "label": "Odblokovat"}
    if {"accept", "allow_merge", "merge"} & set(allowed):
        moved = "allow_merge" in allowed and ball.get("mergeAllowed")
        return {"kind": "accept_merge", "label": "Povolit znovu a začlenit" if moved else LABEL.get(key,
                                                                                               "Přijmout a začlenit")}
    return None


def _row(ball, depth):
    head = ball["axes"]["work"]["sha"]
    checks, preview = ball["axes"]["checks"], ball.get("preview") or {}
    return {"ticketId": ball["ticketId"], "mark": ball.get("mark"), "title": ball["title"], "branch": ball["branch"],
            "target": _target(ball), "sha": head, "depth": depth, "createdAt": ball["createdAt"],
            "key": ball["summary"]["key"], "state": ball["summary"]["text"], "next": ball["summary"]["next"],
            "checks": {"state": checks["state"], "sha": checks["sha"]},
            "preview": None if not preview.get("sha") else preview["sha"] == head,
            "action": _action(ball)}


def order(balls, rows):
    """Seřazená fronta člověka; `rows` = řádky boardu s `depth` (kulička leží na řádku `rowId`)."""
    depth = {row["id"]: row.get("depth") or 0 for row in rows}
    found = [_row(ball, depth.get(ball["rowId"], 0)) for ball in balls if _member(ball)]
    branches = {row["branch"] for row in found}
    for row in found:  # vůz blokuje jiný vůz fronty, když jeho cíl je větev toho vozu (dítě před rodičem)
        row["blocks"] = row["target"] in branches and row["target"] != row["branch"]
    found.sort(key=lambda row: (not row["blocks"], -row["depth"], row["createdAt"] or ""))
    for index, row in enumerate(found):
        after = found[index + 1] if index + 1 < len(found) else None
        row["order"] = index + 1
        row["sentence"] = f"začlení {row['branch']} do {row['target']}, " + (
            f"pak bude na řadě {after['mark'] or after['title']} ({after['branch']})" if after else "pak už nic nečeká")
    return found


def _refuse(step, error):
    said, fix = SAY.get(error.code, (str(error), error.hint))
    return GateError(error.status, error.code, f"{STEP[step]} se zastavilo: {said}. ({error})", fix)


def accept_merge(service, project, ticket_id, sha, op, note, now):
    """Přijmout (revizi `sha`, kterou člověk viděl) → povolit → začlenit; vrací kuličku jako `merge`."""
    shown = work_mod.get(service, project, ticket_id)
    if shown["work"].get("merged") or shown["axes"]["integration"]["state"] == "merged":
        return shown  # už začleněno: opakované kliknutí nic nedělá
    step = "accept"
    try:
        head = shown["axes"]["work"]["sha"] or ""
        # OP-90B0E5.accept_merge: jedno tlačítko smí přijmout jen revizi, kterou člověk viděl, ne novější špičku
        if not head.startswith((sha or "-").lower()):
            raise WorkError("head_moved", 409, f"Revize {sha[:7]} není aktuální hlava {head[:7] or 'žádná'}.")
        if "accept" in shown["allowed"]:
            work_mod.accept(service, project, ticket_id, sha, note, now)
            shown = work_mod.get(service, project, ticket_id)
        step = "allow_merge"
        if "allow_merge" in shown["allowed"]:  # i po posunu cíle: povolení pro dnešní špičku cíle
            work_mod.allow_merge(service, project, ticket_id, None, now)
            shown = work_mod.get(service, project, ticket_id)
        step = "merge"
        work_mod.require(shown, "merge")
        if op:  # stejné op jen pro týž úkol, jako u POST /merge
            idempotency.claim(service.root, project, "merge", op, {"ticket": ticket_id})
        done = merge.merge(service, project, ticket_id, now, op=op, by="human")
    except GateError as error:
        raise _refuse(step, error) from None
    if not done["work"].get("merged"):  # op s dřívějším neúspěchem merge vrátí kuličku beze změny
        raise _refuse("merge", WorkError("merge_not_done", 409, "Operace už dřív skončila neúspěchem."))
    return done
