"""Folie z kódu (F1, docs/navrhy/2026-11-11-platno-3-folie.md): co karta v kódu čeká proti tomu, co v něm opravdu je.

Bez modelu. Očekávání = `steps[].files`, `sourceRef` karty a potomků (`commit_pairs.owned_paths`) a výsledky toku
prvku plátna 2 (`flow.outputs`, `dataTo`). Skutečnost = commity karty (trailer `Opora-Node` přes `commit_pairs`,
commity úkolů Linie karty přes `trace_git.commits`), jejich soubory a symboly z rozdílu commitu (Python `ast`, jinak
`trace_git.SYMBOL`) a `# OP-…` značky (`trace_git.code`). `compare` je čistá; `card` čte git a pamatuje si výsledek,
dokud se nezmění commity karty, její práce v Linii ani očekávání. Symboly z rozdílu: `plan_reality_code`.
"""
import os
import re
import unicodedata
from fnmatch import fnmatchcase

from backend.agi_pletor.linie import gitsnap, trace_git
from backend.canvas import commit_pairs
from backend.canvas.plan_reality_code import changes
from backend.flow import library
from database.repositories.tickets import TicketStore

# Plátno logiky ze skenu má čitelná id uzlů (`scan-flow.ts`); předpona → seznam toku prvku.
FLOW_PREFIX = {"vstup": "inputs", "podminka": "conditions", "krok": "steps", "vystup": "outputs", "data": "dataTo"}
LOG_LIMIT = 500  # shortcut: trailery hledá jen v posledních 500 commitech; starší karta folii ztratí, pak --grep na kartu
DIFF = ("--format=", "--no-color", "--no-ext-diff", "-M", "--diff-merges=first-parent", "--unified=100000")
INDEX, CARDS = {}, {}  # repozitář → (otisk referencí, index trailerů); (repozitář, karta) → (klíč, folie)


def allowed_path(path, patterns):
    """Soubor patří do `files` kroku: přesná cesta, glob (`*` i přes `/`) nebo složka končící `/`."""
    for pattern in patterns:
        text = str(pattern).replace("\\", "/")
        if path == text or fnmatchcase(path, text) or (text.endswith("/") and path.startswith(text)):
            return True
        if text.endswith("/**") and path.startswith(text[:-2]):
            return True
    return False


def outside(paths, patterns):
    """Cesty mimo vzory (ujetí); sdílí ho `card_trail_judgment.files_mismatch`."""
    return [path for path in paths if not allowed_path(path, patterns)]


def flow_lists(flow):
    """Seznamy toku prvku (`inputs`, `conditions`, `steps`, `outputs`, `dataTo`) z uzlů plátna logiky."""
    lists = {key: [] for key in FLOW_PREFIX.values()}
    # shortcut: seznamy jen z id, která píše převzetí skenu (vstup-1, krok-2…); ručně přidané uzly toku se nezařadí.
    for item in (flow or {}).get("nodes") or []:
        key = FLOW_PREFIX.get(str(item.get("id", "")).rsplit("-", 1)[0])
        if key:
            lists[key].append(item.get("notes") or (item.get("params") or {}).get("title") or item["id"])
    return lists


def expectations(node, nodes, steps, flow=None):
    """Co karta v kódu čeká: vzory souborů (kroky, `sourceRef`) a pojmenované výsledky toku prvku plátna 2."""
    files = [(path, f"step:{step.get('id')}") for step in steps or [] for path in step.get("files") or []
             if isinstance(path, str)]
    # `sourceRef` je soubor nebo složka bez koncového `/`: složka pokryje potomky.
    files += [(path, "sourceRef") for path in commit_pairs.owned_paths(node, nodes)]
    found, seen = [], set()
    for path, source in files:
        if path not in seen:
            seen.add(path)
            found.append({"kind": "file", "name": path, "path": path, "line": None, "source": source})
    lists = flow_lists(flow)
    return found + [{"kind": "output", "name": name, "path": None, "line": None, "source": f"flow.{key}"}
                    for key in ("outputs", "dataTo") for name in lists[key]]


def _patterns(item):
    return [item["path"], item["path"].rstrip("/") + "/"]


def _norm(text):
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain.lower())


def compare(expected, files, symbols, evidence=None):
    """`{matched, missing, extra, symbols, evidence}`. Soubor commitu ve vzoru = shoda, vzor bez souboru = chybí,
    soubor mimo všechny vzory = navíc. Bez očekávání souborů nic není navíc: soubory jsou jen „co přibylo“.
    Výsledek toku se shoduje, jen když se tak (bez diakritiky, velikosti a oddělovačů) jmenuje změněný symbol."""
    wanted = [item for item in expected if item["kind"] == "file"]
    matched, missing, extra, seen = [], [], [], set()
    for item in wanted:
        hits = [f for f in files if any(allowed_path(p, _patterns(item)) for p in (f["path"], f.get("from")) if p)]
        missing += [] if hits else [item]
        for hit in hits:
            if hit["path"] not in seen:
                seen.add(hit["path"])
                matched.append(hit)
    extra = [f for f in files if f["path"] not in seen] if wanted else []
    names = {_norm(item["name"].rsplit(".", 1)[-1]) for item in symbols}
    for item in expected:
        if item["kind"] == "output":
            (matched if _norm(item["name"]) in names else missing).append(item)
    return {"matched": matched, "missing": missing, "extra": extra,
            "symbols": symbols + ([] if wanted else files), "evidence": evidence}


def counts(result):
    return {key: len(result[key]) for key in ("matched", "missing", "extra")}


def state(result):
    """Tečka K na tváři karty: bad = ujetí, ok = nic nechybí, part jinak; None = karta nemá commity."""
    if result is None or result["evidence"] is None:
        return None
    return "bad" if result["extra"] else "part" if result["missing"] else "ok"


def index(root):
    """`{sha: {at, nodes, marks}}` posledních commitů všech větví s trailery `Opora-Node` / `Opora-Mark`; jeden git,
    dokud se nepohnou reference."""
    mark = gitsnap.state(root)
    kept = INDEX.get(str(root))
    if kept and mark is not None and kept[0] == mark:
        return kept[1]
    out = gitsnap.read(root, "log", "--all", f"-n{LOG_LIMIT}", "--format=%H%x1f%cI%x1f"
                         "%(trailers:key=Opora-Node,valueonly,separator=%x1d)%x1f"
                         "%(trailers:key=Opora-Mark,valueonly,separator=%x1d)%x1e") or ""
    found = {}
    for record in out.split("\x1e"):
        parts = (record.strip("\n").split("\x1f") + ["", "", ""])[:4]  # `strip()` gitu ubere i prázdná pole \x1f
        if parts[1]:
            found[parts[0]] = {"at": parts[1], "nodes": [v for v in parts[2].split("\x1d") if v.strip()],
                               "marks": [v.strip() for v in parts[3].split("\x1d") if v.strip()]}
    INDEX[str(root)] = (mark, found)
    return found


def node_shas(found, node, marks=()):
    """Commity indexu, které se ke kartě hlásí trailerem `Opora-Node` (`commit_pairs`) nebo značkou úkolu karty.
    Cesta bez traileru (slabý důkaz) se nepočítá: složku vlastní víc karet a navíc by se zamíchalo."""
    log = [{"sha": sha, "trailers": {commit_pairs.TRAILER_KEY: item["nodes"]}, "paths": [], "date": item["at"]}
           for sha, item in found.items() if item["nodes"]]
    pair = commit_pairs.pair_for_scope(scope={"kind": "node", "id": node}, spec_revision=0, spec_saved_at=None,
                                       workspace=None, commits=log, owned=[])
    return set(pair["gitCommits"]) | {sha for sha, item in found.items() if set(item["marks"]) & set(marks)}


def card(root, node, works, expected, build=True):
    """Folie karty: `works` = `work` jejích úkolů Linie (`mark`, `baseSha`, `branch`, `headSha`). Výsledek se počítá
    znovu, jen když se změní commity karty v indexu, práce úkolů nebo očekávání. `build=False` jen z paměti (jinak None)."""
    marks = [work["mark"] for work in works if work.get("mark")]
    own = node_shas(index(root), node, marks)
    tasks = tuple((w.get("repository"), w.get("mark"), w.get("baseSha"), w.get("branch"), w.get("headSha")) for w in works)
    key = (tuple(sorted(own)), tasks, repr(expected))
    kept = CARDS.get((str(root), node))
    if kept and kept[0] == key:
        return kept[1]
    if not build:
        return None
    value = _build(root, own, works, expected)
    CARDS[(str(root), node)] = (key, value)
    return value


def _build(root, own, works, expected):
    # OP-EC073F.1: commity karty = trailer Opora-Node + celá práce úkolu Linie (i commity bez značky na jeho větvi).
    found = index(root)
    at = {sha: item["at"] for sha, item in found.items() if sha in own}
    verified, places, where = set(), [], {}
    for work in works:
        # OP-11EC95.3: větve úkolu žijí v `work.repository` (repo Linie), kořen prostoru může být jiný klon.
        repo = work.get("repository") or root
        if not (work.get("mark") and work.get("baseSha") and work.get("branch")) or not os.path.isdir(repo):
            continue
        task = trace_git.commits(repo, work["mark"], work)
        at |= {item["sha"]: item["at"] for item in task}
        where |= {item["sha"]: repo for item in task}
        verified |= {path for item in task for path in item["paths"]}
        places += trace_git.code(repo, work["mark"], work.get("headSha"), verified)
    # Pořadí od nejstaršího: `git log` vypíše potomka vždy před rodičem (čas commitu má jen sekundy); commit mimo
    # index je starší než celý index.
    order = {sha: position for position, sha in enumerate(found)}
    shas = sorted(at, key=lambda sha: (sha in order, -order.get(sha, 0), at[sha]))
    files, symbols = changes([(sha, gitsnap.frozen(where.get(sha, root), "show", *DIFF, sha) or "") for sha in shas])
    # `# OP-…` značka doplní symbol o důvod; místo bez změněného symbolu je samo položkou fixy.
    for place in places:
        hit = next((s for s in symbols if s["path"] == place["path"] and s["name"].split(".")[-1] == place["symbol"]),
                   None)
        if hit:
            hit["note"] = place["text"]
        else:
            symbols.append({"kind": "symbol", "name": place["symbol"] or f"{place['path']}:{place['line']}",
                            "path": place["path"], "line": place["line"], "source": "mark", "note": place["text"]})
    evidence = {"commit": shas[-1], "at": at[shas[-1]]} if shas else None
    return compare(expected, files, symbols, evidence)


def element_of(node, nodes, edges):
    """Prvek plátna 2 karty: uzel sám (`element`), jinak cíl její vazby „dokládá“ (`evidences`) na prvek; jinak None."""
    # OP-A85582.1: karta plátna 3 (stavba srdcem, `plan_from_page`) nese odkaz na prvek vazbou, ne polem: `element`
    # by z ní udělal architekturu a `sourceRef` je cesta na disku.
    if "element" in node:
        return node
    by_id = {item["id"]: item for item in nodes}
    return next((by_id[edge["target"]] for edge in edges if edge["source"] == node["id"]
                 and edge.get("relation") == "evidences" and "element" in by_id.get(edge["target"], {})), None)


def flow_of(service, project, node):
    """Aktivní (jinak poslední) verze toku prvku plátna 2; uzel, který není prvek (`element`), tok nemá."""
    if not node or "element" not in node:
        return None
    with service.registry_lock:
        found = library.project_flow(service.db, project, node["id"])
    versions = (found or {}).get("versions") or []
    version = next((item for item in versions if item.get("status") == "active"), versions[-1] if versions else None)
    return version and version["graph"]


def facts(service, project, workspace, graph=None, documents=None):
    """Jedno čtení prostoru: uzly a vazby grafu, přijaté kroky po kartách, práce úkolů Linie po kartách. Agent-state
    podá graf a přijatá zadání, která už načetl (jinak by je četl znovu mimo svůj ustálený blok, ~200 ms)."""
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.opora_plan_steps import steps_of

    graph = service.view(project, workspace)["graph"] if graph is None else graph
    if documents is None:
        documents = OporaChangesets(service).context(project, workspace)["acceptedDocuments"]
    with service.reading(project):
        tickets = TicketStore(service.db_for(project), project).list_with_work(workspace)
    works = {}
    for ticket in tickets:
        works.setdefault((ticket.get("machine") or {}).get("cardId"), []).append(ticket["work"])
    return {"nodes": graph["nodes"], "edges": graph["edges"], "steps": {item["nodeId"]: steps_of(item.get("fields")) for item in documents},
            "works": works}


def root_of(service, project, workspace):
    from backend.canvas.card_trail_read import repo_root

    return repo_root(service, project, workspace)


def for_card(service, project, workspace, node, root, known=None, build=True):
    """Folie jedné karty; `ValueError` = uzel v prostoru není. Bez repozitáře None."""
    known = known or facts(service, project, workspace)
    found = next((item for item in known["nodes"] if item["id"] == node), None)
    if found is None:
        raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
    if not root:
        return None
    flow = flow_of(service, project, element_of(found, known["nodes"], known["edges"]))
    expected = expectations(node, known["nodes"], known["steps"].get(node), flow)
    return card(root, node, known["works"].get(node, []), expected, build)


def with_commits(root, known, nodes=None):
    """Id karet, které mají commity (trailer, značka úkolu v indexu, nebo odevzdaná práce úkolu)."""
    found = index(root)
    ids = [item["id"] for item in known["nodes"] if nodes is None or item["id"] in nodes]
    picked = []
    for node in ids:
        works = known["works"].get(node, [])
        if any(work.get("headSha") for work in works) or node_shas(found, node, [w["mark"] for w in works
                                                                                 if w.get("mark")]):
            picked.append(node)
    return picked


def summary(service, project, workspace, root):
    """`{nodeId: {matched, missing, extra}}` jen karet s commity."""
    if not root:
        return {}
    known = facts(service, project, workspace)
    out = {}
    for node in with_commits(root, known):
        result = for_card(service, project, workspace, node, root, known)
        if result and result["evidence"]:
            out[node] = counts(result)
    return out


def attach(service, project, workspace, cards, graph, documents):
    """Agent-state `cards[]` dostanou `mirror` (`state`) a `future` (verdikt F4): jen z paměti (`card`,
    `plan_future.remembered`), studený výpočet stojí na velké větvi ~2 s; paměť plní živá karta, `GET /plan-reality`
    a hlídač, do té doby None."""
    from backend.canvas import plan_future

    root = root_of(service, project, workspace)
    if not root or not cards:
        return [{**entry, "mirror": None, "future": None} for entry in cards]
    known = facts(service, project, workspace, graph, documents)
    picked = set(with_commits(root, known, {entry["nodeId"] for entry in cards}))
    return [{**entry, "mirror": state(for_card(service, project, workspace, entry["nodeId"], root, known, False))
             if entry["nodeId"] in picked else None,
             "future": (plan_future.remembered(root, entry["nodeId"], known["works"].get(entry["nodeId"])) or {}).get("verdict")}
            for entry in cards]
