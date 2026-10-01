"""Confirmed, per-workspace VS Code Hook settings installer."""

import hashlib
import json
import os
import uuid
from copy import deepcopy
from pathlib import Path

from backend.project.workspace.workspace_sources import reparse

EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop")

class VscodeHookInstaller:
    """Uses only the public binding supplied by the injected lookup callback."""
    def __init__(self, service, binding_lookup):
        self.service, self.binding_lookup = service, binding_lookup
    def status(self, binding_id):
        binding, _, target = self._scope(binding_id)
        self._source(binding)
        existing = self._decode(self._read_bytes(target))
        installed = self._installed(existing, self._command(binding))
        return self._public(binding, target, self._digest(target), installed, self._can_install(binding),
                            "Instalace mění pouze tento workspace; účinnost potvrdí až nativní Hook událost.")
    def apply(self, binding_id, expected_revision, expected_digest, action, confirmed):
        if type(expected_revision) is not int or action not in {"install", "remove"} or confirmed is not True:
            raise ValueError("VS Code Hook vyžaduje úplné explicitní potvrzení.")
        if expected_digest is not None and (not isinstance(expected_digest, str) or len(expected_digest) != 64):
            raise ValueError("Neplatný digest nastavení.")
        binding, _, target = self._scope(binding_id)
        if binding["revision"] != expected_revision:
            raise ValueError("Hook binding se změnil v jiném okně. Obnovte jej.")
        if action == "install" and not self._can_install(binding):
            raise ValueError("Hook nelze instalovat do tohoto workspace.")
        before = self._read_bytes(target)
        if self._hash(before) != expected_digest:
            raise ValueError("Nastavení se změnilo v jiném okně. Obnovte je.")
        settings = self._decode(before)
        source = self._source(binding)
        command = self._command(binding)
        updated = self._merge(settings, source, command, action)
        if updated == settings:
            return {**self._public(binding, target, self._hash(before), self._installed(settings, command), self._can_install(binding),
                                    "Nastavení už odpovídá potvrzenému Hooku."), "backupCreated": False}
        encoded = json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self._backup(before)
        if self._read_bytes(target) != before:
            raise ValueError("Nastavení se změnilo před uložením; nic nebylo přepsáno.")
        self._replace(target, encoded)
        return {**self._public(binding, target, self._hash(encoded), self._installed(updated, command), self._can_install(binding),
                                "Nastavení bylo změněno; účinnost potvrdí až nativní Hook událost."), "backupCreated": True}
    def _scope(self, binding_id):
        binding = self.binding_lookup(binding_id)
        required = ("id", "project", "workspace", "nodeId", "sessionId", "revision", "state", "settingsPath", "launchCommand")
        if not isinstance(binding, dict) or binding.get("id") != binding_id or any(not binding.get(key) for key in required):
            raise ValueError("Hook binding není dostupný.")
        if type(binding["revision"]) is not int or any(not isinstance(binding[key], str) or "\x00" in binding[key]
                                                        for key in required if key != "revision"):
            raise ValueError("Hook binding není bezpečný.")
        if binding["state"] not in {"active", "paused", "stopped"}:
            raise ValueError("Hook binding není bezpečný.")
        try:
            uuid.UUID(binding["sessionId"])
        except ValueError as exc:
            raise ValueError("Hook binding není bezpečný.") from exc
        root_value = self.service.workspace_sources.root(binding["project"], binding["workspace"])
        if root_value is None:
            raise ValueError("Projekt nemá připojený workspace.")
        root = Path(root_value)
        if not root.is_dir() or reparse(root):
            raise ValueError("Připojený workspace není bezpečný.")
        root = root.resolve()
        claude = root / ".claude"
        if claude.exists() and reparse(claude):
            raise ValueError("Adresář .claude nesmí být odkaz nebo junction.")
        target = claude / "settings.local.json"
        if target.exists() and reparse(target):
            raise ValueError("Nastavení nesmí být odkaz nebo junction.")
        if not target.resolve(strict=False).is_relative_to(root):
            raise ValueError("Cesta nastavení opouští workspace.")
        return binding, root, target
    def _source(self, binding):
        private = (Path(self.service.root) / "agent-control" / "settings").resolve()
        source = Path(binding["settingsPath"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise ValueError("Privátní export Hooku není dostupný.") from exc
        if reparse(source) or not resolved.is_relative_to(private) or reparse(resolved) or not resolved.is_file():
            raise ValueError("Export Hooku není v privátním agent-control/settings.")
        data = self._decode(self._limited_bytes(resolved))
        if set(data) - {"hooks", "permissions"} or not isinstance(data.get("hooks"), dict):
            raise ValueError("Export Hooku má neznámou strukturu.")
        command = binding["launchCommand"]
        for event in EVENTS:
            rules = data["hooks"].get(event)
            if not isinstance(rules, list) or not rules:
                raise ValueError("Export Hooku neobsahuje ověřenou událost.")
            for rule in rules:
                if not self._rule(rule, command) or any(not isinstance(hook, dict) or hook.get("type") != "command" or hook.get("command") != command
                                                   for hook in rule["hooks"]):
                    raise ValueError("Export Hooku obsahuje neověřený command.")
        permissions = data.get("permissions")
        if permissions is not None and (not isinstance(permissions, dict) or set(permissions) - {"allow"}
                                        or not isinstance(permissions.get("allow", []), list)
                                        or any(item != f"Bash({command})" for item in permissions.get("allow", []))):
            raise ValueError("Export Hooku obsahuje nepovolené oprávnění.")
        return data
    @staticmethod
    def _rule(rule, command):
        return isinstance(rule, dict) and isinstance(rule.get("matcher"), str) and isinstance(rule.get("hooks"), list) and any(
            isinstance(hook, dict) and hook.get("type") == "command" and hook.get("command") == command for hook in rule["hooks"])
    @staticmethod
    def _command(binding):
        command, session = binding["launchCommand"], binding["sessionId"]
        if len(command) > 4096 or any(char in command for char in "\x00\r\n") or "--only-session" in command:
            raise ValueError("Exportovaný Hook command není bezpečný.")
        return f"{command} --only-session {session}"
    def _merge(self, settings, source, command, action):
        result = deepcopy(settings)
        hooks = result.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("Nastavení hooks nemá očekávanou strukturu.")  # noqa: TRY004
        own = {"matcher": ".*", "hooks": [{"type": "command", "command": command}]}
        for event in EVENTS:
            rules = hooks.setdefault(event, [])
            if not isinstance(rules, list) or any(not isinstance(rule, dict) for rule in rules):
                raise ValueError("Nastavení hooks nemá očekávanou strukturu.")
            if action == "install" and own not in rules:
                rules.append(own)
            elif action == "remove":
                hooks[event] = [rule for rule in rules if rule != own]
        self._permissions(result, source, command, action)
        return result
    @staticmethod
    def _permissions(settings, source, command, action):
        permission = f"Bash({command})"
        if not source.get("permissions", {}).get("allow"):
            return
        permissions = settings.setdefault("permissions", {})
        if not isinstance(permissions, dict) or not isinstance(permissions.setdefault("allow", []), list):
            raise ValueError("Nastavení permissions nemá očekávanou strukturu.")  # noqa: TRY004
        if action == "install" and permission not in permissions["allow"]:
            permissions["allow"].append(permission)
        if action == "remove":
            permissions["allow"] = [item for item in permissions["allow"] if item != permission]
    @staticmethod
    def _installed(settings, command):
        hooks = settings.get("hooks", {}) if isinstance(settings, dict) else {}
        own = {"matcher": ".*", "hooks": [{"type": "command", "command": command}]}
        return isinstance(hooks, dict) and all(own in hooks.get(event, []) for event in EVENTS)
    def _can_install(self, binding):
        return binding["state"] != "stopped" and not bool(self.service.view(binding["project"], binding["workspace"]).get("readOnly"))
    @staticmethod
    def _decode(raw):
        if raw is None:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Nastavení JSON nelze bezpečně sloučit.") from exc
        if not isinstance(value, dict):
            raise ValueError("Nastavení JSON musí být objekt.")  # noqa: TRY004
        return value
    @staticmethod
    def _hash(raw):
        return hashlib.sha256(raw).hexdigest() if raw is not None else None
    def _digest(self, target):
        return self._hash(self._read_bytes(target))
    @staticmethod
    def _read_bytes(target):
        return target.read_bytes() if target.exists() else None
    @staticmethod
    def _limited_bytes(path):
        data = path.read_bytes()
        if len(data) > 524288:
            raise ValueError("Export Hooku je příliš velký.")
        return data
    def _backup(self, raw):
        directory = Path(self.service.root) / "agent-installation" / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        backup = directory / f"vscode-{uuid.uuid4().hex}.json"
        backup.write_bytes(raw or b"")
    @staticmethod
    def _replace(target, data):
        target.parent.mkdir(exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
    @staticmethod
    def _public(binding, target, digest, installed, can_install, detail):
        return {"bindingId": binding["id"], "sessionId": binding["sessionId"], "project": binding["project"], "workspace": binding["workspace"],
                "nodeId": binding["nodeId"], "installed": installed, "settingsPath": str(target), "settingsDigest": digest,
                "canInstall": can_install, "detail": detail}
