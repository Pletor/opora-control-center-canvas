"""Context pakety pro LLM: sourcovaný, ověřitelný výřez stejného grafu/deníku/zadání/textu.

Žádná paralelní autorita nad daty. Paket čerpá výhradně z existujícího CanvasService
(graf, NodeSpecStore, NodeTextStore, NodeJournal) a je uložen jako immutable snapshot
s digestem zdrojů, aby šlo později ověřit, že zdroje zůstaly beze změny (validate).
"""
import json
import re
import uuid

from backend.domain.graph.graph import digest, encode, valid_id
from backend.domain.node.node_journal import NodeJournal, valid_day
from backend.domain.service import now

MAX_NEIGHBORS = 20
MAX_JOURNAL_DAYS = 31
MIN_BUDGET_BYTES = 1000
MAX_BUDGET_BYTES = 500000

REQUIRED_KEYS = {"project", "workspace", "node", "includeNodeIds", "includeJournalDays", "maxBytes"}

REDACTED = "[REDACTED]"

# Minimální, samostatný redaktor známých vzorů tajemství. Tvary tokenů drží krok
# s `agent_sources._SECRET_TEXT` (zejména fine-grained `github_pat_`), ale zůstává
# samostatný: paket redakuje jen text, ne klíče, takže záměrné číselné čítače
# (např. cache_read_tokens) tudy vůbec neprocházejí.
_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"github_pat_[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.]{10,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|password|passwd|access[_-]?key|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+_.\-]{8,}['\"]?"
    ),
]


def redact_text(value):
    """Nahradí známé vzory tajemství v netroubém uživatelském textu, beze změny délky sémantiky."""
    if not isinstance(value, str) or not value:
        return value
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def _byte_len(value):
    """Skutečná velikost v bajtech UTF-8 kanonického JSON, ne odhad podle znaků."""
    return len(encode(value).encode("utf-8"))


def validate_build_request(payload):
    if not isinstance(payload, dict) or set(payload) != REQUIRED_KEYS:
        raise ValueError("Neplatný formát požadavku na kontextový paket.")
    project, workspace, node = payload["project"], payload["workspace"], payload["node"]
    if not valid_id(project) or not valid_id(workspace) or not valid_id(node):
        raise ValueError("Neplatný identifikátor rozsahu (projekt/pracovní prostor/uzel).")
    include_nodes = payload["includeNodeIds"]
    if (
        not isinstance(include_nodes, list)
        or len(include_nodes) > MAX_NEIGHBORS
        or not all(isinstance(x, str) and valid_id(x) for x in include_nodes)
    ):
        raise ValueError(f"Neplatný výběr dalších uzlů; nejvýše {MAX_NEIGHBORS} platných ID.")
    include_days = payload["includeJournalDays"]
    if (
        not isinstance(include_days, list)
        or len(include_days) > MAX_JOURNAL_DAYS
        or not all(valid_day(x) for x in include_days)
    ):
        raise ValueError(f"Neplatný výběr dnů deníku; nejvýše {MAX_JOURNAL_DAYS} platných dat YYYY-MM-DD.")
    max_bytes = payload["maxBytes"]
    if type(max_bytes) is not int or not (MIN_BUDGET_BYTES <= max_bytes <= MAX_BUDGET_BYTES):
        raise ValueError(f"Neplatný limit velikosti paketu v bajtech ({MIN_BUDGET_BYTES}–{MAX_BUDGET_BYTES}).")
    return payload


class ContextPackets:
    def __init__(self, canvas):
        self.canvas = canvas
        self.journal = NodeJournal(canvas)
        canvas.db.execute(
            """CREATE TABLE IF NOT EXISTS context_packets(
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
            digest TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)"""
        )
        canvas.db.commit()

    def build(self, payload):
        validate_build_request(payload)
        project, workspace, node = payload["project"], payload["workspace"], payload["node"]
        max_bytes = payload["maxBytes"]
        with self.canvas.graph_lock:
            view = self.canvas.view(project, workspace)
            if view["readOnly"]:
                raise ValueError(
                    "Sestavení kontextového paketu z pouze-pro-čtení mainu není podporováno; použijte pracovní prostor."
                )
            graph = view["graph"]
            by_id = {n["id"]: n for n in graph["nodes"]}
            if node not in by_id:
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            with self.canvas.lock:
                return self._persist(self._assemble(project, workspace, node, by_id, view, payload, max_bytes))

    def _assemble(self, project, workspace, node, by_id, view, payload, max_bytes):
        source_refs = [{"kind": "graph", "digest": view["digest"]}]
        included, excluded, truncated = [], [], []

        def summary(nid):
            n = by_id[nid]
            return {
                "nodeId": n["id"],
                "name": redact_text(n["name"]),
                "kind": n["kind"],
                "purpose": redact_text(n["purpose"]),
                "parentId": n["parentId"],
            }

        spec_scope = (project, workspace, node)
        spec_data = self.canvas.specs.read(spec_scope)
        text_data = self.canvas.texts.read(spec_scope)
        source_refs.append(
            {"kind": "spec", "nodeId": node, "revision": spec_data["revision"], "digest": digest(spec_data["fields"])}
        )
        source_refs.append(
            {"kind": "text", "nodeId": node, "revision": text_data["revision"], "digest": digest(text_data["text"])}
        )
        focus = {
            **summary(node),
            "spec": {"revision": spec_data["revision"], "fields": {k: redact_text(v) for k, v in spec_data["fields"].items()}},
            "text": {"revision": text_data["revision"], "text": redact_text(text_data["text"])},
        }
        included.append({"kind": "focus", "nodeId": node})
        content = {"focus": focus, "neighbors": [], "journal": []}
        if _byte_len(content) > max_bytes:
            raise ValueError(
                "Zadání a text vlastního uzlu přesahují požadovaný limit bajtů; zvyšte maxBytes nebo zkraťte obsah uzlu."
            )

        seen_neighbors = set()
        for nid in payload["includeNodeIds"]:
            if nid == node:
                excluded.append({"kind": "neighbor", "nodeId": nid, "reason": "same_as_focus"})
                continue
            if nid in seen_neighbors:
                excluded.append({"kind": "neighbor", "nodeId": nid, "reason": "duplicate"})
                continue
            seen_neighbors.add(nid)
            if nid not in by_id:
                excluded.append({"kind": "neighbor", "nodeId": nid, "reason": "not_found"})
                continue
            n_scope = (project, workspace, nid)
            n_spec = self.canvas.specs.read(n_scope)
            n_text = self.canvas.texts.read(n_scope)
            candidate = {
                **summary(nid),
                "spec": {"revision": n_spec["revision"], "fields": {k: redact_text(v) for k, v in n_spec["fields"].items()}},
                "text": {"revision": n_text["revision"], "text": redact_text(n_text["text"])},
            }
            content["neighbors"].append(candidate)
            if _byte_len(content) > max_bytes:
                content["neighbors"].pop()
                truncated.append({"kind": "neighbor", "nodeId": nid, "reason": "max_bytes_exceeded"})
            else:
                included.append({"kind": "neighbor", "nodeId": nid})
                source_refs.append(
                    {"kind": "spec", "nodeId": nid, "revision": n_spec["revision"], "digest": digest(n_spec["fields"])}
                )
                source_refs.append(
                    {"kind": "text", "nodeId": nid, "revision": n_text["revision"], "digest": digest(n_text["text"])}
                )

        seen_days = set()
        for day in payload["includeJournalDays"]:
            if day in seen_days:
                excluded.append({"kind": "journal", "nodeId": node, "day": day, "reason": "duplicate"})
                continue
            seen_days.add(day)
            j_scope = (project, workspace, node, day)
            j_data = self.journal.read(j_scope)
            candidate = {"day": day, "revision": j_data["revision"], "text": redact_text(j_data["text"])}
            content["journal"].append(candidate)
            if _byte_len(content) > max_bytes:
                content["journal"].pop()
                truncated.append({"kind": "journal", "nodeId": node, "day": day, "reason": "max_bytes_exceeded"})
            else:
                included.append({"kind": "journal", "nodeId": node, "day": day})
                source_refs.append(
                    {
                        "kind": "journal",
                        "nodeId": node,
                        "day": day,
                        "revision": j_data["revision"],
                        "digest": digest(j_data["text"]),
                    }
                )

        content["journal"].sort(key=lambda item: item["day"])
        return {
            "scope": {"project": project, "workspace": workspace, "node": node},
            "maxBytes": max_bytes,
            "sizeBytes": _byte_len(content),
            "content": content,
            "included": included,
            "excluded": excluded,
            "truncated": truncated,
            "sourceRefs": source_refs,
        }

    def _persist(self, packet):
        packet_digest = digest(
            {key: packet[key] for key in ("scope", "maxBytes", "content", "included", "excluded", "truncated", "sourceRefs")}
        )
        packet_id = uuid.uuid4().hex
        created_at = now()
        stored = {**packet, "id": packet_id, "digest": packet_digest, "createdAt": created_at}
        self.canvas.db.execute(
            "INSERT INTO context_packets VALUES(?,?,?,?,?,?,?)",
            (
                packet_id,
                stored["scope"]["project"],
                stored["scope"]["workspace"],
                stored["scope"]["node"],
                packet_digest,
                encode(stored),
                created_at,
            ),
        )
        self.canvas.db.commit()
        return stored

    def load(self, packet_id):
        if not valid_id(packet_id):
            raise ValueError("Neplatné ID kontextového paketu.")
        with self.canvas.lock:
            row = self.canvas.db.execute(
                "SELECT payload FROM context_packets WHERE id=?", (packet_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Kontextový paket nebyl nalezen.")
        return json.loads(row["payload"])

    def validate(self, packet_id):
        """Porovná uložené digesty zdrojů s aktuálním stavem; nikdy nepřepisuje starý snapshot."""
        stored = self.load(packet_id)
        scope = stored["scope"]
        project, workspace = scope["project"], scope["workspace"]
        with self.canvas.graph_lock:
            try:
                view = self.canvas.view(project, workspace)
            except ValueError:
                return {
                    "id": packet_id,
                    "digest": stored["digest"],
                    "stale": True,
                    "changes": [{"kind": "scope", "reason": "project_or_workspace_missing"}],
                }
            with self.canvas.lock:
                changes = []
                for ref in stored["sourceRefs"]:
                    if ref["kind"] == "graph":
                        if view["digest"] != ref["digest"]:
                            changes.append({"kind": "graph", "reason": "graph_changed"})
                    elif ref["kind"] == "spec":
                        current = self.canvas.specs.read((project, workspace, ref["nodeId"]))
                        if digest(current["fields"]) != ref["digest"]:
                            changes.append({"kind": "spec", "nodeId": ref["nodeId"], "reason": "spec_changed"})
                    elif ref["kind"] == "text":
                        current = self.canvas.texts.read((project, workspace, ref["nodeId"]))
                        if digest(current["text"]) != ref["digest"]:
                            changes.append({"kind": "text", "nodeId": ref["nodeId"], "reason": "text_changed"})
                    elif ref["kind"] == "journal":
                        current = self.journal.read((project, workspace, ref["nodeId"], ref["day"]))
                        if digest(current["text"]) != ref["digest"]:
                            changes.append(
                                {"kind": "journal", "nodeId": ref["nodeId"], "day": ref["day"], "reason": "journal_changed"}
                            )
        return {"id": packet_id, "digest": stored["digest"], "stale": len(changes) > 0, "changes": changes}
