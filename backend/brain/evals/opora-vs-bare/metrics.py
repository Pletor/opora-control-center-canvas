"""Metriky ceny práce a práce s OPOROU (metriky.md §2 a §3) – bez modelu, jen z dat běhu.

- `trace_metrics(raw_path, opora_base)` → C4 (zbytečné pokusy: chybové výsledky nástrojů, opakování) a P4
  (podíl volání a času na OPORU) ze surového stream-json (`baseline/raw/<id>_rep<k>.jsonl`).
- `diff_metrics(diff_text)` → C5 (soubory mimo kód aplikace) a P5 (`.md`/poznámky v repu) z diffu běhu.
- `read_opora(base, project, workspace)` → snímek izolované OPORY (view, agent-state, journeys, map-check);
  volá ho run_eval PŘED ukončením backendu ramene A, jen GET.
- `opora_metrics(snapshot, ws)` → P1 (plán), P2 (dotažení), P3 (plán ↔ kód).
Stdlib; volá ho `run_eval.py` (nový běh) i `recheck.py` (přepočet pilotu).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# Volání nástroje patří OPOŘE, když míří na její skripty, API, runner cesty nebo pracovní drafty plánu.
OPORA_CALL = re.compile(
    r"opora_(hub|read|write|save|stage|cycle|closure)\.py|journey_run|/api/(oporahub|canvas-plan|graph|node-|desktop-v3"
    r"|project-architecture|view|project-settings|brief-vault|canvas-)|hub_http|\.opora-drafts|opora-control-center"
    r"|OPORA_BASE_URL|skill[\\/]+opora", re.IGNORECASE)
HTTP_ERR = re.compile(r"\bHTTP(?:/[\d.]+)?\s*(?:Error\s*)?[45]\d\d\b|\bstatus(?:_code)?[\"']?\s*[:=]\s*[45]\d\d\b"
                      r"|->\s*[45]\d\d\b|\b[45]\d\d (?:Bad Request|Unauthorized|Forbidden|Not Found|Conflict"
                      r"|Unprocessable|Internal Server Error)", re.IGNORECASE)
TRACEBACK = re.compile(r"Traceback \(most recent call last\)")
OK_FALSE = re.compile(r"[\"']ok[\"']\s*:\s*false", re.IGNORECASE)
EXIT_NZ = re.compile(r"\bExit code [1-9]\d*\b|\bexit(?:ed)? (?:with )?(?:code|status) [1-9]\d*\b", re.IGNORECASE)
PERM_DENIED = re.compile(r"Permission for this tool use was denied|permission.*denied", re.IGNORECASE)

APP_ROOT_FILES = {"index.html", "package.json", "vite.config.ts", "vite.config.js", "tsconfig.json",
                  "tsconfig.node.json", "tsconfig.app.json", ".gitignore", "vitest.config.ts", "eslint.config.js"}
APP_DIRS = ("src/", "public/")
APP_EXT = re.compile(r"\.(tsx?|jsx?|css|scss|json|svg|png|jpe?g|webp|gif|ico|woff2?)$", re.IGNORECASE)
NOTE_EXT = re.compile(r"\.(md|markdown|txt|rst)$", re.IGNORECASE)


def _ts(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _events(raw_path: Path):
    out = []
    for ln in Path(raw_path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def _result_text(content):
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content or "")


def opora_base_from_trace(trace):
    """Adresa izolované OPORY z kontextu ramene A (první zpráva trace), nebo None."""
    for item in trace[:2]:
        m = re.search(r"Server OPORA: (http://127\.0\.0\.1:\d+)", item.get("content") or "")
        if m:
            return m.group(1)
    return None


def trace_metrics(raw_path: Path, opora_base: str | None = None) -> dict:
    """C4 + P4 ze surového stream-json. Čas volání = od jeho `tool_use` po další `tool_use` (nebo konec běhu),
    tedy běh nástroje i přemýšlení nad jeho výsledkem."""
    events = _events(raw_path)
    port_re = re.compile(re.escape(opora_base.split("//", 1)[1])) if opora_base else None
    calls, by_id, order = [], {}, []
    end_ts = None
    for e in events:
        ts = _ts(e.get("timestamp"))
        if ts:
            end_ts = ts
        msg = e.get("message") or {}
        if e.get("type") == "assistant":
            for b in msg.get("content") or []:
                if b.get("type") == "tool_use":
                    text = json.dumps(b.get("input"), ensure_ascii=False, sort_keys=True)
                    opora = bool(OPORA_CALL.search(text) or (port_re and port_re.search(text)))
                    call = {"id": b.get("id"), "name": b.get("name"), "key": f"{b.get('name')}:{text}",
                            "opora": opora, "ts": ts, "error": False, "denied": False}
                    calls.append(call)
                    by_id[call["id"]] = call
                    order.append(call)
        elif e.get("type") == "user" and isinstance(msg.get("content"), list):
            for b in msg["content"]:
                if b.get("type") != "tool_result" or b.get("tool_use_id") not in by_id:
                    continue
                call = by_id[b["tool_use_id"]]
                text = _result_text(b.get("content"))
                if PERM_DENIED.search(text[:400]) and b.get("is_error"):
                    call["denied"] = True
                    continue
                call["error"] = bool(b.get("is_error") or TRACEBACK.search(text) or OK_FALSE.search(text)
                                     or EXIT_NZ.search(text[:2000]) or HTTP_ERR.search(text[:4000]))
    for i, call in enumerate(order):
        nxt = order[i + 1]["ts"] if i + 1 < len(order) else end_ts
        call["seconds"] = max(0.0, (nxt or 0) - (call["ts"] or 0)) if call["ts"] and nxt else 0.0
    seen, repeats = set(), 0
    for call in calls:
        if call["key"] in seen and call["name"] not in ("Read", "TodoWrite"):
            repeats += 1
        seen.add(call["key"])
    n = len(calls)
    opora = [c for c in calls if c["opora"]]
    total_s = sum(c["seconds"] for c in calls)
    errors = sum(c["error"] for c in calls)
    return {
        "tool_calls": n,
        "tool_errors": errors,
        "tool_errors_opora": sum(c["error"] for c in opora),
        "tool_errors_code": errors - sum(c["error"] for c in opora),
        "perm_denied": sum(c["denied"] for c in calls),
        "repeats": repeats,
        "wasted": errors + repeats + sum(c["denied"] for c in calls),
        "opora_calls": len(opora),
        "opora_call_share": round(len(opora) / n, 4) if n else 0.0,
        "opora_seconds": round(sum(c["seconds"] for c in opora), 1),
        "opora_time_share": round(sum(c["seconds"] for c in opora) / total_s, 4) if total_s else 0.0,
    }


def diff_files(diff_text: str):
    """[(cesta, stav)] souborů v diffu; stav `added` / `deleted` / `modified`."""
    out, current = [], None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = [line.split(" b/", 1)[-1], "modified"]
            out.append(current)
        elif current and line.startswith("new file mode"):
            current[1] = "added"
        elif current and line.startswith("deleted file mode"):
            current[1] = "deleted"
    return [tuple(x) for x in out]


def is_app_file(path: str) -> bool:
    if NOTE_EXT.search(path):
        return False
    if path in APP_ROOT_FILES:
        return True
    return path.startswith(APP_DIRS) and bool(APP_EXT.search(path))


def diff_metrics(diff_text: str) -> dict:
    """C5 = soubory mimo kód aplikace (pomocné skripty, poznámky, drafty), P5 = poznámky `.md`/`.txt`."""
    files = [(p, s) for p, s in diff_files(diff_text) if s != "deleted"]
    outside = sorted(p for p, _ in files if not is_app_file(p))
    notes = sorted(p for p in outside if NOTE_EXT.search(p))
    return {"files_changed": len(files), "files_outside": len(outside), "outside_list": outside[:30],
            "notes_in_repo": len(notes), "notes_list": notes[:30]}


def apply_to_row(row: dict, checked: dict, tm: dict, dm: dict, om: dict | None) -> dict:
    """Zapíše výsledek kontroly (Q1–Q4, Q8, screenshoty) a cenu práce (C4, C5, P4, P5) a P1–P3 do řádku."""
    meta = row.setdefault("meta", {})
    meta.update({"checks": checked["checks"], "notes": checked["notes"], "info": checked.get("info", {}),
                 "a11y": checked.get("a11y", {}), "tests": checked.get("tests", {}), "shots": checked.get("shots", [])})
    row["grade"] = checked["grade"]
    row["explanation"] = checked["explanation"]
    row["cost"] = {"c4_zbytecne": tm["wasted"], "c4_chyby": tm["tool_errors"], "c4_chyby_opora": tm["tool_errors_opora"],
                   "c4_opakovani": tm["repeats"], "c4_zamitnuto": tm["perm_denied"],
                   "c5_mimo_zadani": dm["files_outside"], "c5_soubory": dm["outside_list"],
                   "files_changed": dm["files_changed"]}
    if meta.get("arm") == "A":
        row["opora"] = {**(om or {}), "p4_podil_volani": tm["opora_call_share"], "p4_podil_casu": tm["opora_time_share"],
                        "p4_volani_opora": tm["opora_calls"], "p4_chyby_opora": tm["tool_errors_opora"],
                        "p5_poznamky_v_repu": dm["notes_in_repo"], "p5_soubory": dm["notes_list"],
                        "snapshot": om is not None}
    return row


# --- snímek izolované OPORY (jen ramene A) ---------------------------------------------------------

def _get(base, route, params, timeout=20):
    url = base.rstrip("/") + route + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})  # anonymní čtení, žádná identita
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - jen loopback izolované OPORY
            return {"status": r.status, "body": json.loads(r.read().decode("utf-8") or "null")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "error": e.read().decode("utf-8", "replace")[:500]}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"status": None, "error": str(e)[:300]}


def read_opora(base: str, project: str, workspace: str) -> dict:
    """Jen GET: view, architektura, agent-state (všechny stránky karet), cesty a kontrola mapy."""
    scope = {"project": project, "workspace": workspace}
    snap = {"base": base, "scope": scope, "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "view": _get(base, "/api/view", scope)}
    state = _get(base, "/api/oporahub/agent-state", scope)
    cards = list((state.get("body") or {}).get("cards") or []) if state.get("status") == 200 else []
    offset = (state.get("body") or {}).get("cardsNextOffset") if state.get("status") == 200 else None
    while offset:
        more = _get(base, "/api/oporahub/agent-state", {**scope, "cardsOffset": offset})
        if more.get("status") != 200:
            break
        cards += more["body"].get("cards") or []
        offset = more["body"].get("cardsNextOffset")
    if state.get("status") == 200:
        state["body"]["cards"] = cards
    snap["agentState"] = state
    snap["architecture"] = _get(base, "/api/project-architecture", {"project": project})
    snap["journeys"] = _get(base, "/api/project-architecture/journeys", {"project": project})
    snap["mapCheck"] = _get(base, "/api/project-architecture/map-check", {"project": project})
    return snap


DONE_REASONS = {"card_closed", "plan_written_back"}


def _graph_nodes(snapshot):
    """Uzly pohledu prostoru doplněné o uzly architektury (aplikace a stránky žijí v architektuře projektu)."""
    nodes = {}
    for key in ("architecture", "view"):
        body = (snapshot.get(key) or {}).get("body") or {}
        for n in (body.get("graph") or {}).get("nodes") or []:
            nodes.setdefault(n.get("id"), n)
    return list(nodes.values())


def opora_metrics(snapshot: dict | None, ws: Path | None = None) -> dict | None:
    """P1–P3 ze snímku; P3 navíc ze `src/` pracovní kopie (literály `data-opora-section`)."""
    if not snapshot:
        return None
    nodes = _graph_nodes(snapshot)
    sites = [n for n in nodes if isinstance(n.get("site"), dict)]
    apps = [n for n in sites if n["site"].get("kind") == "application"]
    pages = [n for n in sites if n["site"].get("kind") == "page"]
    full_pages = [p for p in pages if p["site"].get("goal") and p["site"].get("feel") and p["site"].get("sections")]
    state = (snapshot.get("agentState") or {}).get("body") or {}
    cards = state.get("cards") or []
    steps = [((c.get("steps") or {}).get("total") or 0) for c in cards]
    done = [c for c in cards if c.get("reason") in DONE_REASONS]
    journeys = ((snapshot.get("journeys") or {}).get("body") or {}).get("journeys") or []
    verified = [j for j in journeys if (j.get("lastRun") or {}).get("passed")]
    findings = ((snapshot.get("mapCheck") or {}).get("body") or {}).get("findings") or []
    map_sections = sorted({s.get("id") for p in pages for s in p["site"].get("sections") or []
                           if isinstance(s, dict) and s.get("id")})
    code_sections = set()
    if ws is not None and (Path(ws) / "src").is_dir():
        for f in (Path(ws) / "src").rglob("*.tsx"):
            if re.search(r"\.(test|spec)\.tsx$", f.name):
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            code_sections |= set(re.findall(r"data-opora-section\s*=\s*[{\"'`]*\s*[\"'`]([\w-]+)[\"'`]", text))
    in_code = [s for s in map_sections if s in code_sections]
    return {
        "p1_apps": len(apps), "p1_pages": len(pages), "p1_pages_full": len(full_pages),
        "p1_journeys": len(journeys), "p1_cards": len(cards),
        "p1_cards_with_steps": sum(1 for s in steps if s), "p1_steps": sum(steps),
        "p2_cards_done": len(done), "p2_done_share": round(len(done) / len(cards), 4) if cards else 0.0,
        "p2_map_gaps": state.get("mapGapsTotal", len(state.get("mapGaps") or [])),
        "p2_map_findings": len(findings), "p2_journeys_verified": len(verified),
        "p3_map_sections": len(map_sections), "p3_map_in_code": len(in_code),
        "p3_map_to_code": round(len(in_code) / len(map_sections), 4) if map_sections else 0.0,
        "p3_code_not_in_map": sorted(code_sections - set(map_sections))[:20],
        "read_status": {k: (snapshot.get(k) or {}).get("status") for k in ("view", "architecture", "agentState", "journeys", "mapCheck")},
    }
