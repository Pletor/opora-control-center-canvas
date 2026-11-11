"""Příznaky „potřebuje úsudek“ nad stopou práce karty (docs/stopa-prace-karty.md), bez modelu.

Determinismus jen ukáže, kde sám nestačí; posouzení je práce srdce. Příznak nic nespouští: napojení na srdce
je samostatná, zvlášť měřená změna (lekce m11: měnit, co srdce dostává, po jedné). Vstupem jsou běhy z
`card_trail.project_trail`, nejnovější první. Důvod je pevná šablona, ne text modelu (`source: det`).
"""
from backend.canvas.plan_reality import outside as outside_of

RED_LIMIT = 2
FILES_SHOWN = 20
FINISHED = ("reported", "released", "revoked", "expired", "delivered", "verified", "closed", "failed", "cancelled")


def _red(step):
    return step["status"] == "failed" or any(check["status"] == "red" for check in step["checks"])


def red_twice(runs):
    """Krok, jehož kontrola byla červená (nebo krok selhal) ve dvou a více bězích či pokusech."""
    counts, flags = {}, []
    for run in runs:
        for step in run["steps"]:
            if _red(step):
                counts[step["stepId"]] = counts.get(step["stepId"], 0) + 1
    for step_id, count in counts.items():
        if count >= RED_LIMIT:
            flags.append({"code": "red_twice", "stepId": step_id, "source": "det",
                          "reason": f"Kontrola kroku byla červená v {count} pokusech."})
    return flags


def _newest_done(runs):
    """`{stepId: (run, step)}` nejnovějšího hlášení `done` každého kroku."""
    found = {}
    for run in runs:
        for step in run["steps"]:
            if step["status"] == "done" and step["stepId"] not in found:
                found[step["stepId"]] = (run, step)
    return found


def without_evidence(done):
    return [{"code": "delivered_without_evidence", "stepId": step_id, "executionId": run["executionId"],
             "source": "det", "reason": "Krok je hotový bez kontroly i bez commitu."}
            for step_id, (run, step) in done.items() if not step["checks"] and not step["commits"]]


def missing_summary(runs):
    return [{"code": "missing_summary", "executionId": run["executionId"], "ticketId": run["ticketId"], "source": "det",
             "reason": "Relace dělníka skončila bez shrnutí."}
            for run in runs if run["state"] in FINISHED and run["reported"] and not run["summary"].strip()]


def files_mismatch(done):
    """Commit kroku sahá mimo `files` kroku či úkolu; jen když jsou známé obě strany."""
    flags = []
    for step_id, (run, step) in done.items():
        patterns, changed = step.get("allowed"), step.get("files")
        if not patterns or changed is None:
            continue
        outside = outside_of(changed, patterns)  # výpočet ujetí sdílí folie (plan_reality)
        if outside:
            flags.append({"code": "files_mismatch", "stepId": step_id, "executionId": run["executionId"],
                          "source": "det", "outside": outside[:FILES_SHOWN],
                          "reason": f"Commit mění {len(outside)} souborů mimo soubory kroku."})
    return flags


def judgment(runs):
    """Všechny příznaky karty v pevném pořadí kódů."""
    done = _newest_done(runs)
    return [*red_twice(runs), *without_evidence(done), *missing_summary(runs), *files_mismatch(done)]
