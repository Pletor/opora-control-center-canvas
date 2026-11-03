"""Scénáře O sondy srdce: předávka plánovač (srdce) ↔ vykonavatel (orchestrátor `claude -p` se skillem).

Kontrakt spolupráce: docs/brain-heart-orchestrator.md (O1 pruh, O2 `plan`, O3 git, O4 skill). Jedna smyčka O1:
záměr člověka → dávka srdce → (člověk přijme plán, je-li třeba) → kolo orchestrátora → reakce srdce (merged /
commits) → … až `rounds` kol. Varianta `cards` = karty (`plan`) a pruh executions, `tasks` = fronta brány
(`task`, `opora_gate.py next/report`). Metriky počítá kód z API OPORY a z gitu (`metrics`), žádný model.
Volá `probe.py --scenarios O1 --variant cards --rounds 2`.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import heart_arm
import run_eval

WS = "draft"
O_BUDGET_USD = 3.0
SKILL_SRC = run_eval.SKILL_SRC
HUMAN_ACCEPT = ("propose_graph", "accept_baseline", "accept")
# Sonnet: $/MTok (vstup, zápis cache, čtení cache, výstup) – jen pro hlídač rozpočtu běžícího kola
SONNET = (3.0, 3.75, 0.30, 15.0)

INTENT = """Záměr: v tomto repozitáři postav malou aplikaci v Pythonu `ukoly.py` (jen standardní knihovna) na správu úkolů.

Fáze 1 (MVP): seznam úkolů s přidáním a smazáním. Třída `SeznamUkolu` s metodami `pridat(text)`, `smazat(cislo)`
a `seznam()` (očíslovaně od 1) a interaktivní režim `python ukoly.py` s příkazy `pridat <text>`, `seznam`,
`smazat <číslo>`, `konec`.
Fáze 2: filtrování (`filtr <slovo>` ukáže jen úkoly obsahující slovo, bez ohledu na velikost písmen) a uložení do
souboru (`uloz <soubor>` a `nacti <soubor>`, formát JSON, UTF-8).

Pravidla: texty česky; chybný vstup (neexistující číslo, prázdný text) vypíše srozumitelnou chybu a nespadne;
každá funkce má test v `test_ukoly.py` (`python -m unittest`)."""

PHASE_HINT = {"auto": "",
              "all": "\n\nNaplánuj hned obě fáze najednou.",
              "one": "\n\nNaplánuj teď jen fázi 1 (MVP); fázi 2 naplánuj, až uvidíš MVP sloučené v gitu."}
# --hint-schema: tvar dávky `plan` v záměru (srdce ho v promptu nemá; smoke o-smoke 2026-10-29: 6× 409 a eskalace)
SCHEMA_HINT = ("\n\nTvar dávky `plan` (docs/davka-planu.md): {\"nodes\": [{\"ref\": \"mvp\", \"kind\": \"node\", "
               "\"parent\": null, \"name\": \"[task] …\", \"spec\": {\"goal\": \"…\", \"non_goals\": \"…\", "
               "\"acceptance\": \"…\", \"steps\": [{\"id\": \"s1\", \"order\": 1, \"title\": \"…\", "
               "\"acceptance\": [\"…\"], \"dependsOn\": []}]}}], \"edges\": [{\"from\": \"mvp\", \"to\": \"dalsi\", "
               "\"port\": \"next\"}]}. `kind` je jen node | sector | comment | area.")
VARIANT_HINT = {"cards": "",
                "tasks": "\n\nPráci dělá pracovník přes bránu (`opora_gate.py next/report`): zadej ji úkoly fronty "
                         "(`task`), ne kartami na plátně."}

APP_FILES = {
    "ukoly.py": '"""Správa úkolů (kostra)."""\n\n\nclass SeznamUkolu:\n    pass\n\n\n'
                'def main():\n    print("ukoly: zatím nic")\n\n\nif __name__ == "__main__":\n    main()\n',
    "test_ukoly.py": "import unittest\n\nimport ukoly\n\n\nclass Kostra(unittest.TestCase):\n"
                     "    def test_import(self):\n        self.assertTrue(hasattr(ukoly, 'SeznamUkolu'))\n\n\n"
                     "if __name__ == '__main__':\n    unittest.main()\n",
    "README.md": "# ukoly\n\nMalá aplikace na správu úkolů. Testy: `python -m unittest`.\n",
    ".gitignore": "__pycache__/\n.opora/\n*.json\n",
}


def now():
    return time.time()


def log(*parts):
    print(time.strftime("%H:%M:%S"), "[O]", *parts, flush=True)


def git(ws, *args, check=True):
    r = subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@local", "-c", "core.autocrlf=false",
                        *args], cwd=ws, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def make_app(ws: Path):
    for rel, text in APP_FILES.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "kostra aplikace ukoly")


# --- čisté pomocníky (testované v test_orch.py) ----------------------------------------------------

def tokens(text):
    return set(re.findall(r"[0-9a-záčďéěíňóřšťúůýž]{3,}", (text or "").lower()))


def jaccard(a, b):
    x, y = tokens(a), tokens(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def near_duplicates(titles, threshold=0.7):
    """Dvojice (i, j, J) položek s normalizovanou tokenovou Jaccardovou podobností ≥ threshold."""
    out = []
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            score = jaccard(titles[i], titles[j])
            if score >= threshold:
                out.append((i, j, round(score, 2)))
    return out


def usage_cost(usage, prices=SONNET):
    """Odhad ceny z `usage` zprávy (vstup, zápis cache, čtení cache, výstup)."""
    p_in, p_cw, p_cr, p_out = prices
    return ((usage.get("input_tokens") or 0) * p_in + (usage.get("cache_creation_input_tokens") or 0) * p_cw
            + (usage.get("cache_read_input_tokens") or 0) * p_cr + (usage.get("output_tokens") or 0) * p_out) / 1e6


def stream_usage(lines):
    """Součet `usage` přes jedinečné zprávy asistenta ve stream-json (blok zprávy se opakuje se stejným id)."""
    seen, total, peak = set(), {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                                "output_tokens": 0}, 0
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message") or {}
        if ev.get("type") != "assistant" or not msg.get("usage") or msg.get("id") in seen:
            continue
        seen.add(msg.get("id"))
        u = msg["usage"]
        for k in total:
            total[k] += u.get(k) or 0
        ctx = (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
        peak = max(peak, ctx)
    return {**total, "messages": len(seen), "peakContextTokens": peak}


def heart_commands(batch):
    """Příkazy `opora_heart.py` dávky z přepisu: kolik `plan` (naostro / dry-run) a `task`."""
    cmds = (batch.get("transcript") or {}).get("bash", [])
    plan = [c for c in cmds if re.search(r"opora_heart\.py\s+plan\b", c) and "--file" in c]
    return {"planReal": sum(1 for c in plan if "--dry-run" not in c), "planDry": sum(1 for c in plan if "--dry-run" in c),
            "task": sum(1 for c in cmds if re.search(r"opora_heart\.py\s+task\b", c)),
            "answer": sum(1 for c in cmds if re.search(r"opora_heart\.py\s+answer\b", c)),
            "escalate": sum(1 for c in cmds if re.search(r"opora_heart\.py\s+escalate\b", c))}


def listing(body, *keys):
    """Seznam z odpovědi API neznámého tvaru: první klíč se seznamem, jinak samotný seznam."""
    if isinstance(body, list):
        return body
    for key in keys:
        if isinstance((body or {}).get(key), list):
            return body[key]
    return []


def first(item, *keys):
    for key in keys:
        if isinstance(item, dict) and item.get(key) not in (None, ""):
            return item[key]
    return None


# --- OPORA jako člověk a data ----------------------------------------------------------------------

class Orch:
    def __init__(self, run, args, probe):
        self.run, self.args, self.p = run, args, probe
        self.variant, self.rounds_n, self.phase = args.variant, args.rounds, args.phase
        self.key = "APP"
        self.app = run.dir / "app"
        self.orch_usd, self.rounds, self.timeline, self.accepts = 0.0, [], [], []
        self.seen_items = {}   # id -> {title, firstSeen, afterBatch}
        self.aborted = None

    # pomocníci API
    @property
    def pid(self):
        return self.run.projects[self.key]["id"]

    def q(self, **extra):
        return {"project": self.pid, "workspace": WS, **extra}

    def get(self, path, **query):
        status, body, _ = self.run.api.req("GET", path, query=self.q(**query), human=True, timeout=120)
        return status, body

    def agent_state(self):
        status, body = self.get("/api/oporahub/agent-state")
        return body if status == 200 else {"_status": status, "_body": body}

    def graph_names(self):
        status, body = self.get("/api/view")
        nodes = ((body or {}).get("graph") or {}).get("nodes") or [] if status == 200 else []
        return {n.get("id"): n.get("name") or n.get("label") or "" for n in nodes if isinstance(n, dict)}

    def executions(self):
        status, body = self.get("/api/oporahub/executions")
        return listing(body, "executions", "items", "history") if status == 200 else []

    def events(self):
        out, since = [], 0
        for _ in range(50):
            status, body = self.get("/api/oporahub/events", since=since, limit=200)
            if status != 200:
                break
            chunk = body.get("events") or []
            out += chunk
            if len(chunk) < 200:
                break
            since = body.get("cursor") or since
        return out

    def spent(self):
        return round(heart_arm.heart_cost(self.run.batches(self.key))["usd"] + self.orch_usd, 4)

    # položky plánu (karty nebo úkoly) podle varianty
    def items(self):
        if self.variant == "tasks":
            return [{"id": t["taskId"], "title": t.get("title"), "status": t.get("status"), "raw": t}
                    for t in self.run.tasks(self.key)]
        names = self.graph_names()
        state = self.agent_state()
        cards = listing(state, "cards")
        out = []
        for c in cards:
            nid = c.get("nodeId")
            out.append({"id": nid, "title": names.get(nid, ""), "status": c.get("stage"), "health": c.get("health"),
                        "dod": c.get("dod"), "steps": c.get("steps"), "lease": c.get("lease"),
                        "executionId": c.get("executionId"), "blockedBy": c.get("blockedBy"), "reason": c.get("reason")})
        return out

    def observe(self, label):
        """Zapíše položky, které přibyly, s časem prvního pozorování (po dávce srdce `label`)."""
        nb = len(self.run.batches(self.key))
        fresh = []
        for item in self.items():
            if item["id"] not in self.seen_items:
                self.seen_items[item["id"]] = {"title": item["title"], "firstSeen": now(), "afterBatch": nb,
                                               "label": label}
                fresh.append(item["title"])
        self.timeline.append({"at": now(), "event": "observe", "label": label, "new": fresh, "batches": nb})
        return fresh

    # člověk přijme plán (karty potřebují přijatý graf a kroky; agent je ve zdi nemůže přijmout sám)
    def human_accept(self, label):
        done = []
        for _ in range(8):
            state = self.agent_state()
            todo = [a for a in listing(state, "actions") if a.get("verb") in HUMAN_ACCEPT
                    and a.get("method") == "POST" and a.get("path")]
            if not todo:
                break
            a = todo[0]
            body = {"project": self.pid, "workspace": WS, **(a.get("preconditions") or {})}
            status, resp, _ = self.run.api.req("POST", a["path"], body, human=True, timeout=120)
            done.append({"verb": a.get("verb"), "target": a.get("targetId"), "actionStatus": a.get("status"),
                         "blocked": a.get("blocked") or a.get("reason"), "http": status,
                         "code": (resp or {}).get("code") if isinstance(resp, dict) else None,
                         "error": str((resp or {}).get("error") or (resp or {}).get("detail") or "")[:200]
                         if isinstance(resp, dict) and status >= 400 else None})
            if status >= 400:
                break
        self.accepts.append({"label": label, "at": now(), "done": done})
        return done

    # srdce
    def message(self, text):
        return self.run.api.human("POST", "/api/brain/heart/messages", {**self.q(), "text": text})

    def wait_heart(self, before, timeout, settle):
        try:
            self.run.wait_heart(self.key, before, need_new=True, timeout=timeout, settle=settle)
            return None
        except Exception as error:  # noqa: BLE001
            return f"{type(error).__name__}: {error}"

    # orchestrátor
    def prepare_agent(self):
        skill = self.run.dir / "skill" / "opora-control-center"
        if not skill.exists():
            shutil.copytree(SKILL_SRC, skill, ignore=shutil.ignore_patterns("__pycache__", "test_*.py"))
        gate_py = str(heart_arm.install_gate_client(self.run.dir, "orch")).replace("\\", "/")
        home = self.run.dir / "orch-home"
        home.mkdir(parents=True, exist_ok=True)
        skill_md = (skill / "SKILL.md").read_text("utf-8")
        ctx = ("# Prostředí OPORA (agent-office)\n"
               f"Base directory for this skill: {skill.as_posix()}\n"
               f"Server OPORA: {self.run.api.base} (proměnná OPORA_BASE_URL), projekt `{self.pid}`, pracovní "
               f"prostor `{WS}`. Identita: OPORA_AGENT_NAME=office-orchestrator.\n"
               f"Klient brány pro tebe: `python {gate_py}` (místo `scripts/opora_gate.py`, relace se drží mimo repo).\n"
               "Projekt má zapnutou bránu mozku: plán dělá srdce, ty konáš (references/srdce.md).\n"
               "Člověk během běhu nereaguje. Kód piš jen v aktuálním adresáři (git, větev main, bez origin).\n\n---\n\n"
               + skill_md)
        path = self.run.dir / "orch-context.md"
        path.write_text(ctx, encoding="utf-8")
        return path, gate_py, home

    def orch_prompt(self, rnd, gate_py):
        skill = (self.run.dir / "skill" / "opora-control-center").as_posix()
        hub = f"python {skill}/scripts/opora_hub.py"
        gate = f"python {gate_py}"
        scope = f"--project {self.pid} --workspace {WS}"
        head = (f"Jsi orchestrátor v agent-office pro projekt `{self.pid}` (prostor `{WS}`, lokální projekt bez "
                f"GitHubu). Kolo {rnd} z {self.rounds_n}. Plán dělá srdce OPORY; ty bereš práci, rozesíláš ji dělníkům "
                "a odevzdáváš. V tomto běhu jsi zároveň svým jediným dělníkem: kód napíšeš sám. Zadání máš jen z OPORY; "
                "práci si nevymýšlej.\n\n")
        if self.variant == "tasks":
            start = (f"1. {'Založ relaci brány' if rnd == 1 else 'Relace brány už existuje; pokud ne, založ ji'}: "
                     f"`{gate} session {scope} --name office-orchestrator`.\n")
            body = (start +
                    f"2. Opakuj nejvýš 2×: `{gate} next` → úkol `answer.task`; udělej ho přesně (files, doneWhen, rules), "
                    "commitni (`git add <soubory>`, `git commit -m \"<title>\" -m \"Opora-Task: <id>\"`), spusť "
                    f"`python -m unittest`, pak `{gate} report --task <id> --sha <git rev-parse HEAD> --summary \"…\" "
                    "--check \"python -m unittest=green|red\"` podle skutečnosti.\n"
                    f"3. Je-li úkol nejasný nebo plán špatně, `{gate} ask \"…\"` / `{gate} change \"…\" --reason \"…\"` "
                    f"a odpověď čti `{gate} inbox --wait 30`.\n"
                    "4. Skonči, když `next` vrátí `task: null` nebo po 2 úkolech. Na závěr shrň, co je hotové a co zůstalo.\n")
        else:
            body = (f"1. Stav: `{hub} state {scope}` (karty, ready akce). Plán srdce: `GET /api/brain/heart/snapshot`.\n"
                    f"2. Vezmi `ready` kartu podle pořadí serveru: `{hub} start {scope} --node <nodeId>` (claim + zadání).\n"
                    "3. Udělej kroky `spec.steps` zadání v tomto repu, commit po kroku s trailerem `Opora-Node: <nodeId>`, "
                    "spusť `python -m unittest`.\n"
                    f"4. Odevzdej: `{hub} deliver {scope} --execution <E> --summary \"…\" --step s1:\"…\" "
                    "--check \"python -m unittest=green\"` (lokální projekt: deliver provede i local-merge). "
                    "Když deliver vrátí `missing`, udělej `next`, který ti řekne.\n"
                    "5. Nejvýš 2 karty za kolo, pak skonči. Žádná `ready` karta = skonči (nečekej ve smyčce).\n"
                    f"6. Chybí karta nebo je plán špatně: nepiš plán sám, `{gate} session {scope} --name office-orchestrator` "
                    f"a `{gate} change \"…\" --reason \"…\"` (nebo `ask`); odpověď `{gate} inbox --wait 30`.\n"
                    "7. Po sloučení nic nehlas, srdce to vidí z gitu. Na závěr shrň, co je hotové a co zůstalo.\n")
        return head + body

    def run_round(self, rnd, ctx, gate_py, home):
        prompt = self.orch_prompt(rnd, gate_py)
        cmd = run_eval.agent_command(prompt, "sonnet", "A", ctx, [self.run.dir / "skill", self.run.dir / "gate"])
        raw = self.run.dir / f"orch-{self.variant}-r{rnd}.jsonl"
        env = run_eval.child_env({"OPORA_BASE_URL": self.run.api.base, "OPORA_AGENT_NAME": "office-orchestrator",
                                  "OPORA_HOME": str(home)})
        stop = threading.Event()
        killed = {}

        def watchdog():
            while not stop.wait(10):
                if not raw.exists():
                    continue
                est = usage_cost(stream_usage(raw.read_text("utf-8", "replace").splitlines()))
                if self.spent() + est > O_BUDGET_USD:
                    killed["reason"] = f"rozpočet: srdce+orchestrátor {self.spent()} + kolo {round(est, 3)} > {O_BUDGET_USD}"
                    if proc_ref.get("p"):
                        self.p.grade.kill_tree(proc_ref["p"])
                    return

        proc_ref = {}
        exe = [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]
        t0 = now()
        guard = threading.Thread(target=watchdog, daemon=True)
        with raw.open("wb") as out, raw.with_suffix(".stderr.txt").open("wb") as err:
            proc = subprocess.Popen(exe, cwd=self.app, stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env)
            proc_ref["p"] = proc
            guard.start()
            try:
                proc.wait(timeout=self.args.round_timeout)
            except subprocess.TimeoutExpired:
                killed.setdefault("reason", f"timeout {self.args.round_timeout} s")
                self.p.grade.kill_tree(proc)
        stop.set()
        stats = self.p.stream_stats(raw)
        usage = stream_usage(raw.read_text("utf-8", "replace").splitlines())
        cost = float(stats["costUsd"] or 0) or usage_cost(usage)
        self.orch_usd += cost
        hub_calls = []
        for line in raw.read_text("utf-8", "replace").splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            for block in (ev.get("message") or {}).get("content") or [] if ev.get("type") == "assistant" else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    c = str((block.get("input") or {}).get("command", ""))
                    if "opora_hub.py" in c:
                        hub_calls.append(c.split("opora_hub.py", 1)[1][:140])
        return {"round": rnd, "startEpoch": round(t0, 1), "endEpoch": round(now(), 1), "wallS": round(now() - t0, 1),
                "exit": proc.returncode, "killed": killed.get("reason"), "costUsd": round(cost, 4),
                "usage": usage, "numTurns": stats["numTurns"], "tools": stats["tools"], "gateCalls": stats["gateCalls"],
                "hubCalls": hub_calls, "denials": stats["denials"], "final": stats["final"]}

    # celá smyčka
    def loop(self):
        t_start = now()
        make_app(self.app)
        base_sha = git(self.app, "rev-parse", "HEAD")
        self.run.project(self.key, self.app, f"Sonda-orch-{self.variant}")
        ctx, gate_py, home = self.prepare_agent()
        settle = self.args.git_poll + 35  # merged (okno 20 s) i commits (hlídač + okno 20 s) musí stihnout dávku
        before = len(self.run.batches(self.key))
        text = (INTENT + PHASE_HINT[self.phase] + VARIANT_HINT[self.variant]
                + (SCHEMA_HINT if getattr(self.args, "hint_schema", False) and self.variant == "cards" else ""))
        t_msg = now()
        reply = self.message(text)
        err = self.wait_heart(before, 1200, 15)
        self.timeline.append({"at": now(), "event": "heart-intent", "error": err})
        self.observe("intent")
        accepted = self.human_accept("after-intent") if self.variant == "cards" else []
        for rnd in range(1, self.rounds_n + 1):
            if self.spent() > O_BUDGET_USD - 0.3:
                self.aborted = f"rozpočet před kolem {rnd}: {self.spent()} USD"
                break
            log(f"kolo {rnd} orchestrátora ({self.variant}), útrata {self.spent()} USD")
            before = len(self.run.batches(self.key))
            r = self.run_round(rnd, ctx, gate_py, home)
            self.rounds.append(r)
            log(f"kolo {rnd} hotovo za {r['wallS']} s, {r['costUsd']} USD, killed={r['killed']}")
            if r["killed"] and r["killed"].startswith("rozpočet"):
                self.aborted = r["killed"]
                break
            err = self.wait_heart(before, self.args.heart_wait, settle)
            r["heartAfter"] = {"error": err, "newBatches": len(self.run.batches(self.key)) - before}
            r["newItems"] = self.observe(f"after-round-{rnd}")
            if self.variant == "cards":
                r["humanAccepts"] = self.human_accept(f"after-round-{rnd}")
        return {"baseSha": base_sha, "tMessage": t_msg, "tStart": t_start, "messageReply": reply,
                "firstAccept": accepted}


# --- metriky (kód, ne model) -----------------------------------------------------------------------

def ticket_rows(db):
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10) as con:
            return con.execute("SELECT t.id, t.kind, t.status, s.role, t.body, t.created_at, t.answered_at "
                               "FROM gate_tickets t JOIN gate_sessions s ON s.id=t.session_id ORDER BY t.seq").fetchall()
    except sqlite3.Error as error:
        return [("error", str(error), None, None, None, None, None)]


def metrics(o: Orch, meta):
    run, key, app = o.run, o.key, o.app
    batches = [o.p.batch_view(b) for b in run.batches(key)]
    items = o.items()
    execs = o.executions()
    events = o.events()
    commits = git(app, "log", "--format=%H %s", f"{meta['baseSha']}..HEAD").splitlines()
    status_lines = git(app, "status", "--porcelain").splitlines()

    # předávka
    by_node = {}
    for e in execs:
        by_node.setdefault(first(e, "nodeId", "node"), []).append(e)
    merges = [ev for ev in events if ev.get("kind") == "merge.done"]
    merged_nodes = {ev.get("nodeId") for ev in merges}
    if o.variant == "tasks":
        claimed = [i for i in items if i["status"] in ("assigned", "done", "failed")]
        delivered = [i for i in items if i["status"] == "done"]
        merged = []
        reported = [first(i["raw"].get("report") or {}, "sha") for i in items if i["status"] == "done"]
    else:
        claimed = [i for i in items if i["id"] in by_node]
        delivered = [i for i in items if any(first(e, "status", "state") in ("reported", "delivered", "completed", "merged", "succeeded")
                                             or e.get("resultAt") or e.get("deliveredAt") for e in by_node.get(i["id"], []))]
        merged = [i for i in items if i["id"] in merged_nodes or (i.get("dod") or {}).get("merged")]
        reported = [(ev.get("data") or {}).get("mergeSha") or (ev.get("data") or {}).get("commit") for ev in merges]
    plan_to_claim = []
    for i in claimed:
        seen = o.seen_items.get(i["id"], {}).get("firstSeen")
        times = [first(e, "createdAt", "claimedAt", "startedAt") for e in by_node.get(i["id"], [])]
        ts = [o.p.iso_epoch(t[:19] + "Z") for t in times if isinstance(t, str) and len(t) >= 19]
        if seen and ts:
            plan_to_claim.append(round(min(ts) - seen, 1))

    # duplicita
    owners = {n: {first(e, "owner", "holder", "actor", "agent", "claimedBy") for e in es} for n, es in by_node.items()}
    claimed_twice = [n for n, es in by_node.items() if len(es) > 1]
    open_items = [i for i in items if i["status"] not in ("done", "cancelled", "closed", "merged")
                  and not (i.get("dod") or {}).get("merged")]
    dup_open = [(open_items[a]["title"], open_items[b]["title"], j)
                for a, b, j in near_duplicates([i["title"] or "" for i in open_items])]
    first_merge_t = min((o.p.iso_epoch(str(ev.get("createdAt") or ev.get("at"))[:19] + "Z") for ev in merges
                         if isinstance(ev.get("createdAt") or ev.get("at"), str)), default=None)
    merged_titles = [i["title"] for i in merged] or [c.split(" ", 1)[1] for c in commits if " " in c]
    after_merge = [i for i in items if first_merge_t and o.seen_items.get(i["id"], {}).get("firstSeen", 0) > first_merge_t]
    replanned = [(i["title"], t, round(jaccard(i["title"], t), 2)) for i in after_merge for t in merged_titles
                 if jaccard(i["title"], t) >= 0.7]

    # slepé uličky
    tickets = ticket_rows(run.db(key))
    unanswered = [{"id": t[0], "kind": t[1], "role": t[3], "body": str(t[4])[:160]} for t in tickets
                  if t[2] == "queued"]
    running = [e for e in execs if first(e, "status", "state") in ("running", "claimed", "active", "leased")]
    failed = [i for i in items if i["status"] == "failed"]
    failed_no_follow = [i["title"] for i in failed
                        if not any(j["id"] != i["id"] and jaccard(i["title"], j["title"]) >= 0.5 for j in items)]

    # nepovšimnutá práce
    def covered(sha):
        return any(subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=app,
                                  capture_output=True).returncode == 0 for ref in reported if ref)
    unreferenced = [c for c in commits if not covered(c.split(" ")[0])]
    heart_after_merge = []
    for ev in merges:
        t = ev.get("createdAt") or ev.get("at")
        te = o.p.iso_epoch(str(t)[:19] + "Z") if isinstance(t, str) else None
        woke = [b for b in batches if any(i.get("type") == "merged" for i in b["inputs"])
                and te and b["startEpoch"] >= te - 2]
        heart_after_merge.append({"node": ev.get("nodeId"), "at": t,
                                  "batchStartAfterS": round(woke[0]["startEpoch"] - te, 1) if woke and te else None})

    # vývoj plánu
    by_input = {}
    for b in batches:
        for i in b["inputs"]:
            by_input[i.get("type")] = by_input.get(i.get("type"), 0) + 1
    phase2_words = ("filtr", "uloz", "ulož", "soubor", "nacti", "načti", "json")
    phase2_items = [i["title"] for i in items if any(w in (i["title"] or "").lower() for w in phase2_words)]
    phase2_after_merge = [i["title"] for i in after_merge if any(w in (i["title"] or "").lower() for w in phase2_words)]
    status = run.status(key)

    rounds = o.rounds
    return {
        "variant": o.variant, "phase": o.phase, "roundsPlanned": o.rounds_n, "roundsRun": len(rounds),
        "aborted": o.aborted,
        "handoff": {"planned": len(items), "claimed": len(claimed), "delivered": len(delivered), "merged": len(merged),
                    "planToClaimS": plan_to_claim, "humanAccepts": o.accepts},
        "duplication": {"claimedTwice": claimed_twice, "ownersPerNode": {k: sorted(map(str, v)) for k, v in owners.items()},
                        "nearDuplicateOpen": dup_open, "replannedMergedWork": replanned},
        "deadEnds": {"neverClaimed": [i["title"] for i in items if i not in claimed],
                     "failedWithoutFollowUp": failed_no_follow, "unansweredTickets": unanswered,
                     "executionsLeftRunning": [{k: e.get(k) for k in ("executionId", "id", "nodeId", "status", "state")}
                                               for e in running]},
        "unnoticed": {"commits": commits, "unreferencedCommits": unreferenced, "dirtyFiles": status_lines,
                      "mergeEvents": len(merges), "heartAfterMerge": heart_after_merge},
        "planEvolution": {"heartBatches": len(batches), "batchesByInput": by_input,
                          "batchesWithMergedOrCommits": sum(1 for b in batches if any(i.get("type") in ("merged", "commits")
                                                                                     for i in b["inputs"])),
                          "itemsAfterFirstMerge": [i["title"] for i in after_merge],
                          "phase2Items": phase2_items, "phase2BuiltAfterMerge": bool(phase2_after_merge),
                          "heartCommands": [heart_commands(b) for b in batches]},
        "context": {"heartInputTokensPerBatch": [b.get("inputTokens") for b in batches],
                    "heartSession": status.get("session"), "heartGitError": status.get("gitError"),
                    "heartError": status.get("error"),
                    "orchPerRound": [{"round": r["round"], "peakContextTokens": r["usage"]["peakContextTokens"],
                                      "inputTotal": r["usage"]["input_tokens"] + r["usage"]["cache_read_input_tokens"]
                                      + r["usage"]["cache_creation_input_tokens"], "costUsd": r["costUsd"],
                                      "turns": r["numTurns"]} for r in rounds]},
        "cost": {"heartUsd": heart_arm.heart_cost(run.batches(key))["usd"], "orchUsd": round(o.orch_usd, 4),
                 "totalUsd": o.spent()},
        "wallS": round(now() - meta["tStart"], 1),
        "raw": {"items": items, "executions": execs[:40], "events": [{k: ev.get(k) for k in ("id", "kind", "nodeId",
                                                                                            "executionId", "createdAt")}
                                                                    for ev in events][:200],
                "batches": batches, "rounds": rounds, "timeline": o.timeline, "seen": o.seen_items,
                "tickets": [list(t) for t in tickets], "messageReply": meta.get("messageReply")},
    }


def s_o1(run, args, probe):
    o = Orch(run, args, probe)
    meta = {}
    try:
        meta = o.loop()
    except Exception as error:  # noqa: BLE001
        o.aborted = f"{type(error).__name__}: {error}"
        log("smyčka selhala:", o.aborted)
    meta.setdefault("baseSha", git(o.app, "rev-list", "--max-parents=0", "HEAD") if (o.app / ".git").exists() else "HEAD")
    meta.setdefault("tStart", now())
    if o.key not in run.projects:
        return {"error": o.aborted}
    try:
        return metrics(o, meta)
    except Exception as error:  # noqa: BLE001
        return {"error": f"metriky: {type(error).__name__}: {error}", "aborted": o.aborted,
                "rounds": o.rounds, "timeline": o.timeline}


def table(results):
    """Krátká srovnávací tabulka všech běhů se scénářem O1-*."""
    rows = []
    for name, rr in results.get("runs", {}).items():
        for sc, e in rr.get("scenarios", {}).items():
            if not sc.startswith("O1") or "handoff" not in e:
                continue
            h, d, de, u, pe, c = (e["handoff"], e["duplication"], e["deadEnds"], e["unnoticed"], e["planEvolution"],
                                  e["cost"])
            rows.append([name, sc, h["planned"], h["claimed"], h["delivered"], h["merged"], len(d["claimedTwice"]),
                         len(d["nearDuplicateOpen"]), len(de["neverClaimed"]), len(de["unansweredTickets"]),
                         len(u["unreferencedCommits"]), pe["heartBatches"], pe["batchesWithMergedOrCommits"],
                         "ano" if pe["phase2BuiltAfterMerge"] else "ne", c["heartUsd"], c["orchUsd"], e["wallS"]])
    head = ["běh", "scénář", "plán", "vzato", "odevz", "sloučeno", "2×claim", "dup", "nevzato", "lístky?",
            "commit?", "dávky", "git-dávky", "fáze2", "srdce$", "orch$", "s"]
    widths = [max(len(str(x)) for x in col) for col in zip(head, *rows)] if rows else [len(h) for h in head]
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    lines = [fmt.format(*head)] + [fmt.format(*map(str, r)) for r in rows]
    return "\n".join(lines)
