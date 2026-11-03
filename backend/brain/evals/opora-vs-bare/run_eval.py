"""Runner evalu „OPORA vs. bez OPORY“ (headless Claude Code pod předplatným, ne API).

    python run_eval.py --variant baseline --arm A --cases C01 --reps 1 --dry-run
    python run_eval.py --variant baseline --arm B --cases C01 --reps 3 --timeout-s 3600
    python run_eval.py --variant baseline --arm AB --cases C01 --concurrency 2   # A i B souběžně
    python -B run_eval.py --variant v2 --arm AB --cases C01,C02,C03,C06,C07 --reps 2 --concurrency 4

Jeden běh = (případ, rameno, opakování): čerstvá pracovní kopie šablony v krátké cestě (`--work-root`,
výchozí `C:\\oe`), `npm ci`, `git init` (základ pro diff); u ramene A navíc izolovaná instance OPORY
(`opora_backend.py`, vlastní port a dočasná data, PRÁZDNÝ projekt – plán si agent staví sám; `seeds/` čte jen
grader jako skrytou zlatou mapu) a kopie skillu
`opora-control-center` předaná přes `--append-system-prompt-file`; pak `claude -p` se stejným textem
záměru pro A i B (cases.md, záměr + společná patička), pak kontrola koncového stavu (`grade.check_workspace`).

Výstup (`<flow>/<variant>/`, tvar podle build-eval.md Step 3):
  results.jsonl                 řádek na (případ.rameno, opakování), zapsaný hned po dokončení
  traces/<id>_rep<k>.json       přepis z stream-json (system/user/assistant/tool_call/tool_result)
  raw/<id>_rep<k>.jsonl         surový stream-json (pro audit)
  artifacts/<id>_rep<k>.diff    diff pracovní kopie proti šabloně (vstup párového soudce)
  shots/<id>_rep<k>_{desktop,mobile}.png   screenshoty výstupu (další stránky `<id>_rep<k>_<stránka>_*.png`)
  opora/<id>_rep<k>.json        snímek izolované OPORY po běhu ramene A (view, agent-state, journeys, map-check)
  errors.jsonl                  neúspěšné pokusy s třídou selhání (nikdy v results.jsonl)
Resume na klíči (prompt_id, rep). Pojistka harnessu: sha256 přes tento soubor + `_state.json.harness_paths`;
po změně běh odmítne (exit 2), dokud člověk nespustí `--approve-harness`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FLOW = Path(__file__).resolve().parent
REPO = FLOW.parents[3]
SKILL_SRC = REPO / "backend" / "brain" / "seed" / "opora-control-center" / "skills" / "opora-control-center"
JOURNEY_TOOLS = ["journey_run.py", "journey_run_logic.py", "journey_run_browser.py"]
sys.dont_write_bytecode = True  # žádné __pycache__ ve složce evalu
sys.path.insert(0, str(FLOW))
import grade
import metrics

WIN = os.name == "nt"
LOCK = threading.Lock()

# --- příkaz agenta (flagy ověřené v `claude --help` 2.1.312, viz isolation.md) ------------------------
ALLOWED_TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep", "TodoWrite",
    "Bash(npm *)", "Bash(npx *)", "Bash(node *)", "Bash(git *)", "Bash(python *)", "Bash(uv *)",
    "Bash(ls *)", "Bash(cat *)", "Bash(mkdir *)",
    # Pilot C01 (2026-10-28): 11 zamítnutí v rameni A za běžné shellové tvary; stejné pro A i B.
    "Bash(cd *)", "Bash(export *)", "Bash(echo *)", "Bash(for *)", "Bash(curl *)", "Bash(head *)", "Bash(tail *)",
    "Bash(grep *)", "Bash(OPORA_AGENT_NAME=*)", "PowerShell(Invoke-RestMethod *)", "PowerShell(Get-Content *)",
    "PowerShell(npm *)", "PowerShell(npx *)", "PowerShell(node *)", "PowerShell(git *)", "PowerShell(python *)",
]
DISALLOWED_TOOLS = ["WebFetch", "WebSearch"]
MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable"}

# Stopy OPORY / zlatých dat, které rameno B nesmí vidět ani použít; zlatá data nesmí vidět ani A.
CONTAMINATION_B = re.compile(r"opora_(read|write|hub|save|stage|cycle)\.py|OPORA_BASE_URL|:8740\b|node-brief|agent-state"
                             r"|opora-control-center", re.IGNORECASE)
GOLD_LEAK = re.compile(r"hillclimb|opora-vs-bare|cases\.md|test_journey_plan|seeds[\\/]C\d", re.IGNORECASE)


def agent_command(prompt, model, arm, ctx_file=None, extra_dirs=()):
    """Stejné flagy pro A i B; A navíc jen kontext OPORY (system prompt doplněk) a přístup k jeho složkám.
    Prompt hned za -p: variadické volby (--allowedTools, --add-dir) by jinak pozřely poziční argument."""
    cmd = ["claude", "-p", prompt,
           "--safe-mode",                       # bez CLAUDE.md, skillů, pluginů, hooků, MCP, vlastních agentů
           "--strict-mcp-config",               # žádné MCP mimo --mcp-config (žádné nepředáváme)
           "--no-session-persistence",
           "--output-format", "stream-json", "--verbose",
           "--model", model,
           "--permission-mode", "acceptEdits", "--permission-prompts", "none",
           "--allowedTools", *ALLOWED_TOOLS,
           "--disallowedTools", *DISALLOWED_TOOLS]
    if arm == "A":
        cmd += ["--append-system-prompt-file", str(ctx_file), "--add-dir", *map(str, extra_dirs)]
    return cmd


# --- případy (jediný zdroj pravdy je cases.md) ------------------------------------------------------

def load_cases():
    text = (FLOW / "cases.md").read_text(encoding="utf-8")
    footer_m = re.search(r"\*\*Společná patička záměru[^\n]*\n((?:>.*\n)+)", text)
    footer = _quote(footer_m.group(1))
    tags = {m.group(1): [t.strip() for t in m.group(2).split(",")]
            for m in re.finditer(r"^\| (C\d\d) \| `\[([^\]]*)\]`", text, re.MULTILINE)}
    cases = []
    for m in re.finditer(r"^## (C\d\d) – ([^\n]*)\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL):
        cid, title, body = m.groups()
        intent_m = re.search(r"\*\*Záměr \(A i B\):\*\*\n((?:>.*\n)+)", body)
        tmpl_m = re.search(r"\*\*Výchozí repo:\*\* `([A-Z0-9]+)`", body)
        if not intent_m:
            continue
        intent = _quote(intent_m.group(1))
        cases.append({"id": cid, "title": title.strip(), "intent": intent, "footer": footer,
                      "prompt": intent + "\n\n" + footer, "tags": tags.get(cid, []),
                      "template": tmpl_m.group(1) if tmpl_m else None})
    return cases


def _quote(block):
    return " ".join(line[1:].strip() for line in block.strip().splitlines()).strip()


# --- pojistka harnessu -----------------------------------------------------------------------------

def harness_files(state):
    files = [Path(__file__).resolve()]
    for rel in state.get("harness_paths", []):
        p = (FLOW / rel).resolve()
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.is_file()
                            and not {"node_modules", "dist", "__pycache__"} & set(f.parts))
        elif p.is_file():
            files.append(p)
    return sorted(set(files))


def harness_sha(state):
    h = hashlib.sha256()
    for f in harness_files(state):
        for part in (str(f.relative_to(FLOW)).replace("\\", "/").encode(), b"\0", f.read_bytes(), b"\0"):
            h.update(part)
    return h.hexdigest()


def check_harness(state, approve, dry_run):
    sha = harness_sha(state)
    if state.get("harness_sha") == sha:
        return True
    if approve and not dry_run:
        state["harness_sha"] = sha
        (FLOW / "_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        eprint(f"harness schválen: sha256 {sha[:12]} přes {len(harness_files(state))} souborů zapsán do _state.json")
        return True
    what = "chybí schválené sha" if state.get("harness_sha") is None else "harness se změnil od posledního schválení"
    eprint(f"{what} (spočteno {sha[:12]} přes {len(harness_files(state))} souborů). "
           "Projdi harness a spusť jednou s --approve-harness (rozhoduje člověk).")
    return False


# --- pomocné --------------------------------------------------------------------------------------

def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def append_jsonl(path: Path, row: dict):
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        with path.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")  # oddělí useknutý řádek po pádu
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def done_keys(path: Path):
    keys = set()
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                keys.add((r["prompt_id"], r["rep"]))
            except (ValueError, KeyError):
                pass
    return keys


def run(cmd, cwd, timeout=900, env=None):
    exe = [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]
    r = subprocess.run(exe, cwd=cwd, capture_output=True, timeout=timeout, check=False, env=env)
    if r.returncode:
        raise HarnessError("harness", f"{' '.join(cmd[:3])} -> {r.returncode}: "
                           + (r.stdout + r.stderr).decode("utf-8", "replace")[-600:])
    return r.stdout.decode("utf-8", "replace")


class HarnessError(Exception):
    def __init__(self, failure_class, message, **extra):
        super().__init__(message)
        self.failure_class = failure_class
        self.extra = extra


def child_env(extra=None):
    """Předplatné, ne API: klíč API ani proměnné živé OPORY se agentovi nepředají."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") and not k.startswith("OPORA_")}
    env.update(extra or {})
    return env


# --- příprava běhu --------------------------------------------------------------------------------

def prepare_workspace(case, run_dir: Path):
    if run_dir.exists():
        grade.kill_leftovers(run_dir)  # zamčené soubory po předchozím běhu (vite preview, esbuild)
        grade.rmtree_force(run_dir)  # čistý stav pro každý (případ, rameno, opakování)
        if run_dir.exists():
            raise HarnessError("harness", f"pracovní složku {run_dir} nejde smazat (zamčené soubory)")
    ws = run_dir / "w"
    tmpl = FLOW / "templates" / case["template"]
    if not tmpl.is_dir():
        raise HarnessError("harness", f"šablona {case['template']} neexistuje ({tmpl})")
    shutil.copytree(tmpl, ws, ignore=shutil.ignore_patterns("node_modules", "dist"))
    run(["npm", "ci", "--prefer-offline", "--no-audit", "--no-fund"], ws, timeout=900)
    git = ["git", "-c", "user.name=eval", "-c", "user.email=eval@local", "-c", "core.autocrlf=false"]
    run([*git, "init", "-q", "-b", "main"], ws)
    run([*git, "add", "-A"], ws)
    run([*git, "commit", "-qm", f"šablona {case['template']}"], ws)
    base = run(["git", "rev-parse", "HEAD"], ws).strip()
    return ws, base


def start_opora(case, run_dir: Path, ws: Path):
    """Izolovaná OPORA pro rameno A: vlastní port, dočasná data, PRÁZDNÝ projekt (žádný seed – zlatá mapa
    `seeds/<případ>.json` zůstává jen graderu), plná autonomie agenta. Vrací (proc, ready, preview_port)."""
    port, preview_port = grade.free_port(), grade.free_port()
    ready_file = run_dir / "opora-ready.json"
    log = (run_dir / "opora.log").open("wb")
    proc = subprocess.Popen([shutil.which("uv") or "uv", "run", "--project", str(REPO), "python",
                             str(FLOW / "opora_backend.py"), "--data", str(run_dir / "d"), "--repo", str(ws),
                             "--port", str(port), "--ready-file", str(ready_file),
                             "--autonomy-log", str(run_dir / "autonomy.json")], cwd=REPO, stdout=log, stderr=log,
                            env=child_env())
    deadline = time.time() + 180
    while time.time() < deadline:
        if proc.poll() is not None:
            raise HarnessError("harness", "OPORA backend skončil při startu: "
                               + (run_dir / "opora.log").read_text(encoding="utf-8", errors="replace")[-600:])
        if ready_file.exists():
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return proc, json.loads(ready_file.read_text(encoding="utf-8")), preview_port
        time.sleep(0.5)
    grade.kill_tree(proc)
    raise HarnessError("harness", "OPORA backend nenaběhl do 180 s")


def opora_context(case, run_dir: Path, ready: dict, preview_port: int):
    """Doplněk system promptu ramene A: kopie skillu + adresa a rozsah izolované OPORY. Žádná zlatá data."""
    skill = run_dir / "skill" / "opora-control-center"
    shutil.copytree(SKILL_SRC, skill, ignore=shutil.ignore_patterns("__pycache__", "test_*.py"))
    tools = run_dir / "opora-tools"
    tools.mkdir(parents=True, exist_ok=True)
    for name in JOURNEY_TOOLS:
        shutil.copy2(REPO / "tools" / name, tools / name)
    skill_md = (skill / "SKILL.md").read_text(encoding="utf-8")
    autonomy_file = run_dir / "autonomy.json"
    autonomy = json.loads(autonomy_file.read_text(encoding="utf-8")) if autonomy_file.exists() else {}
    full = autonomy.get("status") == "on"  # grant_autonomy vrací "on" až po sloučení přepínače v backendu
    text = (
        "# Prostředí OPORA\n"
        f"Base directory for this skill: {skill}\n"
        f"Server OPORA: {ready['baseUrl']} (proměnná OPORA_BASE_URL), projekt `{ready['project']}`, "
        f"pracovní prostor `{ready['workspace']}`. Identita agenta: OPORA_AGENT_NAME=eval-agent.\n"
        "Projekt v OPOŘE je prázdný: žádná aplikace, stránky, cesty ani karty. Celý plán a souvislosti vytvoř sám "
        "v plátně a stav přes karty: aplikaci (`site.kind: application`) a stránky se `site` (goal, feel, sections) "
        "podle záměru, cesty zákazníka, rozklad na karty a kroky (`spec.steps`) dávkou `canvas-plan` a návrhy změn; "
        "pak karty převezmi (executions), stav kód po krocích, odevzdávej výsledky, uzavři karty s doklady, "
        "zkontroluj mapu (díry `mapGaps` v agent-state) a ověř cesty runnerem `journey_run.py`. Využij možnosti, "
        "které skill popisuje.\n"
        "OPORA je tvůj mozek a mapa projektu: plán, rozklad, rozhodnutí a poznámky piš do OPORY (karty, spec, "
        "kroky, výsledky), ne do .md souborů v repu.\n"
        + ("Projekt má zapnutou plnou autonomii agentů: akce, které skill označuje jako lidské, smíš provést sám "
           "(viz `autonomy` v agent-state). " if full else "")
        + "Člověk během běhu nereaguje.\n"
        f"Aplikace poběží na http://127.0.0.1:{preview_port} (`vite preview --port {preview_port}`, prostředí "
        f"aplikace `127.0.0.1:{preview_port}`); runner cesty `journey_run.py` je v {tools} (spouštěj systémovým "
        "`python`, má Playwright a Chromium).\n"
        "Kód piš jen v aktuálním pracovním adresáři (git, větev main, bez origin; nic nepushuj ani nenasazuj).\n\n"
        "---\n\n" + skill_md)
    ctx = run_dir / "opora-context.md"
    ctx.write_text(text, encoding="utf-8")
    return ctx, [skill, tools], text


# --- běh agenta a přepis stream-json --------------------------------------------------------------

def run_agent(cmd, ws, env, raw_path: Path, timeout_s):
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    exe = [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]
    t0 = time.time()
    with raw_path.open("wb") as raw, (raw_path.with_suffix(".stderr.txt")).open("wb") as err:
        proc = subprocess.Popen(exe, cwd=ws, stdin=subprocess.DEVNULL, stdout=raw, stderr=err, env=env)
        try:
            proc.wait(timeout=timeout_s if timeout_s > 0 else None)  # tvrdý strop, nezávislý na živosti streamu
        except subprocess.TimeoutExpired:
            grade.kill_tree(proc)
            return None, time.time() - t0
    return proc.returncode, time.time() - t0


def parse_stream(raw_path: Path, system_text: str, prompt: str):
    events = []
    for ln in raw_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(ln))
        except ValueError:
            pass
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    trace = [{"role": "system", "content": system_text}, {"role": "user", "content": prompt}]
    models, tool_calls = set(), 0
    for e in events:
        msg = e.get("message") or {}
        if e.get("type") == "assistant":
            if msg.get("model"):
                models.add(msg["model"])
            thinking = None
            for block in msg.get("content") or []:
                kind = block.get("type")
                if kind == "thinking":
                    thinking = block.get("thinking")
                elif kind == "text" and block.get("text", "").strip():
                    trace.append({"role": "assistant", "content": block["text"], **({"thinking": thinking} if thinking else {})})
                    thinking = None
                elif kind == "tool_use":
                    tool_calls += 1
                    trace.append({"role": "tool_call", "name": block.get("name"),
                                  "content": json.dumps(block.get("input"), ensure_ascii=False, indent=2),
                                  **({"thinking": thinking} if thinking else {})})
                    thinking = None
        elif e.get("type") == "user":
            for block in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                if block.get("type") == "tool_result":
                    content = block.get("content")
                    if isinstance(content, list):
                        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
                    trace.append({"role": "tool_result", "content": str(content)[:20000],
                                  **({"is_error": True} if block.get("is_error") else {})})
    return {"init": init, "result": result, "trace": trace, "models": sorted(models), "tool_calls": tool_calls,
            "text": "\n".join(json.dumps(e, ensure_ascii=False) for e in events)}


def assert_model(requested, served):
    for m in served:
        if requested in MODEL_ALIASES:
            if requested not in m:
                raise HarnessError("serving_substitution", f"obslouženo {m}, požadováno {requested}")
        elif m != requested and not re.fullmatch(re.escape(requested.removesuffix("-latest")) + r"[-@](\d{8}|\d{4}-\d{2}-\d{2})", m):
            raise HarnessError("serving_substitution", f"obslouženo {m}, požadováno {requested}")


def contamination(arm, parsed):
    """B nesmí mít ani použít OPORU; A ani B nesmí sáhnout na zlatá data evalu."""
    found = []
    init = parsed["init"]
    for key in ("skills", "plugins", "mcp_servers", "slash_commands", "agents"):
        blob = json.dumps(init.get(key, []), ensure_ascii=False)
        if arm == "B" and re.search("opora", blob, re.IGNORECASE):
            found.append(f"init.{key} obsahuje opora")
    calls = "\n".join(t["content"] for t in parsed["trace"] if t["role"] == "tool_call")
    if arm == "B" and CONTAMINATION_B.search(calls):
        found.append("B volá OPORU: " + CONTAMINATION_B.search(calls).group(0))
    if GOLD_LEAK.search(calls):
        found.append("sahá na data evalu: " + GOLD_LEAK.search(calls).group(0))
    return found


def collect_diff(ws: Path, base: str, out: Path):
    run(["git", "-c", "core.autocrlf=false", "add", "-A"], ws)
    diff = run(["git", "-c", "core.autocrlf=false", "diff", "--cached", base, "--", ".",
                ":(exclude)package-lock.json"], ws)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(diff, encoding="utf-8")
    return diff


# --- jeden (případ, rameno, opakování) ------------------------------------------------------------

def run_one(case, arm, rep, args, vdir: Path):
    pid = f"{case['id']}.{arm}"
    run_dir = Path(args.work_root) / f"{args.variant}-{arm}-{case['id']}-r{rep}"
    opora = None
    t0 = time.time()
    try:
        ws, base = prepare_workspace(case, run_dir)
        system_text = "(výchozí system prompt Claude Code, --safe-mode)"
        env_extra, ctx_file, dirs, autonomy = {}, None, [], None
        if arm == "A":
            opora, ready, preview_port = start_opora(case, run_dir, ws)
            ctx_file, dirs, ctx_text = opora_context(case, run_dir, ready, preview_port)
            system_text += "\n\n--append-system-prompt-file:\n" + ctx_text
            autonomy = json.loads((run_dir / "autonomy.json").read_text(encoding="utf-8"))
            env_extra = {"OPORA_BASE_URL": ready["baseUrl"], "OPORA_AGENT_NAME": "eval-agent"}
        cmd = agent_command(case["prompt"], args.model, arm, ctx_file, dirs)
        raw = vdir / "raw" / f"{pid}_rep{rep}.jsonl"
        code, agent_s = run_agent(cmd, ws, child_env(env_extra), raw, args.timeout_s)
        snapshot = None
        if opora is not None:
            # P1–P3: stav izolované OPORY přečíst PŘED jejím ukončením (jen GET), uložit vedle výsledků
            snapshot = metrics.read_opora(ready["baseUrl"], ready["project"], ready["workspace"])
            snap_path = vdir / "opora" / f"{pid}_rep{rep}.json"
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
            grade.kill_tree(opora)  # kontrola koncového stavu už OPORU nevidí
            opora = None
        leftovers = grade.kill_leftovers(run_dir)  # procesy, které agent nechal běžet (vite preview)
        parsed = parse_stream(raw, system_text, case["prompt"])
        res = parsed["result"] or {}
        if code is None:
            raise HarnessError("timeout", f"agent překročil {args.timeout_s} s", usage=res.get("usage"))
        if not parsed["result"]:
            raise HarnessError("agent_error", f"claude skončil kódem {code} bez události result")
        assert_model(args.model, parsed["models"])
        dirty = contamination(arm, parsed)
        if dirty:
            raise HarnessError("contamination", "; ".join(dirty), usage=res.get("usage"))
        diff_rel = f"{args.variant}/artifacts/{pid}_rep{rep}.diff"
        diff = collect_diff(ws, base, FLOW / diff_rel)
        checked = grade.check_workspace(case["id"], ws, shots_dir=vdir / "shots", shot_prefix=f"{pid}_rep{rep}")
        tm = metrics.trace_metrics(raw, env_extra.get("OPORA_BASE_URL"))
        dm = metrics.diff_metrics(diff)
        om = metrics.opora_metrics(snapshot, ws) if arm == "A" else None
        row = {
            "prompt_id": pid, "rep": rep, "prompt": case["prompt"], "tags": [f"arm-{arm}", *case["tags"]],
            "meta": {"case": case["id"], "arm": arm, "diff": diff_rel, "diff_lines": diff.count("\n"),
                     "no_op": not diff.strip(), "leftover_processes": leftovers, "checks": checked["checks"], "notes": checked["notes"],
                     "num_turns": res.get("num_turns"), "permission_denials": len(res.get("permission_denials") or []),
                     "reported_cost_usd": res.get("total_cost_usd"), "api_key_source": parsed["init"].get("apiKeySource"),
                     "init_skills": parsed["init"].get("skills"), "exit_code": code, "autonomy": autonomy,
                     "result_subtype": res.get("subtype"), "is_error": res.get("is_error"),
                     "agent_seconds": round(agent_s, 1), "total_seconds": round(time.time() - t0, 1)},
            "model": (parsed["models"] or [None])[-1], "usage": res.get("usage"),
            "stop_reason": res.get("subtype"), "status": "ok",
            "latency_s": round(agent_s, 1), "tool_calls": parsed["tool_calls"],
            "turns": res.get("num_turns"), "perm_denials": len(res.get("permission_denials") or []),
            "grade": checked["grade"], "explanation": checked["explanation"],
        }
        metrics.apply_to_row(row, checked, tm, dm, om)
        append_jsonl(vdir / "results.jsonl", row)
        tp = vdir / "traces" / f"{pid}_rep{rep}.json"
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(json.dumps(parsed["trace"], ensure_ascii=False, indent=2), encoding="utf-8")
        eprint(f"  {pid} rep{rep}: checks_pass={row['grade']['checks_pass']} "
               f"sekce={row['grade']['section_coverage']} ({row['latency_s']} s)")
        return True
    except (HarnessError, grade.CaseNotReady, subprocess.TimeoutExpired, OSError) as e:
        cls = getattr(e, "failure_class", "case_not_ready" if isinstance(e, grade.CaseNotReady) else "harness")
        append_jsonl(vdir / "errors.jsonl", {"prompt_id": pid, "rep": rep, "failure_class": cls, "error": str(e)[:800],
                                             "usage": getattr(e, "extra", {}).get("usage"),
                                             "latency_s": round(time.time() - t0, 1)})
        eprint(f"  {pid} rep{rep} SELHAL [{cls}]: {str(e)[:300]}")
        return False
    finally:
        if opora is not None:
            grade.kill_tree(opora)
        if not args.keep_workspace:
            grade.rmtree_force(run_dir)


# --- CLI ------------------------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(description="Eval OPORA vs. bez OPORY (headless Claude Code)")
    p.add_argument("--variant", required=True, help="baseline nebo v<N> (verze harnessu/skillu)")
    p.add_argument("--arm", required=True, choices=["A", "B", "AB"],
                   help="A = s OPOROU, B = bez, AB = obě ramena v jednom poolu (souběžně s --concurrency ≥ 2)")
    p.add_argument("--cases", default="", help="čárkami oddělená id (výchozí všechny připravené)")
    p.add_argument("--reps", type=int, default=2, help="opakování na rameno a případ (metriky.md §4: 2)")
    p.add_argument("--timeout-s", type=int, default=3600, help="tvrdý strop na běh agenta (0 = bez stropu)")
    p.add_argument("--model", default="opus", help="model agenta (alias nebo plné id)")
    p.add_argument("--work-root", default=os.environ.get("OPORA_EVAL_WORK_ROOT", r"C:\oe"),
                   help="krátká cesta bez mezer mimo repozitáře (git worktree a npm na Windows)")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--keep-workspace", action="store_true")
    p.add_argument("--approve-harness", action="store_true", help="zapíše sha harnessu (rozhoduje člověk)")
    p.add_argument("--dry-run", action="store_true", help="jen vypíše plán příkazů, nic nespouští")
    a = p.parse_args(argv)
    if not re.fullmatch(r"baseline|v[1-9]\d*", a.variant):
        p.error("--variant musí být baseline nebo v<N> (report jiné složky ignoruje)")
    if a.reps < 1 or a.concurrency < 1 or a.timeout_s < 0:
        p.error("--reps/--concurrency ≥ 1, --timeout-s ≥ 0")
    return a


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv if argv is not None else sys.argv[1:])
    state = json.loads((FLOW / "_state.json").read_text(encoding="utf-8"))
    approved = check_harness(state, args.approve_harness, args.dry_run)
    if not approved and not args.dry_run:
        return 2
    cases = load_cases()
    wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
    if wanted:
        unknown = set(wanted) - {c["id"] for c in cases}
        if unknown:
            eprint(f"neznámé případy: {sorted(unknown)}")
            return 2
        cases = [c for c in cases if c["id"] in wanted]
    else:
        cases = [c for c in cases if c["id"] in grade.SPECS]
    # Rameno A seed nedostává (prázdný projekt); zlatou mapu čte jen grader, když případ má cesty.
    not_ready = [c["id"] for c in cases if c["id"] not in grade.SPECS
                 or not (FLOW / "templates" / str(c["template"])).is_dir()
                 or (grade.SPECS[c["id"]].get("journeys") and not (FLOW / "seeds" / f"{c['id']}.json").exists())]
    if not_ready:  # před jakoukoli útratou: nepřipravený případ se nespouští, nikdy neskóruje nulou
        eprint(f"případy bez kontrol/šablony/zlaté mapy: {not_ready} – doplň grade.SPECS, templates/, seeds/")
        return 2
    work_root = Path(args.work_root)
    if " " in str(work_root) or len(str(work_root)) > 40:
        eprint(f"--work-root {work_root}: potřeba krátká cesta bez mezer (Windows MAX_PATH, git)")
        return 2
    vdir = FLOW / args.variant
    done = done_keys(vdir / "results.jsonl")
    arms = list(args.arm)  # "AB" -> ["A", "B"]: každý běh má vlastní run_dir, porty i pracovní kopii
    # Prokládaně (C01.A, C01.B, …), aby souběh pustil obě ramena téhož případu najednou.
    tasks = [(c, arm, r) for c in cases for r in range(args.reps) for arm in arms
             if (f"{c['id']}.{arm}", r) not in done]
    eprint(f"[{args.variant}/{args.arm}] {len(tasks)} z {len(cases) * args.reps * len(arms)} (případ, rameno, "
           f"opakování) k běhu, souběh {args.concurrency}; harness {'schválen' if approved else 'NESCHVÁLEN'}")
    if args.dry_run:
        print_plan(tasks, args)
        return 0
    for parent in [work_root, *work_root.parents]:
        if (parent / "CLAUDE.md").exists() or (parent / ".git").exists():
            eprint(f"{parent} obsahuje CLAUDE.md nebo .git – pracovní kořen musí ležet mimo repozitáře")
            return 2
    work_root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        outcomes = list(pool.map(lambda t: run_one(t[0], t[1], t[2], args, vdir), tasks))
    ok = sum(outcomes)
    eprint(f"[{args.variant}/{args.arm}] hotovo: {ok} ok, {len(outcomes) - ok} selhalo -> {vdir / 'results.jsonl'}")
    return 0 if ok == len(outcomes) else 1


def print_plan(tasks, args):
    for case, arm, rep in tasks:
        run_dir = Path(args.work_root) / f"{args.variant}-{arm}-{case['id']}-r{rep}"
        ws = run_dir / "w"
        print(f"\n### {case['id']}.{arm} rep{rep}  (šablona {case['template']}, tagy {case['tags']})")
        print(f"1. kopie templates/{case['template']} -> {ws}; npm ci --prefer-offline; git init + commit (základ diffu)")
        if arm == "A":
            print(f"2. uv run --project <repo> python opora_backend.py --data {run_dir / 'd'} --repo {ws} "
                  f"--port <volný> --ready-file {run_dir / 'opora-ready.json'} --autonomy-log {run_dir / 'autonomy.json'}")
            print("   PRÁZDNÝ lokální projekt (žádný seed; zlatá mapa jen pro grader) + grant_autonomy jako člověk")
            print(f"   kopie skillu -> {run_dir / 'skill' / 'opora-control-center'}; journey_run*.py -> {run_dir / 'opora-tools'}; "
                  f"kontext -> {run_dir / 'opora-context.md'}")
            print("   env agenta: OPORA_BASE_URL=http://127.0.0.1:<port>, OPORA_AGENT_NAME=eval-agent; bez ANTHROPIC_API_KEY")
        else:
            print("2. (rameno B: žádná OPORA, žádný skill; env bez ANTHROPIC_API_KEY a bez OPORA_*)")
        cmd = agent_command("<ZÁMĚR>", args.model, arm, run_dir / "opora-context.md",
                            [run_dir / "skill" / "opora-control-center", run_dir / "opora-tools"])
        print(f"3. cwd={ws}, strop {args.timeout_s} s:\n   " + subprocess.list2cmdline(cmd))
        print(f"4. stream-json -> {args.variant}/raw/{case['id']}.{arm}_rep{rep}.jsonl -> traces/; "
              f"kontrola kontaminace a modelu; diff -> artifacts/")
        if arm == "A":
            print(f"4b. před ukončením OPORY: GET view, agent-state, journeys, map-check -> {args.variant}/opora/{case['id']}.A_rep{rep}.json (P1–P3)")
        print(f"5. grade.check_workspace('{case['id']}'): npm ci, build, test, sekce (statické + vite preview + Playwright), "
              f"kritéria, stavy (Q3), přístupnost (Q4), testy (Q8), screenshoty -> {args.variant}/shots/; C4/C5/P4/P5 z raw a diffu")
        print(f"6. řádek {case['id']}.{arm} rep{rep} -> {args.variant}/results.jsonl (chyba -> errors.jsonl)")
        print(f"   záměr ({len(case['prompt'])} znaků):\n   > " + case["prompt"].replace("\n", "\n   > "))


if __name__ == "__main__":
    sys.exit(main())
