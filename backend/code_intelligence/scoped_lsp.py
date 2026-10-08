"""Short-lived JSON-RPC LSP sessions constrained to one workspace and file.

The adapter deliberately has no semantic-search implementation.  Graphify remains a
structural map and is not represented as embeddings or a semantic retrieval provider.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from backend.project.workspace.workspace_sources import relative_path, reparse

MAX_OPERATION_SECONDS = 15.0
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_RPC_BYTES = 4 * 1024 * 1024
LAUNCHER_ROOT = Path("C:/Users/Admin/.claude/skills/opory-lsp")
LANGUAGE_EXTENSIONS = {
    "typescript": {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"},
    "python": {".py", ".pyi"},
}
OPERATIONS = {"definition", "references", "hover", "documentSymbols"}
METHODS = {
    "definition": "textDocument/definition",
    "references": "textDocument/references",
    "hover": "textDocument/hover",
    "documentSymbols": "textDocument/documentSymbol",
}


class LspProtocolError(RuntimeError):
    """Controlled protocol/startup failure; callers expose it as unavailable."""


@dataclass(frozen=True)
class QueryRequest:
    project: str
    workspace: str
    language: str
    path: str
    operation: str
    line: int
    character: int


class FramedJsonRpcProtocol:
    """JSON-RPC 2.0 over stdio that accepts notifications and client requests."""

    def __init__(self, language: str, launcher: Path, root: Path, server_cwd: Path):
        del language, root
        env = dict(os.environ)
        # The launchers resolve project dependencies from this directory; rootUri stays scoped.
        env["CLAUDE_PROJECT_DIR"] = str(server_cwd)
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(
                ["node", str(launcher)],
                cwd=str(server_cwd),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=flags,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            raise LspProtocolError("LSP server could not be started.") from exc
        self._incoming: queue.Queue[object] = queue.Queue()
        self._write_lock = threading.Lock()
        self._next_id = 0
        self._closed = False
        self._stderr = bytearray()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        assert self.process.stdout is not None
        try:
            while True:
                frame = self._read_frame(self.process.stdout)
                if frame is None:
                    break
                self._incoming.put(frame)
        except Exception as exc:  # The request waiter turns this into a controlled unavailable state.
            self._incoming.put(exc)
        finally:
            self._incoming.put(None)

    def _read_stderr(self):
        assert self.process.stderr is not None
        while len(self._stderr) < 8192:
            chunk = self.process.stderr.read(min(1024, 8192 - len(self._stderr)))
            if not chunk:
                return
            self._stderr.extend(chunk)

    @staticmethod
    def _read_frame(stream):
        headers: dict[str, str] = {}
        for _ in range(32):
            raw = stream.readline(8193)
            if not raw:
                return None
            if raw in (b"\r\n", b"\n"):
                break
            try:
                name, value = raw.decode("ascii").rstrip("\r\n").split(":", 1)
            except (UnicodeDecodeError, ValueError) as exc:
                raise LspProtocolError("Invalid LSP response framing.") from exc
            headers[name.lower()] = value.strip()
        else:
            raise LspProtocolError("LSP response headers exceed limit.")
        try:
            length = int(headers["content-length"])
        except (KeyError, ValueError) as exc:
            raise LspProtocolError("LSP response misses Content-Length.") from exc
        if not 0 <= length <= MAX_RPC_BYTES:
            raise LspProtocolError("LSP response exceeds limit.")
        body = stream.read(length)
        if len(body) != length:
            raise LspProtocolError("Truncated LSP response.")
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LspProtocolError("Invalid LSP response JSON.") from exc
        if not isinstance(value, dict):
            raise LspProtocolError("Invalid LSP response payload.")
        return value

    def _send(self, message: dict):
        if self._closed or self.process.poll() is not None:
            raise LspProtocolError("LSP server stopped before replying.")
        data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_RPC_BYTES:
            raise LspProtocolError("LSP request exceeds limit.")
        frame = b"Content-Length: " + str(len(data)).encode("ascii") + b"\r\n\r\n" + data
        try:
            assert self.process.stdin is not None
            with self._write_lock:
                self.process.stdin.write(frame)
                self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise LspProtocolError("LSP server stopped before replying.") from exc

    def notify(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method, params, timeout):
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + max(0.01, timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LspProtocolError("LSP request timed out.")
            try:
                message = self._incoming.get(timeout=remaining)
            except queue.Empty as exc:
                raise LspProtocolError("LSP request timed out.") from exc
            if message is None:
                detail = self._stderr.decode("utf-8", "replace").strip()
                raise LspProtocolError("LSP server stopped before replying" + (f": {detail}" if detail else "."))
            if isinstance(message, Exception):
                raise LspProtocolError(str(message)) from message
            if "method" in message and "id" in message:
                self._reply_to_server_request(message)
                continue
            if message.get("id") != request_id:
                # Notifications and stale responses are legal and must not be mistaken for ours.
                continue
            if "error" in message:
                raise LspProtocolError("LSP server returned an error response.")
            return message.get("result")

    def _reply_to_server_request(self, message):
        method = message.get("method")
        params = message.get("params")
        # These standard requests do not widen workspace access.  Unknown requests receive null.
        if method == "workspace/configuration":
            items = params.get("items", []) if isinstance(params, dict) else []
            result = [None for _ in items] if isinstance(items, list) else []
        elif method == "window/showMessageRequest":
            result = None
        else:
            result = None
        self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self.process.stdin:
                self.process.stdin.close()
            self.process.wait(timeout=2.0)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        self._terminate_tree()

    def _terminate_tree(self):
        if self.process.poll() is not None:
            return
        if os.name == "nt":
            # Node launchers fork a server. /T is the fallback guarantee against an orphan child.
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                    check=False,
                )
            except OSError:
                self.process.kill()
        else:
            self.process.kill()
        try:
            self.process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass


class CodeIntelligence:
    """LSP-first adapter. Each query owns and then shuts down one process tree."""

    def __init__(self, root_provider, *, protocol_factory=FramedJsonRpcProtocol, server_cwd=None,
                 node_executable="node", launchers=None, operation_timeout=MAX_OPERATION_SECONDS,
                 semantic_status=None):
        self._root_provider = root_provider
        self._protocol_factory = protocol_factory
        self._server_cwd = Path(server_cwd).resolve() if server_cwd else None
        self._node_executable = node_executable
        self._launchers = launchers or {
            "typescript": LAUNCHER_ROOT / "ts-lsp.mjs",
            "python": LAUNCHER_ROOT / "py-lsp.mjs",
        }
        self._operation_timeout = min(float(operation_timeout), MAX_OPERATION_SECONDS)
        self._semantic_status = semantic_status

    def status(self, project, workspace):
        self._validate_identity(project, workspace)
        providers = []
        node_ready = bool(shutil.which(self._node_executable))
        for language in ("typescript", "python"):
            launcher = self._launchers[language]
            ready = node_ready and launcher.is_file()
            providers.append({
                "language": language,
                "status": "configured" if ready else "unavailable",
                "detail": (
                    f"Configured via Node launcher: {launcher}" if ready
                    else "Node runtime or the fixed Opory LSP launcher is unavailable; no server was started."
                ),
            })
        try:
            semantic = self._semantic_status() if callable(self._semantic_status) else {
                "status": "unavailable",
                "reason": "No semantic retrieval service is implemented; Graphify is structural, not embeddings.",
            }
        except Exception:
            semantic = {"status": "unavailable", "reason": "Semantic provider status is unavailable."}
        if not isinstance(semantic, dict) or semantic.get("status") not in {"configured", "unavailable"} or not isinstance(semantic.get("reason"), str):
            semantic = {"status": "unavailable", "reason": "Semantic provider reported an invalid status."}
        return {
            "providers": providers,
            "semantic": semantic,
            "preference": ["lsp", "semantic", "scoped-text"],
        }

    def query(self, query: QueryRequest):
        self._validate_query(query)  # no root lookup or filesystem access before this boundary
        root = self._validated_root(query.project, query.workspace)
        target = self._validated_target(root, query.path, query.language)
        text = self._read_and_validate_position(target, query.line, query.character)
        launcher = self._launchers[query.language]
        if not shutil.which(self._node_executable) or not launcher.is_file():
            return self._unavailable(query, "LSP provider is not configured on this machine.")
        server_cwd = self._server_cwd or root
        if not server_cwd.is_dir():
            return self._unavailable(query, "LSP launcher project directory is unavailable.")
        protocol = None
        initialized = False
        deadline = time.monotonic() + self._operation_timeout
        try:
            protocol = self._protocol_factory(query.language, launcher, root, server_cwd)
            initialize = {
                "processId": None,
                "rootUri": root.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": root.as_uri(), "name": root.name or "workspace"}],
            }
            protocol.request("initialize", initialize, self._remaining(deadline))
            initialized = True
            protocol.notify("initialized", {})
            uri = target.as_uri()
            protocol.notify("textDocument/didOpen", {
                "textDocument": {"uri": uri, "languageId": self._language_id(query.language, target), "version": 1,
                                 "text": text},
            })
            params = self._params(query, uri)
            result = protocol.request(METHODS[query.operation], params, self._remaining(deadline))
            results = self._filter_results(query.operation, result, root)
            return {
                "status": "ok" if results else "empty",
                "language": query.language,
                "operation": query.operation,
                "results": results,
                "detail": f"LSP returned {len(results)} scoped result(s).",
            }
        except (LspProtocolError, OSError, UnicodeError) as exc:
            return self._unavailable(query, f"LSP query unavailable: {str(exc)[:240]}")
        finally:
            if protocol is not None:
                if initialized:
                    try:
                        protocol.request("shutdown", None, min(2.0, self._remaining(deadline)))
                    except (LspProtocolError, OSError):
                        pass
                    try:
                        protocol.notify("exit", {})
                    except (LspProtocolError, OSError):
                        pass
                protocol.close()

    @staticmethod
    def _validate_identity(project, workspace):
        for value in (project, workspace):
            if not isinstance(value, str) or not value or len(value) > 200:
                raise ValueError("project a workspace musí být neprázdné textové identifikátory.")

    def _validate_query(self, query):
        if not isinstance(query, QueryRequest):
            raise ValueError("Neplatný LSP dotaz.")
        self._validate_identity(query.project, query.workspace)
        if query.language not in LANGUAGE_EXTENSIONS or query.operation not in OPERATIONS:
            raise ValueError("Neplatný jazyk nebo LSP operace.")
        relative_path(query.path)
        if not query.path:
            raise ValueError("LSP dotaz vyžaduje relativní cestu souboru.")
        if Path(query.path).suffix.lower() not in LANGUAGE_EXTENSIONS[query.language]:
            raise ValueError("Přípona souboru nepatří k vybranému LSP jazyku.")
        for name, value in (("line", query.line), ("character", query.character)):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
                raise ValueError(f"{name} musí být nezáporná 0-based LSP souřadnice.")

    def _validated_root(self, project, workspace):
        return self._root_for(project, workspace)

    def _validated_target(self, root, path, language):
        candidate = root
        for part in path.split("/"):
            candidate = candidate / part
            try:
                if reparse(candidate):
                    raise ValueError("LSP nepovoluje odkazy ani junctiony v cestě souboru.")
            except FileNotFoundError as exc:
                raise ValueError("LSP soubor ve workspace neexistuje.") from exc
        try:
            target = candidate.resolve(strict=True)
            target.relative_to(root)
        except (OSError, ValueError) as exc:
            raise ValueError("LSP cesta opouští připojený workspace.") from exc
        if not target.is_file():
            raise ValueError("LSP cesta musí označovat soubor.")
        if target.suffix.lower() not in LANGUAGE_EXTENSIONS[language]:
            raise ValueError("Přípona souboru nepatří k vybranému LSP jazyku.")
        return target

    def _read_and_validate_position(self, target, line, character):
        try:
            data = target.read_bytes()
        except OSError as exc:
            raise ValueError("LSP soubor nelze přečíst.") from exc
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError("LSP soubor překračuje limit 2 MiB.")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("LSP soubor není UTF-8 text.") from exc
        lines = text.split("\n")
        if line >= len(lines):
            raise ValueError("line je mimo rozsah souboru.")
        raw_line = lines[line].removesuffix("\r")
        units = len(raw_line.encode("utf-16-le")) // 2
        if character > units:
            raise ValueError("character je mimo UTF-16 rozsah řádku.")
        return text

    def _root_for(self, project, workspace):
        root = self._root_provider(project, workspace)
        if root is None:
            raise ValueError("Projekt nemá připojený workspace zdroj.")
        root = Path(root)
        try:
            if not root.is_dir() or reparse(root):
                raise ValueError("Kořen workspace není bezpečný adresář.")
            canonical = root.resolve(strict=True)
        except OSError as exc:
            raise ValueError("Kořen workspace není dostupný.") from exc
        if canonical != root.absolute():
            raise ValueError("Kořen workspace se změnil; připojte jej znovu.")
        return canonical

    def _params(self, query, uri):
        document = {"uri": uri}
        position = {"line": query.line, "character": query.character}
        if query.operation == "references":
            return {"textDocument": document, "position": position, "context": {"includeDeclaration": True}}
        if query.operation == "documentSymbols":
            return {"textDocument": document}
        return {"textDocument": document, "position": position}

    @staticmethod
    def _language_id(language, target):
        if language == "python":
            return "python"
        return "typescriptreact" if target.suffix.lower() == ".tsx" else "typescript"

    @staticmethod
    def _remaining(deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LspProtocolError("LSP operation exceeded 15 second limit.")
        return remaining

    def _filter_results(self, operation, result, root):
        values = result if isinstance(result, list) else ([] if result is None else [result])
        if operation in {"definition", "references", "documentSymbols"}:
            return [value for value in values if self._result_is_scoped(value, root)]
        return values if operation == "hover" else []

    @staticmethod
    def _result_is_scoped(value, root):
        if not isinstance(value, dict):
            return False
        uri = value.get("uri", value.get("targetUri"))
        # DocumentSymbol is implicitly scoped by textDocument/didOpen; SymbolInformation has uri.
        if uri is None:
            return "range" in value or "selectionRange" in value
        if not isinstance(uri, str):
            return False
        parsed = urlparse(uri)
        if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
            return False
        decoded = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", decoded):
            decoded = decoded[1:]
        try:
            Path(decoded).resolve(strict=False).relative_to(root)
        except (OSError, ValueError):
            return False
        return True

    @staticmethod
    def _unavailable(query, detail):
        return {"status": "unavailable", "language": query.language, "operation": query.operation,
                "results": [], "detail": detail}
