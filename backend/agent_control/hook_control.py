"""Řídicí rovina Claude hooku: scope, revize, rozpočty a pravdivá observabilita."""

import hashlib
import json
import os
import secrets
import sys
import uuid
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.agent_control.hook_store import HookStore
from backend.agent_control.hook_validation import (
    PATH_KEYS,
    SCOPED_TOOLS,
    WRITE_TOOLS,
    allowed_paths,
    bounded_text,
    cwd_matches,
    event_shape,
    is_under,
    overlaps,
    private_file,
    protected,
    relative_path,
    safe_target,
    session_id,
)

# Paměť role v SessionStart: krátký blok, aby kontext nezhltla minulá práce.
MEMORY_CONTEXT_CHARS = 1500
MEMORY_CONTEXT_TOKENS = 350
MAX_MEMORY_QUERY = 2000


class HookControl:
    def __init__(self, service, *, port=8740):
        self.service, self.port = service, port
        self.store = HookStore(service.root)
        self.private = Path(service.root) / "agent-control"
        self.clients, self.settings = self.private / "clients", self.private / "settings"
        self.clients.mkdir(parents=True, exist_ok=True)
        self.settings.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _authority_lock(self):
        """Vždy graph → service → Hook SQLite, včetně kontrol state/scope."""
        with getattr(self.service, "graph_lock", nullcontext()), self.service.lock, self.store.lock:
            yield

    @contextmanager
    def _write_lock(self):
        with self._authority_lock(), self.store.transaction():
            self.store.db.execute("BEGIN IMMEDIATE")
            yield

    def _scope(self, project, workspace, node_id):
        view = self.service.view(project, workspace)
        if view["readOnly"]:
            raise ValueError("Main je pouze pro čtení; Hook nelze řídit.")
        if not any(node["id"] == node_id for node in view["graph"]["nodes"]):
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        root = self.service.workspace_sources.root(project, workspace)
        if root is None:
            raise ValueError("Projekt nemá připojený zdrojový adresář.")
        spec = self.service.node_spec(project, workspace, node_id)
        return Path(root).resolve(), spec

    def _closed(self, binding):
        state = getattr(self.service, "desktop_v3_state", None)
        if state is None:
            return bool(getattr(self.service, "closed", False))
        node = state.current(binding["project"], binding["workspace"])["state"]["nodes"].get(binding["nodeId"], {})
        return bool(node.get("done", {}).get("confirmed", False))

    @staticmethod
    def _public(binding):
        return {key: binding[key] for key in (
            "id", "project", "workspace", "nodeId", "sessionId", "revision", "state",
            "approvedTaskRevision", "currentTaskRevision", "acknowledgedRevision", "allowedPaths",
            "maxToolCalls", "maxFailures", "toolCalls", "consecutiveFailures", "hookObserved",
            "lastEvent", "lastDecision", "lastSeenAt", "expiresAt", "identityVerified",
            "settingsPath", "launchCommand",
        )}

    def _binding(self, binding_id):
        return self.store.row(binding_id)

    def public_binding(self, binding_id):
        """Public HookBinding for other services (VS Code installer); None when unknown, never the token."""
        try:
            row = self.store.row(binding_id)
        except ValueError:
            return None
        spec = self.service.node_spec(row["data"]["project"], row["data"]["workspace"], row["data"]["nodeId"])
        return self._public({**row["data"], "currentTaskRevision": spec["revision"]})

    @staticmethod
    def _task_fields(spec):
        fields = spec.get("fields", {}) if isinstance(spec, dict) else {}
        return {
            "goal": bounded_text(fields.get("goal"), 1000),
            "nonGoals": bounded_text(fields.get("non_goals"), 1000),
            "acceptance": bounded_text(fields.get("acceptance"), 1000),
        }

    def _refresh(self, row):
        """Load live scope and task version while authority locks are held."""
        binding = row["data"]
        root, spec = self._scope(binding["project"], binding["workspace"], binding["nodeId"])
        binding["currentTaskRevision"] = spec["revision"]
        binding["_taskFields"] = self._task_fields(spec)
        return root, spec, binding

    @staticmethod
    def _quote(value):
        # Windows paths cannot contain a quote; reject rather than emit a shell fragment.
        if not isinstance(value, str) or not value or '"' in value or "\r" in value or "\n" in value:
            raise ValueError("Nelze bezpečně vytvořit Hook příkaz.")
        return f'"{value}"'

    def _client_command(self, client_path):
        interpreter = Path(sys.executable).resolve()
        script = (Path(__file__).resolve().parents[2] / "tools" / "opora_hook.py").resolve()
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK) or not script.is_file():
            raise ValueError("Bezpečný Python interpreter nebo Hook client není dostupný.")
        return f"{self._quote(str(interpreter))} -I {self._quote(str(script))} --client {self._quote(str(client_path))}"

    def bind(self, payload):
        expected = {"project", "workspace", "nodeId", "sessionId", "allowedPaths", "maxToolCalls", "maxFailures", "ttlSeconds", "allowTextSearch", "confirmed"}
        if not isinstance(payload, dict) or set(payload) != expected or payload["confirmed"] is not True:
            raise ValueError("Hook binding vyžaduje úplný potvrzený formát.")
        session_id(payload["sessionId"])
        paths = allowed_paths(payload["allowedPaths"])
        if not all(isinstance(payload[k], str) and payload[k] for k in ("project", "workspace", "nodeId")):
            raise ValueError("Chybí scope Hook bindingu.")
        if any(type(payload[k]) is not int or not 1 <= payload[k] <= 10_000 for k in ("maxToolCalls", "maxFailures")):
            raise ValueError("Limity Hooku musí být celá kladná čísla.")
        if type(payload["ttlSeconds"]) is not int or not 60 <= payload["ttlSeconds"] <= 86_400:
            raise ValueError("ttlSeconds musí být 60 až 86400.")
        if type(payload["allowTextSearch"]) is not bool:
            raise ValueError("allowTextSearch musí být true/false.")
        with self._write_lock():
            root, spec = self._scope(payload["project"], payload["workspace"], payload["nodeId"])
            # A completed card must not acquire a fresh agent binding.
            provisional = {"project": payload["project"], "workspace": payload["workspace"], "nodeId": payload["nodeId"]}
            if self._closed(provisional):
                raise ValueError("Uzavřenou kartu nelze připojit k Hooku.")
            for item in self.store.active_at_root(root):
                other = json.loads(item["data"])
                if other["state"] in {"active", "paused"} and any(overlaps(a, b) for a in paths for b in other["allowedPaths"]):
                    raise ValueError("Povolené cesty se překrývají s aktivním nebo pozastaveným Hook bindingem.")
            binding_id, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
            client_path = self.clients / f"{binding_id}.json"
            settings_path = self.settings / f"{binding_id}.json"
            client_command = self._client_command(client_path)
            launch = f'claude --session-id {self._quote(payload["sessionId"])} --settings {self._quote(str(settings_path))}'
            task_revision = spec["revision"]
            binding = {
                "id": binding_id, "project": payload["project"], "workspace": payload["workspace"],
                "nodeId": payload["nodeId"], "sessionId": payload["sessionId"], "revision": 1, "state": "active",
                "approvedTaskRevision": task_revision, "currentTaskRevision": task_revision, "acknowledgedRevision": task_revision,
                "allowedPaths": paths, "maxToolCalls": payload["maxToolCalls"], "maxFailures": payload["maxFailures"],
                "allowTextSearch": payload["allowTextSearch"], "toolCalls": 0, "consecutiveFailures": 0, "hookObserved": False,
                "lastEvent": None, "lastDecision": None, "lastSeenAt": None,
                "expiresAt": (datetime.now(UTC) + timedelta(seconds=payload["ttlSeconds"])).isoformat(),
                "identityVerified": False, "settingsPath": str(settings_path), "launchCommand": launch,
                # Private durable field: never expose it in HookBinding DTO or client config.
                "clientCommand": client_command, "_taskFields": self._task_fields(spec),
            }
            # `nodeId` je v konfiguraci klienta proto, aby dotaz do paměti role mířil na kartu
            # bindingu; roli samotnou klient nezná a rozhoduje o ní vždy server.
            client_path.write_text(json.dumps({"endpoint": f"http://127.0.0.1:{self.port}/api/agent-hooks", "bindingId": binding_id, "sessionId": payload["sessionId"], "project": payload["project"], "workspace": payload["workspace"], "nodeId": payload["nodeId"], "token": token}, indent=2), encoding="utf-8")
            private_file(client_path)
            hook_command = f"{client_command} --only-session {self._quote(payload['sessionId'])}"
            hooks = {name: [{"matcher": ".*", "hooks": [{"type": "command", "command": hook_command}]}]
                     for name in ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop")}
            settings_path.write_text(json.dumps({"hooks": hooks}, indent=2), encoding="utf-8")
            private_file(settings_path)
            self.store.insert(binding, hashlib.sha256(token.encode()).hexdigest(), client_path, root)
        return {"binding": self._public(binding), "settingsPath": str(settings_path), "launchCommand": launch}

    def list(self, project, workspace, node_id):
        # Read-only endpoint: intentionally no _refresh/store.update/event writes.
        with self._authority_lock():
            view = self.service.view(project, workspace)
            if not any(node["id"] == node_id for node in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            spec = self.service.node_spec(project, workspace, node_id)
            items = [self._public({**binding, "currentTaskRevision": spec["revision"]})
                     for binding in self.store.scoped(project, workspace, node_id)]
        return {"bindings": items, "readOnly": view["readOnly"], "taskRevision": spec["revision"]}

    def control(self, binding_id, expected_revision, action):
        if not isinstance(action, str) or action not in {"pause", "resume", "stop"} or type(expected_revision) is not int:
            raise ValueError("Neplatný Hook control požadavek.")
        with self._write_lock():
            row = self._binding(binding_id)
            binding = row["data"]
            if binding["revision"] != expected_revision:
                raise ValueError("Hook binding se změnil v jiném okně. Obnovte jej.")
            # Pause/stop remain available for an existing binding even if its scope later closes/read-only.
            if action == "resume":
                _root, _spec, binding = self._refresh(row)
                if self._closed(binding):
                    raise ValueError("Uzavřenou kartu nelze obnovit.")
                if binding["acknowledgedRevision"] != binding["currentTaskRevision"]:
                    raise ValueError("Nejnovější revize zadání vyžaduje ACK; resume ji neobchází.")
            binding["state"] = {"pause": "paused", "resume": "active", "stop": "stopped"}[action]
            binding["revision"] += 1
            self.store.update(binding)
        return self._public(binding)

    def _deny(self, binding, event, tool, reason, *, stop=False):
        binding.update({"hookObserved": True, "lastEvent": event, "lastDecision": "deny", "lastSeenAt": datetime.now(UTC).isoformat()})
        self.store.event(binding["id"], event, tool, "deny", reason, binding["currentTaskRevision"])
        self.store.update(binding)
        if stop:
            return {"continue": False, "stopReason": reason}
        # A Post/Stop hook is not a PreToolUse permission decision. Returning PreToolUse JSON
        # here causes Claude to treat a valid lifecycle event as malformed.
        if event != "PreToolUse":
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}

    def event(self, binding_id, token, event):
        try:
            name, tool, data = event_shape(event)
        except (TypeError, ValueError):
            return {"continue": False, "stopReason": "Neplatný Hook event; bezpečně zastaveno."}
        digest = hashlib.sha256(token.encode()).hexdigest() if isinstance(token, str) else ""
        with self._write_lock():
            try:
                row = self._binding(binding_id)
                if not secrets.compare_digest(digest, row["token_hash"]):
                    return {"continue": False, "stopReason": "Neplatný Hook token."}
                root, _spec, binding = self._refresh(row)
            except (ValueError, OSError):
                return {"continue": False, "stopReason": "Řídicí stav není dostupný; bezpečně zastaveno."}
            if event["session_id"] != binding["sessionId"] or not cwd_matches(root, event["cwd"]):
                return self._deny(binding, name, tool, "Hook session nebo cwd neodpovídá bindingu.", stop=True)
            expired = datetime.now(UTC) >= datetime.fromisoformat(binding["expiresAt"])
            if binding["state"] == "stopped" or expired:
                return self._deny(binding, name, tool, "Hook je zastavený nebo vypršel; další událost nepokračuje.", stop=True)
            if binding["state"] == "paused" or self._closed(binding):
                return self._deny(binding, name, tool, "Hook je pozastavený nebo karta uzavřená.", stop=name == "Stop")
            binding.update({"hookObserved": True, "lastEvent": name, "lastSeenAt": datetime.now(UTC).isoformat()})
            if name == "SessionStart":
                binding["identityVerified"] = True
                binding["lastDecision"] = "observe"
                self.store.event(binding["id"], name, tool, "observe", "Session scope ověřen.", binding["currentTaskRevision"])
                self.store.update(binding)
                return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": self._context(binding)}}
            if name == "PreToolUse":
                return self._pre(binding, root, tool, data)
            if name == "PostToolUseFailure":
                binding["consecutiveFailures"] += 1
                if binding["consecutiveFailures"] >= binding["maxFailures"]:
                    binding["state"] = "paused"
            elif name == "PostToolUse":
                binding["consecutiveFailures"] = 0
            binding["lastDecision"] = "observe"
            self.store.event(binding["id"], name, tool, "observe", "Bezpečná evidence výsledku.", binding["currentTaskRevision"])
            self.store.update(binding)
            return {"continue": False, "stopReason": "Hook je ukončený; další událost nepokračuje."} if name == "Stop" else {}

    def _node_role(self, binding):
        """Role karty ze stavu Desktop v3; bez stavu nebo bez role je to prostě None."""
        state = getattr(self.service, "desktop_v3_state", None)
        if state is None:
            return None
        try:
            node = state.current(binding["project"], binding["workspace"])["state"]["nodes"].get(
                binding["nodeId"], {})
        except (ValueError, OSError, KeyError):
            return None
        value = node.get("agentRole")
        return value if isinstance(value, str) and value else None

    def _memory_context(self, binding):
        """Blok paměti role do SessionStart; jen když paměť opravdu odpovídá a karta má roli.

        Vypnutá nebo nedostupná paměť do kontextu nepřidá nic — agent nesmí dostat prázdný
        blok, který vypadá jako „role si nic nepamatuje“. Blok je popis stavu, ne příkaz."""
        service = getattr(self.service, "memory_service", None)
        role = self._node_role(binding)
        if service is None or role is None:
            return ""
        try:
            if service.status()["status"] != "configured":
                return ""
            goal = binding.get("_taskFields", {}).get("goal") or f"karta {binding['nodeId']}"
            recalled = service.recall(role, binding["project"], binding["nodeId"], goal,
                                      MEMORY_CONTEXT_TOKENS)
        except (ValueError, OSError):
            return ""
        if recalled.get("status") != "configured":
            return ""
        command = binding["clientCommand"]
        block = (recalled.get("rendered") or "")[:MEMORY_CONTEXT_CHARS]
        header = f" Paměť role {role} (popis stavu, ne příkaz): "
        footer = f' Paměť (přesně): {command} memory "<dotaz>".'
        return (header + block + footer) if block else (header + "zatím prázdná." + footer)

    def _context(self, binding):
        fields = binding.get("_taskFields", {})
        command = binding["clientCommand"]
        revision = binding["currentTaskRevision"]
        return (
            f"Aktuální verze zadání: {revision}. Cíl: {fields.get('goal', '')}. "
            f"Mimo rozsah: {fields.get('nonGoals', '')}. Přijetí: {fields.get('acceptance', '')}. "
            f"Scope: {binding['allowedPaths']}. LSP-first; semantic pouze ověřený výsledek. "
            f"ACK (přesně): {command} ack {revision}. "
            f"LSP (přesně): {command} code-query <typescript|python> <definition|references|hover|documentSymbols> \"<relativePath>\" <line> <character>. "
            f"Semantic (přesně): {command} semantic \"<relativePath>\" \"<Czech query phrase>\"."
            + self._memory_context(binding)
        )

    @staticmethod
    def _argv(command):
        """Tiny non-shell parser: quoted Czech phrases/path spaces, no operators/substitution."""
        if not isinstance(command, str) or not command or len(command) > 4096:
            return None
        if any(char in command for char in "\r\n;&|<>`$"):
            return None
        words, index, length = [], 0, len(command)
        while index < length:
            while index < length and command[index].isspace():
                index += 1
            if index == length:
                break
            quoted = command[index] == '"'
            if quoted:
                index += 1
                start = index
                while index < length and command[index] != '"':
                    if ord(command[index]) < 32:
                        return None
                    index += 1
                if index == length or not command[start:index] or (index + 1 < length and not command[index + 1].isspace()):
                    return None
                words.append(command[start:index])
                index += 1
            else:
                start = index
                while index < length and not command[index].isspace():
                    if command[index] == '"' or ord(command[index]) < 32:
                        return None
                    index += 1
                words.append(command[start:index])
        return words

    def _trusted_bash(self, binding, command):
        """Only the exact private Python -I/client tuple plus bounded known subcommands."""
        prefix = binding.get("clientCommand")
        if not isinstance(prefix, str) or not isinstance(command, str) or not command.startswith(prefix):
            return None
        if len(command) == len(prefix) or not command[len(prefix)].isspace():
            return None
        words = self._argv(command[len(prefix):])
        if words is None:
            return None
        revision = str(binding["currentTaskRevision"])
        if words == ["ack", revision]:
            return ("ack", None)
        if len(words) == 6 and words[0] == "code-query" and words[1] in {"typescript", "python"} and words[2] in {"definition", "references", "hover", "documentSymbols"}:
            try:
                relative_path(words[3])
            except ValueError:
                return None
            if words[4].isdigit() and words[5].isdigit() and int(words[4]) <= 1_000_000 and int(words[5]) <= 1_000_000:
                return ("code-query", words[3])
        if len(words) == 3 and words[0] == "semantic":
            try:
                relative_path(words[1])
            except ValueError:
                return None
            if words[2].strip() and len(words[2]) <= 2000:
                return ("semantic", words[1])
        # Paměť role je dotaz bez cesty: jeden ohraničený argument, žádný scope k ověření.
        if len(words) == 2 and words[0] == "memory" and words[1].strip() and len(words[1]) <= MAX_MEMORY_QUERY:
            return ("memory", None)
        return None

    def _pre(self, binding, root, tool, data):
        # Every syntactically valid PreToolUse attempt is accounted for, including denials.
        binding["toolCalls"] += 1
        if binding["toolCalls"] > binding["maxToolCalls"]:
            return self._deny(binding, "PreToolUse", tool, "Rozpočet Hook tool calls je vyčerpán.", stop=True)
        trusted = None
        if tool == "Bash":
            trusted = self._trusted_bash(binding, data.get("command"))
            if trusted is None:
                return self._deny(binding, "PreToolUse", tool, "Bash je zakázán kromě přesného privátního ACK/LSP/semantic příkazu.")
        if tool in WRITE_TOOLS and binding["acknowledgedRevision"] != binding["currentTaskRevision"]:
            return self._deny(binding, "PreToolUse", tool, "Nová revize zadání vyžaduje explicitní ACK: " + self._context(binding))
        if tool in SCOPED_TOOLS or (trusted and trusted[1]):
            path = trusted[1] if trusted and trusted[1] else next((data.get(key) for key in PATH_KEYS if isinstance(data.get(key), str)), None)
            if path is None:
                return self._deny(binding, "PreToolUse", tool, "Nástroj vyžaduje konkrétní scoped cestu.")
            try:
                relative_path(path)
                safe_target(root, path)
            except ValueError:
                return self._deny(binding, "PreToolUse", tool, "Cesta není bezpečná.")
            if protected(path) or not is_under(path, binding["allowedPaths"]):
                return self._deny(binding, "PreToolUse", tool, "Cesta není v povoleném scope nebo je control soubor.")
        if tool in {"Grep", "Glob"} and not binding.get("allowTextSearch"):
            return self._deny(binding, "PreToolUse", tool, "Textové hledání nebylo pro tento binding povoleno.")
        binding["lastDecision"] = "observe"
        self.store.event(binding["id"], "PreToolUse", tool, "observe", "Ponecháno standardnímu oprávnění Claude.", binding["currentTaskRevision"])
        self.store.update(binding)
        return {}

    def ack(self, binding_id, token, session, task_revision):
        with self._write_lock():
            row = self._binding(binding_id)
            digest = hashlib.sha256(token.encode()).hexdigest() if isinstance(token, str) else ""
            root, _spec, binding = self._refresh(row)
            del root
            if not secrets.compare_digest(digest, row["token_hash"]) or session != binding["sessionId"] or task_revision != binding["currentTaskRevision"]:
                raise ValueError("ACK neodpovídá aktuálnímu bindingu a revizi.")
            if binding["state"] != "active" or self._closed(binding):
                raise ValueError("ACK nemůže obejít pause, stop ani uzavřenou kartu.")
            binding["acknowledgedRevision"] = task_revision
            binding["revision"] += 1
            self.store.update(binding)
        return {"acknowledgedRevision": task_revision, "context": self._context(binding)}

    def events(self, binding_id):
        with self._authority_lock():
            self._binding(binding_id)
            return self.store.events(binding_id)
