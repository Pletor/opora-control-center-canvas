"""Průchodový test cesty (docs/navrhy/2026-11-13-denik-chyb.md §11): pískoviště projde cestu agenta bez modelu.

Kroky jdou stejnými veřejnými routami jako `opora_hub.py start/deliver`, klientem nad aplikací v procesu
(žádný socket, žádný model): projekt → karta se `spec.steps` → přijetí → start → commit a průběžný krok →
deliver s commitem → uzavřená karta. Každý krok má čas a výsledek; první selhání se zapíše do deníku chyb
(`source=path`), průchod se zastaví a zbytek je „neprověřeno“. Zelený průchod zavře dřívější záznamy průchodu.

Pískoviště zakládá a autonomii zapíná jen člověk (výjimka §4 plné autonomie): projde to jen průchod, který
spustil člověk svým dokladem UI; agent a denní tik dostanou krok `projekt` jako „vyžaduje člověka“.
Stav je jeden JSON v datovém kořeni (`path-probe/probe.json`: pískoviště, poslední průchod, historie 30),
protože jediný zapisovatel je tento modul pod zámkem a tabulka v registru by potřebovala migraci.
"""
import json
import os
import subprocess
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as StepTimeout
from datetime import UTC, datetime
from pathlib import Path

from backend.app import errors

HUB = "/api/oporahub"
AGENT = {"X-Opora-Actor": "agent; name=pruchod"}
STEP_TIMEOUT, HISTORY, DAY, CHECK_EVERY = 60, 30, 86400, 900
ACCEPT = ("accept_baseline", "propose_graph", "accept")
SPEC_STEPS = [{"id": "s1", "order": 1, "title": "Zapsat soubor průchodu", "acceptance": ["soubor je v commitu"],
               "dependsOn": []}]
STEPS = (("projekt", "pískoviště: lokální git a plná autonomie"), ("karta", "karta se spec.steps"),
         ("prijeti", "přijetí obsahu a grafu"), ("start", "claim/start"), ("krok", "commit a průběžný krok"),
         ("deliver", "deliver s commitem"), ("uzavreni", "uzavření karty"))
HUMAN_LEVER = "Člověk: spusť POST /api/pletor/path-probe z UI (jeho doklad založí pískoviště a zapne autonomii)."
_running = threading.Lock()


class Stop(Exception):
    """Krok neprošel: `cause` = text odpovědi, `lever` = co uvolnit, `human` = projde jen s člověkem."""

    def __init__(self, reason, cause="", lever="", human=False):
        super().__init__(reason)
        self.reason, self.cause, self.lever, self.human = reason, cause, lever, human


def folder(root):
    return Path(root) / "path-probe"


def _load(root):
    try:
        return json.loads((folder(root) / "probe.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _save(root, data):
    target = folder(root) / "probe.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8", newline="") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    temp.replace(target)


def last(root):
    """Poslední průchod, nebo None."""
    return _load(root).get("last")


def headline(result):
    """Jedna řádka pro Velín a průhled srdce: zelený / stojí na kroku X: důvod → páka."""
    if not result:
        return "PRŮCHOD CESTY: zatím neproběhl → POST /api/pletor/path-probe"
    if result["ok"]:
        return f"PRŮCHOD CESTY: zelený ({result['at']}, {result['ms']} ms)"
    step = next(item for item in result["steps"] if item["status"] in ("fail", "human"))
    return (f"PRŮCHOD CESTY: stojí na kroku {step['id']} ({result['at']}): {step['reason']}"
            f"{' → ' + step['lever'] if step.get('lever') else ''}")


def text(result):
    lines = [headline(result)]
    for step in (result or {}).get("steps", []):
        ms = "" if step["ms"] is None else f" {step['ms']} ms"
        lines.append(f"  {step['status']:<10} {step['id']}{ms}: {step['label']}"
                     f"{' · ' + step['reason'] if step.get('reason') else ''}")
    return "\n".join(lines)


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *args], check=False, capture_output=True, text=True,
                          timeout=STEP_TIMEOUT)
    if done.returncode:
        raise Stop(f"git {args[0]} → {done.returncode}", done.stderr, "Oprav pískoviště " + str(repo))
    return done.stdout.strip()


class Probe:
    def __init__(self, app, cookies):
        # Klient nad aplikací v procesu, nikdy `with` (spustil by lifespan a při odchodu zavřel živou službu).
        from starlette.testclient import TestClient

        port = int(os.environ.get("OPORA_CANVAS_PORT", "8740"))
        self.origin = f"http://127.0.0.1:{port}"
        self.client = TestClient(app, base_url=self.origin, raise_server_exceptions=False)
        self.client.cookies.clear()  # identitu nese jen doklad volajícího člověka, nic zděděného
        self.client.cookies.update(cookies or {})
        self.human = bool(cookies)
        self.root = app.state.service.root
        self.data = _load(self.root)
        self.repo = folder(self.root) / "repo"
        self.scope = None

    def call(self, method, path, body=None, *, human=False, headers=None, params=None):
        sent = {"Origin": self.origin, **({} if human else AGENT), **(headers or {})}
        response = self.client.request(method, path, headers=sent, json=body, params=params)
        if response.status_code != 200:
            try:
                value = response.json()
            except ValueError:
                value = {}
            raise Stop(f"{method} {path} → {response.status_code} {value.get('code', '')}".strip(), response.text,
                       value.get("hint") or "")
        return response.json()

    # --- kroky ---------------------------------------------------------------------------------

    def projekt(self):
        pid = self.data.get("project")
        if pid:
            try:
                if self.call("GET", "/api/project-settings", params={"project": pid})["agentAutonomy"]["full"]:
                    self.scope = {"project": pid, "workspace": "draft"}
                    return
            except Stop:
                pass  # projekt zmizel: založit znovu smí jen člověk
        if not self.human:
            raise Stop("pískoviště chybí nebo nemá plnou autonomii; zakládá ho a autonomii zapíná jen člověk",
                       f"project={pid}", HUMAN_LEVER, human=True)
        if not (self.repo / ".git").exists():
            self.repo.mkdir(parents=True, exist_ok=True)
            _git(self.repo, "init", "-b", "main")
            _git(self.repo, "config", "user.name", "OPORA průchod")
            _git(self.repo, "config", "user.email", "pruchod@opora.invalid")
            (self.repo / "README.md").write_text("Pískoviště průchodového testu cesty OPORY.\n", encoding="utf-8")
            _git(self.repo, "add", ".")
            _git(self.repo, "commit", "-m", "Pískoviště průchodu")
        pid = self.call("POST", "/api/local-project", {"name": "Pískoviště průchodu", "path": str(self.repo.resolve()),
                                                      "confirmed": True}, human=True)["id"]
        self.call("POST", "/api/project-settings/agent-autonomy", {"project": pid, "full": True}, human=True)
        # OP-803AC7.projekt: pískoviště si mapy neobnovuje (worker by na každém sloučení volal Graphify).
        self.call("POST", "/api/map-refresh/settings", {"project": pid, "tool": "graphify", "automatic": False},
                  human=True)
        self.data["project"], self.scope = pid, {"project": pid, "workspace": "draft"}
        _save(self.root, self.data)

    def karta(self):
        sector = self.data.get("sector")
        nodes = [] if sector else [{"ref": "sektor", "kind": "sector", "parent": None, "name": "Průchod cesty"}]
        nodes.append({"ref": "karta", "kind": "node", "parent": "@" + sector if sector else "sektor",
                      "name": "[task] Průchod " + datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                      "spec": {"goal": "Průchod cesty agenta.", "acceptance": "soubor průchodu je v commitu",
                               "steps": SPEC_STEPS}})
        # OP-803AC7.karta: návrh grafu, ne /api/canvas-plan. Nad přijatým grafem by přímý zápis plánu nechal pracovní
        # graf odlišný od přijatého a agent-state nenabídne žádnou akci (start → 409); srdce i UI jdou touto cestou.
        context = self.call("GET", HUB + "/graph-proposals/context", params=self.scope)
        refs = self.call("POST", HUB + "/graph-proposals", {
            **self.scope, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
            "subject": "Průchod cesty", "plan": {"nodes": nodes, "edges": []}})["refs"]
        self.card = refs["karta"]
        if not sector:
            self.data["sector"] = refs["sektor"]
            _save(self.root, self.data)

    def prijeti(self):
        # Jako `opora_hub.py act`: ready akce přijetí přesně podle method/path/preconditions, dokud nějaká je.
        for _ in range(6):
            actions = self.call("GET", HUB + "/agent-state", params=self.scope)["actions"]
            found = [a for a in actions if a["verb"] in ACCEPT]
            ready = next((a for a in found if a["status"] == "ready"), None)
            if ready is None:
                if found:  # zablokované přijetí: zastavit tady s jeho důvodem, ne až na startu s cizí pákou
                    raise Stop("přijetí je zablokované: " + ", ".join(str(a.get("blockReason")) for a in found),
                               json.dumps(found, ensure_ascii=False)[:2000], "GET /api/oporahub/agent-state → actions")
                return
            self.call("POST", ready["path"], {**self.scope, **(ready.get("preconditions") or {})})
        raise Stop("přijetí se necyklí do konce (6 akcí)", "", "GET /api/oporahub/agent-state → actions")

    def start(self):
        self.run = self.call("POST", HUB + "/executions/start", {**self.scope, "nodeId": self.card, "ttlSeconds": 600})

    def krok(self):
        (self.repo / "pruchod.txt").write_text(f"{self.card} {uuid.uuid4().hex}\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-m", "Průchod cesty", "-m", "Opora-Node: " + self.card)
        self.sha = _git(self.repo, "rev-parse", "HEAD")
        self.call("POST", f"{HUB}/executions/{self.run['executionId']}/steps", {
            **self.scope, "token": self.run["token"], "epoch": self.run["epoch"], "requestId": "step-s1-done",
            "stepId": "s1", "status": "done", "evidence": {"notes": "soubor průchodu", "commits": [self.sha]}})

    def deliver(self):
        self.delivered = self.call("POST", f"{HUB}/executions/{self.run['executionId']}/deliver", {
            **self.scope, "summary": "Průchod cesty bez modelu.", "steps": [{"stepId": "s1", "status": "done"}],
            "checks": [{"name": "pruchod", "status": "green"}], "commit": self.sha},
            headers={"X-Opora-Execution-Token": self.run["token"]})

    def uzavreni(self):
        if not self.delivered.get("closed"):
            raise Stop("deliver kartu neuzavřel: chybí " + ", ".join(self.delivered.get("missing") or []),
                       json.dumps(self.delivered, ensure_ascii=False)[:2000], (self.delivered.get("next") or {}).get("command") or "")
        cards = self.call("GET", HUB + "/agent-state", params=self.scope)["cards"]
        dod = next((c["dod"] for c in cards if c["nodeId"] == self.card), {})
        if not dod.get("done"):
            raise Stop("karta po deliver není hotová", json.dumps(dod, ensure_ascii=False), "")


def _step(pool, action):
    """Krok ve vlákně se skutečným timeoutem: zaseknutý zámek nesmí zastavit průchod (§0)."""
    future = pool.submit(action)
    try:
        future.result(timeout=STEP_TIMEOUT)
    except StepTimeout:
        raise Stop(f"krok přesáhl {STEP_TIMEOUT} s", "", "GET /api/pletor/heart/explain?format=text → POMALÉ POŽADAVKY") from None


def run(app, cookies=None, steps=None):
    """Jeden průchod; `cookies` = doklad volajícího člověka (jen ten smí založit pískoviště). None = už běží."""
    if not _running.acquire(blocking=False):
        return None
    try:
        return _run(app, cookies, steps)
    finally:
        _running.release()


def _run(app, cookies, steps):
    probe, began = Probe(app, cookies), time.monotonic()
    out, stopped = [], None
    # Jedno vlákno na celý průchod: kroky běží po sobě, timeout jen přestane čekat (vlákno se nedá zabít).
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="opora-pruchod")
    try:
        for key, label in STEPS:
            item = {"id": key, "label": label, "status": "unchecked", "ms": None}
            out.append(item)
            if stopped:
                continue
            at = time.monotonic()
            try:
                _step(pool, (steps or {}).get(key) or getattr(probe, key))
                item["status"] = "ok"
            except Stop as stop:
                item.update(status="human" if stop.human else "fail", reason=stop.reason, lever=stop.lever)
                stopped = (key, "blocked", stop.reason, stop.cause, stop.lever)
            except Exception as error:  # noqa: BLE001 – průchod hlásí, co spadlo, nikdy nespadne sám
                item.update(status="fail", reason=f"{type(error).__name__}: {error}"[:300], lever="")
                stopped = (key, "exception", item["reason"], traceback.format_exc(), "")
            item["ms"] = round((time.monotonic() - at) * 1000)
    finally:
        pool.shutdown(wait=False)
    project = (probe.scope or {}).get("project")
    if stopped:
        key, kind, reason, cause, lever = stopped
        # OP-803AC7.denik: stálé message (sčítá se do count), proměnlivý text odpovědi v cause.
        errors.record("path", kind, f"Průchod cesty stojí na kroku {key}", project=project, subject=key,
                      cause=f"{reason}\n{cause}", lever=lever or None)
    else:
        errors.resolve(source="path")
    result = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "ok": stopped is None,
              "ms": round((time.monotonic() - began) * 1000), "project": project,
              "by": "human" if probe.human else "agent", "steps": out}
    data = _load(probe.root)
    data["last"] = result
    data["history"] = ([result] + data.get("history", []))[:HISTORY]
    _save(probe.root, data)
    return result


def due(root, now=None):
    """Denní průchod: pískoviště existuje a poslední průchod je starší než 24 h (čas z JSON, restart ho nesmaže)."""
    data = _load(root)
    if not data.get("project"):
        return False
    at = (data.get("last") or {}).get("at")
    return at is None or (now or time.time()) - datetime.fromisoformat(at).timestamp() >= DAY


def tick_forever(app, stop):
    """Denní tik: první kontrola až po CHECK_EVERY (testy ani start serveru nic nespustí), pak každých 15 min."""
    while not stop.wait(CHECK_EVERY):
        try:
            if due(app.state.service.root):
                run(app)
        except Exception:  # noqa: BLE001 – tik nesmí umřít; selhání kroku už je v deníku
            traceback.print_exc()
