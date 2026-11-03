"""Runner evalu o víc sezeních „Zelený balkon“ (SCENAR.md): ramena A (OPORA), B (terminál), C (terminál + recept),
E (srdce + brána: zadání jde srdci, pracovník jako C dostane jen pokyn pracovat přes bránu; `heart_arm.py`).

    python -B run_multi.py --variant m1 --arms A,B,C --reps 2 --dry-run
    python -B run_multi.py --variant m1 --arms A,B,C --reps 2 --concurrency 3 --timeout-s 3600 --approve-harness
    python -B run_multi.py --variant m2smoke --arms E --reps 1 --sessions S1 --approve-harness

Jedno (rameno, opakování) = jedna perzistentní pracovní kopie T0 (git) v `<work-root>\\<varianta>-<rameno>-r<k>\\w`
a u A jedna izolovaná OPORA (`opora_serve.py`, data `…\\d` přes všechna sezení; mezi sezeními se proces restartuje
nad stejnými daty, protože `grade.kill_leftovers` po sezení ukončí vše, co má cestu běhu v příkazové řádce).
Kroky za sebou: S1 → kontrola → S2 → kontrola → zásah kolegy → S3 → kontrola → S4 (X a Y současně: dva procesy,
A s různým `OPORA_AGENT_NAME`, B/C ve stejném adresáři) → kontrola → S5 (návrat po pauze, nepravdivý předpoklad
o `/api/terminy`) → kontrola → S6 (změna směru: ceník zrušen) → kontrola. Ramena a opakování běží souběžně (`--concurrency`).
Rameno E navíc odpovídá na otázky výslechu srdce jako člověk (`heart_arm.answer_briefs`, `POST /api/intake/brief/answer`,
pevný text ze SCENAR.md, nejvýš 3 kola na sezení; `meta.brief_questions`, `meta.brief_rounds`).
Každé sezení = nový `claude -p` s čerstvým kontextem (`run_eval.agent_command`, stejné flagy a `ALLOWED_TOOLS`).

Výstup (`multi/<varianta>/`): `results.jsonl` (řádek na sezení: Q-*, cena, orientace, C4/C5, snímek OPORY u A),
`raw/<S><část>.<rameno>_rep<k>.jsonl`, `traces/`, `artifacts/<S>.<rameno>_rep<k>.diff` (diff sezení) a `.cum.diff`
(od T0), `final/<S><část>.<rameno>_rep<k>.txt` (závěrečná zpráva agenta, vstup Q-konfliktu), `shots/`, `opora/`,
`progress/<rameno>_r<k>.json` (stav pro navázání), `errors.jsonl`.
Navázání po pádu: hotová sezení (řádek v results.jsonl) se nepouštějí znovu; rozběhnuté a nedokončené sezení se vrátí
na stav před ním (git strom + kopie dat OPORY) a pustí znovu. Pojistka harnessu: sha přes `HARNESS_PATHS` +
`run_eval.py` v `multi/_state.json`; změna = exit 2, dokud člověk nespustí `--approve-harness`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MULTI = Path(__file__).resolve().parent
FLOW = MULTI.parent
REPO = FLOW.parents[3]
MCP_SERVER = REPO / "backend" / "api" / "brain_opora" / "mcp" / "opora_mcp.py"  # H1d, pracovník E-MCP
sys.dont_write_bytecode = True
for p in (str(FLOW), str(MULTI)):
    if p not in sys.path:
        sys.path.insert(0, p)
import checks_multi  # noqa: E402
import grade  # noqa: E402
import heart_arm  # noqa: E402
import judge_multi  # noqa: E402
import metrics  # noqa: E402
import run_eval  # noqa: E402
import sessions  # noqa: E402
from run_eval import HarnessError, append_jsonl, eprint  # noqa: E402

STATE = MULTI / "_state.json"
HARNESS_PATHS = ["multi/SCENAR.md", "multi/run_multi.py", "multi/sessions.py", "multi/checks_multi.py",
                 "multi/judge_multi.py", "multi/opora_serve.py", "multi/heart_arm.py", "grade.py", "specs.py",
                 "metrics.py", "opora_backend.py", "templates/T0"]
STEPS = ["S1", "S2", "INJECT", "S3", "S4", "S5", "S6"]
ARMS = ["A", "B", "C", "E"]
OPORA_ARMS = ("A", "E")  # ramena s izolovanou OPOROU (data přes sezení, kopie dat před sezením)
AGENT = {"": "eval-agent", "X": "eval-agent-x", "Y": "eval-agent-y"}
EMPTY_INTRO = ("Projekt v OPOŘE je prázdný: žádná aplikace, stránky, cesty ani karty. Celý plán a souvislosti "
               "vytvoř sám")
CONTINUE_INTRO = ("Projekt v OPOŘE obsahuje práci z předchozích sezení na této aplikaci (plán, karty, výsledky). "
                  "Plán a souvislosti udržuj sám")
# Odhad ceny na jeden proces agenta (SCENAR §5); dry-run ho zpřesní průměrem z dřívějších variant, pokud jsou.
# E: na celé sezení (dávky srdce Haiku + poradce Opus a 1–3 kola pracovníka Opus).
EST_USD = {"A": (3.0, 5.0), "B": (0.3, 0.6), "C": (0.3, 0.6), "E": (1.0, 2.0)}
EST_JUDGE_USD = 0.07


# --- pojistka harnessu (sha jako run_eval, vlastní _state.json) -----------------------------------

def harness_state():
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    state["harness_paths"] = HARNESS_PATHS
    return state


def check_harness(approve, dry_run):
    state = harness_state()
    sha = run_eval.harness_sha(state)
    if state.get("harness_sha") == sha:
        return True, sha
    if approve and not dry_run:
        state["harness_sha"] = sha
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        eprint(f"harness schválen: sha256 {sha[:12]} přes {len(run_eval.harness_files(state))} souborů -> {STATE.name}")
        return True, sha
    what = "chybí schválené sha" if state.get("harness_sha") is None else "harness se změnil od posledního schválení"
    eprint(f"{what} (spočteno {sha[:12]} přes {len(run_eval.harness_files(state))} souborů). "
           "Projdi harness a spusť jednou s --approve-harness (rozhoduje člověk).")
    return False, sha


# --- git snímky pracovní kopie --------------------------------------------------------------------

GIT = ["git", "-c", "core.autocrlf=false"]


def write_tree(ws: Path, index: Path) -> str:
    """Strom celé pracovní kopie (i neuložené a nesledované soubory) přes dočasný index – skutečný index agenta
    zůstane netknutý."""
    if index.exists():
        index.unlink()
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    run_eval.run([*GIT, "add", "-A"], ws, env=env)
    sha = run_eval.run([*GIT, "write-tree"], ws, env=env).strip()
    index.unlink(missing_ok=True)
    return sha


def tree_diff(ws: Path, a: str, b: str, out: Path) -> str:
    diff = run_eval.run([*GIT, "diff", a, b, "--", ".", ":(exclude)package-lock.json"], ws)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(diff, encoding="utf-8")
    return diff


def restore_tree(ws: Path, head: str, tree: str, index: Path):
    """Vrátí pracovní kopii na stav před rozběhnutým sezením (po pádu harnessu)."""
    run_eval.run([*GIT, "reset", "-q", "--hard", head], ws)
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    index.unlink(missing_ok=True)
    run_eval.run([*GIT, "read-tree", tree], ws, env=env)
    run_eval.run([*GIT, "checkout-index", "-a", "-f"], ws, env=env)
    run_eval.run([*GIT, "clean", "-fdq"], ws, env=env)
    index.unlink(missing_ok=True)


# --- OPORA ramene A -------------------------------------------------------------------------------

def start_opora(run_dir: Path, ws: Path):
    """Izolovaná OPORA nad `run_dir/d` (první start = prázdný projekt + autonomie, další = tentýž projekt)."""
    port = grade.free_port()
    ready_file = run_dir / "opora-ready.json"
    log = (run_dir / "opora.log").open("ab")
    proc = subprocess.Popen([shutil.which("uv") or "uv", "run", "--project", str(REPO), "python",
                             str(MULTI / "opora_serve.py"), "--data", str(run_dir / "d"), "--repo", str(ws),
                             "--port", str(port), "--ready-file", str(ready_file),
                             "--autonomy-log", str(run_dir / "autonomy.json")],
                            cwd=REPO, stdout=log, stderr=log, env=run_eval.child_env())
    deadline = time.time() + 180
    while time.time() < deadline:
        if proc.poll() is not None:
            raise HarnessError("harness", "OPORA backend skončil při startu: "
                               + (run_dir / "opora.log").read_text(encoding="utf-8", errors="replace")[-600:])
        if ready_file.exists():
            try:
                ready = json.loads(ready_file.read_text(encoding="utf-8"))
            except ValueError:
                ready = {}
            if str(ready.get("baseUrl", "")).endswith(f":{port}"):
                with socket.socket() as s:
                    if s.connect_ex(("127.0.0.1", port)) == 0:
                        return proc, ready
        time.sleep(0.5)
    grade.kill_tree(proc)
    raise HarnessError("harness", "OPORA backend nenaběhl do 180 s")


def a_context(run_dir: Path, sid: str, ready: dict, preview_port: int, agent: str, first: bool):
    """Kontext ramene A z `run_eval.opora_context` (beze změny textu skillu), jen identita agenta a u dalších sezení
    místo „projekt je prázdný“ věcná věta, že obsahuje práci z předchozích sezení."""
    sdir = run_dir / "ctx" / sid
    if sdir.exists():
        grade.rmtree_force(sdir)
    sdir.mkdir(parents=True)
    if (run_dir / "autonomy.json").exists():
        shutil.copy2(run_dir / "autonomy.json", sdir / "autonomy.json")
    ctx, dirs, text = run_eval.opora_context({}, sdir, ready, preview_port)
    ident = "Identita agenta: OPORA_AGENT_NAME=eval-agent."
    if ident not in text or EMPTY_INTRO not in text:
        raise HarnessError("harness", "kontext A z run_eval.opora_context se změnil – uprav kotvy v run_multi.py")
    text = text.replace(ident, f"Identita agenta: OPORA_AGENT_NAME={agent}.")
    if not first:
        text = text.replace(EMPTY_INTRO, CONTINUE_INTRO)
    ctx.write_text(text, encoding="utf-8")
    return ctx, dirs, text


def read_opora_full(ready: dict) -> dict:
    """Snímek pro P1–P3 (`metrics.read_opora`) + rozhodnutí a záznam činnosti (vstup soudce Q-konfliktu). Jen GET."""
    base, scope = ready["baseUrl"], {"project": ready["project"], "workspace": ready["workspace"]}
    snap = metrics.read_opora(base, ready["project"], ready["workspace"])
    snap["desktopState"] = metrics._get(base, "/api/desktop-v3/state", scope)
    snap["activity"] = metrics._get(base, "/api/activity-log", {**scope, "limit": 200})
    return snap


# --- OPORA ramene E (srdce + brána) ---------------------------------------------------------------

def start_opora_e(run_dir: Path, ws: Path, prog: dict, save):
    """Izolovaná OPORA se srdcem nad `run_dir/d` (jako A přes všechna sezení). Harness je člověk: tajemství cookie
    `opora_ui` vznikne tady, jde jen procesu OPORY (`OPORA_EVAL_UI_SECRET`) a nikdy agentovi. První start založí
    lokální projekt nad pracovní kopií a zapne bránu (bez autonomie agenta). Vrací (proc, ready, human)."""
    port = grade.free_port()
    secret = os.urandom(24).hex()
    ready_file = run_dir / "opora-ready.json"
    ready_file.unlink(missing_ok=True)
    log = (run_dir / "opora.log").open("ab")
    proc = subprocess.Popen([shutil.which("uv") or "uv", "run", "--project", str(REPO), "python",
                             str(MULTI / "opora_serve.py"), "--heart", "--data", str(run_dir / "d"), "--repo", str(ws),
                             "--port", str(port), "--ready-file", str(ready_file)],
                            cwd=REPO, stdout=log, stderr=log, env=run_eval.child_env({"OPORA_EVAL_UI_SECRET": secret}))
    deadline = time.time() + 180
    while True:
        if proc.poll() is not None:
            raise HarnessError("harness", "OPORA (E) skončila při startu: "
                               + (run_dir / "opora.log").read_text(encoding="utf-8", errors="replace")[-600:])
        if ready_file.exists():
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
        if time.time() > deadline:
            grade.kill_tree(proc)
            raise HarnessError("harness", "OPORA (E) nenaběhla do 180 s")
        time.sleep(0.5)
    base = f"http://127.0.0.1:{port}"
    human = heart_arm.Human(base, secret)
    try:
        if not prog.get("e_project"):
            prog["e_project"] = human.setup_project(ws)
            save(prog)
        st = human.status(prog["e_project"])
        if not st.get("enabled"):
            raise RuntimeError(f"supervisor srdce neběží (enabled=false): {st}")
    except Exception as e:  # noqa: BLE001
        grade.kill_tree(proc)
        raise HarnessError("harness", f"OPORA (E): {e}") from None
    return proc, {"baseUrl": base, "project": prog["e_project"], "workspace": heart_arm.WORKSPACE}, human


def e_recipe() -> str:
    """Recept C pro pracovníka E bez zřetězeného `npm run build && npm test` (m5: Sonnet po zamítnutí řetězu skončil)."""
    return sessions.c_recipe().replace("`npm run build && npm test` pusť jednou na ucelený kus práce (`&&`: test jen po prošlém buildu)",
                                       "`npm run build`, a když projde, `npm test` (dva samostatné příkazy) pusť jednou na ucelený kus práce")


def e_worker_cmd(prompt, args, run_dir, gate_py: str):
    """Pracovník E = flagy a recept ramene C + povolený klient brány (Bash(python * ) už povoluje i ALLOWED_TOOLS)."""
    cmd = run_eval.agent_command(prompt, args.model, "B")
    i = cmd.index("--disallowedTools")
    cmd[i:i] = [f"Bash(python {gate_py}:*)"]
    recipe = run_dir / "recipe-c.md"
    recipe.write_text(e_recipe(), encoding="utf-8")
    cmd += ["--append-system-prompt-file", str(recipe)]
    return cmd, "(výchozí system prompt Claude Code, --safe-mode)\n\n--append-system-prompt-file:\n" + e_recipe()


def e_worker_mcp_cmd(prompt, args, run_dir, sid, env):
    """Pracovník E-MCP (H1d): stejné flagy jako E, brána jako MCP server `opora` (`--safe-mode` MCP vypíná, proto
    `--setting-sources project` + `--strict-mcp-config`); bez klienta brány v shellu."""
    cmd = [c for c in run_eval.agent_command(prompt, args.model, "B") if c != "--safe-mode"]
    i = cmd.index("--disallowedTools")
    cmd[i:i] = ["mcp__opora__*"]
    cfg = run_dir / "gate" / f"mcp-{sid}.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"mcpServers": {"opora": {"command": sys.executable, "args": [str(MCP_SERVER)], "env": env}}}),
                   encoding="utf-8")
    recipe = run_dir / "recipe-c.md"
    recipe.write_text(e_recipe(), encoding="utf-8")
    cmd += ["--setting-sources", "project", "--disable-slash-commands", "--mcp-config", str(cfg),
            "--append-system-prompt-file", str(recipe)]
    return cmd, "(výchozí system prompt Claude Code, MCP opora)\n\n--append-system-prompt-file:\n" + e_recipe()


def run_e_parts(session, rep, args, vdir, run_dir, ws, ready, human):
    """Sezení ramene E: zadání (stejný text jako C) → srdce jako zpráva člověka → čekání na dávku → pracovník(ci)
    přes bránu, nejvýš `WORKER_ROUNDS` kol, dokud jsou ve frontě otevřené úkoly. Vrací (jobs, outs, heart)."""
    project, base = ready["project"], ready["baseUrl"]
    data = run_dir / "d"
    brain = heart_arm.project_dir(data, project) / "brain"

    def count():
        return len(heart_arm.read_batches(brain))

    def status():
        return human.status(project)

    def wait(before, need_new):
        try:
            return heart_arm.wait_heart(status, count, before, need_new=need_new)
        except (RuntimeError, TimeoutError) as e:
            raise HarnessError("heart", f"{session}.E_rep{rep}: {e}") from None

    brief = {"questions": [], "rounds": 0, "errors": []}
    mark = [0]

    def list_open():
        mark[0] = count()  # dávky před odpověďmi: čeká se na novou
        return heart_arm.open_brief_questions(human.intake(project))

    def grill():
        """Výslech: na otázky srdce odpoví harness jako člověk pevným textem (nejvýš BRIEF_ROUNDS kol na sezení)."""
        got, n, errs = heart_arm.answer_briefs(
            list_open, lambda q: human.answer_brief(project, q["requirement"], q["question"]),
            lambda: heart_arm.wait_heart(status, count, mark[0], need_new=True),
            heart_arm.BRIEF_ROUNDS - brief["rounds"])
        brief["questions"] += got
        brief["rounds"] += n
        brief["errors"] += errs

    since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    b0 = count()
    before_ids = {t.get("taskId") or t.get("id") for t in human.tasks(project)}
    parts = sessions.parts(session)
    prompts = [sessions.prompt(session, part) for part in parts]
    for text in prompts:  # S4: X i Y jdou srdci jako dvě zprávy
        human.message(project, text)
    wait(b0, need_new=True)
    grill()
    jobs_all, outs_all, rounds = [], [], 0
    for rnd in range(1, heart_arm.WORKER_ROUNDS + 1):
        rounds = rnd
        jobs = []
        for part in parts:
            sid = f"{session}{part}"
            if args.worker_mcp:
                prompt = heart_arm.worker_prompt_mcp(project, sid, sessions.FOOTER)
                cmd, system_text = e_worker_mcp_cmd(prompt, args, run_dir, sid, {
                    "OPORA_BASE_URL": base, "OPORA_PROJECT": project, "OPORA_WORKSPACE": heart_arm.WORKSPACE,
                    "OPORA_WORKER_NAME": heart_arm.worker_name(sid)})
            else:
                gate_py = str(heart_arm.install_gate_client(run_dir, sid)).replace("\\", "/")
                first = not heart_arm.has_gate_session(run_dir, sid)
                prompt = heart_arm.worker_prompt(gate_py, project, sid, sessions.FOOTER, first_round=first)
                cmd, system_text = e_worker_cmd(prompt, args, run_dir, gate_py)
            jobs.append({"part": part, "sid": sid, "id": f"{sid}.w{rnd}", "key": f"{part or '-'}.w{rnd}",
                         "agent": heart_arm.worker_name(sid), "prompt": prompt, "cmd": cmd, "system": system_text,
                         "env": {"OPORA_BASE_URL": base}, "raw": vdir / "raw" / f"{sid}.w{rnd}.E_rep{rep}.jsonl"})
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:  # S4: dva pracovníci souběžně, každý vlastní relace
            outs = list(pool.map(lambda j: run_eval.run_agent(j["cmd"], ws, run_eval.child_env(j["env"]), j["raw"],
                                                              args.timeout_s), jobs))
        jobs_all += jobs
        outs_all += outs
        if any(code is None for code, _ in outs):
            break  # vypršení řeší společné zpracování (HarnessError timeout)
        wait(count(), need_new=False)  # selhaný úkol / lístek budí srdce po 20 s – počkat na klid
        grill()  # otázka výslechu může přijít i po kole pracovníka
        if not any(t.get("status") in heart_arm.OPEN for t in human.tasks(project)):
            break
    tasks = human.tasks(project)
    new_batches = heart_arm.read_batches(brain)[b0:]
    cost = heart_arm.heart_cost(new_batches)
    esc = heart_arm.escalations(data, project, since)
    counts = heart_arm.task_counts(tasks, before_ids)
    try:
        intake_view = human.intake(project)
    except Exception as e:  # noqa: BLE001 - jen do snímku
        intake_view = {"error": str(e)[:300]}
    heart = {"cost": cost, "tasks": counts, "escalations": esc, "rounds": rounds, "prompts": prompts, "brief": brief,
             "snapshot": {"project": project, "status": status(), "tasks": tasks, "batches": new_batches,
                          "escalations": esc, "brief_answered": brief["questions"], "intake": intake_view}}
    return jobs_all, outs_all, heart


# --- metriky sezení -------------------------------------------------------------------------------

EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SRC_PATH = re.compile(r"(^|[\\/])src[\\/]")
SHELL_WRITE = re.compile(r"(>>?|\btee\b|\bsed\s+-i|Set-Content|Out-File|Add-Content|\bcp\b|\bmv\b)[^|;&\n]*\bsrc[\\/]")


def _is_src_edit(block) -> bool:
    inp = block.get("input") or {}
    if block.get("name") in EDIT_TOOLS:
        return bool(SRC_PATH.search(str(inp.get("file_path") or inp.get("notebook_path") or "")))
    if block.get("name") in ("Bash", "PowerShell"):
        return bool(SHELL_WRITE.search(str(inp.get("command") or "")))
    return False


def orientation(raw_path: Path) -> dict:
    """Orientace = volání nástrojů a tokeny do první editace souboru v `src/` (Write/Edit nebo zápis shellem).
    Tokeny = součet usage všech volání modelu až po to, které editaci vygenerovalo (každá zpráva jednou)."""
    usage, calls, edit_at, t_first, t_edit = {}, 0, None, None, None
    for e in metrics._events(raw_path):
        ts = metrics._ts(e.get("timestamp"))
        if ts and t_first is None:
            t_first = ts
        if e.get("type") != "assistant":
            continue
        msg = e.get("message") or {}
        mid = msg.get("id") or f"anon{len(usage)}"
        if edit_at is None:
            usage[mid] = msg.get("usage") or usage.get(mid) or {}
        for b in msg.get("content") or []:
            if b.get("type") != "tool_use" or edit_at is not None:
                continue
            if _is_src_edit(b):
                edit_at, t_edit = mid, ts
            else:
                calls += 1
    tin = sum((u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
              + (u.get("cache_read_input_tokens") or 0) for u in usage.values())
    tout = sum(u.get("output_tokens") or 0 for u in usage.values())
    return {"edited": edit_at is not None, "calls": calls, "model_calls": len(usage), "tokens_in": tin,
            "tokens_out": tout, "seconds": round(t_edit - t_first, 1) if t_edit and t_first else None}


def sum_usage(items):
    out = {}
    for u in items:
        for k, v in (u or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = out.get(k, 0) + v
    return out


def final_message(parsed) -> str:
    res = parsed.get("result") or {}
    if isinstance(res.get("result"), str) and res["result"].strip():
        return res["result"]
    texts = [t["content"] for t in parsed["trace"] if t["role"] == "assistant"]
    return texts[-1] if texts else ""


# --- průběh (navázání po pádu) --------------------------------------------------------------------

def progress_path(vdir, arm, rep):
    return vdir / "progress" / f"{arm}_r{rep}.json"


def load_progress(vdir, arm, rep):
    p = progress_path(vdir, arm, rep)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_progress(vdir, arm, rep, prog):
    p = progress_path(vdir, arm, rep)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prog, ensure_ascii=False, indent=1), encoding="utf-8")


def session_done(vdir, session, arm, rep):
    return (f"{session}.{arm}", rep) in run_eval.done_keys(vdir / "results.jsonl")


# --- jedno sezení ---------------------------------------------------------------------------------

def agent_cmd(prompt, arm, args, run_dir, sid, ready=None, preview_port=None, agent=None, first=False):
    """(cmd, env_extra, system_text). C = flagy B + recept jako doplněk system promptu (stejný kanál jako skill A)."""
    system_text = "(výchozí system prompt Claude Code, --safe-mode)"
    if arm == "A":
        ctx, dirs, text = a_context(run_dir, sid, ready, preview_port, agent, first)
        env = {"OPORA_BASE_URL": ready["baseUrl"], "OPORA_AGENT_NAME": agent,
               "OPORA_HOME": str(run_dir / "home" / agent)}
        return run_eval.agent_command(prompt, args.model, "A", ctx, dirs), env, system_text + "\n\n" + text
    cmd = run_eval.agent_command(prompt, args.model, "B")
    if arm == "C":
        recipe = run_dir / "recipe-c.md"
        recipe.write_text(sessions.c_recipe(), encoding="utf-8")
        cmd += ["--append-system-prompt-file", str(recipe)]
        system_text += "\n\n--append-system-prompt-file:\n" + sessions.c_recipe()
    return cmd, {}, system_text


def run_session(session, arm, rep, args, vdir, run_dir, ws, prog):
    t0 = time.time()
    tag = f"{session}.{arm}_rep{rep}"
    pre = prog["pre"][session]
    parts = sessions.parts(session)
    opora, ready, snapshot, heart = None, None, None, None
    try:
        if arm == "A":
            opora, ready = start_opora(run_dir, ws)
        elif arm == "E":
            opora, ready, human = start_opora_e(run_dir, ws, prog, lambda p: save_progress(vdir, arm, rep, p))
        preview_port = prog.setdefault("preview_port", grade.free_port())
        if arm == "E":
            jobs, outs, heart = run_e_parts(session, rep, args, vdir, run_dir, ws, ready, human)
            snap_path = vdir / "opora" / f"{tag}.json"
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(json.dumps(heart["snapshot"], ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            jobs = []
            for part in parts:
                sid = f"{session}{part}"
                prompt = sessions.prompt(session, part)
                cmd, env, system_text = agent_cmd(prompt, arm, args, run_dir, sid, ready, preview_port, AGENT[part],
                                                  first=session == "S1")
                jobs.append({"part": part, "sid": sid, "prompt": prompt, "cmd": cmd, "env": env, "system": system_text,
                             "raw": vdir / "raw" / f"{sid}.{arm}_rep{rep}.jsonl"})
            with ThreadPoolExecutor(max_workers=len(jobs)) as pool:  # S4: X a Y současně nad stejnou kopií
                outs = list(pool.map(lambda j: run_eval.run_agent(j["cmd"], ws, run_eval.child_env(j["env"]), j["raw"],
                                                                  args.timeout_s), jobs))
        if arm == "A":
            snapshot = read_opora_full(ready)  # před ukončením OPORY, jen GET
            snap_path = vdir / "opora" / f"{tag}.json"
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        if opora is not None:
            grade.kill_tree(opora)
    leftovers = grade.kill_leftovers(run_dir)  # vite preview, esbuild … (a zbytky OPORY)
    procs, parsed_all, worker_msgs = {}, [], []
    for job, (code, secs) in zip(jobs, outs):
        jid = job.get("id", job["sid"])
        parsed = run_eval.parse_stream(job["raw"], job["system"], job["prompt"])
        res = parsed["result"] or {}
        if code is None:
            raise HarnessError("timeout", f"{jid}: agent překročil {args.timeout_s} s", usage=res.get("usage"))
        if not parsed["result"]:
            raise HarnessError("agent_error", f"{jid}: claude skončil kódem {code} bez události result")
        run_eval.assert_model(args.model, parsed["models"])
        dirty = run_eval.contamination("A" if arm in OPORA_ARMS else "B", parsed)
        if dirty:
            raise HarnessError("contamination", f"{jid}: " + "; ".join(dirty), usage=res.get("usage"))
        fin = vdir / "final" / f"{jid}.{arm}_rep{rep}.txt"
        fin.parent.mkdir(parents=True, exist_ok=True)
        fin.write_text(final_message(parsed), encoding="utf-8")
        worker_msgs.append((jid, final_message(parsed)))
        tp = vdir / "traces" / f"{jid}.{arm}_rep{rep}.json"
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(json.dumps(parsed["trace"], ensure_ascii=False, indent=2), encoding="utf-8")
        tm = metrics.trace_metrics(job["raw"], job["env"].get("OPORA_BASE_URL"))
        procs[job.get("key", job["part"] or "-")] = {
            "agent": job.get("agent", AGENT[job["part"]]), "exit_code": code, "agent_seconds": round(secs, 1),
            "reported_cost_usd": res.get("total_cost_usd"), "num_turns": res.get("num_turns"),
            "tool_calls": parsed["tool_calls"], "permission_denials": len(res.get("permission_denials") or []),
            "usage": res.get("usage"), "orientation": orientation(job["raw"]), "trace_metrics": tm,
            "final_message": str(fin.relative_to(FLOW)).replace("\\", "/"),
            "raw": str(job["raw"].relative_to(FLOW)).replace("\\", "/"), "init_skills": parsed["init"].get("skills"),
            "api_key_source": parsed["init"].get("apiKeySource"), "result_subtype": res.get("subtype")}
        parsed_all.append(parsed)

    tree_end = write_tree(ws, run_dir / "snap.index")
    diff_rel = f"multi/{args.variant}/artifacts/{tag}.diff"
    cum_rel = f"multi/{args.variant}/artifacts/{tag}.cum.diff"
    diff = tree_diff(ws, pre["tree"], tree_end, FLOW / diff_rel)
    tree_diff(ws, prog["base"], tree_end, FLOW / cum_rel)
    checked = checks_multi.check_session(ws, session, shots_dir=vdir / "shots", shot_prefix=tag)
    dm = metrics.diff_metrics(diff)
    tms = [p["trace_metrics"] for p in procs.values()]
    ors = [p["orientation"] for p in procs.values()]
    worker_usd = sum(p["reported_cost_usd"] or 0 for p in procs.values())
    cost_usd = worker_usd + (heart["cost"]["usd"] if heart else 0)
    final_rel = procs[(parts[0] or "-")]["final_message"] if heart is None else None
    if heart is not None:  # E: zprávy pracovníků + shrnutí dávek srdce + eskalace (maskované) pro soudce Q-konfliktu
        fin = vdir / "final" / f"{tag}.txt"
        fin.parent.mkdir(parents=True, exist_ok=True)
        text = heart_arm.final_text(worker_msgs, heart["cost"]["summaries"], heart["escalations"],
                                    heart["brief"]["questions"])
        fin.write_text(judge_multi.MASK.sub("[nástroj]", text), encoding="utf-8")
        final_rel = str(fin.relative_to(FLOW)).replace("\\", "/")
    row = {
        "prompt_id": f"{session}.{arm}", "rep": rep,
        "prompt": "\n\n".join(heart["prompts"] if heart else [j["prompt"] for j in jobs]),
        "tags": [f"arm-{arm}", f"session-{session}"], "status": "ok",
        "model": (parsed_all[-1]["models"] or [None])[-1], "usage": sum_usage(p["usage"] for p in procs.values()),
        "latency_s": round(max(p["agent_seconds"] for p in procs.values()), 1),
        "tool_calls": sum(p["tool_calls"] for p in procs.values()),
        "turns": sum(p["num_turns"] or 0 for p in procs.values()),
        "perm_denials": sum(p["permission_denials"] for p in procs.values()),
        "grade": checked["grade"], "explanation": checked["explanation"],
        "cost": {"usd": round(cost_usd, 4), "c4_zbytecne": sum(t["wasted"] for t in tms),
                 "c4_chyby": sum(t["tool_errors"] for t in tms), "c4_chyby_opora": sum(t["tool_errors_opora"] for t in tms),
                 "c4_opakovani": sum(t["repeats"] for t in tms), "c4_zamitnuto": sum(t["perm_denied"] for t in tms),
                 "c5_mimo_zadani": dm["files_outside"], "c5_soubory": dm["outside_list"], "files_changed": dm["files_changed"]},
        "orientation": {"calls": sum(o["calls"] for o in ors), "tokens_in": sum(o["tokens_in"] for o in ors),
                        "tokens_out": sum(o["tokens_out"] for o in ors), "edited": all(o["edited"] for o in ors),
                        "model_calls": sum(o["model_calls"] for o in ors)},
        "meta": {"session": session, "arm": arm, "variant": args.variant, "diff": diff_rel, "diff_cum": cum_rel,
                 "diff_lines": diff.count("\n"), "no_op": not diff.strip(),
                 "final_message": final_rel, "processes": procs,
                 "checks": checked["checks"], "notes": checked["notes"], "groups": checked["groups"],
                 "pages": checked["pages"], "pressure": checked["pressure"], "variants": checked["variants"],
                 "shots": checked["shots"], "reported_cost_usd": round(cost_usd, 4), "leftover_processes": leftovers,
                 "tree_start": pre["tree"], "tree_end": tree_end, "head_start": pre["head"], "base": prog["base"],
                 "injection": prog["steps"].get("INJECT") if session not in ("S1", "S2") else None,
                 "terminy": checked.get("terminy"),
                 "harness_sha": args.harness_sha, "total_seconds": round(time.time() - t0, 1),
                 "notes_files": dm["notes_list"]},
    }
    if arm == "A":
        row["meta"]["opora_snapshot"] = f"multi/{args.variant}/opora/{tag}.json"
        row["meta"]["autonomy"] = json.loads((run_dir / "autonomy.json").read_text(encoding="utf-8")) \
            if (run_dir / "autonomy.json").exists() else None
        om = metrics.opora_metrics(snapshot, ws)
        calls = sum(t["opora_calls"] for t in tms)
        row["opora"] = {**(om or {}), "p4_volani_opora": calls,
                        "p4_podil_volani": round(calls / row["tool_calls"], 4) if row["tool_calls"] else 0.0,
                        "p5_poznamky_v_repu": dm["notes_in_repo"], "snapshot": om is not None}
    if heart is not None:
        row["latency_s"] = row["meta"]["total_seconds"]  # E: kola pracovníka jdou po sobě a čeká se na srdce
        row["meta"].update({
            "opora_snapshot": f"multi/{args.variant}/opora/{tag}.json",
            "heart_usd": heart["cost"]["usd"], "worker_usd": round(worker_usd, 4),
            "heart_advisor_usd": heart["cost"]["advisor_usd"], "heart_batches": heart["cost"]["batches"],
            "heart_statuses": heart["cost"]["statuses"], "heart_summaries": heart["cost"]["summaries"],
            "heart_escalations": heart["escalations"], "tasks_created": heart["tasks"]["created"],
            "tasks_failed": heart["tasks"]["failed"], "tasks_done": heart["tasks"]["done"],
            "tasks_open": heart["tasks"]["open"], "worker_rounds": heart["rounds"],
            "brief_questions": len(heart["brief"]["questions"]), "brief_rounds": heart["brief"]["rounds"],
            "brief_asked": [{k: q.get(k) for k in ("requirement", "question", "text", "recommended")}
                            for q in heart["brief"]["questions"]],
            "brief_errors": heart["brief"]["errors"]})
    append_jsonl(vdir / "results.jsonl", row)
    g = row["grade"]
    eprint(f"  {tag}: nové={g.get('q_nove')} regrese={g.get('q_regrese')} pravidla={g.get('q_pravidla')} "
           f"plán={g.get('q_plan')} oprava={g.get('q_oprava')} paralelně={g.get('q_paralelne')} "
           f"build={g['build']} test={g['test']} | {cost_usd:.2f} USD, {row['latency_s']} s"
           + (f" | srdce {heart['cost']['usd']:.2f} USD / {heart['cost']['batches']} dávek, pracovník "
              f"{worker_usd:.2f} USD / {heart['rounds']} kol, úkolů {heart['tasks']['created']} "
              f"(selhalo {heart['tasks']['failed']}), výslech {len(heart['brief']['questions'])} otázek / "
              f"{heart['brief']['rounds']} kol" if heart else ""))


# --- jedno (rameno, opakování) --------------------------------------------------------------------

def build_verify(ws: Path):
    r = grade._run([grade._tool("npm"), "run", "build"], ws, 600)
    return r["exit"] == 0, r["tail"]


def run_task(arm, rep, args, vdir):
    run_dir = Path(args.work_root) / f"{args.variant}-{arm}-r{rep}"
    ws = run_dir / "w"
    step = "příprava"
    try:
        prog = load_progress(vdir, arm, rep)
        any_done = any(session_done(vdir, s, arm, rep) for s in sessions.ORDER)
        if prog is None or not (ws / ".git").exists():
            if any_done:
                raise HarnessError("harness", f"pracovní kopie {ws} chybí, ale sezení už proběhla – nejde navázat "
                                              "(smaž řádky tohoto ramene a opakování z results.jsonl a progress/)")
            ws, base = run_eval.prepare_workspace({"template": "T0"}, run_dir)
            prog = {"base": base, "run_dir": str(run_dir), "steps": {}, "pre": {}, "started": None}
            save_progress(vdir, arm, rep, prog)
        for step in STEPS:
            if step not in args.step_list:
                continue
            if step == "INJECT":
                if "INJECT" not in prog["steps"]:
                    res = sessions.inject_colleague(ws, verify=build_verify)
                    prog["steps"]["INJECT"] = res
                    save_progress(vdir, arm, rep, prog)
                    eprint(f"  INJECT.{arm}_rep{rep}: {res['injection']} (aria-invalid {res['aria_invalid'].get('done')}, "
                           f"Ceník {res['cenik_link'].get('done')})")
                continue
            if session_done(vdir, step, arm, rep):
                continue
            if prog.get("started") == step:  # pád uprostřed sezení: zpět na stav před ním
                pre = prog["pre"][step]
                grade.kill_leftovers(run_dir)
                restore_tree(ws, pre["head"], pre["tree"], run_dir / "snap.index")
                snap = run_dir / f"d-before-{step}"
                if arm in OPORA_ARMS:
                    grade.rmtree_force(run_dir / "d")
                    if snap.exists():
                        shutil.copytree(snap, run_dir / "d")
                    else:  # pád v S1: OPORA ještě neměla data – příští start založí projekt znovu
                        for f in ("opora-ready.json", "autonomy.json"):
                            (run_dir / f).unlink(missing_ok=True)
                        prog.pop("e_project", None)
                if arm == "E":  # relace brány pracovníků toho sezení zpět (tokeny patří vráceným datům)
                    for part in sessions.parts(step):
                        grade.rmtree_force(run_dir / "gate" / heart_arm.worker_name(f"{step}{part}"))
                eprint(f"  {step}.{arm}_rep{rep}: navazuji – stav vrácen před sezení")
            head = run_eval.run([*GIT, "rev-parse", "HEAD"], ws).strip()
            prog["pre"][step] = {"tree": write_tree(ws, run_dir / "snap.index"), "head": head}
            if arm in OPORA_ARMS and (run_dir / "d").exists():
                snap = run_dir / f"d-before-{step}"
                grade.rmtree_force(snap)
                shutil.copytree(run_dir / "d", snap)
            prog["started"] = step
            save_progress(vdir, arm, rep, prog)
            run_session(step, arm, rep, args, vdir, run_dir, ws, prog)
            prog["started"] = None
            prog["steps"][step] = "done"
            save_progress(vdir, arm, rep, prog)
        if not all(session_done(vdir, s, arm, rep) for s in sessions.ORDER):
            return True  # --sessions: zbytek sezení později nad stejnou kopií (kopie zůstává)
        prog["finished"] = True
        save_progress(vdir, arm, rep, prog)
        if not args.keep_workspace:
            grade.kill_leftovers(run_dir)
            grade.rmtree_force(run_dir)
        return True
    except Exception as e:  # noqa: BLE001 - každé selhání do errors.jsonl, nikdy do skóre; kopie zůstává

        cls = getattr(e, "failure_class", "harness")
        append_jsonl(vdir / "errors.jsonl", {"prompt_id": f"{step}.{arm}", "rep": rep, "failure_class": cls,
                                             "error": str(e)[:800], "usage": getattr(e, "extra", {}).get("usage")})
        eprint(f"  {step}.{arm}_rep{rep} SELHAL [{cls}]: {str(e)[:300]} – pracovní kopie zůstává pro navázání")
        grade.kill_leftovers(run_dir)
        return False


# --- plán (dry-run) a odhad -----------------------------------------------------------------------

def prior_costs():
    """Průměrná cena a čas procesu z dřívějších variant jednoho sezení (v*/results.jsonl), pokud existují."""
    acc = {}
    for path in sorted(FLOW.glob("v*/results.jsonl")) + [FLOW / "baseline" / "results.jsonl"]:
        for r in grade._rows(path):
            arm = r.get("meta", {}).get("arm")
            if arm in ("A", "B") and r.get("meta", {}).get("reported_cost_usd") is not None:
                acc.setdefault(arm, []).append((r["meta"]["reported_cost_usd"], r.get("latency_s") or 0))
    return {a: (sum(c for c, _ in v) / len(v), sum(t for _, t in v) / len(v) / 60, len(v)) for a, v in acc.items()}


def print_plan(tasks, args, vdir):
    for arm, rep in tasks:
        run_dir = Path(args.work_root) / f"{args.variant}-{arm}-r{rep}"
        ws = run_dir / "w"
        print(f"\n### rameno {arm}, opakování {rep}  (pracovní kopie {ws})")
        print(f"0. kopie templates/T0 -> {ws}; npm ci --prefer-offline; git init + commit (základ diffů)")
        n = 1
        for step in STEPS:
            if step not in args.step_list:
                continue
            if step == "INJECT":
                print(f"{n}. zásah kolegy: sessions.inject_colleague(ws, verify=npm run build) -> commit "
                      f"'{sessions.COLLEAGUE_MSG}' od {sessions.COLLEAGUE[0]} <{sessions.COLLEAGUE[1]}>; "
                      "bez aria-invalid na polích formuláře + odkaz Ceník v menu na /cennik")
                n += 1
                continue
            done = session_done(vdir, step, arm, rep)
            print(f"{n}. {step}{' (HOTOVO, přeskočí se)' if done else ''}: snímek stromu (git write-tree, dočasný index)"
                  + (f" + kopie dat OPORY -> {run_dir / f'd-before-{step}'}" if arm in OPORA_ARMS and step != "S1" else ""))
            if arm == "E":
                print_plan_e(step, rep, args, run_dir, ws)
                n += 1
                continue
            if arm == "A":
                print(f"   uv run --project <repo> python multi/opora_serve.py --data {run_dir / 'd'} --repo {ws} "
                      f"--port <volný> --ready-file {run_dir / 'opora-ready.json'} --autonomy-log {run_dir / 'autonomy.json'}"
                      + ("  (první start: prázdný projekt + grant_autonomy)" if step == "S1" else "  (týž projekt)"))
            for part in sessions.parts(step):
                sid = f"{step}{part}"
                if arm == "A":
                    cmd = run_eval.agent_command("<ZADÁNÍ " + sid + ">", args.model, "A", run_dir / "ctx" / sid / "opora-context.md",
                                                 [run_dir / "ctx" / sid / "skill" / "opora-control-center",
                                                  run_dir / "ctx" / sid / "opora-tools"])
                    env = f"OPORA_BASE_URL=http://127.0.0.1:<port> OPORA_AGENT_NAME={AGENT[part]} OPORA_HOME={run_dir / 'home' / AGENT[part]}"
                else:
                    cmd = run_eval.agent_command("<ZADÁNÍ " + sid + ">", args.model, "B")
                    if arm == "C":
                        cmd += ["--append-system-prompt-file", str(run_dir / "recipe-c.md")]
                    env = "bez ANTHROPIC_API_KEY a OPORA_*"
                par = " (souběžně s druhým procesem S4)" if len(sessions.parts(step)) > 1 else ""
                print(f"   [{sid}]{par} cwd={ws}, strop {args.timeout_s} s, env: {env}\n   " + subprocess.list2cmdline(cmd))
            print(f"   -> raw/{step}*.{arm}_rep{rep}.jsonl, final/, traces/; GET snímek OPORY -> opora/{step}.{arm}_rep{rep}.json"
                  if arm == "A" else f"   -> raw/{step}*.{arm}_rep{rep}.jsonl, final/, traces/")
            print(f"   kill_leftovers({run_dir}); diff sezení + kumulativní -> artifacts/{step}.{arm}_rep{rep}[.cum].diff; "
                  f"checks_multi.check_session(ws, '{step}') -> results.jsonl")
            n += 1
    print("\n### zadání (stejná pro A, B, C; u E jde srdci jako zpráva člověka)")
    for s in sessions.ORDER:
        for part in sessions.parts(s):
            print(f"[{s}{part}] " + sessions.prompt(s, part).replace("\n", "\n    "))
    if "C" in args.arm_list or "E" in args.arm_list:
        print("\n### recept ramene C a pracovníka E (doplněk system promptu)\n" + sessions.c_recipe())
    if "E" in args.arm_list:
        print("### zadání pracovníka E (S1, první kolo; původní zadání sezení nevidí)\n"
              + heart_arm.worker_prompt("<run_dir>/gate/worker-S1/opora_gate.py", "<projekt>", "S1", sessions.FOOTER))
        print("\n### odpověď harnessu na každou otázku výslechu srdce (jako člověk)\n" + heart_arm.BRIEF_ANSWER)
    estimate(tasks, args)


def print_plan_e(step, rep, args, run_dir, ws):
    """Plán jednoho sezení ramene E (dry-run)."""
    print(f"   uv run --project <repo> python multi/opora_serve.py --heart --data {run_dir / 'd'} --repo {ws} --port <volný> "
          f"--ready-file {run_dir / 'opora-ready.json'}  (env OPORA_HEART=on, OPORA_CANVAS_HOST=127.0.0.1, "
          "OPORA_*_WORKER=0, tajemství člověka jen v OPORA_EVAL_UI_SECRET)")
    if step == "S1":
        print("   jako člověk (cookie opora_ui): POST /api/local-project {name: Eval, path: ws} -> projekt; "
              "POST /api/brain/gate-setting {project, enabled: true}; bez autonomie agenta")
    for part in sessions.parts(step):
        print(f"   POST /api/brain/heart/messages {{project, workspace: draft, text: <ZADÁNÍ {step}{part}>}}")
    print(f"   čekání na srdce: GET /api/brain/heart/status running=false, pending=0, nová dávka v batches.jsonl, "
          f"klid {heart_arm.SETTLE_S:.0f} s (strop {heart_arm.HEART_WAIT_S // 60} min)")
    print("   výslech: GET /api/intake {project, workspace: draft} -> otevřené brief.questions -> jako člověk "
          "POST /api/intake/brief/answer {project, workspace, requirement, question, answer: <pevný text>} -> čekání "
          f"na novou dávku; nejvýš {heart_arm.BRIEF_ROUNDS} kola na sezení (i po kole pracovníka); bez otázky nic")
    for part in sessions.parts(step):
        sid = f"{step}{part}"
        gate_py = f"{run_dir / 'gate' / heart_arm.worker_name(sid) / 'opora_gate.py'}".replace("\\", "/")
        cmd = run_eval.agent_command(f"<POKYN PRACOVNÍKA {sid}>", args.model, "B")
        cmd[cmd.index("--disallowedTools"):cmd.index("--disallowedTools")] = [f"Bash(python {gate_py}:*)"]
        cmd += ["--append-system-prompt-file", str(run_dir / "recipe-c.md")]
        par = " (souběžně s druhým pracovníkem S4, každý vlastní relace brány)" if len(sessions.parts(step)) > 1 else ""
        print(f"   [{sid}.w<kolo>]{par} cwd={ws}, strop {args.timeout_s} s, env: OPORA_BASE_URL=http://127.0.0.1:<port>\n   "
              + subprocess.list2cmdline(cmd))
    print(f"   po kole: klid srdce (selhaný úkol / lístek ho budí po 20 s), výslech; ve frontě ready/assigned -> další "
          f"kolo, nejvýš {heart_arm.WORKER_ROUNDS}")
    print(f"   -> raw/{step}*.w<k>.E_rep{rep}.jsonl, final/{step}.E_rep{rep}.txt (pracovníci + shrnutí srdce + eskalace), "
          f"opora/{step}.E_rep{rep}.json (úkoly, dávky, eskalace); cena = pracovníci + costUsd nových dávek srdce")
    print(f"   kill_leftovers({run_dir}); diff sezení + kumulativní; checks_multi.check_session(ws, '{step}') -> results.jsonl")


def estimate(tasks, args):
    procs = {a: 0 for a in args.arm_list}
    sel = [s for s in sessions.ORDER if s in args.step_list]
    for arm, _rep in tasks:
        # E se odhaduje na sezení (srdce + kola pracovníka), ostatní na proces agenta
        procs[arm] += len(sel) if arm == "E" else sum(len(sessions.parts(s)) for s in sel)
    prior = prior_costs()
    reps = sorted({r for _a, r in tasks})
    pairs = [(x, y) for x, y in judge_multi.PAIR_ARMS if x in args.arm_list and y in args.arm_list] \
        if sel[-1] == sessions.ORDER[-1] or "S4" in sel else []
    judges = (len(tasks) if "S3" in sel else 0) + (len(tasks) if "S5" in sel else 0) + len(pairs) * len(reps)
    lo = sum(procs[a] * EST_USD[a][0] for a in procs) + judges * EST_JUDGE_USD
    hi = sum(procs[a] * EST_USD[a][1] for a in procs) + judges * EST_JUDGE_USD
    print("\n### odhad (nic se nespouští)")
    print(f"jednotky ceny: {sum(procs.values())} ({', '.join(f'{a}: {n}' for a, n in procs.items())}; "
          f"A/B/C = proces agenta, na (rameno, opakování) S4 = 2 procesy; E = sezení; sezení {', '.join(sel)})")
    print(f"soudce `claude -p` (sonnet): {judges} (Q-konflikt po S3 + Q-realita po S5 + {len(pairs) * len(reps)} párů "
          "nad finální aplikací; `judge_multi.py conflict|realita|pairs` pouští člověk po běhu)")
    print(f"cena: {lo:.1f}–{hi:.1f} USD (A 3–5, B/C 0,3–0,6 USD na proces, E 1–2 USD na sezení, soudce ~{EST_JUDGE_USD} USD)")
    if prior and set(procs) & {"A", "B", "C"}:
        emp = sum(procs[a] * (prior.get("B" if a == "C" else a, (EST_USD[a][0], 0, 0))[0] if a != "E" else EST_USD["E"][0])
                  for a in procs) + judges * EST_JUDGE_USD
        print("podle dřívějších jednosezeních běhů (průměr na proces): "
              + ", ".join(f"{a} {c:.2f} USD / {m:.1f} min (n={n})" for a, (c, m, n) in sorted(prior.items()))
              + f" -> ~{emp:.0f} USD (C jako B; pozdější sezení nad větším repem budou dražší)")
    a_min = (prior.get("A", (0, 15, 0))[1] or 15) * 5 + 5 * 3  # 5 procesů + kontroly ~3 min po sezení
    if set(procs) & {"A", "B", "C"}:
        print(f"zeď: sezení za sebou, ramena souběžně (--concurrency {args.concurrency}); rameno A ~{a_min:.0f} min na opakování "
              f"-> celkem ~{a_min * max(1, len(tasks) // max(1, args.concurrency) ) / 60:.1f} h + soudci")
    if "E" in procs:
        print(f"rameno E: na sezení dávka srdce (~1–5 min) + 1–{heart_arm.WORKER_ROUNDS} kola pracovníka (~10–30 min) "
              f"+ klid srdce {heart_arm.SETTLE_S:.0f} s po kole; ~{len(sel) * 30} min na opakování")


# --- CLI ------------------------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(description="Eval o víc sezeních (OPORA vs. terminál vs. terminál + recept vs. srdce)")
    p.add_argument("--variant", required=True, help="m<N>[přípona] (výstup multi/<varianta>/), např. m2, m2smoke")
    p.add_argument("--arms", default="A,B,C", help="čárkami oddělená ramena z A,B,C,E")
    p.add_argument("--sessions", default=",".join(sessions.ORDER),
                   help="jen tato sezení (např. S1 nebo S1,S2; výchozí S1–S6); zásah kolegy běží se S3. "
                        "Zbytek lze pustit později")
    p.add_argument("--reps", type=int, default=2)
    p.add_argument("--timeout-s", type=int, default=3600, help="tvrdý strop na proces agenta (0 = bez stropu)")
    p.add_argument("--model", default="opus")
    p.add_argument("--work-root", default=os.environ.get("OPORA_EVAL_WORK_ROOT", r"C:\oe"))
    p.add_argument("--concurrency", type=int, default=3, help="kolik (rameno, opakování) běží najednou")
    p.add_argument("--keep-workspace", action="store_true", help="pracovní kopie po posledním sezení nemazat")
    p.add_argument("--worker-mcp", action="store_true", help="E: pracovník přes MCP server opora (H1d)")
    p.add_argument("--approve-harness", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if not re.fullmatch(r"m\d+[a-z0-9]*", a.variant):
        p.error("--variant musí být m<N>[přípona z a-z0-9]")
    a.arm_list = [x.strip().upper() for x in a.arms.split(",") if x.strip()]
    if not a.arm_list or set(a.arm_list) - set(ARMS) or len(set(a.arm_list)) != len(a.arm_list):
        p.error("--arms: neprázdná podmnožina A,B,C,E bez opakování")
    sel = [x.strip().upper() for x in a.sessions.split(",") if x.strip()]
    if not sel or set(sel) - set(sessions.ORDER):
        p.error("--sessions: neprázdná podmnožina " + ",".join(sessions.ORDER))
    a.step_list = [s for s in STEPS if s in sel or (s == "INJECT" and "S3" in sel)]
    if a.reps < 1 or a.concurrency < 1 or a.timeout_s < 0:
        p.error("--reps/--concurrency ≥ 1, --timeout-s ≥ 0")
    return a


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv if argv is not None else sys.argv[1:])
    approved, args.harness_sha = check_harness(args.approve_harness, args.dry_run)
    if not approved and not args.dry_run:
        return 2
    work_root = Path(args.work_root)
    if " " in str(work_root) or len(str(work_root)) > 40:
        eprint(f"--work-root {work_root}: potřeba krátká cesta bez mezer (Windows MAX_PATH, git)")
        return 2
    vdir = MULTI / args.variant
    sel = [s for s in sessions.ORDER if s in args.step_list]
    tasks = [(arm, r) for r in range(args.reps) for arm in args.arm_list
             if not all(session_done(vdir, s, arm, r) for s in sel)]
    for arm, r in tasks:  # vybrané sezení potřebuje hotová (nebo také vybraná) předchozí sezení
        first = sessions.ORDER.index(sel[0])
        missing = [s for s in sessions.ORDER[:first] if not session_done(vdir, s, arm, r)]
        if missing:
            eprint(f"--sessions {','.join(sel)}: {arm} rep{r} ještě nemá hotová sezení {', '.join(missing)}")
            return 2
    eprint(f"[{args.variant}] {len(tasks)} z {len(args.arm_list) * args.reps} (rameno, opakování) k běhu, souběh "
           f"{args.concurrency}; harness {'schválen' if approved else 'NESCHVÁLEN'} ({args.harness_sha[:12]})")
    if args.dry_run:
        print_plan(tasks, args, vdir)
        return 0
    for parent in [work_root, *work_root.parents]:
        if (parent / "CLAUDE.md").exists() or (parent / ".git").exists():
            eprint(f"{parent} obsahuje CLAUDE.md nebo .git – pracovní kořen musí ležet mimo repozitáře")
            return 2
    work_root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        outcomes = list(pool.map(lambda t: run_task(t[0], t[1], args, vdir), tasks))
    ok = sum(outcomes)
    eprint(f"[{args.variant}] hotovo: {ok} ok, {len(outcomes) - ok} selhalo -> {vdir / 'results.jsonl'}")
    return 0 if ok == len(outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
