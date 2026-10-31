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
    python opora_heart.py intake --entry ie_… --verdict V [--reason R] [--requirement rq_…|new [--title T]
                                 [--open-condition ms_…]]
    python opora_heart.py milestone --area A --title T --criterion "text::nodeId,nodeId" [--criterion …]
    python opora_heart.py milestone-decide --activate MS_ID | --reject MS_ID   (reject i aktivního)
    python opora_heart.py brief --requirement rq_… --synthesis @soubor.json
    python opora_heart.py ask --requirement rq_… --question Q --recommended R --why W
    python opora_heart.py decide --text T [--node N] [--pin] [--workspace W]
    python opora_heart.py prune --node ID [--node ID]… [--dry-run] [--no-accept] [--workspace W]
    python opora_heart.py member --area AREA|none --nodes ID,ID… [--dry-run] [--workspace W]
    python opora_heart.py order --nodes ID=101,ID=102|none,… [--dry-run] [--workspace W]
    python opora_heart.py proposal --accept ID
    python opora_heart.py steps --node ID --file F [--dry-run]
    python opora_heart.py rule --text T
    python opora_heart.py done --summary S
    python opora_heart.py ctx tasks|tickets|journal|messages|rules|decisions|tree
    python opora_heart.py ctx plan-of --project P [--workspace W] [--node N | --full]
    python opora_heart.py run SCRIPT [ARG…]
    python opora_heart.py research --question Q --title T [--target URL|cesta]… [--layer L]… [--fragment F] [--deep]
                                   [--requirement rq_…]
    python opora_heart.py skill vyslech
    python opora_heart.py duel --subject F --a TEXT --b TEXT

Adresa, token srdce, projekt a pracovní prostor jsou v prostředí (OPORA_BASE_URL, OPORA_HEART_TOKEN,
OPORA_PROJECT, OPORA_WORKSPACE); token se nikam nezapisuje. `done` zapíše shrnutí do `last_done.json` v cwd.
Dílna (§3b, cwd = `brain/`): `ctx` zapíše data do `dilna/data/<name>.json` (jedna položka na řádek, ať jde číst
po řádcích a Grep vrací položky) a vypíše jen cestu, počet a velikost;
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
`ctx plan-of --project P [--workspace W]` zapíše celý plán jiného projektu kompaktně do `dilna/data/plan-of-<P>.txt`
(řádek na uzel `id · cesta · název · stage`); `--full` zhuštěný JSON `plan-of-<P>.json` (cíl, přijetí, titulky kroků;
pro skripty `rlm.load`), `--node N` plné zadání podstromu uzlu N do `plan-of-<P>-<N>.json`. Zkrácený výstup
hlásí `truncated` a `cut` (vynechané uzly).
`member` navrhne členství existujících karet a sektorů v oblasti (`--area none` ho zruší) návrhem grafu
s `updateNodes` jen pole `memberOf`; při `autonomy.full` (agent-state) ho srdce hned samo přijme (`accepted: true`),
jinak čeká na přijetí člověkem v UI. `proposal --accept ID` přijme návrh grafu akcí `accept` z agent-state
(úklid; bez autonomie `Rozhodne člověk v UI`). `order` stejně navrhne pořadí karet a sektorů podle záměru (pole `order`,
fáze × 100 + pozice, `ID=none` ho odebere; docs/navrhy/2026-10-31-poradi-karty.md): láme remízu `topoIndex`,
nikdy neblokuje jako vazba `next`; stránky a sektory sdílené architektury řadí přímo v `/api/project-architecture`
(jen `order`, s revizí) a převezme je do plánu prostoru návrhem s `adoptArchitectureContext` (§4). Zamítnutí
návrhu server nemá: nahrazený novější návrh zmizí z nabídky sám.
`steps` doplní existující kartě 2–8 kroků s `kind` a `files` (soubor `{steps, goal?, acceptance?}`) návrhem změny
zadání (`/api/oporahub/changesets`, docs/oporahub-plan-steps.md); při `autonomy.full` ho přijme jako `member`.
`brief` uloží syntézu výslechu požadavku (JSON v souboru `@cesta` nebo přímo) a vrátí `status` a co do jasna chybí
(`missing`); `ask` položí člověku otázku výslechu s doporučenou odpovědí (docs/navrhy/2026-10-30-vyslech-srdce.md §7).
`research` (§3d, výzkumný stůl) je v `opora_research.py`, `duel` (§3c) v `opora_duel.py` vedle nástroje;
`research --requirement rq_…` je rešerše výslechu se stropem ceny na požadavek (vyslech-srdce.md §8).
`skill NAME` vypíše postup režimu ze `skills/NAME.md` vedle nástroje (výslech čte `skill vyslech`, jen při výslechu).
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
# Stanoviska vstupní brány, která srdce smí dát (kopie determinism.intake.VERDICTS, nástroj je jen stdlib).
VERDICTS = ("done", "extends_in_progress", "fix_for_milestone", "changes_intent", "later_extension", "needs_info")
LAYERS = ("fe", "be", "db", "api", "cache", "infra", "security", "data", "ops")  # vrstvy výzkumu (§3d)
SCRIPT = re.compile(r"[A-Za-z0-9_-]+\Z")
SKILLS = "skills"  # složka postupů režimů vedle nástroje (supervisor ji kopíruje do `brain/`)
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


def active_workspace():
    """Prostor posledního přijatého plánu z `active_workspace.json` v cwd, jinak `None`."""
    try:
        return json.loads(Path(ACTIVE).read_text(encoding="utf-8")).get("workspace") or None
    except (OSError, ValueError, AttributeError):
        return None


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


def criteria(values):
    """`"text::nodeId,nodeId"` → `{text, cards[]}` (kritérium milníku a karty, které ho dokládají)."""
    result = []
    for value in values:
        text, _, cards = value.rpartition("::")
        result.append({"text": text.strip(), "cards": [card.strip() for card in cards.split(",") if card.strip()]})
    return result


def read_synthesis(value):
    """Syntéza výslechu: `@cesta` k JSON souboru, jinak JSON přímo v argumentu."""
    try:
        text = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
        synthesis = json.loads(text)
    except (OSError, ValueError) as error:
        raise Failure({"error": f"Syntézu nejde přečíst: {error}", "code": "brief_file",
                       "hint": "Ulož syntézu jako JSON objekt do dilna/out/brief.json (Write) a předej @cestu."}) from None
    if not isinstance(synthesis, dict):
        raise Failure({"error": "Syntéza musí být JSON objekt.", "code": "brief_file",
                       "hint": "Objekt {goal, users, parts, acceptance, outOfScope, dependencies, questions…}."})
    return synthesis


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
         "purpose": "Úkoly v paměti: přidat, smazat, vypsat.",
         "card": {"layer": "backend", "status": "ready", "effort": "medium"},
         "spec": {"goal": "ukoly.py má třídu SeznamUkolu s metodami pridat, smazat a seznam.",
                  "non_goals": "Příkazovou řádku řeší karta CLI.", "acceptance": "python -m unittest projde",
                  "steps": [{"id": "s1", "order": 1, "title": "Třída SeznamUkolu", "dependsOn": [], "kind": "code",
                             "files": ["ukoly.py"], "acceptance": ["pridat, smazat a seznam pracují nad pamětí"]},
                            {"id": "s2", "order": 2, "title": "Testy třídy", "dependsOn": ["s1"], "kind": "test",
                             "files": ["test_ukoly.py"], "acceptance": ["test_ukoly.py pokrývá pridat, smazat i seznam"]}]},
         "checks": [{"id": "unit", "command": "python -m unittest"}]},
        {"ref": "cli", "kind": "node", "parent": "mvp", "name": "[task] CLI ukoly.py",
         "purpose": "Úkoly z příkazové řádky.", "card": {"layer": "backend", "status": "ready"},
         "spec": {"goal": "python ukoly.py pridat|smazat|seznam volá SeznamUkolu.", "non_goals": "",
                  "acceptance": "python -m unittest projde",
                  "steps": [{"id": "s1", "order": 1, "title": "Argumenty a výstup", "dependsOn": [], "kind": "code",
                             "files": ["ukoly.py"], "acceptance": ["python ukoly.py seznam vypíše přidaný úkol"]},
                            {"id": "s2", "order": 2, "title": "Test CLI", "dependsOn": ["s1"], "kind": "test",
                             "files": ["test_cli.py"], "acceptance": ["test_cli.py spustí pridat a seznam"]}]},
         "checks": [{"id": "unit", "command": "python -m unittest"}]},
    ],
    "edges": [{"from": "model", "to": "cli", "port": "next"}],
}
PLAN_SHAPE = ("Tvar dávky: `python opora_heart.py plan --example` (sektor, karty node s card, spec.steps a checks, "
              "vazba next); celý kontrakt docs/davka-planu.md §3.")
# Přijetí plánu (docs/brain-heart-orchestrator.md §3 O2b): kroky z agent-state, které z plátna udělají přijatý plán.
GRAPH_PROPOSALS = "/api/oporahub/graph-proposals"
CHANGESETS = "/api/oporahub/changesets"  # návrhy změny zadání karet (docs/oporahub-plan-steps.md)
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


def accept_proposal(proposal_id, base=None):
    """Přijme návrh `proposal_id` (grafu, s `base` = CHANGESETS návrh zadání) přesnou akcí `accept` z agent-state
    (ne cizí návrhy) s jejími preconditions. Bez `autonomy.full` projektu návrh zůstává člověku (`Failure` s hintem)."""
    base = base or GRAPH_PROPOSALS
    state = call("GET", "/api/oporahub/agent-state", query=scope())
    if not (state.get("autonomy") or {}).get("full"):
        raise Failure({"error": "Návrh přijímá člověk, projekt nemá plnou autonomii.", "code": "human_only",
                       "status": 403, "hint": "Rozhodne člověk v UI."})
    path = f"{base}/{quote(proposal_id, safe='')}/accept"
    action = next((item for item in state.get("actions", [])
                   if item.get("verb") == "accept" and item.get("path") == path), None)
    if action is None or action.get("status") != "ready":
        raise Failure({"error": f"Agent-state nenabízí přijetí návrhu {proposal_id}.", "code": "proposal_not_offered",
                       "hint": f"Návrh je už přijatý nebo ho nahradil novější; vezmi ID z GET {base}."})
    try:
        call("POST", action["path"], {**scope(), **(action.get("preconditions") or {})})
    except Failure as failure:
        if failure.payload.get("status") in (403, 428):
            failure.payload["hint"] = "Rozhodne člověk v UI."
        raise
    return {"proposalId": proposal_id, "accepted": True}


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
# Návrh grafu nese tatáž pole karty jako první plán (`card` s effortem, `checks`, `goal_mode`, spec.steps), jen vazby `next`.
ADDITION_KEYS = {"ref", "kind", "name", "parent", "purpose", "size", "position", "sourceRef", "spec", "memberOf",
                 "card", "checks", "goal_mode"}
ADDITION_EDGE_KEYS = {"from", "to", "port", "carries"}
ADDITION_SHAPE = ("Plán nad už přijatým grafem jde jako návrh grafu: uzel jen s poli ref, kind (node|sector|area), "
                  "name, parent, purpose, spec (i steps), card (i effort), checks, goal_mode, sourceRef, position, size, "
                  "memberOf; vazby jen next (from, to); nic dalšího (text, bloky, pravidla, rozhodnutí). "
                  "Existující uzel odkazuj \"@<id>\".")
ARCHITECTURE_HINT = ("Architekturu (sektor domény se site.kind application, stránky se site.kind page) pošli do main: "
                     "plan --file F --workspace main (nejdřív s --dry-run). Prostory s přijatým plánem ji převezmou "
                     "samy; karty pak plánuj v prostoru domény.")


def addition_plan(plan):
    """Dávka → plán návrhu grafu; jiná pole odmítne česky, než je odmítne server."""
    if not set(plan) <= {"nodes", "edges"}:
        raise Failure({"error": f"Přírůstek plánu neumí {', '.join(sorted(set(plan) - {'nodes', 'edges'}))}.",
                       "code": "plan_shape", "hint": ADDITION_SHAPE})
    nodes = []
    for index, node in enumerate(plan.get("nodes") or []):
        if not isinstance(node, dict):
            raise Failure({"error": f"nodes[{index}] není objekt.", "code": "plan_shape", "hint": ADDITION_SHAPE})
        extra = set(node) - ADDITION_KEYS
        if "site" in extra:
            # Doména a stránky (site) jsou architektura: ta se píše jen v main a prostory ji převezmou.
            raise Failure({"error": f"nodes[{index}]: site je architektura, prostor ji nepřijme.",
                           "code": "plan_architecture", "hint": ARCHITECTURE_HINT})
        if extra or node.get("kind") not in ("node", "sector", "area"):
            what = f"neznámé pole {', '.join(sorted(extra))}" if extra else f"druh {node.get('kind')!r}"
            raise Failure({"error": f"nodes[{index}]: {what}.", "code": "plan_shape", "hint": ADDITION_SHAPE})
        nodes.append(node)
    edges = []
    for index, edge in enumerate(plan.get("edges") or []):
        if not isinstance(edge, dict) or not set(edge) <= ADDITION_EDGE_KEYS or edge.get("port", "next") != "next":
            raise Failure({"error": f"edges[{index}]: jen vazba next (from, to).", "code": "plan_shape",
                           "hint": ADDITION_SHAPE})
        edges.append(edge)
    return {"nodes": nodes, "edges": edges}


def submit_addition(args, plan, context):
    """Plán nad přijatým grafem: `POST /api/oporahub/graph-proposals` s přírůstkem, pak jeho přijetí tokenem srdce.
    Karty vzniknou na plátně až přijetím, takže pracovní a přijatý graf se nerozejdou a claimy ostatních karet platí."""
    addition, warnings = addition_plan(plan), []
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


def submit_unlink(args):
    """`unlink`: odebere vazbu `next` mezi dvěma kartami návrhem grafu `{removeEdges}` (stejná cesta a stejné přijetí
    tokenem srdce jako `submit_addition`). Neznámá vazba = česká chyba bez zápisu; `--dry-run` jen ukáže, co by zmizelo."""
    context = call("GET", f"{GRAPH_PROPOSALS}/context", query=scope())
    edges = [edge for edge in call("GET", "/api/view", query=scope())["graph"]["edges"]
             if edge["source"] == args.from_node and edge["target"] == args.to_node and edge.get("port", "next") == "next"]
    if not edges:
        raise Failure({"error": f"Mezi {args.from_node} a {args.to_node} není vazba next (směr from → to).",
                       "code": "unlink_unknown_edge",
                       "hint": "Zkontroluj ID karet a směr: from je předchůdce, to následník (snapshot ukazuje vazby)."})
    ids = [edge["id"] for edge in edges]
    out = {"ok": True, "dryRun": bool(args.dry_run), "removedEdges": ids, "path": "graph-proposal"}
    return remove(args, context, {"removeEdges": ids}, f"Srdce odebralo závislost {args.from_node} → {args.to_node}",
                  out, "unlink")


def submit_prune(args):
    """`prune`: odebere uzly (prázdné nebo zbylé po zkoušení) návrhem grafu `{removeNodes, removeEdges}` se stejným
    přijetím jako `unlink`. Server nekaskáduje: s uzly jdou jejich vazby a uzel s potomkem, který není v seznamu,
    odmítne česky bez zápisu. Uzavřenou kartu odmítne server.

    Uzly a vazby hledá v pracovním i přijatém grafu: uzel, který zůstal jen v přijatém plánu (pracovní graf ho po nové
    architektuře z main už nemá), jinak blokuje každou změnu prostoru. Má-li prostor zastaralou architekturu, převezme
    ji týž návrh (`adoptArchitectureContext`), takže úklid je jedna změna grafu."""
    context = call("GET", f"{GRAPH_PROPOSALS}/context", query=scope())
    working = call("GET", "/api/view", query=scope())["graph"]
    graphs = [working, context.get("acceptedGraph") or {"nodes": [], "edges": []}]
    known = {node["id"] for graph in graphs for node in graph["nodes"]}
    ids = list(dict.fromkeys(args.node))
    unknown = [node for node in ids if node not in known]
    if unknown:
        raise Failure({"error": f"Uzel {', '.join(unknown)} v prostoru není.", "code": "prune_unknown_node",
                       "hint": "Vezmi celá ID uzlů z /api/view nebo snapshotu tohoto prostoru."})
    kept = list(dict.fromkeys(node["id"] for graph in graphs for node in graph["nodes"]
                              if node.get("parentId") in ids and node["id"] not in ids))
    if kept:
        raise Failure({"error": f"Uzel má potomky, které v seznamu nejsou: {', '.join(kept)}.", "code": "prune_children",
                       "hint": "Přidej potomky jako další --node, nebo je nejdřív přesuň; nic se nekaskáduje."})
    edges = list(dict.fromkeys(edge["id"] for graph in graphs for edge in graph["edges"]
                               if edge["source"] in ids or edge["target"] in ids))
    plan = {"removeNodes": ids, "removeEdges": edges}
    out = {"ok": True, "dryRun": bool(args.dry_run), "removedNodes": ids, "removedEdges": edges, "path": "graph-proposal"}
    if stale_architecture(context):
        plan["adoptArchitectureContext"] = out["adoptArchitecture"] = True
    return remove(args, context, plan, f"Srdce odebralo {len(ids)} uzlů", out, "prune")


MEMBER_KINDS = ("node", "sector")  # kdo smí nést memberOf (graph.validate_graph, H01)


def known_nodes():
    """Kontext návrhů grafu a uzly pracovního i přijatého grafu podle id (pracovní graf má přednost)."""
    context = call("GET", f"{GRAPH_PROPOSALS}/context", query=scope())
    graphs = [call("GET", "/api/view", query=scope())["graph"], context.get("acceptedGraph") or {"nodes": []}]
    known = {}
    for graph in reversed(graphs):  # pracovní graf má přednost (dnešní memberOf a order)
        known.update({node["id"]: node for node in graph["nodes"]})
    return context, known


def submit_member(args):
    """`member`: návrh grafu `{updateNodes}` měnící u existujících karet a sektorů jen `memberOf` (oblast, nebo zrušení
    s `--area none`). Uzly hledá v pracovním i přijatém grafu jako `prune`. Návrh srdce nepřijímá: člověk ho přijme
    v UI stejnou cestou jako jiné návrhy grafu. Sektor stačí zařadit, jeho karty členství zdědí (docs/plan-lens.md)."""
    context, known = known_nodes()
    area = None if args.area == "none" else args.area
    if area is not None and (known.get(area) or {}).get("kind") != "area":
        raise Failure({"error": f"{area} není oblast (kind area) tohoto prostoru.", "code": "member_area",
                       "hint": "Vezmi ID oblasti ze snapshotu (uzel kind area), nebo --area none pro zrušení."})
    ids = list(dict.fromkeys(item.strip() for item in args.nodes.split(",") if item.strip()))
    if not ids:
        raise Failure({"error": "Chybí --nodes.", "code": "member_nodes", "hint": "--nodes id1,id2 (celá ID uzlů)."})
    unknown = [node for node in ids if node not in known]
    if unknown:
        raise Failure({"error": f"Uzel {', '.join(unknown)} v prostoru není.", "code": "member_unknown_node",
                       "hint": "Vezmi celá ID karet a sektorů z /api/view nebo snapshotu tohoto prostoru."})
    wrong = [node for node in ids if known[node].get("kind") not in MEMBER_KINDS]
    if wrong:
        raise Failure({"error": f"Do oblasti jde jen karta nebo sektor, ne {', '.join(wrong)}.",
                       "code": "member_kind", "hint": "Zařazuj uzly kind node nebo sector."})
    changes = [{"id": node, "from": known[node].get("memberOf"), "to": area} for node in ids
               if known[node].get("memberOf") != area]
    out = {"ok": True, "dryRun": bool(args.dry_run), "area": area, "changes": changes,
           "unchanged": [node for node in ids if node not in {item["id"] for item in changes}], "path": "graph-proposal"}
    if args.dry_run or not changes:
        return out
    plan = {"updateNodes": [{"id": item["id"], "fields": {"memberOf": area}} for item in changes]}
    subject = (f"Srdce zařadilo {len(changes)} uzlů do oblasti {known[area].get('name') or area}" if area
               else f"Srdce zrušilo členství {len(changes)} uzlů v oblasti")
    proposal = call("POST", GRAPH_PROPOSALS, {**scope(), "parentRevision": context["acceptedHead"],
                                              "expectedGraphDigest": context["graphDigest"],
                                              "subject": subject, "plan": plan})
    out = {**out, "proposalId": proposal["id"]}
    state = call("GET", "/api/oporahub/agent-state", query=scope())
    if (state.get("autonomy") or {}).get("full"):  # plná autonomie: srdce přijme jen svůj vlastní návrh
        try:
            return {**out, **accept_proposal(proposal["id"])}
        except Failure as failure:
            return {**out, "accepted": False, "code": failure.payload.get("code"), "error": failure.payload.get("error"),
                    "hint": "Přijetí návrhu členství selhalo; přijme ho člověk v UI."}
    return {**out, "accepted": False, "hint": "Návrh členství čeká na přijetí člověkem v UI (změny grafu)."}


ORDER_MIN, ORDER_MAX = 1, 9999  # kopie graph.NODE_ORDER_*, nástroj je jen stdlib


def order_pairs(text):
    """`ID=101,ID2=none` → `{id: číslo nebo None}` v pořadí zápisu (pozdější zápis téhož ID vyhrává)."""
    pairs = {}
    for item in (part.strip() for part in text.split(",")):
        if not item:
            continue
        node, sep, value = (piece.strip() for piece in item.partition("="))
        if not sep or not node:
            raise Failure({"error": f"Neplatný zápis {item!r}.", "code": "order_value",
                           "hint": "--nodes ID=101,ID=102 (fáze × 100 + pozice), ID=none pořadí odebere."})
        if value == "none":
            pairs[node] = None
            continue
        if not (value.isascii() and value.isdigit()) or not ORDER_MIN <= int(value) <= ORDER_MAX:
            raise Failure({"error": f"Pořadí {value!r} u {node} není celé číslo {ORDER_MIN}–{ORDER_MAX}.",
                           "code": "order_value", "hint": "Zapiš fáze × 100 + pozice (101, 102, 201 …) nebo none."})
        pairs[node] = int(value)
    return pairs


ARCHITECTURE = "/api/project-architecture"


def order_changes(nodes, pairs):
    return [{"id": node, "from": nodes[node].get("order"), "to": value} for node, value in pairs.items()
            if nodes[node].get("order") != value]


def ordered_architecture(graph, changes):
    """Kopie grafu architektury, v níž se u daných uzlů změní jen `order` (`None` pole odebere). Před uložením ověří,
    že se jinak nic neliší (uzly, jejich pořadí, ostatní pole i vazby), stejně jako server."""
    values = {item["id"]: item["to"] for item in changes}
    nodes = []
    for node in graph["nodes"]:
        node = dict(node)
        if node["id"] in values:
            node.pop("order", None)
            if values[node["id"]] is not None:
                node["order"] = values[node["id"]]
        nodes.append(node)
    result = {**graph, "nodes": nodes}

    def rest(item):
        return {key: value for key, value in item.items() if key != "order"}
    if (list(map(rest, graph["nodes"])) != list(map(rest, nodes)) or result["edges"] != graph["edges"]
            or set(result) != set(graph)):
        raise Failure({"error": "Úprava architektury by změnila víc než pořadí.", "code": "order_architecture_diff",
                       "hint": "Nic se neuložilo; načti architekturu znovu."})
    return result


def submit_order(args):
    """`order`: pořadí podle záměru (`ID=none` ho odebere), nic neblokuje (docs/navrhy/2026-10-31-poradi-karty.md).
    Karty a sektory obsahu prostoru: návrh grafu `{updateNodes}` jen s `order`. Stránky a sektory sdílené architektury
    (§4): `POST /api/project-architecture` s očekávanou revizí, v níž se mění jen `order`, a hned návrh grafu
    s `adoptArchitectureContext` (převzetí do plánu prostoru), je-li prostor přijatý se starší architekturou. Návrh
    srdce přijme samo jen při `autonomy.full`, jinak čeká na člověka v UI."""
    pairs = order_pairs(args.nodes)
    if not pairs:
        raise Failure({"error": "Chybí --nodes.", "code": "order_nodes", "hint": "--nodes id1=101,id2=102 (celá ID uzlů)."})
    context, known = known_nodes()
    stored = call("GET", ARCHITECTURE, query={"project": scope()["project"]})
    shared = {node["id"]: node for node in stored["graph"]["nodes"]}
    unknown = [node for node in pairs if node not in known and node not in shared]
    if unknown:
        raise Failure({"error": f"Uzel {', '.join(unknown)} v prostoru není.", "code": "order_unknown_node",
                       "hint": "Vezmi celá ID karet a sektorů z /api/view nebo snapshotu tohoto prostoru."})
    wrong = [node for node in pairs if (shared.get(node) or known[node]).get("kind") not in MEMBER_KINDS]
    if wrong:
        raise Failure({"error": f"Pořadí má jen karta nebo sektor, ne {', '.join(wrong)}.",
                       "code": "order_kind", "hint": "Řaď uzly kind node nebo sector."})
    pages = {node: value for node, value in pairs.items() if node in shared}
    changes = order_changes(known, {node: value for node, value in pairs.items() if node not in shared})
    page_changes = order_changes(shared, pages)
    changed = {item["id"] for item in [*changes, *page_changes]}
    out = {"ok": True, "dryRun": bool(args.dry_run), "changes": changes,
           "unchanged": [node for node in pairs if node not in changed], "path": "graph-proposal"}
    if pages:
        out["architecture"] = {"revision": stored["revision"], "changes": page_changes}
    if args.dry_run or not changed:
        return out
    plan = {}
    if page_changes:
        saved = call("POST", ARCHITECTURE, {**scope(), "expectedRevision": stored["revision"],
                                            "graph": ordered_architecture(stored["graph"], page_changes)})
        out["architecture"]["revision"] = saved["revision"]
        context = call("GET", f"{GRAPH_PROPOSALS}/context", query=scope())  # pracovní graf má novou architekturu
        if stale_architecture(context):
            plan["adoptArchitectureContext"] = out["adoptArchitecture"] = True
        if not changes and not plan:
            # Prostor bez přijatého plánu (nebo main) skládá architekturu sám: pořadí platí hned, návrh netřeba.
            return {**out, "path": "project-architecture", "proposalId": None, "accepted": True}
    if changes:
        plan["updateNodes"] = [{"id": item["id"], "fields": {"order": item["to"]}} for item in changes]
    subject = (f"Srdce přeřadilo {len(changes)} uzlů podle záměru" if changes else
               f"Srdce převzalo pořadí {len(page_changes)} stránek z architektury")
    proposal = call("POST", GRAPH_PROPOSALS, {**scope(), "parentRevision": context["acceptedHead"],
                                              "expectedGraphDigest": context["graphDigest"],
                                              "subject": subject, "plan": plan})
    out = {**out, "proposalId": proposal["id"]}
    state = call("GET", "/api/oporahub/agent-state", query=scope())
    if (state.get("autonomy") or {}).get("full"):  # plná autonomie: srdce přijme jen svůj vlastní návrh
        try:
            return {**out, **accept_proposal(proposal["id"])}
        except Failure as failure:
            return {**out, "accepted": False, "code": failure.payload.get("code"), "error": failure.payload.get("error"),
                    "hint": "Přijetí návrhu pořadí selhalo; přijme ho člověk v UI."}
    return {**out, "accepted": False, "hint": "Návrh pořadí čeká na přijetí člověkem v UI (změny grafu)."}


# Realizační karta (prompt.md část Plán, docs/navrhy/2026-10-30-metriky-a-spoustece.md): 2–8 kroků s `kind` a `files`.
STEP_KINDS = ("code", "test", "docs", "design", "research")  # kopie opora_plan_steps, nástroj je jen stdlib
STEPS_MIN, STEPS_MAX = 2, 8
STEPS_SHAPE = ('Soubor: {"steps": [{"title": "…", "kind": "code|test|docs|design|research", "files": ["cesta"], '
               '"acceptance": ["ověřitelná podmínka"]}, …], "goal"?: "…", "acceptance"?: "…"}; '
               "id, order a dependsOn (lineárně s1 → s2 → …) doplní nástroj, když chybí.")


def steps_failure(error, code):
    return Failure({"error": error, "code": code, "hint": STEPS_SHAPE})


def read_steps(path):
    """Soubor příkazu `steps` → pole zadání `{steps, goal?, acceptance?}`. Tvar kroku (id, order, title, acceptance,
    dependsOn, limity) ověří server stejně jako u každého návrhu zadání (`validate_steps`, docs/oporahub-plan-steps.md);
    tady jen pravidlo realizační karty, které server nemá: 2–8 kroků, každý s `kind` a neprázdnými `files`."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise steps_failure(f"Soubor kroků nejde přečíst: {error}", "steps_file") from None
    if not isinstance(data, dict) or not set(data) <= {"steps", "goal", "acceptance"} or "steps" not in data:
        raise steps_failure("Soubor má jen klíče steps, goal a acceptance (steps povinně).", "steps_file")
    steps = data["steps"]
    if not isinstance(steps, list) or not STEPS_MIN <= len(steps) <= STEPS_MAX or not all(isinstance(s, dict) for s in steps):
        raise steps_failure(f"Realizační karta má {STEPS_MIN}–{STEPS_MAX} kroků (objektů).", "steps_count")
    for index, step in enumerate(steps, 1):
        if step.get("kind") not in STEP_KINDS:
            raise steps_failure(f"Krok {index} nemá kind z {'|'.join(STEP_KINDS)}.", "steps_kind")
        files = step.get("files")
        if not isinstance(files, list) or not files or not all(isinstance(item, str) and item for item in files):
            raise steps_failure(f"Krok {index} nemá files (odhad dotčených cest).", "steps_files")
    filled = []
    for index, step in enumerate(steps, 1):
        previous = filled[-1]["id"] if filled else None
        filled.append({"id": f"s{index}", "order": index, "dependsOn": [previous] if previous else [], **step})
    for key in ("goal", "acceptance"):
        if key in data and not isinstance(data[key], str):
            raise steps_failure(f"{key} je text.", "steps_file")
    return {**data, "steps": filled}


def submit_steps(args):
    """`steps`: návrh změny zadání jedné existující karty (`POST /api/oporahub/changesets`, úplná `fields` z pracovního
    zadání + nové `steps`, volitelně `goal` / `acceptance`). Při `autonomy.full` ho srdce přijme akcí `accept`
    z agent-state (jako `member`), jinak ho přijme člověk v OporaHubu. Graf ani jiné karty se nemění."""
    if not args.file:
        raise steps_failure("Chybí --file.", "steps_file")
    update = read_steps(args.file)
    context = call("GET", f"{CHANGESETS}/context", query=scope())
    card = next((item for item in context.get("documents") or [] if item.get("nodeId") == args.node), None)
    if card is None:
        raise Failure({"error": f"Karta {args.node} v tomto prostoru nemá zadání.", "code": "steps_unknown_node",
                       "hint": "Vezmi celé ID karty z řádku VÝSLECH nebo ze snapshotu tohoto prostoru."})
    if not context.get("acceptedHead") or args.node not in {item.get("nodeId") for item in
                                                             context.get("acceptedDocuments") or []}:
        raise Failure({"error": f"Karta {args.node} nemá přijaté zadání.", "code": "steps_not_accepted",
                       "hint": "Kroky existující karty se mění návrhem nad přijatým zadáním; nejdřív musí být přijatý "
                               "plán s kartou (plan), kroky nové karty dej rovnou do plan."})
    fields = {**card["fields"], **update}
    out = {"ok": True, "dryRun": bool(args.dry_run), "node": args.node, "path": "spec-changeset",
           "stepsBefore": len(card["fields"].get("steps") or []), "steps": [step["id"] for step in update["steps"]]}
    if args.dry_run:
        return out
    try:
        proposal = call("POST", CHANGESETS, {
            **scope(), "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
            "subject": f"Srdce doplnilo kroky karty {args.node}",
            "changes": [{"nodeId": args.node, "expectedRevision": card["revision"], "fields": fields}]})
    except Failure as failure:
        if failure.payload.get("hint") == GENERIC_HINT:
            failure.payload["hint"] = (f"Server návrh zadání odmítl: {failure.payload.get('error')} "
                                       "Tvar kroku: docs/oporahub-plan-steps.md. " + STEPS_SHAPE)
        raise
    out = {**out, "proposalId": proposal["id"]}
    state = call("GET", "/api/oporahub/agent-state", query=scope())
    if (state.get("autonomy") or {}).get("full"):  # plná autonomie: srdce přijme jen svůj vlastní návrh
        try:
            return {**out, **accept_proposal(proposal["id"], CHANGESETS)}
        except Failure as failure:
            return {**out, "accepted": False, "code": failure.payload.get("code"), "error": failure.payload.get("error"),
                    "hint": "Přijetí návrhu kroků selhalo; přijme ho člověk v OporaHubu (Upravit zadání karty)."}
    return {**out, "accepted": False, "hint": "Návrh kroků čeká na přijetí člověkem v OporaHubu (návrhy zadání)."}


def remove(args, context, plan, subject, out, command):
    """Návrh grafu s odebráním a jeho přijetí tokenem srdce (cesta formuláře úprav plánu v UI)."""
    if args.dry_run:
        return out
    proposal = call("POST", GRAPH_PROPOSALS, {**scope(), "parentRevision": context["acceptedHead"],
                                              "expectedGraphDigest": context["graphDigest"],
                                              "subject": subject, "plan": plan})
    out["proposalId"] = proposal["id"]
    if args.no_accept:
        return {**out, "accepted": False}
    try:
        call("POST", f"{GRAPH_PROPOSALS}/{quote(proposal['id'], safe='')}/accept",
             {**scope(), "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
              "adoptBaseGraphDigest": None, "reviewedChangesId": proposal["id"]})
    except Failure as failure:
        return {**out, "accepted": False, "code": failure.payload.get("code"), "error": failure.payload.get("error"),
                "hint": "Návrh odebrání čeká na přijetí (plátno se mezitím změnilo, nebo chybí oprávnění); "
                        f"přijme ho člověk v UI, nebo pošli {command} znovu."}
    return {**out, "accepted": True}


def plan_lines(items):
    """Kompaktní plán: jeden řádek na uzel `id · cesta · název · stage` (stage karty, jinak druh uzlu); zkrácený plán
    končí řádkem s ID vynechaných uzlů."""
    rows = []
    for item in items:
        if item.get("truncated"):
            cut = [node.get("id") for node in item.get("cut") or []]
            rows.append(f"… vynecháno {len(cut)} uzlů (dočti --node): {', '.join(str(node) for node in cut)}")
            continue
        rows.append(" · ".join(str(part) for part in (item.get("id"), item.get("path") or "—", item.get("name") or "",
                                                      item.get("stage") or item.get("kind") or "?")))
    return rows


def load_context(name, of=None, of_workspace=None, of_node=None, full=False):
    """`ctx <name>`: data z OPORY do `dilna/data/<name>.json` (JSON pole, jedna položka na řádek); vrací jen cestu,
    počet položek a velikost. `plan-of` čte plán projektu `of` (prostor `of_workspace`, jinak main git / draft
    lokálního): výchozí je kompaktní `plan-of-<of>.txt` (`plan_lines`, jeden řádek na uzel), `full` dá zhuštěný JSON
    `plan-of-<of>.json` (cíl, přijetí, titulky kroků; čte ho `rlm.load`), `of_node` plné zadání podstromu do
    `plan-of-<of>-<node>.json`; zkrácený plán přidá do výstupu `truncated` a `cut` (ID vynechaných uzlů)."""
    lines = False
    query = {**scope(), "name": name}
    if name == "plan-of":
        if not of or not SCRIPT.match(of) or (of_node and not SCRIPT.match(of_node)):
            raise Failure({"error": "ctx plan-of potřebuje --project <id> (a platné --node <id>).",
                           "code": "plan_of_project",
                           "hint": "ID projektu je v GET /api/bootstrap; prostor volitelně --workspace <id>, "
                                   "podstrom --node <id uzlu> ze zhuštěného plánu."})
        query.update({"of": of, **({"ofWorkspace": of_workspace} if of_workspace else {}),
                      **({"ofNode": of_node} if of_node else {})})
        name = f"plan-of-{of}" + (f"-{of_node}" if of_node else "")
        lines = not of_node and not full
    items = call("GET", "/api/brain/heart/context", query=query)["items"]
    path = DILNA / "data" / f"{name}.{'txt' if lines else 'json'}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if lines:
        raw = "".join(row + "\n" for row in plan_lines(items)).encode("utf-8")
    else:
        rows = ",\n".join(json.dumps(item, ensure_ascii=False) for item in items)
        raw = (f"[\n{rows}\n]\n" if items else "[]\n").encode("utf-8")
    path.write_bytes(raw)
    out = {"path": path.as_posix(), "items": len(items), "bytes": len(raw)}
    last = items[-1] if items and isinstance(items[-1], dict) else {}
    if last.get("truncated"):
        out.update({"items": len(items) - 1, "truncated": True, "total": last.get("total"),
                    "cut": [node.get("id") for node in last.get("cut") or []]})
    return out


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


def read_skill(name):
    """`skill NAME`: text postupu `skills/NAME.md` vedle nástroje (v `brain/` kopie, v testech složka balíčku)."""
    path = Path(__file__).resolve().parent / SKILLS / f"{name}.md"
    if not SCRIPT.match(name) or not path.is_file():
        raise Failure({"error": f"Postup {name!r} neexistuje.", "code": "skill_missing",
                       "hint": "Postupuj podle části promptu, která režim popisuje (např. Výslech)."})
    return path.read_text(encoding="utf-8")


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


def open_workspace(domain, reuse, name=None):
    """`workspace --domain NODE [--reuse] [--name N]`: pracovní prostor (git worktree větve `work/<id>`) vázaný na
    doménu architektury; s `--reuse` vrátí existující prostor téže domény, když je. `--name` = „stránka · co se dělá“,
    čitelný popisek prostoru pro člověka i kancelář (≤ 120 znaků). `POST /api/workspaces` tokenem srdce."""
    project = env("OPORA_PROJECT")
    spaces = call("GET", "/api/view", query={"project": project, "workspace": "main"}).get("workspaces") or []
    found = next((space for space in spaces if space.get("node_id") == domain), None) if reuse else None
    created = found is None
    if created:
        try:
            found = call("POST", "/api/workspaces", {"project": project, "nodeId": domain,
                                                     "actor": (name or "").strip()[:120] or "heart"})
        except Failure as failure:
            if failure.payload.get("hint") == GENERIC_HINT:
                failure.payload["hint"] = ("--domain je ID sektoru domény (site.kind application) z architektury "
                                           "v main; doménu postav nejdřív plánem v main.")
            raise
    return {"workspace": found["id"], "branch": found.get("branch"), "domain": found.get("node_id"),
            "created": created}


def run(args):
    if args.command == "skill":  # postup režimu nepotřebuje prostředí dávky
        return read_skill(args.name)
    project = env("OPORA_PROJECT")
    # `--workspace` jen u plan, task a decide; u ctx je to prostor cizího plánu (plan-of), ne přepis prostoru srdce
    _override["workspace"] = getattr(args, "workspace", None) if args.command in ("plan", "task", "decide", "unlink", "prune", "member", "order", "research", "duel") else None
    if args.command in ("research", "duel") and not _override["workspace"] and os.environ.get("OPORA_WORKSPACE") == "main":
        _override["workspace"] = active_workspace()  # schránka v main neexistuje (read-only): výzkum jde do prostoru posledního plánu
    if args.command == "ctx":
        return load_context(args.name, args.project, args.workspace, args.node, args.full)
    if args.command == "workspace":
        return open_workspace(args.domain, args.reuse, args.name)
    if args.command == "run":
        return run_script(args.script, args.script_args)
    if args.command in ("research", "duel"):
        module = research_module("opora_research" if args.command == "research" else "opora_duel")
        return getattr(module, args.command)(args, sys.modules[__name__])
    if args.command == "snapshot":
        return call("GET", "/api/brain/heart/snapshot", query=scope())["snapshot"]
    if args.command == "plan":
        return submit_plan(args)
    if args.command == "unlink":
        return submit_unlink(args)
    if args.command == "prune":
        return submit_prune(args)
    if args.command == "member":
        return submit_member(args)
    if args.command == "order":
        return submit_order(args)
    if args.command == "proposal":
        return accept_proposal(args.accept)
    if args.command == "steps":
        return submit_steps(args)
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
    if args.command == "intake":
        options = {"reason": args.reason, "requirement": args.requirement, "title": args.title,
                   "openCondition": args.open_condition}
        body = {**scope(), "entry": args.entry, "verdict": args.verdict}
        return call("POST", "/api/brain/heart/intake", body | {key: value for key, value in options.items() if value})
    if args.command == "milestone":
        body = {**scope(), "area": args.area, "title": args.title, "criteria": criteria(args.criterion)}
        return call("POST", "/api/brain/heart/milestone", body)
    if args.command == "milestone-decide":
        action, milestone_id = ("activate", args.activate) if args.activate else ("reject", args.reject)
        try:
            return call("POST", "/api/intake/milestone", {**scope(), "milestoneId": milestone_id, "action": action})
        except Failure as failure:
            if failure.payload.get("status") in (403, 428):  # bez plné autonomie rozhoduje člověk
                failure.payload["hint"] = "Rozhodne člověk ve Velínu."
            raise
    if args.command == "brief":
        body = {**scope(), "requirement": args.requirement, "synthesis": read_synthesis(args.synthesis)}
        return call("POST", "/api/brain/heart/brief", body)
    if args.command == "ask":
        body = {**scope(), "requirement": args.requirement, "question": args.question,
                "recommended": args.recommended, "why": args.why}
        return call("POST", "/api/brain/heart/ask", body)
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
    unlink = commands.add_parser("unlink")
    unlink.add_argument("--from", dest="from_node", required=True)
    unlink.add_argument("--to", dest="to_node", required=True)
    unlink.add_argument("--dry-run", action="store_true")
    unlink.add_argument("--no-accept", action="store_true")
    unlink.add_argument("--workspace")
    prune = commands.add_parser("prune")
    prune.add_argument("--node", action="append", required=True)
    prune.add_argument("--dry-run", action="store_true")
    prune.add_argument("--no-accept", action="store_true")
    prune.add_argument("--workspace")
    member = commands.add_parser("member")  # členství existujících uzlů v oblasti, přijme ho člověk
    member.add_argument("--area", required=True, help="ID oblasti (kind area), nebo none pro zrušení")
    member.add_argument("--nodes", required=True, help="id1,id2,… karet a sektorů")
    member.add_argument("--dry-run", action="store_true")
    member.add_argument("--workspace")
    order = commands.add_parser("order")  # pořadí existujících uzlů podle záměru, ne vazba next
    order.add_argument("--nodes", required=True, help="id1=101,id2=102,… (fáze × 100 + pozice), id=none odebere")
    order.add_argument("--dry-run", action="store_true")
    order.add_argument("--workspace")
    proposal = commands.add_parser("proposal")  # přijetí návrhu grafu z agent-state, jen při plné autonomii
    proposal.add_argument("--accept", required=True, metavar="ID")
    steps = commands.add_parser("steps")  # kroky existující karty návrhem zadání (krátký výslech karty)
    steps.add_argument("--node", required=True)
    steps.add_argument("--file", required=True, help='JSON {"steps": […], "goal"?, "acceptance"?}')
    steps.add_argument("--dry-run", action="store_true")
    space = commands.add_parser("workspace")
    space.add_argument("--domain", required=True)
    space.add_argument("--reuse", action="store_true")
    space.add_argument("--name", help="stránka · co se dělá (popisek prostoru)")
    answer = commands.add_parser("answer")
    answer.add_argument("--ticket", required=True)
    answer.add_argument("--text", required=True)
    commands.add_parser("cancel").add_argument("--task", required=True)
    commands.add_parser("escalate").add_argument("--text", required=True)
    verdict = commands.add_parser("intake")  # stanovisko vstupu brány (docs/navrhy/2026-10-30-vstupni-brana.md §3)
    verdict.add_argument("--entry", required=True)
    verdict.add_argument("--verdict", required=True, choices=VERDICTS)
    verdict.add_argument("--reason")
    verdict.add_argument("--requirement", help="rq_… = připojit k požadavku, new = založit (s --title)")
    verdict.add_argument("--title")
    verdict.add_argument("--open-condition", help="jen later_extension: ID milníku, po jehož splnění se otevře")
    milestone = commands.add_parser("milestone")  # návrh milníku oblasti (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5)
    milestone.add_argument("--area", required=True)
    milestone.add_argument("--title", required=True)
    milestone.add_argument("--criterion", action="append", required=True, help='"text::nodeId,nodeId"')
    decision = commands.add_parser("milestone-decide")  # rozhodnutí o návrhu milníku, jen při plné autonomii
    choice = decision.add_mutually_exclusive_group(required=True)
    choice.add_argument("--activate", metavar="MILESTONE_ID")
    choice.add_argument("--reject", metavar="MILESTONE_ID")
    brief = commands.add_parser("brief")  # syntéza výslechu (docs/navrhy/2026-10-30-vyslech-srdce.md §7)
    brief.add_argument("--requirement", required=True)
    brief.add_argument("--synthesis", required=True, help="@cesta k JSON souboru, nebo JSON")
    ask = commands.add_parser("ask")  # otázka výslechu pro člověka, s doporučenou odpovědí
    for flag in ("--requirement", "--question", "--recommended", "--why"):
        ask.add_argument(flag, required=True)
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
    ctx.add_argument("--node")  # jen plan-of: plné zadání podstromu uzlu
    ctx.add_argument("--full", action="store_true")  # jen plan-of: zhuštěný JSON místo řádků (pro skripty dílny)
    script = commands.add_parser("run")
    script.add_argument("script")
    script.add_argument("script_args", nargs=argparse.REMAINDER)
    research = commands.add_parser("research")
    research.add_argument("--question", required=True)
    research.add_argument("--title", required=True)
    research.add_argument("--target", action="append", default=[])
    research.add_argument("--fragment")
    research.add_argument("--workspace")  # schránka je v prostoru; v main (read-only) bez tohoto jde do aktivního prostoru
    research.add_argument("--deep", action="store_true")
    research.add_argument("--layer", action="append", default=[], choices=LAYERS)
    research.add_argument("--requirement")  # rešerše výslechu: strop ceny na požadavek, cena do spisu
    commands.add_parser("skill").add_argument("name")
    duel = commands.add_parser("duel")
    for flag in ("--subject", "--a", "--b"):
        duel.add_argument(flag, required=True)
    duel.add_argument("--workspace")
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
