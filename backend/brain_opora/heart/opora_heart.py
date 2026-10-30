"""Jediný nástroj srdce (docs/brain-heart.md §4), jen standardní knihovna. Jedno volání = jeden záměr.

    python opora_heart.py snapshot
    python opora_heart.py task --title T --do D [--why W] [--file F]… [--done-when C]… [--dont-touch P[@kdo]]…
                               [--rule R]… [--intent I] [--node N] [--order N] [--commit C] [--model M] [--workspace W]
    python opora_heart.py plan --file F [--dry-run] [--no-accept] [--workspace W]
    python opora_heart.py plan --example
    python opora_heart.py workspace --domain NODE [--reuse]
    python opora_heart.py answer --ticket ID --text T
    python opora_heart.py cancel --task ID
    python opora_heart.py escalate --text T
    python opora_heart.py decide --text T [--node N] [--pin] [--workspace W]
    python opora_heart.py rule --text T
    python opora_heart.py done --summary S
    python opora_heart.py ctx tasks|tickets|journal|messages|rules|decisions|tree
    python opora_heart.py ctx plan-of --project P [--workspace W]
    python opora_heart.py run SCRIPT [ARG…]
    python opora_heart.py research --question Q --title T [--target URL|cesta]… [--layer L]… [--fragment F] [--deep]
    python opora_heart.py duel --subject F --a TEXT --b TEXT

Adresa, token srdce, projekt a pracovní prostor jsou v prostředí (OPORA_BASE_URL, OPORA_HEART_TOKEN,
OPORA_PROJECT, OPORA_WORKSPACE); token se nikam nezapisuje. `done` zapíše shrnutí do `last_done.json` v cwd.
Dílna (§3b, cwd = `brain/`): `ctx` zapíše data do `dilna/data/<name>.json` a vypíše jen cestu, počet a velikost;
`run` spustí `dilna/scripts/<SCRIPT>.py` (`python -I`, cwd `dilna/`, 120 s) bez tokenu srdce a klíčů API
ve vlastní skupině procesů (po vypršení zemře celý strom i s pod-voláními `claude`) a zapíše řádek do `dilna/runs.jsonl`.
`plan` (docs/brain-heart-orchestrator.md §3) pošle dávku plánu ze souboru F na `/api/canvas-plan` s čerstvým digestem
a ostrou dávku hned přijme (návrh grafu + přijetí, §3 O2b; `--no-accept` nechá přijetí člověku); `--example` vypíše
platný vzor dávky (tentýž je v prompt.md, část Plán).
Git projekt (docs/brain-heart-orchestrator.md §9 O7): `main` nese jen architekturu (prostředí › doména › stránka) a nic
se v něm nepřijímá; ostrý plán architektury ještě převezme změnu architektury do pracovních prostorů s přijatým plánem
(`adoptArchitectureContext`), jinak by jejich karty nešly převzít. `workspace --domain` založí (s `--reuse` nejdřív
hledá) pracovní prostor = git worktree vázaný na doménu; `--workspace W` u `plan`, `task`, `decide` přepíše prostor
z prostředí. Přijatý plán zapíše prostor do `active_workspace.json` v cwd (`activeWorkspace` ve stavu srdce).
`ctx plan-of --project P [--workspace W]` zapíše plán jiného projektu do `dilna/data/plan-of-<P>.json`.
`research` (§3d, výzkumný stůl) je v `opora_research.py`, `duel` (§3c) v `opora_duel.py` vedle nástroje.
Výstup je jeden JSON na stdout (`snapshot` vypíše text); chyba vypíše `code` a `hint` a skončí nenulovým kódem.
"""
import argparse
import importlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

HEADER = "X-Opora-Gate-Token"
TIMEOUT = 60
LAST_DONE = "last_done.json"
ACTIVE = "active_workspace.json"  # prostor posledního přijatého plánu (kopie brain_files.ACTIVE, nástroj je jen stdlib)
_OPENER = build_opener(ProxyHandler({}))  # loopback bez systémové proxy
DILNA = Path("dilna")
CONTEXTS = ("tasks", "tickets", "journal", "messages", "rules", "decisions", "tree", "plan-of")
LAYERS = ("fe", "be", "db", "api", "cache", "infra", "security", "data", "ops")  # vrstvy výzkumu (§3d)
SCRIPT = re.compile(r"[A-Za-z0-9_-]+\Z")
RUN_TIMEOUT, STDOUT_LIMIT, STDERR_LIMIT = 120, 8000, 2000
# Prostředí skriptu: bez tokenu srdce a adresy (skript OPORU nemění) a bez klíčů API (kopie command.STRIPPED,
# nástroj je jen stdlib).
SCRIPT_STRIPPED = ("OPORA_HEART_TOKEN", "OPORA_BASE_URL", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "CELERIS_API_KEY")
# `-I` nedá cwd do sys.path: zavaděč ho přidá, aby skript našel `rlm.py`, a spustí skript jako __main__.
BOOT = ("import os,runpy,sys;sys.path.insert(0,os.getcwd());sys.argv=sys.argv[1:];"
        "runpy.run_path(sys.argv[0],run_name='__main__')")


class Failure(Exception):
    def __init__(self, payload):
        super().__init__(payload.get("error", ""))
        self.payload = payload


def env(name):
    value = os.environ.get(name, "")
    if not value:
        raise Failure({"error": f"Chybí {name}.", "code": "heart_env_missing",
                       "hint": "Nástroj spouští jen dávka srdce, která prostředí nastaví."})
    return value


def call(method, path, body=None, query=None, actor="heart"):
    """Jedno volání OPORY s tokenem srdce; odmítnutí serveru je `Failure` s jeho `code` a `hint`.
    `actor` = jméno agenta v X-Opora-Actor (duel: strany a soudci jsou různí aktéři, token zůstává srdce)."""
    base = env("OPORA_BASE_URL").rstrip("/")
    url = base + path + ("?" + urlencode(query) if query else "")
    headers = {"Accept": "application/json", "Origin": base, "X-Opora-Actor": f"agent; name={actor}",
               HEADER: env("OPORA_HEART_TOKEN")}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json"
    try:
        with _OPENER.open(Request(url, data=data, headers=headers, method=method), timeout=TIMEOUT) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        try:
            payload = json.loads(error.read() or b"{}")
        except ValueError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        raise Failure(server_failure(error.code, payload)) from None
    except (URLError, OSError) as error:
        raise Failure({"error": f"OPORA neodpovídá: {error}", "code": "server_unreachable",
                       "hint": "Server OPORY neběží nebo je na jiné adrese než OPORA_BASE_URL."}) from None


GENERIC_HINT = "Zkontrolujte argumenty příkazu."
DETAILS = ("field", "expected", "example", "cycle")  # podrobnosti chyby serveru (payload_errors, card_cycle)


def server_failure(status, payload):
    """Odmítnutí serveru jako výstup nástroje: `error`, `status`, `code`, `hint` a podrobnosti pole, když je server dá."""
    payload = payload if isinstance(payload, dict) else {}
    out = {"error": str(payload.get("error") or payload.get("detail") or f"HTTP {status}"), "status": status,
           "code": payload.get("code") or f"http_{status}", "hint": payload.get("hint") or GENERIC_HINT}
    out.update({key: payload[key] for key in DETAILS if key in payload})
    return out


_override = {"workspace": None}  # `--workspace W` jednoho volání (`run` ho nastaví u každého příkazu znovu)


def scope():
    return {"project": env("OPORA_PROJECT"), "workspace": _override["workspace"] or env("OPORA_WORKSPACE")}


def held(value):
    path, _, holder = value.partition("@")
    return {"path": path.strip(), "heldBy": holder.strip() or "jiný úkol"}


def task_payload(args):
    """Tělo `POST /api/brain/tasks` v pevném tvaru úkolu (docs/brain-gate.md §6)."""
    body = {"do": args.do, "why": args.why or "", "files": args.file, "doneWhen": args.done_when,
            "dontTouch": [held(item) for item in args.dont_touch], "commit": args.commit or ""}
    context = {key: value for key, value in (("rules", args.rule), ("intent", args.intent)) if value}
    payload = {**scope(), "title": args.title, "body": {**body, "context": context}}
    if args.model:
        payload["body"]["model"] = args.model
    if args.node:
        payload["nodeId"] = args.node
    if args.order is not None:
        payload["order"] = args.order
    return payload


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def item_payload(item):
    """Přidání položky paměti (`POST /api/desktop-v3/decision|rule`, CAS: `expected` null)."""
    return {**scope(), "id": item["id"], "op": "add", "expected": None, "item": item}


def decision_payload(args):
    """Rozhodnutí srdce v paměti prostoru (DECISION_KEYS); `by: agent`, cesta prázdná."""
    return item_payload({"id": "hd_" + uuid.uuid4().hex, "text": args.text, "pinned": args.pin, "path": "",
                         "nodeId": args.node or "", "createdAt": now(), "by": "agent"})


def rule_payload(args):
    """Pravidlo celé aplikace; `by: agent` (návrh do schválení člověkem) doplní server."""
    return item_payload({"id": "hr_" + uuid.uuid4().hex, "text": args.text, "kind": "must", "scope": "project",
                         "target": ""})


STALE = "změnilo"  # 409 dávky plánu se zastaralým digestem („Plátno se změnilo v jiném okně.“), bez vlastního kódu


def read_plan(path):
    """Obsah `plan` ze souboru: JSON objekt dávky (`nodes`, `edges`, …) podle docs/davka-planu.md."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Failure({"error": f"Soubor plánu nejde přečíst: {error}", "code": "plan_file",
                       "hint": "Ulož plán jako JSON objekt do dilna/out/<jméno>.json (Write) a předej cestu."}) from None
    if not isinstance(value, dict):
        raise Failure({"error": "Plán musí být JSON objekt.", "code": "plan_file",
                       "hint": "Soubor obsahuje objekt {\"nodes\": […], \"edges\": […]} bez obálky digest/project."})
    return value


# Vzor dávky pro srdce: sektor, dvě karty se spec.steps a checks, vazba `next`. Tentýž JSON stojí v prompt.md (část
# Plán); test ho z promptu vytáhne, porovná s tímto a pošle skutečnému `/api/canvas-plan` s dryRun, aby nezastaral.
PLAN_EXAMPLE = {
    "nodes": [
        {"ref": "mvp", "kind": "sector", "parent": None, "name": "MVP seznam úkolů",
         "purpose": "První použitelná verze aplikace."},
        {"ref": "model", "kind": "node", "parent": "mvp", "name": "[task] Třída SeznamUkolu",
         "purpose": "Úkoly v paměti: přidat, smazat, vypsat.", "card": {"layer": "backend", "status": "ready"},
         "spec": {"goal": "ukoly.py má třídu SeznamUkolu s metodami pridat, smazat a seznam.",
                  "non_goals": "Příkazovou řádku řeší karta CLI.", "acceptance": "python -m unittest projde",
                  "steps": [{"id": "s1", "order": 1, "title": "Třída a její testy", "dependsOn": [],
                             "acceptance": ["test_ukoly.py pokrývá pridat, smazat i seznam"]}]},
         "checks": [{"id": "unit", "command": "python -m unittest"}]},
        {"ref": "cli", "kind": "node", "parent": "mvp", "name": "[task] CLI ukoly.py",
         "purpose": "Úkoly z příkazové řádky.", "card": {"layer": "backend", "status": "ready"},
         "spec": {"goal": "python ukoly.py pridat|smazat|seznam volá SeznamUkolu.", "non_goals": "",
                  "acceptance": "python -m unittest projde",
                  "steps": [{"id": "s1", "order": 1, "title": "Argumenty a výstup", "dependsOn": [],
                             "acceptance": ["python ukoly.py seznam vypíše přidaný úkol"]}]},
         "checks": [{"id": "unit", "command": "python -m unittest"}]},
    ],
    "edges": [{"from": "model", "to": "cli", "port": "next"}],
}
PLAN_SHAPE = ("Tvar dávky: `python opora_heart.py plan --example` (sektor, karty node s card, spec.steps a checks, "
              "vazba next); celý kontrakt docs/davka-planu.md §3.")
# Přijetí plánu (docs/brain-heart-orchestrator.md §3 O2b): kroky z agent-state, které z plátna udělají přijatý plán.
GRAPH_PROPOSALS = "/api/oporahub/graph-proposals"
ACCEPT_ROUNDS = 6


def plan_hint(failure, shape=None):
    """Odmítnutí dávky nese vlastní text serveru (a pole), ne obecnou radu: srdce se podle něj opraví samo."""
    payload = failure.payload
    if not 400 <= (payload.get("status") or 0) < 500 or payload.get("hint") not in (None, GENERIC_HINT):
        return
    detail = (f" Pole {payload['field']}: {payload['expected']}."
              if payload.get("field") and payload.get("expected") else "")
    payload["hint"] = (f"Server dávku odmítl: {payload.get('error')}{detail} Oprav soubor a pošli ho s --dry-run. "
                       + (shape or PLAN_SHAPE))


def acceptance_step(action):
    """Krok přijetí plánu, který smí udělat srdce: návrh grafu, přijetí návrhu grafu, výchozí zadání.
    Cizí návrhy zadání a obsahu (`accept` mimo graf) nechává člověku."""
    if action.get("method") != "POST" or not action.get("path"):
        return False
    if action.get("status") != "ready" and action.get("blockReason") != "human_only":
        return False
    verb, path = action.get("verb"), action["path"]
    return (verb in ("propose_graph", "accept_baseline")
            or (verb == "accept" and path.startswith(GRAPH_PROPOSALS + "/") and path.endswith("/accept")))


def accept_plan():
    """Po ostré dávce: kroky přijetí z `GET /api/oporahub/agent-state` jeden po druhém (jako člověk v UI), tokenem
    srdce. `accepted` = žádný krok přijetí nezbyl a pracovní plán se shoduje s přijatým (`heads.workingDiffers`)."""
    steps = []
    for _ in range(ACCEPT_ROUNDS):
        state = call("GET", "/api/oporahub/agent-state", query=scope())
        todo = [action for action in state.get("actions", []) if acceptance_step(action)]
        if not todo:
            if (state.get("heads") or {}).get("workingDiffers"):
                return {"accepted": False, "acceptSteps": steps, "code": "plan_not_accepted",
                        "hint": "Plán na plátně se liší od přijatého a agent-state nenabízí krok přijetí "
                                "(dávka nad už přijatým grafem); nové karty přijme člověk v UI."}
            return {"accepted": True, "acceptSteps": steps}
        action = todo[0]
        try:
            call("POST", action["path"], {**scope(), **(action.get("preconditions") or {})})
        except Failure as failure:
            return {"accepted": False, "acceptSteps": steps, "code": failure.payload.get("code"),
                    "error": failure.payload.get("error"),
                    "hint": f"Přijetí plánu ({action['verb']} {action['path']}) selhalo; karty jsou na plátně, "
                            "přijme je člověk v UI."}
        steps.append(action["verb"])
    return {"accepted": False, "acceptSteps": steps, "code": "plan_accept_loop",
            "hint": f"Přijetí plánu nedoběhlo za {ACCEPT_ROUNDS} kroků; přijme ho člověk v UI."}


def submit_plan(args, retried=False):
    """`plan`: bez přijatého grafu čerstvý digest z `GET /api/view`, pak `POST /api/canvas-plan` a přijetí
    (`accept_plan`); s přijatým grafem přírůstek přes návrh grafu (`submit_addition`). Zastaralý stav zkusí ještě
    jednou; `--no-accept` nechá přijetí člověku; `--example` jen vypíše vzor dávky."""
    if args.example:
        return PLAN_EXAMPLE
    if not args.file:
        raise Failure({"error": "Chybí --file.", "code": "plan_file",
                       "hint": "Ulož plán do dilna/out/<jméno>.json (Write) a předej --file. " + PLAN_SHAPE})
    plan = read_plan(args.file)
    context = call("GET", f"{GRAPH_PROPOSALS}/context", query=scope())
    if context.get("graphManifestId"):
        try:
            return remember(submit_addition(args, plan, context))
        except Failure as failure:
            if failure.payload.get("status") == 409 and "changed" in failure.payload.get("error", "") and not retried:
                return submit_plan(args, retried=True)
            plan_hint(failure, ADDITION_SHAPE)
            raise
    body = {**scope(), "digest": call("GET", "/api/view", query=scope())["digest"], "plan": plan}
    if args.dry_run:
        body["dryRun"] = True
    try:
        result = call("POST", "/api/canvas-plan", body)
    except Failure as failure:
        if failure.payload.get("status") != 409 or STALE not in failure.payload.get("error", ""):
            plan_hint(failure, MAIN_SHAPE if context.get("readOnly") else None)
            raise
        if not retried:
            return submit_plan(args, retried=True)
        failure.payload.update(code="stale", hint="Plátno se mění pod rukama; načti snapshot a pošli plán znovu.")
        raise
    out = {key: result.get(key) for key in ("ok", "dryRun", "refs", "summary", "warnings")}
    if args.dry_run:
        return out
    if context.get("readOnly"):
        # main git projektu: jen architektura, přijetí tu neexistuje (návrh grafu chce zapisovatelný prostor).
        out["warnings"] = list(out["warnings"] or [])
        return {**out, "architecture": True, "adopted": adopt_everywhere(out["warnings"])}
    return remember({**out, **({"accepted": False} if args.no_accept else accept_plan())})


MAIN_SHAPE = ("V main git projektu jde jen architektura (prostředí › doména = sektor se site.kind application › "
              "stránka se site.kind page). Karty plánuj v pracovním prostoru domény: workspace --domain <nodeId> "
              "--reuse, pak plan --file F --workspace <W>.")


def remember(out):
    """Přijatý plán zapíše svůj prostor do `active_workspace.json` v cwd (`brain/`); stav srdce ho vrací jako
    `activeWorkspace` a kancelář jde za ním."""
    if out.get("accepted") is True:
        Path(ACTIVE).write_text(json.dumps({"workspace": scope()["workspace"], "at": now()}, ensure_ascii=False),
                                encoding="utf-8")
    return out


def adopt_architecture(context):
    """Pracovní prostor s přijatým plánem převezme změněnou architekturu (`adoptArchitectureContext`, jako volba
    „převzít architekturu“ v UI úprav plánu): návrh změn grafu a jeho přijetí tokenem srdce. Bez toho se pracovní graf
    liší od přijatého a žádná karta prostoru nejde převzít. Vrací čerstvý kontext návrhů."""
    proposal = call("POST", GRAPH_PROPOSALS, {**scope(), "parentRevision": context["acceptedHead"],
                                              "expectedGraphDigest": context["graphDigest"],
                                              "subject": "Srdce převzalo architekturu z main",
                                              "plan": {"adoptArchitectureContext": True}})
    call("POST", f"{GRAPH_PROPOSALS}/{quote(proposal['id'], safe='')}/accept",
         {**scope(), "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
          "adoptBaseGraphDigest": None, "reviewedChangesId": proposal["id"]})
    return call("GET", f"{GRAPH_PROPOSALS}/context", query=scope())


def stale_architecture(context):
    """Má prostor přijatý plán a architekturu jinou, než s jakou byl přijat?"""
    return bool(context.get("graphManifestId")) and bool((context.get("architectureContext") or {}).get("differs"))


def adopt_everywhere(warnings):
    """Po ostrém plánu architektury v main: každý pracovní prostor projektu s přijatým plánem a jinou architekturou ji
    převezme. Vrací ID převzatých prostorů; selhání jde do `warnings` (plán architektury už platí)."""
    adopted, keep = [], _override["workspace"]
    for space in call("GET", "/api/view", query=scope()).get("workspaces") or []:
        _override["workspace"] = space["id"]
        try:
            context = call("GET", f"{GRAPH_PROPOSALS}/context", query=scope())
            if stale_architecture(context):
                adopt_architecture(context)
                adopted.append(space["id"])
        except Failure as failure:
            warnings.append(f"Prostor {space['id']}: architekturu nepřevzal ({failure.payload.get('error')}); "
                            "převezme ji příští plan --workspace v něm.")
        finally:
            _override["workspace"] = keep
    return adopted


# Přírůstek nad přijatým grafem (O2c): stejná cesta jako formulář „Rozšíření plánu“ v UI (frontend/hub/graph-proposals).
# Návrh grafu umí jen tato pole uzlu a jen vazby `next`; `card` a `checks` z dávky se do přírůstku nepřenesou.
ADDITION_KEYS = {"ref", "kind", "name", "parent", "purpose", "size", "position", "sourceRef", "spec", "memberOf"}
ADDITION_DROPPED = ("card", "checks")
ADDITION_EDGE_KEYS = {"from", "to", "port", "carries"}
ADDITION_SHAPE = ("Plán nad už přijatým grafem jde jako návrh grafu: uzel jen s poli ref, kind (node|sector|area), "
                  "name, parent, purpose, spec, sourceRef, position, size, memberOf; vazby jen next (from, to); "
                  "nic dalšího (text, bloky, pravidla, rozhodnutí). Existující uzel odkazuj \"@<id>\".")


def addition_plan(plan):
    """Dávka → plán návrhu grafu. Vrací (plán, vynechaná pole); jiná pole odmítne česky, než je odmítne server."""
    if not set(plan) <= {"nodes", "edges"}:
        raise Failure({"error": f"Přírůstek plánu neumí {', '.join(sorted(set(plan) - {'nodes', 'edges'}))}.",
                       "code": "plan_shape", "hint": ADDITION_SHAPE})
    nodes, dropped = [], set()
    for index, node in enumerate(plan.get("nodes") or []):
        if not isinstance(node, dict):
            raise Failure({"error": f"nodes[{index}] není objekt.", "code": "plan_shape", "hint": ADDITION_SHAPE})
        extra = set(node) - ADDITION_KEYS - set(ADDITION_DROPPED)
        if extra or node.get("kind") not in ("node", "sector", "area"):
            what = f"neznámé pole {', '.join(sorted(extra))}" if extra else f"druh {node.get('kind')!r}"
            raise Failure({"error": f"nodes[{index}]: {what}.", "code": "plan_shape", "hint": ADDITION_SHAPE})
        dropped |= set(node) & set(ADDITION_DROPPED)
        nodes.append({key: value for key, value in node.items() if key in ADDITION_KEYS})
    edges = []
    for index, edge in enumerate(plan.get("edges") or []):
        if not isinstance(edge, dict) or not set(edge) <= ADDITION_EDGE_KEYS or edge.get("port", "next") != "next":
            raise Failure({"error": f"edges[{index}]: jen vazba next (from, to).", "code": "plan_shape",
                           "hint": ADDITION_SHAPE})
        edges.append(edge)
    return {"nodes": nodes, "edges": edges}, sorted(dropped)


def submit_addition(args, plan, context):
    """Plán nad přijatým grafem: `POST /api/oporahub/graph-proposals` s přírůstkem, pak jeho přijetí tokenem srdce.
    Karty vzniknou na plátně až přijetím, takže pracovní a přijatý graf se nerozejdou a claimy ostatních karet platí."""
    addition, dropped = addition_plan(plan)
    warnings = [f"Pole {', '.join(dropped)} se do přírůstku nad přijatým grafem nepřenáší."] if dropped else []
    adopted = []
    if not args.dry_run and not args.no_accept and stale_architecture(context):
        context, adopted = adopt_architecture(context), ["adopt_architecture", "accept"]
    if args.dry_run:
        # Návrh grafu nemá dryRun: tvar ověří stejná validace dávky plánu bez zápisu.
        result = call("POST", "/api/canvas-plan", {**scope(), "digest": context["graphDigest"], "plan": addition,
                                                    "dryRun": True})
        return {"ok": result.get("ok"), "dryRun": True, "refs": result.get("refs"), "summary": result.get("summary"),
                "warnings": [*warnings, *(result.get("warnings") or [])], "path": "graph-proposal"}
    proposal = call("POST", GRAPH_PROPOSALS, {**scope(), "parentRevision": context["acceptedHead"],
                                              "expectedGraphDigest": context["graphDigest"],
                                              "subject": f"Plán srdce: {len(addition['nodes'])} uzlů", "plan": addition})
    out = {"ok": True, "dryRun": False, "refs": proposal.get("refs"), "proposalId": proposal["id"],
           "summary": f"Návrh grafu: {len(addition['nodes'])} uzlů, {len(addition['edges'])} vazeb.",
           "warnings": warnings, "path": "graph-proposal"}
    if args.no_accept:
        return {**out, "accepted": False}
    try:
        call("POST", f"{GRAPH_PROPOSALS}/{quote(proposal['id'], safe='')}/accept",
             {**scope(), "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
              "adoptBaseGraphDigest": None})
    except Failure as failure:
        return {**out, "accepted": False, "acceptSteps": [*adopted, "graph_addition"], "code": failure.payload.get("code"),
                "error": failure.payload.get("error"),
                "hint": "Návrh grafu čeká na přijetí (plátno se mezitím změnilo, nebo chybí oprávnění); "
                        "přijme ho člověk v UI, nebo pošli plán znovu."}
    return {**out, "accepted": True, "acceptSteps": [*adopted, "graph_addition", "accept"]}


def load_context(name, of=None, of_workspace=None):
    """`ctx <name>`: data z OPORY do `dilna/data/<name>.json`; vrací jen cestu, počet položek a velikost.
    `plan-of` čte plán projektu `of` (prostor `of_workspace`, jinak main git / draft lokálního) do `plan-of-<of>.json`."""
    query = {**scope(), "name": name}
    if name == "plan-of":
        if not of or not SCRIPT.match(of):
            raise Failure({"error": "ctx plan-of potřebuje --project <id>.", "code": "plan_of_project",
                           "hint": "ID projektu je v GET /api/bootstrap; prostor volitelně --workspace <id>."})
        query.update({"of": of, **({"ofWorkspace": of_workspace} if of_workspace else {})})
        name = f"plan-of-{of}"
    items = call("GET", "/api/brain/heart/context", query=query)["items"]
    path = DILNA / "data" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(items, ensure_ascii=False).encode("utf-8")
    path.write_bytes(raw)
    return {"path": path.as_posix(), "items": len(items), "bytes": len(raw)}


def _cut(text, limit):
    return text if len(text) <= limit else text[:limit] + f"\n… (zkráceno, celkem {len(text)} znaků)"


def _sub_usage(log):
    calls = cost = 0
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0, 0.0
    for line in lines:
        try:
            cost += float(json.loads(line).get("costUsd") or 0)
            calls += 1
        except (ValueError, AttributeError, TypeError):
            continue
    return calls, round(cost, 6)


def _group():
    """Skript ve vlastní skupině procesů, ať po vypršení jde zabít celý strom (§3b)."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def kill_tree(process):
    """Zabije proces i všechny jeho potomky (pod-volání `claude` z `rlm.py`); na Windows `taskkill /T`."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=30, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()  # pojistka, kdyby strom už nebyl celý


def _execute(argv, cwd, env, timeout=None, input_text=None):
    """`(exit, stdout, stderr, timedOut)`; po `timeout` (výchozí `RUN_TIMEOUT`) zabije strom a dočte, co proces stihl vypsat.
    `input_text` jde na stdin (zadání výzkumníka a pod-volání duelu)."""
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               stdin=subprocess.DEVNULL if input_text is None else subprocess.PIPE,
                               encoding="utf-8", errors="replace", **_group())
    try:
        out, err = process.communicate(input=input_text, timeout=RUN_TIMEOUT if timeout is None else timeout)
        return process.returncode, out, err, False
    except subprocess.TimeoutExpired:
        kill_tree(process)
        try:
            out, err = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:  # roura drží ještě někdo jiný; výstup oželíme
            out, err = "", ""
        return None, out, err, True


def log_run(script, script_args, exit_code, ms, calls, cost):
    """Řádek do `dilna/runs.jsonl` (běh skriptu, výzkum, duel); dávka z něj sečte `subCostUsd` do deníku."""
    entry = {"at": now(), "script": script, "args": list(script_args), "exit": exit_code, "ms": ms,
             "subCalls": calls, "subCostUsd": round(cost, 6)}
    DILNA.mkdir(parents=True, exist_ok=True)
    with (DILNA / "runs.jsonl").open("a", encoding="utf-8") as runs:
        runs.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def research_module(name="opora_research"):
    """`opora_research.py` / `opora_duel.py`: kopie vedle nástroje v `brain/`, v testech modul balíčku."""
    try:
        return importlib.import_module(name)
    except ImportError:
        return importlib.import_module(f"backend.brain_opora.heart.{name}")


def run_script(script, script_args):
    """`run <script>`: skript dílny v odděleném prostředí; výsledek a řádek do `dilna/runs.jsonl`."""
    if not SCRIPT.match(script):
        raise Failure({"error": f"Neplatné jméno skriptu {script!r}.", "code": "script_name",
                       "hint": "Jméno bez přípony a cesty, jen písmena, číslice, _ a -; skript leží v dilna/scripts/."})
    dilna = DILNA.resolve()
    if not (dilna / "scripts" / f"{script}.py").is_file():
        raise Failure({"error": f"Skript {script}.py neexistuje.", "code": "script_missing",
                       "hint": "Napiš ho nástrojem Write do dilna/scripts/<jméno>.py (první řádek docstringu = co dělá)."})
    log = dilna / f".sub-{uuid.uuid4().hex}.jsonl"
    env = {key: value for key, value in os.environ.items() if key not in SCRIPT_STRIPPED}
    env.update({"OPORA_RLM_LOG": str(log), "PYTHONIOENCODING": "utf-8"})
    env.pop("OPORA_RLM_DEPTH", None)
    started = time.time()
    exit_code, out, err, timed_out = _execute([sys.executable, "-I", "-c", BOOT, f"scripts/{script}.py", *script_args],
                                              str(dilna), env)
    ms = int((time.time() - started) * 1000)
    calls, cost = _sub_usage(log)
    log.unlink(missing_ok=True)
    entry = log_run(script, script_args, exit_code, ms, calls, cost)
    result = {**entry, "stdout": _cut(out or "", STDOUT_LIMIT)}
    if err:
        result["stderr"] = (err or "")[-STDERR_LIMIT:]
    if timed_out:
        result["timedOut"] = True
    return result


def open_workspace(domain, reuse):
    """`workspace --domain NODE [--reuse]`: pracovní prostor (git worktree větve `work/<id>`) vázaný na doménu
    architektury; s `--reuse` vrátí existující prostor téže domény, když je. `POST /api/workspaces` tokenem srdce."""
    project = env("OPORA_PROJECT")
    spaces = call("GET", "/api/view", query={"project": project, "workspace": "main"}).get("workspaces") or []
    found = next((space for space in spaces if space.get("node_id") == domain), None) if reuse else None
    created = found is None
    if created:
        try:
            found = call("POST", "/api/workspaces", {"project": project, "nodeId": domain, "actor": "heart"})
        except Failure as failure:
            if failure.payload.get("hint") == GENERIC_HINT:
                failure.payload["hint"] = ("--domain je ID sektoru domény (site.kind application) z architektury "
                                           "v main; doménu postav nejdřív plánem v main.")
            raise
    return {"workspace": found["id"], "branch": found.get("branch"), "domain": found.get("node_id"),
            "created": created}


def run(args):
    project = env("OPORA_PROJECT")
    # `--workspace` jen u plan, task a decide; u ctx je to prostor cizího plánu (plan-of), ne přepis prostoru srdce
    _override["workspace"] = getattr(args, "workspace", None) if args.command in ("plan", "task", "decide") else None
    if args.command == "ctx":
        return load_context(args.name, args.project, args.workspace)
    if args.command == "workspace":
        return open_workspace(args.domain, args.reuse)
    if args.command == "run":
        return run_script(args.script, args.script_args)
    if args.command in ("research", "duel"):
        module = research_module("opora_research" if args.command == "research" else "opora_duel")
        return getattr(module, args.command)(args, sys.modules[__name__])
    if args.command == "snapshot":
        return call("GET", "/api/brain/heart/snapshot", query=scope())["snapshot"]
    if args.command == "plan":
        return submit_plan(args)
    if args.command == "task":
        task = call("POST", "/api/brain/tasks", task_payload(args))
        return {key: task[key] for key in ("taskId", "title", "status", "order")}
    if args.command == "answer":
        ticket = call("POST", f"/api/gate/tickets/{quote(args.ticket, safe='')}/answer",
                      {"answer": {"text": args.text}}, {"project": project})
        return {key: ticket[key] for key in ("ticketId", "status", "answeredBy")}
    if args.command == "cancel":
        task = call("POST", f"/api/brain/tasks/{quote(args.task, safe='')}/cancel", {}, {"project": project})
        return {key: task[key] for key in ("taskId", "status")}
    if args.command == "escalate":
        return call("POST", "/api/brain/heart/escalate", {**scope(), "text": args.text})
    if args.command in ("decide", "rule"):
        path, payload = (("/api/desktop-v3/decision", decision_payload(args)) if args.command == "decide"
                         else ("/api/desktop-v3/rule", rule_payload(args)))
        item = call("POST", path, payload)["item"]
        return {key: item.get(key) for key in ("id", "text", "by")}
    summary = {"summary": args.summary, "at": now()}
    Path(LAST_DONE).write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return {"done": True}


def parser():
    root = argparse.ArgumentParser(prog="opora_heart.py", description="Nástroj srdce OPORY.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("snapshot")
    task = commands.add_parser("task")
    task.add_argument("--title", required=True)
    task.add_argument("--do", required=True)
    task.add_argument("--why")
    for flag in ("--file", "--done-when", "--dont-touch", "--rule"):
        task.add_argument(flag, action="append", default=[])
    for flag in ("--intent", "--node", "--commit"):
        task.add_argument(flag)
    task.add_argument("--order", type=int)
    task.add_argument("--model", choices=("sonnet", "opus", "haiku", "fable"))
    task.add_argument("--workspace")
    plan = commands.add_parser("plan")
    plan.add_argument("--file")
    plan.add_argument("--dry-run", action="store_true")
    plan.add_argument("--no-accept", action="store_true")
    plan.add_argument("--example", action="store_true")
    plan.add_argument("--workspace")
    space = commands.add_parser("workspace")
    space.add_argument("--domain", required=True)
    space.add_argument("--reuse", action="store_true")
    answer = commands.add_parser("answer")
    answer.add_argument("--ticket", required=True)
    answer.add_argument("--text", required=True)
    commands.add_parser("cancel").add_argument("--task", required=True)
    commands.add_parser("escalate").add_argument("--text", required=True)
    decide = commands.add_parser("decide")
    decide.add_argument("--text", required=True)
    decide.add_argument("--node")
    decide.add_argument("--pin", action="store_true")
    decide.add_argument("--workspace")
    commands.add_parser("rule").add_argument("--text", required=True)
    commands.add_parser("done").add_argument("--summary", required=True)
    ctx = commands.add_parser("ctx")
    ctx.add_argument("name", choices=CONTEXTS)
    ctx.add_argument("--project")  # jen plan-of: projekt, jehož plán číst
    ctx.add_argument("--workspace")  # jen plan-of: jeho prostor
    script = commands.add_parser("run")
    script.add_argument("script")
    script.add_argument("script_args", nargs=argparse.REMAINDER)
    research = commands.add_parser("research")
    research.add_argument("--question", required=True)
    research.add_argument("--title", required=True)
    research.add_argument("--target", action="append", default=[])
    research.add_argument("--fragment")
    research.add_argument("--deep", action="store_true")
    research.add_argument("--layer", action="append", default=[], choices=LAYERS)
    duel = commands.add_parser("duel")
    for flag in ("--subject", "--a", "--b"):
        duel.add_argument(flag, required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except Failure as failure:
        print(json.dumps(failure.payload, ensure_ascii=False))
        return 1
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
