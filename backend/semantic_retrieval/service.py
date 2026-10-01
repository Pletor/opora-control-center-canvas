"""Safe candidate collection and isolated local-ONNX invocation for semantic search."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from backend.project.workspace.workspace_sources import relative_path, reparse

MODEL_REPOSITORY = "Xenova/multilingual-e5-small"
MODEL_REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
MODEL_NAME = f"{MODEL_REPOSITORY}@{MODEL_REVISION}"
DEFAULT_MODEL_DIR = Path("C:/Users/Admin/.cache/opora/models/multilingual-e5-small")
REQUIRED_MODEL_FILES = ("onnx/model_quantized.onnx", "tokenizer.json", "config.json")
SOURCE_EXTENSIONS = frozenset({".py", ".ts", ".tsx", ".js", ".md"})
PROTECTED_DIRECTORIES = frozenset({
    ".git", "node_modules", ".data", ".claude", ".hermes", ".env", "control",
})
MAX_FILES = 64
MAX_CHUNKS = 128
MAX_FILE_BYTES = 128 * 1024
MAX_CHUNK_LINES = 40
MAX_CHUNK_BYTES = 6 * 1024
MAX_QUERY_BYTES = 2048
MAX_RESULTS = 20
MAX_PAYLOAD_BYTES = 1024 * 1024
WORKER_TIMEOUT_SECONDS = 60


class SemanticWorkerError(RuntimeError):
    """A local model worker did not produce a bounded valid response."""


class WorkerRunner:
    """One local system-Python worker per explicit query; never enables network access."""

    def __init__(self, *, script=None, python=None, model_dir=None, timeout=WORKER_TIMEOUT_SECONDS):
        self.script = Path(script) if script else Path(__file__).resolve().parents[2] / "tools" / "opora_semantic.py"
        self.python = Path(python or os.environ.get("OPORA_SEMANTIC_SYSTEM_PYTHON", r"C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe"))
        self.model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        self.timeout = min(float(timeout), WORKER_TIMEOUT_SECONDS)

    def __call__(self, query, chunks):
        if not self.python.is_file() or not self.script.is_file():
            raise SemanticWorkerError("Configured system Python worker is unavailable.")
        payload = json.dumps({"query": query, "chunks": [chunk["text"] for chunk in chunks], "modelDir": str(self.model_dir)}, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise SemanticWorkerError("Semantic query exceeds the local worker input limit.")
        env = dict(os.environ)
        env.update({
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
            "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
            "ORT_DISABLE_ALL": "0",
        })
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        process = None
        try:
            process = subprocess.Popen(
                [str(self.python), "-I", str(self.script), "worker"], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(self.script.parent.parent), env=env,
                shell=False, creationflags=flags, start_new_session=os.name != "nt",
            )
            stdout, stderr = process.communicate(payload, timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            self._terminate_tree(process)
            raise SemanticWorkerError("Local semantic inference timed out after 60 seconds.") from exc
        except OSError as exc:
            raise SemanticWorkerError("Local semantic worker could not be started.") from exc
        finally:
            if process is not None and process.poll() is None:
                self._terminate_tree(process)
        assert process is not None
        if len(stdout) > 128 * 1024 or process.returncode != 0:
            detail = stderr.decode("utf-8", "replace").strip().replace("\n", " ")[:240]
            raise SemanticWorkerError("Local semantic inference failed" + (f": {detail}" if detail else "."))
        try:
            result = json.loads(stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SemanticWorkerError("Local semantic worker returned invalid JSON.") from exc
        scores = result.get("scores") if isinstance(result, dict) else None
        if not isinstance(scores, list) or len(scores) != len(chunks) or any(isinstance(score, bool) or not isinstance(score, (int, float)) for score in scores):
            raise SemanticWorkerError("Local semantic worker returned invalid scores.")
        return [float(score) for score in scores]

    @staticmethod
    def _terminate_tree(process):
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=False)
            else:
                process.kill()
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            pass


class SemanticRetrieval:
    """Read-only scoped source retrieval; dense scores come only from the local worker."""

    def __init__(self, sources, *, model_dir=None, runner=None):
        self.sources = sources
        self.model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        self.runner = runner or WorkerRunner(model_dir=self.model_dir)

    def status(self, project, workspace):
        self._identity(project, workspace)
        detail = self._availability_detail()
        if detail is None:
            return {"status": "configured", "model": MODEL_NAME,
                    "detail": "Local model files are configured; inference remains cold until an explicit query.",
                    "localOnly": True}
        return {"status": "unavailable", "model": MODEL_NAME, "detail": detail, "localOnly": True}

    def query(self, payload):
        project, workspace, path, query, limit = self._validate_payload(payload)
        unavailable = self._availability_detail()
        if unavailable:
            return self._response("unavailable", [], 0, 0, False, unavailable)
        root = self._root(project, workspace)
        chunks, files_scanned, truncated = self._collect(root, path)
        if not chunks:
            return self._response("empty", [], files_scanned, 0, truncated, "No supported UTF-8 source chunks in the selected scope.")
        try:
            scores = self.runner(query, chunks)
        except SemanticWorkerError as exc:
            return self._response("unavailable", [], files_scanned, len(chunks), truncated, str(exc))
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: (-pair[1], pair[0]["path"], pair[0]["startLine"]))[:limit]
        results = [{"path": chunk["path"], "startLine": chunk["startLine"], "endLine": chunk["endLine"],
                    "snippet": chunk["snippet"], "score": round(score, 6)} for chunk, score in ranked]
        return self._response("ok" if results else "empty", results, files_scanned, len(chunks), truncated,
                              f"Dense cosine ranking over {len(chunks)} local source chunk(s).")

    @staticmethod
    def _response(status, results, files_scanned, chunks_indexed, truncated, detail):
        return {"status": status, "results": results, "model": MODEL_NAME, "localOnly": True,
                "filesScanned": files_scanned, "chunksIndexed": chunks_indexed, "truncated": truncated, "detail": detail}

    def availability_detail(self):
        """None when the pinned local model is usable, otherwise the truthful unavailable reason."""
        return self._availability_detail()

    def _availability_detail(self):
        manifest = self.model_dir / "manifest.json"
        if not manifest.is_file():
            return f"Local model manifest is missing at {self.model_dir}; no download is attempted at runtime."
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return "Local model manifest is unreadable; no download is attempted at runtime."
        if data.get("repo") != MODEL_REPOSITORY or data.get("revision") != MODEL_REVISION:
            return "Local model manifest does not match the pinned supported model revision."
        files = data.get("files")
        if (not isinstance(files, dict) or any(not isinstance(files.get(name), str) or not files[name] for name in REQUIRED_MODEL_FILES)
                or any(not (self.model_dir / name).is_file() for name in REQUIRED_MODEL_FILES)):
            return "Required local model files are missing; no download is attempted at runtime."
        return None

    @staticmethod
    def _identity(project, workspace):
        if not all(isinstance(value, str) and value and len(value) <= 200 for value in (project, workspace)):
            raise ValueError("project a workspace musí být neprázdné textové identifikátory.")

    def _validate_payload(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "path", "query", "limit"}:
            raise ValueError("Sémantický dotaz vyžaduje pouze project, workspace, path, query a limit.")
        project, workspace, path, query, limit = (payload[key] for key in ("project", "workspace", "path", "query", "limit"))
        self._identity(project, workspace)
        relative_path(path)
        if not path:
            raise ValueError("Sémantický dotaz vyžaduje konkrétní relativní soubor nebo podstrom.")
        if any(part.casefold() in PROTECTED_DIRECTORIES or part.casefold().startswith(".env") for part in Path(path).parts):
            raise ValueError("Sémantické dohledání nepovoluje řídicí ani chráněné adresáře.")
        if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > MAX_QUERY_BYTES:
            raise ValueError("query musí být neprázdný text do 2048 UTF-8 bytů.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RESULTS:
            raise ValueError(f"limit musí být celé číslo 1 až {MAX_RESULTS}.")
        return project, workspace, path, query.strip(), limit

    def _root(self, project, workspace):
        root = self.sources.root(project, workspace)
        if root is None:
            raise ValueError("Projekt nemá připojený workspace zdroj.")
        root = Path(root)
        if not root.is_dir() or reparse(root):
            raise ValueError("Kořen workspace není bezpečný adresář.")
        canonical = root.resolve(strict=True)
        if canonical != root.absolute():
            raise ValueError("Kořen workspace se změnil; připojte jej znovu.")
        return canonical

    def _target(self, root, path):
        if hasattr(self.sources, "target"):
            return self.sources.target(root, path)
        candidate = root
        for part in path.split("/"):
            candidate /= part
            if reparse(candidate):
                raise ValueError("Odkazy a junctiony nelze prohledávat.")
        target = candidate.resolve(strict=True)
        if not target.is_relative_to(root):
            raise ValueError("Cesta opouští připojený projekt.")
        return target

    def _collect(self, root, path):
        target = self._target(root, path)
        if target.is_file():
            files = [target] if self._eligible(target) else []
            return self._chunks(root, files)
        if not target.is_dir():
            raise ValueError("Sémantická cesta musí být soubor nebo adresář.")
        files, truncated = [], False
        pending = [target]
        while pending and len(files) < MAX_FILES:
            directory = pending.pop()
            try:
                entries = sorted(list(os.scandir(directory)), key=lambda entry: (entry.name.casefold(), entry.name))
            except OSError as exc:
                raise ValueError("Vybraný podstrom nelze bezpečně přečíst.") from exc
            directories = []
            for entry in entries:
                candidate = Path(entry.path)
                if reparse(candidate):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.casefold() not in PROTECTED_DIRECTORIES and not entry.name.casefold().startswith(".env"):
                        directories.append(candidate)
                elif entry.is_file(follow_symlinks=False) and self._eligible(candidate):
                    files.append(candidate)
                    if len(files) == MAX_FILES:
                        truncated = True
                        break
            pending.extend(reversed(directories))
        chunks, files_scanned, chunk_truncated = self._chunks(root, files)
        return chunks, files_scanned, truncated or chunk_truncated

    @staticmethod
    def _eligible(path):
        try:
            return path.suffix.casefold() in SOURCE_EXTENSIONS and path.stat().st_size <= MAX_FILE_BYTES
        except OSError:
            return False

    def _chunks(self, root, files):
        chunks, files_scanned, truncated = [], 0, False
        for file in files:
            try:
                data = file.read_bytes()
                text = data.decode("utf-8")
            except (OSError, UnicodeError):
                continue
            files_scanned += 1
            lines = text.splitlines()
            for offset in range(0, len(lines), MAX_CHUNK_LINES):
                if len(chunks) >= MAX_CHUNKS:
                    truncated = True
                    return chunks, files_scanned, truncated
                selected = lines[offset:offset + MAX_CHUNK_LINES]
                chunk_text = "\n".join(selected).encode("utf-8")[:MAX_CHUNK_BYTES].decode("utf-8", "ignore")
                if not chunk_text.strip():
                    continue
                chunks.append({"path": file.relative_to(root).as_posix(), "startLine": offset + 1,
                               "endLine": offset + len(selected), "text": chunk_text,
                               "snippet": chunk_text[:1600]})
        return chunks, files_scanned, truncated
