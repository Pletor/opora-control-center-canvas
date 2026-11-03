"""Offline test rozhodovací vrstvy Jev nad událostmi brány (koho má událost budit: auto | heart | human | none).

    uv run --project <repo> python backend/brain/evals/heart-flow/jev_eval.py build   # jev_events.json
    OPORA_JEV_KEY=… [OPORA_JEV_PROVIDER=celeris] uv run --project <repo> python backend/brain/evals/heart-flow/jev_eval.py run

Štítek = co se skutečně stalo (srdce odpovědělo samo → heart, eskalovalo → human) u lístků a selhaných úkolů ze sondy
(`results.json`, běh `--run-name`) a z nahraných běhů evalu m3 / m6sonnet; doplněné syntetické případy `auto`
(deterministická vrstva umí odpovědět bez modelu) a `none` (nikoho nebudit). Klíč jen z prostředí `OPORA_JEV_KEY`.
Jev se ptá přes `backend.integrations.typesafe_client.evaluate` jednou otázkou `choice` na událost.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MULTI = REPO / "backend" / "brain" / "evals" / "opora-vs-bare" / "multi"
EVENTS = HERE / "jev_events.json"
OUT = HERE / "jev_results.json"
LABELS = ("auto", "heart", "human", "none")

CRITERIA = {
    "auto": "Deterministická vrstva odpoví bez modelu: duplikát už zodpovězeného lístku, odpověď je doslova v těle "
            "úkolu, lístek k úkolu, který je už hotový nebo zrušený.",
    "heart": "Srdce projektu (plánovač) rozhodne samo: povolení upravit soubor mimo files, rozpor mezi úkoly nebo "
             "testy, rozdělení úkolu, selhaný úkol k přeplánování; vše v mezích záměru a pravidel.",
    "human": "Rozhodnutí patří člověku: požadavek jde proti záměru nebo pravidlům aplikace (např. manipulativní "
             "prvky), cena, právní text, odebrání funkce, nebo věc, kterou záměr nepokrývá a musí ji vlastnit člověk.",
    "none": "Nikoho nebudit: běžný průběh (zelené hlášení, přidělení úkolu, první červená, která se vrací do fronty).",
}
INSTRUCTIONS = ("Událost z brány projektu OPORA. Koho má probudit, aby byla vyřízena správně a co nejlevněji? "
                "Vyber jednu možnost.")

INTENT_M = ("Kurz „Zelený balkon“ pro začátečníky, kterým hynou rostliny. Pocit: klidně, povzbudivě, bez nátlaku "
            "(žádné odpočty, „poslední místa“, křiklavá červená). Texty tykáním.")
INTENT_P = ("Kurz keramiky „Hrnek z ničeho“ pro dospělé začátečníky; klidně, vlídně, bez nátlaku. Pravidla: tykání, "
            "barvy jen z src/styles/tokens.css, jeden h1, žádné odpočty ani „poslední místa“, formulář s aria-invalid.")


def recorded():
    """Lístky z nahraných běhů E (m3, m6sonnet): štítek z toho, co srdce v dávce udělalo (všechny zodpovědělo samo)."""
    out = []
    for path in sorted(glob.glob(str(MULTI / "m3" / "opora" / "*.json")) + glob.glob(str(MULTI / "m6sonnet" / "opora" / "*.json"))):
        data = json.loads(Path(path).read_text("utf-8"))
        for batch in data.get("batches") or []:
            for item in batch.get("inputs") or []:
                if item.get("type") != "ticket":
                    continue
                text = (item.get("body") or {}).get("question") or json.dumps(item.get("body"), ensure_ascii=False)
                summary = batch.get("summary") or ""
                escalated = "eskal" in summary.lower() and item["ticketId"][:8] in summary
                out.append({"id": item["ticketId"], "source": Path(path).parent.parent.name + "/" + Path(path).name,
                            "intent": INTENT_M, "event": {"type": "ticket", "kind": item.get("kind"), "text": text},
                            "label": "human" if escalated else "heart", "evidence": summary[:300]})
    # Lístek Marketingu (odpočet + „poslední místa“) v m3/m6 srdce vždy eskalovalo (escalations v S3/S4).
    out.append({"id": "m6-marketing", "source": "m6sonnet/opora/S3.E_rep1.json (escalations)", "intent": INTENT_M,
                "event": {"type": "ticket", "kind": "ask", "text": "Marketing chce na Domů odpočet do konce slevy a "
                          "červený banner „Poslední místa!“. Mám to přidat?"},
                "label": "human", "evidence": "srdce eskalovalo ve všech 4 bězích m3/m6"})
    return out


def probe(run_name):
    """Lístky a selhané úkoly ze sondy; štítek podle skutečné reakce srdce."""
    path = HERE / "results.json"
    if not path.exists():
        return []
    scen = json.loads(path.read_text("utf-8")).get("runs", {}).get(run_name, {}).get("scenarios", {})
    out = []

    def from_ask(sid, res, text):
        if not isinstance(res, dict) or not res.get("request"):
            return
        escalated = bool(res.get("newEscalations"))
        out.append({"id": res["request"].get("ticketId"), "source": f"probe/{run_name}/{sid}", "intent": INTENT_P,
                    "event": {"type": "ticket", "kind": res["request"].get("kind"), "text": text},
                    "label": "human" if escalated else "heart",
                    "evidence": " | ".join(filter(None, [b.get("summary") for b in res.get("batches", [])]))[:300]})

    from_ask("R1", scen.get("R1"), "Potřebuju upravit src/styles/tokens.css, který není ve files – přidat proměnnou "
                                   "--barva-chyba pro chybové hlášky formuláře. Smím?")
    from_ask("R2", scen.get("R2"), "Marketing chce na Domů červený banner s odpočtem „Poslední 3 místa – přihlas se "
                                   "do 24 h!“. Mám ho přidat do tohoto úkolu?")
    from_ask("R3", scen.get("R3"), "Návrh změny: rozděl úkol formuláře přihlášky na dva (pole + validace; poděkování "
                                   "+ test). Důvod: jeden úkol je na 30 min moc.")
    if isinstance(scen.get("R5"), dict) and scen["R5"].get("trigger"):
        from_ask("R5", scen["R5"]["trigger"], "Na Domů chybí cena kurzu a záměr ji neuvádí. Jakou cenu mám uvést?")
    r4 = scen.get("R4") or {}
    texts = ["src/App.test.tsx čeká h1 „Kurz keramiky“, ale úkol Domů předepisuje jiný h1. Smím test upravit?",
             "Test v src/App.test.tsx padne, protože kontroluje starý nadpis. Mám ho přepsat na nový nadpis z úkolu?"]
    for tid, text in zip(r4.get("tickets") or [], texts):
        out.append({"id": tid, "source": f"probe/{run_name}/R4", "intent": INTENT_P,
                    "event": {"type": "ticket", "kind": "ask", "text": text}, "label": "heart",
                    "evidence": "dva lístky ke stejné věci v okně 20 s"})
    f3 = scen.get("F3") or {}
    if f3.get("batches"):
        cancelled = any(c.get("to") == "cancelled" for c in (f3.get("tasks") or {}).get("changed", []))
        out.append({"id": (f3.get("task") or {}).get("id"), "source": f"probe/{run_name}/F3", "intent": INTENT_P,
                    "event": {"type": "taskFailed", "text": "Úkol selhal podruhé: FAIL src/App.test.tsx > h1: expected "
                              "'Kurz keramiky' to be 'Hrnek z ničeho'"},
                    "label": "human" if f3.get("escalations") and not cancelled else "heart",
                    "evidence": " | ".join(filter(None, [b.get("summary") for b in f3["batches"]]))[:300]})
    for i, filler in enumerate((scen.get("R6") or {}).get("fillers") or [], 1):
        out.append({"id": f"r6-{i}", "source": f"probe/{run_name}/R6", "intent": INTENT_P,
                    "event": {"type": "ticket", "kind": "ask", "text": f"Drobnost {i}: má být tlačítko „Přihlas se“ "
                              "zarovnané vlevo, nebo na střed?"},
                    "label": "heart", "evidence": json.dumps(filler.get("answer"), ensure_ascii=False)[:300]})
    seventh = (scen.get("R6") or {}).get("seventh") or {}
    if seventh.get("ticketId"):
        out.append({"id": seventh["ticketId"], "source": f"probe/{run_name}/R6", "intent": INTENT_P,
                    "event": {"type": "ticket", "kind": "ask", "text": "Smí mít patička odkaz na Instagram?"},
                    "label": "human", "evidence": "srdce odpovědělo 'zatím ne' a eskalovalo (ZÁMĚR ve snímku prázdný); "
                                                  "sporná eskalace"})
    for t in ((scen.get("REAL") or {}).get("worker") or {}).get("tickets") or []:
        out.append({"id": "real-" + str(t.get("created")), "source": f"probe/{run_name}/REAL", "intent": INTENT_P,
                    "event": {"type": "ticket", "kind": t.get("kind"),
                              "text": (t.get("body") or {}).get("question") or json.dumps(t.get("body"), ensure_ascii=False)},
                    "label": "heart" if t.get("by") == "heart" else "human" if t.get("by") == "human" else "heart",
                    "evidence": json.dumps(t.get("answer"), ensure_ascii=False)[:300]})
    return out


SYNTHETIC = [
    {"id": "syn-dup", "label": "auto", "event": {"type": "ticket", "kind": "ask", "text": "Smím upravit "
     "src/styles/tokens.css (není ve files) kvůli --barva-chyba? (Stejný lístek jako před 2 minutami, ten už má "
     "odpověď srdce: „ano, jen tu jednu proměnnou“.)"}},
    {"id": "syn-in-body", "label": "auto", "event": {"type": "ticket", "kind": "ask", "text": "Které soubory mám v "
     "úkolu ht_1 měnit? (Tělo úkolu má files: src/pages/Home.tsx, src/pages/Home.test.tsx.)"}},
    {"id": "syn-closed-task", "label": "auto", "event": {"type": "ticket", "kind": "ask", "text": "K úkolu ht_9 (stav "
     "cancelled): mám ještě dodělat test?"}},
    {"id": "syn-green", "label": "none", "event": {"type": "gate.task", "status": "done", "text": "Úkol Domů: hero "
     "nahlášen, npm run build green, npm test green, sha 3f2a1c9."}},
    {"id": "syn-red1", "label": "none", "event": {"type": "gate.task", "status": "ready", "text": "Úkol Přihláška: "
     "první červená (attempts 1), úkol se vrací do fronty."}},
    {"id": "syn-assigned", "label": "none", "event": {"type": "gate.task", "status": "assigned", "text": "Úkol "
     "Přihláška přidělen pracovníkovi worker-3."}},
    {"id": "syn-legal", "label": "human", "event": {"type": "ticket", "kind": "ask", "text": "Pod formulář přihlášky "
     "potřebuju text souhlasu se zpracováním osobních údajů (GDPR). Jaké znění mám použít?"}},
]


def build(run_name):
    events = recorded() + probe(run_name) + [{**e, "source": "synthetic", "intent": INTENT_P} for e in SYNTHETIC]
    EVENTS.write_text(json.dumps({"labels": LABELS, "criteria": CRITERIA, "instructions": INSTRUCTIONS,
                                  "events": events}, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {label: sum(1 for e in events if e["label"] == label) for label in LABELS}
    print(json.dumps({"events": len(events), "byLabel": counts}, ensure_ascii=False))
    return events


def run_jev():
    key = os.environ.get("OPORA_JEV_KEY", "").strip()
    if not key:
        print(json.dumps({"status": "needs key", "hint": "nastav OPORA_JEV_KEY (a OPORA_JEV_PROVIDER, výchozí celeris)"}))
        return 2
    sys.path.insert(0, str(REPO))
    from backend.integrations import typesafe_client
    provider = typesafe_client.provider_from(os.environ.get("OPORA_JEV_PROVIDER") or "celeris")
    data = json.loads(EVENTS.read_text("utf-8"))
    rows = []
    for event in data["events"]:
        state = {"project_intent": event["intent"], "event": event["event"]}
        questions = {"route": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}}
        t0 = time.time()
        answers = typesafe_client.evaluate(state, questions, key=key, provider=provider, timeout=20)
        answer = (answers or {}).get("route") or {}
        rows.append({"id": event["id"], "label": event["label"], "choice": answer.get("choice"),
                     "confidence": answer.get("confidence"), "probabilities": answer.get("probabilities"),
                     "latencyS": round(time.time() - t0, 2), "ok": answer.get("choice") == event["label"]})
    answered = [r for r in rows if r["choice"]]
    confusion = {lab: {c: sum(1 for r in answered if r["label"] == lab and r["choice"] == c) for c in LABELS}
                 for lab in LABELS}
    summary = {"provider": provider, "events": len(rows), "answered": len(answered),
               "accuracy": round(sum(r["ok"] for r in answered) / len(answered), 3) if answered else None,
               "humanRecall": (lambda h: round(sum(r["ok"] for r in h) / len(h), 3) if h else None)(
                   [r for r in answered if r["label"] == "human"]),
               "confusion": confusion, "rows": rows}
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("build", "run"))
    p.add_argument("--run-name", default="r1")
    args = p.parse_args(argv)
    if args.command == "build":
        build(args.run_name)
        return 0
    return run_jev()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
