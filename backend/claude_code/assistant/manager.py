"""Správce session asistenta: registr, procesy, události a limity (docs/asistent.md §3, §4, §8).

Proces vznikne až s první zprávou a po nečinnosti zanikne; další zpráva ho obnoví přes
`--resume <claudeSessionId>`. Model spouští jen člověk zprávou, nic jiného.
Dotaz CLI na oprávnění (`control_request` can_use_tool, §5.1) backend buď sám zamítne, nebo ho
ukáže v UI jako `approval` a čeká na rozhodnutí člověka (`decide`); bez odpovědi do 10 min zamítne.
"""

from __future__ import annotations

import shutil
import threading
import time
import uuid

from backend.claude_code.assistant import approvals
from backend.claude_code.assistant import command as cli
from backend.claude_code.assistant.approval_book import ApprovalBook, ApprovalNotFound, Pending
from backend.claude_code.assistant.context import compose, validate_context, validate_text, validate_title
from backend.claude_code.assistant.errors import AssistantError, AssistantUnavailable, SessionNotFound
from backend.claude_code.assistant.event_log import EventLog
from backend.claude_code.assistant.registry import PLACEHOLDER_TITLES, SessionRegistry, title_from
from backend.claude_code.assistant.session_process import SessionProcess
from backend.claude_code.assistant.stream import EMPTY_STATE, control_request, map_line, tool_summary
from backend.claude_code.assistant.transcript import read_transcript
from backend.claude_code.assistant.watchdog import Limits, Watchdog, expired

__all__ = ["ApprovalNotFound", "AssistantError", "AssistantManager", "AssistantUnavailable", "Limits",
           "SessionNotFound"]
DECISIONS = ("allow", "deny")
NOTE_LIMIT = 2000


class _Live:
    def __init__(self, process, now):
        self.process = process
        self.stream = dict(EMPTY_STATE)
        self.turn_started = None
        self.last_activity = now


class AssistantManager:
    def __init__(self, data_root, locate, *, which=shutil.which, command_builder=cli.build_command,
                 environ=None, limits=None, clock=time.monotonic, home=None, version_probe=cli.claude_version,
                 base_url=None, route_hint=None, route_timeout=4.0):
        self.registry = SessionRegistry(data_root)
        self.locate = locate
        self.limits = limits or Limits()
        self._which, self._build, self._environ = which, command_builder, environ
        self._clock, self._home, self._probe = clock, home, version_probe
        self._base_url = base_url  # adresa vlastní instance pro skill (OPORA_BASE_URL, §13.1)
        # Směrovač Jev (§13.2): `route_hint(text, context)` → hint | None; bez něj zpráva jde beze změny.
        self._route_hint, self._route_timeout = route_hint, route_timeout
        self._versions = {}
        self._lock = threading.RLock()
        self._live = {}
        self._logs = {}
        self._approvals = ApprovalBook()
        self._watchdog = Watchdog(self.sweep, self.limits.tick_seconds)

    # --- čtení -----------------------------------------------------------------------
    def _log(self, session_id):
        return self._logs.setdefault(session_id, EventLog())

    def _record(self, session_id):
        record = self.registry.get(session_id) if isinstance(session_id, str) else None
        if record is None:
            raise SessionNotFound("Session asistenta neexistuje.")
        return record

    def _public(self, record):
        log = self._logs.get(record["id"])
        return {**record, "lastSeq": log.last_seq if log else 0}

    def running(self):
        with self._lock:
            return sum(1 for live in self._live.values() if live.process.alive)

    def status(self):
        path = cli.find_claude(self._which)
        if path and path not in self._versions:
            self._versions[path] = self._probe(path)
        return {"available": bool(path), "claudePath": path, "version": self._versions.get(path) if path else None,
                "running": self.running(), "limit": self.limits.max_processes}

    def sessions(self, project):
        return [self._public(item) for item in self.registry.list(project)]

    def session(self, session_id):
        return self._public(self._record(session_id))

    def events(self, session_id, after=0):
        with self._lock:
            record = self._record(session_id)
            log = self._logs.get(session_id)
            return (log.after(after) if log else []), record["state"] == "closed"

    def transcript(self, session_id):
        return read_transcript(self._record(session_id).get("claudeSessionId"), self._home)

    # --- zápis -----------------------------------------------------------------------
    def create(self, project, workspace=None, title=None, model=None):
        model = model or cli.DEFAULT_MODEL
        if model not in cli.MODELS:
            raise AssistantError("Model asistenta je opus, sonnet nebo fable.")
        if title is not None and (not isinstance(title, str) or len(title) > 120):
            raise AssistantError("Název session může mít nejvýše 120 znaků.")
        chosen, _root = self.locate(project, workspace)
        return self._public(self.registry.create(project, chosen, model, title))

    def _route(self, text, context):
        """Hint a telemetrie směrovače mimo zámek, s tvrdou mezí; porucha = bez hintu."""
        if self._route_hint is None or text.lstrip().startswith("/"):
            return None, None
        result, started = [], time.monotonic()

        def run():
            try:
                result.append(self._route_hint(text, context))
            except Exception:  # noqa: BLE001 — Jev je jen zrychlení; chyba nesmí zastavit zprávu člověka
                result.append(None)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(self._route_timeout)
        ms = round((time.monotonic() - started) * 1000)
        hint = result[0] if result else None
        if hint is None:
            return None, {"skipped": "timeout" if not result else "unavailable", "ms": ms}
        return hint, {**hint, "ms": ms}

    def send(self, session_id, text, context=None):
        text, context = validate_text(text), validate_context(context)
        hint, telemetry = self._route(text, context)
        with self._lock:
            record = self._record(session_id)
            if record["state"] == "closed":
                raise AssistantError("Session je zavřená; založte novou.")
            live = self._live.get(session_id)
            if live is not None and live.turn_started is not None:
                raise AssistantError("Asistent ještě odpovídá na předchozí zprávu. Počkejte, nebo tah zastavte.")
            if live is None or not live.process.alive:
                live = self._spawn(record)
            changes = {"state": "running"}
            if record["title"] in PLACEHOLDER_TITLES and not record["claudeSessionId"]:
                changes["title"] = title_from(text)
            self.registry.update(session_id, **changes)
            event = self._log(session_id).append({"type": "message", "role": "user", "text": text})
            if telemetry is not None:
                self._log(session_id).append({"type": "status", "router": telemetry})
            live.turn_started = live.last_activity = self._clock()
            try:
                live.process.send(compose(text, context, hint))
            except OSError:
                self._detach(session_id)
                self._end_turn(session_id, "Proces Claude Code nepřijal zprávu; zkuste to znovu.")
            else:
                return event
        live.process.kill()
        raise AssistantUnavailable("Proces Claude Code nepřijal zprávu; zkuste to znovu.")

    def rename(self, session_id, title):
        title = validate_title(title)
        with self._lock:
            if self._record(session_id)["state"] == "closed":
                raise AssistantError("Session je zavřená; přejmenovat ji nelze.")
            self.registry.update(session_id, title=title)
        return self.session(session_id)

    def _spawn(self, record):
        if self.running() >= self.limits.max_processes:
            raise AssistantError(f"Najednou mohou běžet nejvýš {self.limits.max_processes} procesy asistenta. "
                                 "Zastavte nebo zavřete jinou session.")
        claude = cli.find_claude(self._which)
        if not claude:
            raise AssistantUnavailable("Claude Code (`claude`) není nainstalovaný nebo není v PATH.")
        _workspace, root = self.locate(record["projectId"], record["workspace"])
        command = self._build(claude, record["model"], record["claudeSessionId"])
        sid = record["id"]
        process = SessionProcess(command, cwd=root, env=cli.child_env(self._environ, self._base_url),
                                 on_line=lambda proc, line: self._on_line(sid, proc, line),
                                 on_exit=lambda proc: self._on_exit(sid, proc))
        live = self._live[sid] = _Live(process, self._clock())
        try:
            process.start()
        except OSError as exc:
            self._live.pop(sid, None)
            raise AssistantUnavailable("Proces Claude Code nelze spustit.") from exc
        try:
            process.send_json(approvals.INITIALIZE)  # bez něj CLI dotazy na oprávnění neposílá (§11)
        except OSError as exc:
            self._live.pop(sid, None)
            process.kill()
            raise AssistantUnavailable("Proces Claude Code nepřijal úvodní initialize.") from exc
        self._watchdog.ensure()
        return live

    def _end_turn(self, session_id, message=None):
        if message:
            self._log(session_id).append({"type": "error", "message": message})
        self._log(session_id).append({"type": "status", "state": "idle"})
        record = self.registry.get(session_id)
        if record and record["state"] != "closed":
            self.registry.update(session_id, state="idle")

    def _on_line(self, session_id, process, line):
        with self._lock:
            live = self._live.get(session_id)
            if live is None or live.process is not process:
                return
            control = control_request(line)
            if control is not None:
                live.last_activity = self._clock()
                self._on_control(session_id, live, *control)
                return
            known = live.stream.get("sessionId")
            events, live.stream = map_line(line, live.stream)
            live.last_activity = self._clock()
            if live.stream.get("sessionId") and live.stream["sessionId"] != known:
                self.registry.update(session_id, claudeSessionId=live.stream["sessionId"])
            for event in events:
                if event["type"] == "turn_end":
                    live.turn_started = None
                    self.registry.update(session_id, state="idle")
                self._log(session_id).append(event)

    def _on_exit(self, session_id, process):
        with self._lock:
            live = self._live.get(session_id)
            if live is None or live.process is not process:
                return
            del self._live[session_id]
            self._drop_approvals(session_id)
            if live.turn_started is not None and not process.intentional:
                tail = process.stderr_tail().strip()
                detail = f" ({tail[-500:]})" if tail else ""
                self._end_turn(session_id, "Proces Claude Code skončil uprostřed tahu." + detail)

    def _detach(self, session_id):
        live = self._live.pop(session_id, None)
        if live is not None:
            live.process.intentional = True
        self._drop_approvals(session_id)
        return live

    # --- schválení (§5.1) ------------------------------------------------------------
    def _reply(self, live, item):
        try:
            live.process.send_json(item)
        except OSError:
            pass  # proces končí; jeho konec ohlásí _on_exit

    def _on_control(self, session_id, live, request_id, request):
        """Dotaz CLI pod zámkem: sám zamítne, co není zápis přes opora_write.py, zbytek ukáže v UI."""
        if request.get("subtype") != "can_use_tool":
            self._reply(live, approvals.error_response(request_id, "Backend asistenta tento dotaz neobsluhuje."))
            return
        tool = request.get("tool_name") if isinstance(request.get("tool_name"), str) else ""
        tool_input = request.get("input") if isinstance(request.get("input"), dict) else {}
        kind, data = approvals.classify(request)
        if kind == "auto_allow":  # čtení skillu a graphify: bez UI, bez záznamu (krok už je v tool_use)
            self._reply(live, approvals.response(request_id, "allow", tool_input))
            return
        approval_id = uuid.uuid4().hex
        log = self._log(session_id)
        if kind == "auto_deny":
            log.append({"type": "approval", "approvalId": approval_id, "tool": tool, "auto": True,
                        "input": {"summary": tool_summary(tool, tool_input)}, "reason": data})
            self._reply(live, approvals.response(request_id, "deny", tool_input, data))
            self._approvals.mark_resolved(approval_id, session_id)
            log.append({"type": "approval_resolved", "approvalId": approval_id, "decision": "deny", "auto": True})
            return
        self._approvals.add(Pending(approval_id, session_id, request_id, tool_input, self._clock(), tool))
        self.registry.update(session_id, state="waiting_approval")
        log.append({"type": "status", "state": "waiting_approval"})
        log.append({"type": "approval", "approvalId": approval_id, "tool": tool, "input": data,
                    "reason": approvals.reason_of(request)})

    def _resolve(self, entry, decision, note=None, **flags):
        """Pošle `control_response` a zapíše `approval_resolved`; bez další žádosti session zase běží."""
        sid = entry.session_id
        live = self._live.get(sid)
        if live is not None:
            self._reply(live, approvals.response(entry.request_id, decision, entry.tool_input, note))
        event = {"type": "approval_resolved", "approvalId": entry.approval_id, "decision": decision, **flags}
        if note:
            event["note"] = note
        self._log(sid).append(event)
        if live is not None and live.turn_started is not None and not self._approvals.has_pending(sid):
            self.registry.update(sid, state="running")
            self._log(sid).append({"type": "status", "state": "running"})

    def _drop_approvals(self, session_id):
        for entry in self._approvals.drop_session(session_id):
            self._log(session_id).append({"type": "approval_resolved", "approvalId": entry.approval_id,
                                          "decision": "deny", "auto": True})

    def approval_session(self, approval_id):
        with self._lock:
            return self._approvals.session_of(approval_id)

    def decide(self, session_id, approval_id, decision, note=None):
        """Rozhodnutí člověka: allow pošle původní input, deny poznámku. Dvojí rozhodnutí = 409."""
        if decision not in DECISIONS:
            raise ValueError("Rozhodnutí je allow nebo deny.")
        if note is not None and (not isinstance(note, str) or len(note) > NOTE_LIMIT):
            raise ValueError(f"Poznámka je text do {NOTE_LIMIT} znaků.")
        note = note.strip() if isinstance(note, str) and note.strip() else None
        with self._lock:
            self._record(session_id)
            entry = self._approvals.take(approval_id, session_id)
            self._resolve(entry, decision, note)
        return {"approvalId": approval_id, "decision": decision, "session": self.session(session_id)}

    def decide_approval(self, approval_id, decision, note=None):
        """Endpoint zná jen id žádosti: session se dohledá v knize schválení."""
        return self.decide(self.approval_session(approval_id), approval_id, decision, note)

    def stop(self, session_id):
        with self._lock:
            self._record(session_id)
            live = self._detach(session_id)
        if live is not None:
            live.process.kill()
            with self._lock:
                if live.turn_started is not None:
                    self._end_turn(session_id)
        return self.session(session_id)

    def close(self, session_id):
        self.stop(session_id)
        with self._lock:
            self.registry.update(session_id, state="closed")
            self._log(session_id).append({"type": "status", "state": "closed"})
        return self.session(session_id)

    # --- limity a vypnutí ---------------------------------------------------------------
    def sweep(self):
        with self._lock:
            timing = {sid: (live.turn_started, live.last_activity) for sid, live in self._live.items()}
            for entry in self._approvals.expired(self._clock(), self.limits.approval_seconds):
                self._resolve(entry, "deny", approvals.TIMEOUT_MESSAGE, auto=True, timeout=True)
            victims = [(sid, self._detach(sid), overdue) for sid, overdue in expired(timing, self._clock(), self.limits)]
        for sid, live, overdue in victims:
            live.process.kill()
            if overdue:
                with self._lock:
                    minutes = round(self.limits.turn_seconds / 60)
                    self._end_turn(sid, f"Tah překročil limit {minutes} minut; proces byl ukončen.")
        return len(victims)

    def close_all(self):
        self._watchdog.stop()
        with self._lock:
            lives = [(sid, self._detach(sid)) for sid in list(self._live)]
        for sid, live in lives:
            live.process.kill()
            record = self.registry.get(sid)
            if record and record["state"] in ("running", "waiting_approval"):
                self.registry.update(sid, state="idle")
