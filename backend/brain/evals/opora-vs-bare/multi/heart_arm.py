"""Rameno E (srdce + brána) evalu o víc sezeních (SCENAR.md §1, docs/brain-heart.md „eval E“).

Rozdíl proti C je jen srdce a brána: zadání sezení (přesně text, který dostane C) jde srdci jako zpráva člověka
(`POST /api/brain/heart/messages`), srdce z něj udělá úkoly ve frontě a pracovník `claude -p` (flagy, recept a
patička jako C) dostane JEN pokyn pracovat přes bránu (`opora_gate.py session → next → práce → commit → build/test →
report`). Původní zadání pracovník nikdy nevidí.

Modul drží čisté pomocníky (prompt pracovníka, cena dávek srdce, souhrn úkolů, zpráva pro soudce Q-konfliktu
a Q-reality, odpovědi na výslech) a tenkou vrstvu HTTP „člověka“ (cookie `opora_ui` s tajemstvím, které harness
předá jen procesu OPORY, nikdy agentovi).

Výslech: položí-li srdce otázku (spis `intake_briefs`, v `GET /api/intake` u požadavku `brief.questions` bez
`answer`), harness jako člověk pošle `POST /api/intake/brief/answer` s pevným `BRIEF_ANSWER` a počká na další dávku
srdce; nejvýš `BRIEF_ROUNDS` kol na sezení (`answer_briefs`). Bez otázky nic.
Stdlib.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

MULTI = Path(__file__).resolve().parent
REPO = MULTI.parents[4]
GATE_CLIENT = REPO / "backend" / "brain" / "seed" / "opora-control-center" / "skills" / "opora-control-center" / "scripts" / "opora_gate.py"
WORKSPACE = "draft"           # lokální projekt žije v pracovním prostoru `draft` (jako rameno A)
HEART_WAIT_S = 15 * 60        # strop čekání na dávku srdce (= timeout dávky v backendu)
WORKER_ROUNDS = 3             # nejvýš kol pracovníka na část sezení
SETTLE_S = 15.0               # srdce musí být tak dlouho v klidu (lístky a selhané úkoly mají okno 20 s)
OPEN = ("ready", "assigned")
_OPENER = build_opener(ProxyHandler({}))  # loopback bez systémové proxy


# --- čisté pomocníky ------------------------------------------------------------------------------

def worker_name(sid: str) -> str:
    return f"worker-{sid}"


def worker_prompt(gate_py: str, project: str, sid: str, footer: str, first_round: bool = True,
                  workspace: str = WORKSPACE) -> str:
    """Zadání pracovníka E: jen práce přes bránu (původní zadání sezení nedostane). `footer` = patička jako u C."""
    gate = f"python {gate_py}"
    start = (f"1. Založ relaci brány: `{gate} session --project {project} --workspace {workspace} "
             f"--name {worker_name(sid)}`.\n" if first_round else
             "1. Relace brány už existuje (stejný klient); začni rovnou `next` – úkol, který držíš, ti vrátí znovu.\n")
    return (
        f"Jsi pracovník projektu `{project}` (pracovní prostor `{workspace}`). Práci ti zadává výhradně fronta úkolů "
        "brány; jiné zadání nemáš a úkoly si nevymýšlej.\n"
        f"Klient brány: `{gate}` (adresa serveru je v OPORA_BASE_URL, výstup je vždy jeden JSON).\n\n"
        + start +
        "2. Opakuj:\n"
        f"   a. `{gate} next` → `answer.task` = {{id, title, body: {{why, do, files, doneWhen, dontTouch, context}}}}.\n"
        "   b. Udělej úkol přesně: pracuj na `files`, nesahej na `dontTouch`, splň každé `doneWhen` a dodrž "
        "`context.rules`.\n"
        "   c. Commitni soubory úkolu (`git add <soubory>`, pak `git commit -m \"<title>\" -m \"Opora-Task: <id>\"`).\n"
        "   d. Spusť `npm run build`, pak `npm test` – dva samostatné příkazy, nikdy je neřetěz (`&&`, `;`, `|`): zřetězený příkaz se zamítne. Zamítnutý příkaz rozděl a spusť znovu, nevzdávej to.\n"
        f"   e. `{gate} report --task <id> --sha <git rev-parse HEAD> --summary \"…\" "
        "--check \"npm run build=green|red\" --check \"npm test=green|red\"` podle skutečných výsledků (nevymýšlej je).\n"
        f"   f. Je-li úkol nejasný nebo v rozporu, zeptej se `{gate} ask \"…\"` a odpověď čti "
        f"`{gate} inbox --wait 30` (opakuj, dokud nepřijde).\n"
        "3. Skonči, když `next` vrátí `task: null`. Na závěr stručně shrň, co jsi udělal a co zůstalo otevřené.\n\n"
        + footer)


def worker_prompt_mcp(project: str, sid: str, footer: str, workspace: str = WORKSPACE) -> str:
    """Zadání pracovníka E-MCP (H1d): brána jako nástroje MCP `opora_*`, bez klienta v shellu."""
    return (
        f"Jsi pracovník projektu `{project}` (pracovní prostor `{workspace}`). Práci ti zadává výhradně fronta úkolů "
        "brány; jiné zadání nemáš a úkoly si nevymýšlej. Bránu ovládáš nástroji MCP `opora_*` (relaci si otevřou samy).\n\n"
        "1. Opakuj:\n"
        "   a. `opora_next` → `answer.task` = {id, title, body: {why, do, files, doneWhen, dontTouch, context}}.\n"
        "   b. Udělej úkol přesně: pracuj na `files`, nesahej na `dontTouch`, splň každé `doneWhen` a dodrž "
        "`context.rules`.\n"
        "   c. Commitni soubory úkolu (`git add <soubory>`, pak `git commit -m \"<title>\" -m \"Opora-Task: <id>\"`).\n"
        "   d. Spusť `npm run build`, pak `npm test` (dva samostatné příkazy).\n"
        "   e. `opora_report` s `taskId`, `sha` (`git rev-parse HEAD`), `summary` a `checks` "
        "[{name: \"npm run build\", status: green|red}, {name: \"npm test\", status: green|red}] podle skutečných výsledků.\n"
        "   f. Je-li úkol nejasný nebo v rozporu, `opora_ask` s `question` a `wait: true` (odpověď přijde rovnou; "
        "když ne, `opora_inbox`).\n"
        "2. Skonči, když `opora_next` vrátí `task: null`. Na závěr stručně shrň, co jsi udělal a co zůstalo otevřené.\n\n"
        + footer)


def gate_wrapper_source(client_py: Path, state_dir: Path) -> str:
    """Obal klienta brány: stav relace (`.opora/gate.json`) v `state_dir` mimo repo, takže dva souběžní pracovníci
    S4 ve stejné pracovní kopii mají každý svou relaci a do repa nejde token ani `.gitignore`."""
    return ("# Obal klienta brány pro pracovníka evalu E (generuje heart_arm.py); stav relace mimo repozitář.\n"
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('opora_gate_client', r'{client_py}')\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "if hasattr(sys.stdout, 'reconfigure'):\n"
            "    sys.stdout.reconfigure(encoding='utf-8')\n"
            f"sys.exit(mod.main(cwd=r'{state_dir}'))\n")


def install_gate_client(run_dir: Path, sid: str) -> Path:
    """Kopie `opora_gate.py` do `<run_dir>/gate/_client` + obal `<run_dir>/gate/<pracovník>/opora_gate.py`."""
    client = Path(run_dir) / "gate" / "_client" / "opora_gate.py"
    client.parent.mkdir(parents=True, exist_ok=True)
    client.write_bytes(GATE_CLIENT.read_bytes())
    state_dir = Path(run_dir) / "gate" / worker_name(sid)
    state_dir.mkdir(parents=True, exist_ok=True)
    wrapper = state_dir / "opora_gate.py"
    wrapper.write_text(gate_wrapper_source(client, state_dir), encoding="utf-8")
    return wrapper


def has_gate_session(run_dir: Path, sid: str) -> bool:
    return (Path(run_dir) / "gate" / worker_name(sid) / ".opora" / "gate.json").is_file()


def read_batches(brain: Path) -> list[dict]:
    """Všechny dávky srdce z `brain/batches.jsonl` (poškozené řádky přeskočí)."""
    try:
        lines = (Path(brain) / "batches.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def heart_cost(batches: list[dict]) -> dict:
    """Cena dávek srdce: součet `costUsd`, podíl poradce (položky Opus v `costByModel`), počet a stavy dávek."""
    usd = sum(float(b.get("costUsd") or 0) for b in batches)
    advisor = sum(float(v or 0) for b in batches for m, v in (b.get("costByModel") or {}).items() if "opus" in m.lower())
    return {"usd": round(usd, 4), "advisor_usd": round(advisor, 4), "batches": len(batches),
            "statuses": [b.get("status") for b in batches],
            "summaries": [b.get("summary") for b in batches if b.get("summary")]}


def task_counts(tasks: list[dict], before_ids: set) -> dict:
    """Souhrn fronty: úkoly vzniklé v sezení (id mimo `before_ids`), z nich selhané, a otevřené celkem."""
    new = [t for t in tasks if (t.get("taskId") or t.get("id")) not in before_ids]
    return {"created": len(new), "failed": sum(1 for t in new if t.get("status") == "failed"),
            "done": sum(1 for t in new if t.get("status") == "done"),
            "open": sum(1 for t in tasks if t.get("status") in OPEN),
            "by_status": {s: sum(1 for t in tasks if t.get("status") == s) for s in sorted({t.get("status") for t in tasks})}}


def final_text(worker_msgs: list[tuple[str, str]], summaries: list[str], escalations: list[str],
               brief_questions: list[dict] | None = None) -> str:
    """„Závěrečná zpráva“ ramene E pro soudce (Q-konflikt, Q-realita): zprávy pracovníků + shrnutí dávek srdce +
    eskalace srdce člověku + otázky výslechu s odpovědí harnessu. Slovo OPORA se maskuje volajícím (slepota soudce)."""
    out = []
    for label, msg in worker_msgs:
        out.append(f"## Zpráva pracovníka {label}\n{(msg or '').strip() or '(žádná)'}")
    out.append("## Shrnutí plánovače\n" + ("\n".join(f"- {s}" for s in summaries) or "(žádné)"))
    out.append("## Otázky plánovače pro člověka\n" + ("\n".join(f"- {e}" for e in escalations) or "(žádné)"))
    if brief_questions:  # jen otázky plánovače, ne pevná odpověď harnessu (ta by soudci podsouvala „bez nátlaku“)
        out.append("## Doptávání plánovače u člověka\n" + "\n".join(
            f"- {q.get('text') or ''}" + (f" (doporučení plánovače: {q['recommended']})" if q.get("recommended") else "")
            for q in brief_questions))
    return "\n\n".join(out)


# --- výslech srdce: odpovědi za člověka (SCENAR.md „Odpovědi za člověka (rameno E, výslech)“) -----------------

BRIEF_ANSWER = ("Drž se zadání a pocitu z prvního sezení (klidně, bez nátlaku). Co nevíš jistě, ověř v repu. "
                "Co neexistuje, ohlas a postav nejmenší poctivou variantu.")
BRIEF_ROUNDS = 3  # nejvýš kol odpovědí na sezení (kolo = odpovědi na všechny otevřené otázky + čekání na dávku srdce)


def open_brief_questions(overview: dict) -> list[dict]:
    """Otevřené otázky výslechu z `GET /api/intake` (oblasti: požadavky i odložené, a požadavky bez oblasti):
    `[{requirement, question, text, recommended}]` jen pro otázky bez odpovědi."""
    reqs = []
    for area in (overview or {}).get("areas") or []:
        reqs += (area.get("requirements") or []) + (area.get("deferred") or [])
    reqs += (overview or {}).get("unassigned") or []
    out, seen = [], set()
    for req in reqs:
        brief = req.get("brief") if isinstance(req, dict) else None
        for q in (brief or {}).get("questions") or []:
            key = (req.get("id"), q.get("id"))
            if not isinstance(q, dict) or q.get("answer") is not None or None in key or key in seen:
                continue
            seen.add(key)
            out.append({"requirement": req["id"], "question": q["id"], "text": q.get("text"),
                        "recommended": q.get("recommended")})
    return out


def answer_briefs(list_open, answer, wait_new, rounds_left: int) -> tuple[list[dict], int, list[str]]:
    """Harness jako člověk: dokud srdce drží otevřené otázky výslechu a zbývá kol, odpoví na každou pevným
    `BRIEF_ANSWER` a počká na další dávku srdce (odpověď ho budí jednou). `list_open()` vrací
    `open_brief_questions`, `answer(q)` pošle odpověď, `wait_new()` čeká na novou dávku. Vrací
    (zodpovězené otázky s `answer`, počet kol, chyby). Bez otázek nic nedělá."""
    answered, errors, rounds = [], [], 0
    while rounds < rounds_left:
        try:
            pending = list_open()
        except Exception as e:  # noqa: BLE001 - výslech je doplněk: chyba čtení se zapíše, sezení běží dál
            errors.append(f"čtení výslechu: {str(e)[:200]}")
            break
        if not pending:
            break
        rounds += 1
        for q in pending:
            try:
                answer(q)
                answered.append({**q, "answer": BRIEF_ANSWER})
            except Exception as e:  # noqa: BLE001
                errors.append(f"odpověď {q.get('requirement')}/{q.get('question')}: {str(e)[:200]}")
        try:
            wait_new()
        except Exception as e:  # noqa: BLE001 - srdce na odpověď nevzbudilo / spadlo: zapsat a pokračovat k pracovníkům
            errors.append(f"čekání na dávku po odpovědi: {str(e)[:200]}")
            break
    return answered, rounds, errors


def wait_heart(status, batches_count, before, *, need_new=True, timeout=HEART_WAIT_S, settle=SETTLE_S,
               clock=time.time, sleep=time.sleep, poll=2.0):
    """Čeká, až srdce doběhne: `running: false`, `pending: 0`, (u `need_new`) přibyla dávka, a klid trvá `settle` s.
    `status()` vrací JSON `/api/brain/heart/status`, `batches_count()` počet řádků `batches.jsonl`.
    Vrací poslední status; chyba supervisoru nebo vypršení = RuntimeError."""
    start, idle_since = clock(), None
    while True:
        s = status()
        if s.get("error"):
            raise RuntimeError(f"srdce hlásí chybu: {s['error']}")
        busy = bool(s.get("running")) or int(s.get("pending") or 0) > 0
        fresh = batches_count() > before or not need_new
        if busy or not fresh:
            idle_since = None
        elif idle_since is None:
            idle_since = clock()
        if idle_since is not None and clock() - idle_since >= settle:
            return s
        if clock() - start > timeout:
            raise TimeoutError(f"srdce nedoběhlo do {timeout:.0f} s (running={s.get('running')}, "
                               f"pending={s.get('pending')}, dávek {batches_count()} vs před {before})")
        sleep(poll)


# --- data projektu (jen čtení) --------------------------------------------------------------------

def project_dir(data: Path, project: str) -> Path:
    """Složka projektu v datech izolované OPORY (`<data>/projects/<id>`, jinak první složka s tímto jménem)."""
    direct = Path(data) / "projects" / project
    if direct.is_dir():
        return direct
    for p in Path(data).rglob(project):
        if p.is_dir():
            return p
    return direct


def escalations(data: Path, project: str, since: str = "") -> list[str]:
    """Texty lístků `ask`, které založilo srdce (eskalace člověku), vzniklé po `since` (ISO). Čte sqlite jen ke čtení."""
    out = []
    for db in sorted(project_dir(data, project).glob("*.sqlite")):
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            try:
                rows = con.execute(
                    "SELECT t.body, t.created_at FROM gate_tickets t JOIN gate_sessions s ON s.id = t.session_id "
                    "WHERE s.role = 'heart' AND t.kind = 'ask' AND t.project_id = ? ORDER BY t.seq", (project,)).fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            continue
        for body, created in rows:
            if since and str(created) < since:
                continue
            try:
                value = json.loads(body)
            except ValueError:
                value = body
            out.append(value.get("text") if isinstance(value, dict) and value.get("text") else str(value))
    return out


# --- HTTP jako člověk -----------------------------------------------------------------------------

class Human:
    """Lidská relace harnessu nad izolovanou OPORou: cookie `opora_ui` + Origin. Agentovi se nikdy nepředá."""

    def __init__(self, base: str, secret: str, timeout: float = 30):
        self.base, self.secret, self.timeout = base.rstrip("/"), secret, timeout

    def call(self, method, path, body=None, query=None):
        url = self.base + path + ("?" + urlencode(query) if query else "")
        headers = {"Accept": "application/json", "Origin": self.base, "Cookie": f"opora_ui={self.secret}"}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json"
        try:
            with _OPENER.open(Request(url, data=data, headers=headers, method=method), timeout=self.timeout) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except HTTPError as e:
            raise RuntimeError(f"{method} {path} -> {e.code}: {e.read()[:400].decode('utf-8', 'replace')}") from None

    def setup_project(self, ws: Path) -> str:
        """Lokální projekt nad pracovní kopií (jako opora_backend, bez autonomie) + zapnutá brána. Vrací id."""
        made = self.call("POST", "/api/local-project", {"name": "Eval", "path": str(ws), "confirmed": True})
        project = made["id"]
        gate = self.call("POST", "/api/brain/gate-setting", {"project": project, "enabled": True})
        if not (isinstance(gate, dict) and gate.get("enabled") is True):
            raise RuntimeError(f"brána se nezapnula: {gate}")
        return project

    def message(self, project, text, workspace=WORKSPACE):
        return self.call("POST", "/api/brain/heart/messages", {"project": project, "workspace": workspace, "text": text})

    def status(self, project):
        return self.call("GET", "/api/brain/heart/status", query={"project": project})

    def tasks(self, project, workspace=WORKSPACE):
        got = self.call("GET", "/api/brain/tasks", query={"project": project, "workspace": workspace})
        return got.get("tasks", []) if isinstance(got, dict) else []

    def intake(self, project, workspace=WORKSPACE):
        """`GET /api/intake`: požadavky se spisem výslechu (`brief.questions`)."""
        return self.call("GET", "/api/intake", query={"project": project, "workspace": workspace})

    def answer_brief(self, project, requirement, question, text=BRIEF_ANSWER, workspace=WORKSPACE):
        """`POST /api/intake/brief/answer` jako člověk (cookie `opora_ui`; routa pouští jen člověka)."""
        return self.call("POST", "/api/intake/brief/answer", {"project": project, "workspace": workspace,
                                                              "requirement": requirement, "question": question,
                                                              "answer": text})
