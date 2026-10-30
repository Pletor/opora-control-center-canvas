"""Měřák karty (`gauge`) a štítek složitosti → profil běhu dělníka (`run`).

Kontrakt: docs/navrhy/2026-10-30-metriky-a-spoustece.md §2 a §3. Čisté funkce bez modelu a bez čtení:
volající (agent-state, assignment, node-brief, snímek srdce) podá fakta, která už načetl. Měřák se
počítá, nikdy neukládá. Body a prahy štítku jsou konstanty na jednom místě níže; kalibrují se z `costUsd`
hotových karet (řez 3).

`profile` je stabilní část (jen struktura karty: kroky, soubory, druhy, riziko, `fanIn`, `card.effort` /
`card.model`), a proto jediná, která smí do zadání běhu. `gauge` k ní přidá živé metriky (postup, dod, běhy, stáří).
"""
import re
from datetime import datetime

from backend.canvas.card_dag import CARD_KINDS, next_edges
from backend.canvas.opora_card_done import REQUIREMENTS

# Body štítku (§3): průhledný součet, každá položka se stropem.
POINTS = {"step": 1.0, "stepsMax": 12, "file": 0.5, "filesMax": 10, "heavyKind": 2.0,
          "elevated": 3.0, "critical": 6.0, "fanIn": 1.0, "fanInMax": 3}
HEAVY_KINDS = ("design", "research")
# Prahy: štítek platí do svého stropu včetně; nad posledním je XL.
THRESHOLDS = (("XS", 3), ("S", 6), ("M", 10), ("L", 15))
XL = "XL"
LABELS = (*(label for label, _ in THRESHOLDS), XL)
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Štítek → úsilí, dělník, poradce (O10, docs/brain-heart-orchestrator.md §12); XL se nepředává.
BY_LABEL = {"XS": ("low", "sonnet", None), "S": ("medium", "sonnet", "opus"), "M": ("high", "sonnet", "opus"),
            "L": ("xhigh", "sonnet", "opus"), XL: (None, None, None)}
# `card.effort` od srdce nebo člověka → dělník a poradce podle tabulky O10.
BY_EFFORT = {"low": ("sonnet", None), "medium": ("sonnet", "opus"), "high": ("sonnet", "opus"),
             "xhigh": ("sonnet", "opus"), "max": ("opus", None)}
RISKS = ("standard", "elevated", "critical")
# Chudé podklady (≤ 1 krok a 0 souborů): štítek se nevydává, běh se vezme z karty, jinak bezpečný výchozí stav.
UNKNOWN = "?"
THIN_STEPS = 1
DEFAULT_RUN = ("medium", "sonnet", "opus")
THIN_REASON = "málo podkladů – doplň kroky a soubory"
# Riziko z textu karty, když chybí soubory. Pravidla review kódu (`opora_review_jobs.toml`) mají jen globy cest, takže
# klíčové slovo globu (`migrations`, `schema`, `auth`, `secret`) se převádí na slova, kterými ho karta píše česky
# i anglicky; signál platí jen tehdy, když jeho slovo v pravidlech skutečně je, a dá nejvýš `elevated`.
TEXT_SIGNALS = (("migrations", "migrace", r"migra[cčt]"),
                ("schema", "schéma", r"sch[eé]ma"),
                ("auth", "RLS", r"\brls\b|row[- ]level security"),
                ("auth", "auth", r"\bauth(?!or)"),
                ("auth", "oprávnění", r"oprávněn|permission"),
                ("secret", "secret", r"secret|tajemstv"))
ENDED_WITHOUT_RESULT = ("released", "cancelled", "revoked")


def plan_of(steps):
    """`{steps, files, kinds}` z přijatých `spec.steps`: počet kroků, sjednocené soubory, počty druhů."""
    files, kinds = set(), {}
    for step in steps or []:
        files.update(item for item in step.get("files") or [] if isinstance(item, str))
        kind = step.get("kind")
        if kind:
            kinds[kind] = kinds.get(kind, 0) + 1
    return {"steps": len(steps or []), "files": sorted(files), "kinds": dict(sorted(kinds.items()))}


def text_of(node, steps):
    """Text karty pro signály rizika: název, popis (`purpose`) a `acceptance` kroků."""
    parts = [(node or {}).get("name"), (node or {}).get("purpose")]
    parts += [item for step in steps or [] for item in step.get("acceptance") or []]
    return " ".join(item for item in parts if isinstance(item, str))


def text_signals(text, config):
    """Signály citlivých cest v textu karty (`TEXT_SIGNALS`, jen slova přítomná v globech pravidel), bez opakování."""
    globs = " ".join([*config["sensitive"], *config.get("security", {}).get("paths", [])]).lower()
    lowered, found = (text or "").lower(), []
    for word, signal, pattern in TEXT_SIGNALS:
        if word in globs and signal not in found and re.search(pattern, lowered):
            found.append(signal)
    return found


def evidence_of(plan):
    """`thin`, když karta má nejvýš jeden krok a žádný soubor (měřák nemá z čeho měřit), jinak `ok`."""
    return "thin" if plan["steps"] <= THIN_STEPS and not plan["files"] else "ok"


def risk_of(files, config=None, text=""):
    """Riziko zásahu nad `files` (standard / elevated / critical) z pravidel review kódu (opora_review_risk):
    citlivá cesta (`risk.sensitive`, vždy vyžaduje člověka) = critical; bezpečnostní cesta (`security.paths`)
    nebo aspoň `medium_files` souborů = elevated. `classify_risk` čte záznam návrhu, ne soubory (odchylka §7).
    Bez souborů rozhoduje `text` karty (`text_signals`): shoda dá nejvýš elevated, critical dávají jen soubory."""
    from backend.canvas import opora_review_risk as review_risk

    config = review_risk.load() if config is None else config
    if not files:
        reasons = ["text: " + signal for signal in text_signals(text, config)]
        return {"level": "elevated" if reasons else "standard", "reasons": reasons}
    sensitive = sorted({glob for glob in config["sensitive"] for path in files if review_risk.matches(glob, path)})
    if sensitive:
        return {"level": "critical", "reasons": ["sensitive_path:" + glob for glob in sensitive]}
    security = sorted({glob for glob in config.get("security", {}).get("paths", [])
                       for path in files if review_risk.matches(glob, path)})
    reasons = ["security_path:" + glob for glob in security]
    if len(files) >= config["mediumFiles"]:
        reasons.append("many_files")
    return {"level": "elevated" if reasons else "standard", "reasons": reasons}


def graph_index(graph):
    """Jednou na graf: `fanIn` / `fanOut` (vazby `next` mezi kartami) a děti karet (`parentId`)."""
    pairs = next_edges(graph)
    fan_in, fan_out, children = {}, {}, {}
    for source, target in pairs:
        fan_out[source] = fan_out.get(source, 0) + 1
        fan_in[target] = fan_in.get(target, 0) + 1
    for node in graph.get("nodes", []):
        if node.get("kind") in CARD_KINDS and node.get("parentId"):
            children.setdefault(node["parentId"], []).append(node["id"])
    return {"fanIn": fan_in, "fanOut": fan_out, "children": children,
            "nodes": {node["id"]: node for node in graph.get("nodes", [])}}


def split_of(index, node):
    """`{children, depth}`: přímé děti karty a hloubka jejího podstromu (0 = nerozpadlá)."""
    depth, layer, seen = 0, list(index["children"].get(node, [])), {node}
    while layer:
        depth += 1
        seen.update(layer)
        layer = [child for item in layer for child in index["children"].get(item, []) if child not in seen]
    return {"children": len(index["children"].get(node, [])), "depth": depth}


def points_of(plan, risk, fan_in):
    """Součet bodů §3 a jeho rozpis (stejné klíče jako `POINTS` bez stropů)."""
    heavy = sum(count for kind, count in plan["kinds"].items() if kind in HEAVY_KINDS)
    parts = {"steps": min(plan["steps"], POINTS["stepsMax"]) * POINTS["step"],
             "files": min(len(plan["files"]) * POINTS["file"], POINTS["filesMax"]),
             "heavyKinds": heavy * POINTS["heavyKind"],
             "risk": POINTS.get(risk, 0.0),
             "fanIn": min(fan_in, POINTS["fanInMax"]) * POINTS["fanIn"]}
    return sum(parts.values()), parts


def label_of(points):
    return next((label for label, ceiling in THRESHOLDS if points <= ceiling), XL)


def _rank(label=None, effort=None):
    """Stupeň na společné škále štítků a úsilí: XS/low 0 … XL/max 4."""
    return LABELS.index(label) if label is not None else EFFORTS.index(effort)


def _thin_run(points, card):
    """Chudé podklady: štítek „?“, žádné doporučení ani odchylka; běh z `card.effort`/`card.model`, jinak výchozí."""
    chosen = (card or {}).get("effort")
    if chosen in BY_EFFORT:
        model, advisor = BY_EFFORT[chosen]
        run = {"effort": chosen, "model": (card or {}).get("model") or model, "advisor": advisor, "source": "card"}
    else:
        effort, model, advisor = DEFAULT_RUN
        run = {"effort": effort, "model": (card or {}).get("model") or model, "advisor": advisor, "source": "default",
               "reason": THIN_REASON}
    return {"label": UNKNOWN, "points": points, **run, "recommended": None, "evidence": "thin",
            "handout": True, "humanReview": False}


def run_of(points, risk, card=None, evidence="ok"):
    """Profil běhu `{label, points, effort, model, advisor, source, evidence, handout, humanReview}` (+ `recommended`
    a `mismatch`, když rozhodl `card.effort`). `risk == critical` vždy vynutí poradce opus a review člověka.
    Při `evidence == thin` se štítek nevydává (`_thin_run`)."""
    if evidence == "thin":
        run = _thin_run(points, card)
        if risk == "critical":
            run.update(advisor="opus", humanReview=True)
        return run
    label = label_of(points)
    effort, model, advisor = BY_LABEL[label]
    run = {"label": label, "points": points, "effort": effort, "model": model, "advisor": advisor,
           "source": "recommended", "evidence": "ok", "handout": label != XL, "humanReview": False}
    chosen = (card or {}).get("effort")
    if chosen in BY_EFFORT:
        model, advisor = BY_EFFORT[chosen]
        run.update(recommended={"label": label, "effort": effort, "model": BY_LABEL[label][1], "advisor": BY_LABEL[label][2]},
                   effort=chosen, model=(card or {}).get("model") or model, advisor=advisor, source="card",
                   handout=True, mismatch=abs(_rank(label=label) - _rank(effort=chosen)) > 1)
    if risk == "critical":
        run.update(advisor="opus", humanReview=True)
    return run


def profile(node, graph, steps, index=None, config=None):
    """Stabilní profil běhu karty `node` (uzel grafu) z jejích přijatých kroků a grafu: do zadání a node-brief.
    Bez stáří a ceny, takže se během běhu nemění."""
    index = graph_index(graph) if index is None else index
    plan = plan_of(steps)
    risk = risk_of(plan["files"], config, text_of(node, steps))
    points, _ = points_of(plan, risk["level"], index["fanIn"].get(node["id"], 0))
    return run_of(points, risk["level"], node.get("card"), evidence_of(plan))


def brief(run):
    """Stabilní část pro zadání a node-brief: `{label, effort, model, advisor}` (+ `handout`, `humanReview`)."""
    return {key: run[key] for key in ("label", "effort", "model", "advisor", "handout", "humanReview")}


def tag(run):
    """Krátký štítek pro snímek srdce: `[S · sonnet+opus]`; XL a odchylku zvýrazní."""
    if run.get("evidence") == "thin":
        return f"[{UNKNOWN} – doplň kroky a soubory]"
    if not run["handout"]:
        return "[XL – nepředávat, rozděl]"
    worker = run["model"] + (f"+{run['advisor']}" if run["advisor"] else "")
    text = f"{run['label']} · {worker}"
    if run.get("mismatch"):
        text += f" · ODCHYLKA: karta {run['effort']}, doporučeno {run['recommended']['label']}"
    return f"[{text}]"


def tally(history, linked=()):
    """`{nodeId: {attempts, failures, claimedAt}}` z historie běhů (od nejnovějšího, `Executions.history`).
    Selhání = běh skončený bez výsledku (released / cancelled / revoked), který nepatří k PR (sloučení PR běh
    také uvolní). `claimedAt` je čas claimu nejnovějšího běhu."""
    pulled = {item.get("executionId") for item in linked or [] if item.get("state") in ("open", "merged")}
    result = {}
    for record in history:
        entry = result.setdefault(record["nodeId"], {"attempts": 0, "failures": 0, "claimedAt": record.get("createdAt")})
        entry["attempts"] += 1
        if record.get("state") in ENDED_WITHOUT_RESULT and record.get("executionId") not in pulled:
            entry["failures"] += 1
    return result


def _seconds(value):
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def _percent(done, total):
    return round(100 * done / total) if total else 0


def gauge(entry, node, steps, index, runs, latest, now, config=None, cost=None):
    """Měřák jedné karty agent-state: `entry` nese `steps` a `dod` (plan_steps.attach), `node` uzel grafu,
    `steps` přijaté kroky, `runs` záznam `tally`, `latest` nejnovější běh z agent-state (nebo None)."""
    plan = plan_of(steps)
    risk = risk_of(plan["files"], config, text_of(node, steps))
    evidence = evidence_of(plan)
    fan_in = index["fanIn"].get(entry["nodeId"], 0)
    points, parts = points_of(plan, risk["level"], fan_in)
    progress, dod = entry.get("steps") or {}, entry.get("dod") or {}
    total, done = progress.get("total", 0), progress.get("done", 0)
    met = sum(dod.get(name) is True for name in REQUIREMENTS)
    claimed = _seconds((runs or {}).get("claimedAt"))
    active = bool(latest) and latest.get("state") == "running" and latest.get("deadline", 0) > now
    return {"steps": {"total": total, "done": done, "percent": _percent(done, total)},
            "dod": {"met": met, "total": len(REQUIREMENTS), "percent": _percent(met, len(REQUIREMENTS))},
            "files": len(plan["files"]), "kinds": plan["kinds"], "risk": risk, "evidence": evidence,
            "fanIn": fan_in, "fanOut": index["fanOut"].get(entry["nodeId"], 0),
            "split": split_of(index, entry["nodeId"]),
            "attempts": (runs or {}).get("attempts", 0), "failures": (runs or {}).get("failures", 0),
            "age": round(now - claimed) if active and claimed is not None else None,
            "costUsd": cost, "pointsBreakdown": parts,
            "run": run_of(points, risk["level"], (node or {}).get("card"), evidence)}


def attach(entries, graph, documents, runs, latest, now):
    """Agent-state `cards[]` dostanou `gauge`; graf a konfigurace rizika se čtou jednou na dávku, ne na kartu."""
    from backend.canvas import opora_review_risk as review_risk
    from backend.canvas.opora_plan_steps import steps_of

    index, config = graph_index(graph), review_risk.load()
    accepted = {item["nodeId"]: item for item in documents or []}
    newest = {item["nodeId"]: item for item in latest or []}
    return [{**entry, "gauge": gauge(entry, index["nodes"].get(entry["nodeId"]),
                                     steps_of((accepted.get(entry["nodeId"]) or {}).get("fields")),
                                     index, runs.get(entry["nodeId"]), newest.get(entry["nodeId"]), now, config)}
            for entry in entries]
