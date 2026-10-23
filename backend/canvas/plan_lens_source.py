"""Realita pro Lens plánu: hlavní checkout projektu jen ke čtení (docs/plan-lens.md).

Zjistí, které cesty zdrojů karet v hlavním pracovním stromu existují, revizi a vlastníka repozitáře
pro `provenance` a vazby souborů z mapy Graphify (`graphify-out/graph.json`, rozparsované jednou
na otisk souboru). Nic nezapisuje, nic nespouští kromě `git rev-parse` / `git remote`, model nikdy.
`PlanLensReader` skládá graf, stav plochy a realitu do razítka pro ETag a drží hotovou odpověď
v `read_cache`, dokud se razítko nezmění."""
import json
import re
import subprocess

from backend.canvas.plan_lens import build
from backend.canvas.plan_lens_cards import is_card, source_path
from backend.canvas.plan_lens_code import file_links
from backend.integrations.gitio import git
from backend.project.maps.graphify_runtime import PUBLISH_LOCK
from backend.project.maps.map_artifacts import main_project_root
from backend.project.workspace.workspace_sources import WorkspaceSources

SHA = re.compile(r"[0-9a-f]{7,40}")
GITHUB = re.compile(r"github\.com[:/]([A-Za-z0-9-]{1,64})/([A-Za-z0-9._-]{1,128}?)(?:\.git)?/?$")
MAX_GRAPH = 32 * 1024 * 1024


def _root(service, project):
    try:
        return main_project_root(service, project)
    except Exception:  # noqa: BLE001 - projekt bez zdroje (draft, odpojený adresář) má jen plán
        return None


def _exists(sources, root, path):
    try:
        return sources.target(root, path).exists()
    except (OSError, ValueError):
        return False


def _git_facts(root):
    """(sha HEAD, {owner, name}) hlavního checkoutu; bez gitu (None, None)."""
    if not (root / ".git").exists():
        return None, None
    head = git(root, "rev-parse", "HEAD", timeout=3, optional=True)
    sha = head.strip() if isinstance(head, str) and SHA.fullmatch(head.strip()) else None
    remote = git(root, "remote", "get-url", "origin", timeout=3, optional=True)
    match = GITHUB.search(remote.strip()) if isinstance(remote, str) else None
    return sha, ({"owner": match.group(1), "name": match.group(2)} if match else None)


class PlanLensReader:
    def __init__(self, service, desktop_state):
        self.service, self.state = service, desktop_state
        self.sources = WorkspaceSources(service)

    def _graphify(self, root):
        """(vazby souborů, {available, sourceRevision?}); chybějící nebo vadná mapa = nedostupná."""
        if root is None:
            return [], {"available": False}
        with PUBLISH_LOCK:
            try:
                target = self.sources.target(root, "graphify-out/graph.json")
                stat = target.stat()
            except (OSError, ValueError):
                return [], {"available": False}
            stamp = (str(target), stat.st_mtime_ns, stat.st_size)
            key = ("plan-lens-graphify", str(root))
            cached = self.service.read_cache.get(key, stamp)
            if cached is None:
                cached = self.service.read_cache.put(key, stamp, self._parse(root, target, stat.st_size))
        return cached

    def _parse(self, root, target, size):
        if size > MAX_GRAPH:
            return [], {"available": False}
        try:
            links = file_links(json.loads(target.read_bytes()), str(root))
        except (OSError, ValueError, RecursionError):
            return [], {"available": False}
        info = {"available": True}
        try:
            receipt = json.loads(self.sources.target(root, "graphify-out/opora-receipt.json").read_bytes())
            revision = receipt.get("sourceRevision") if isinstance(receipt, dict) else None
            if isinstance(revision, str) and SHA.fullmatch(revision):
                info["sourceRevision"] = revision
        except (OSError, ValueError, RecursionError):
            pass
        return links, info

    def reality(self, project, graph):
        root = _root(self.service, project)
        paths = sorted({path for node in graph.get("nodes") or [] if is_card(node) for path in [source_path(node)] if path})
        existing = [path for path in paths if root is not None and _exists(self.sources, root, path)]
        try:
            sha, repo = _git_facts(root) if root is not None else (None, None)
        except (OSError, ValueError, subprocess.SubprocessError):
            sha, repo = None, None
        links, graphify = self._graphify(root)
        return {"existing": existing, "links": links, "graphify": graphify,
                "sha": sha or graphify.get("sourceRevision"), "repo": repo}

    def read(self, project, workspace, area=None):
        """(razítko, odpověď) pro `GET /api/oporahub/plan-lens`; `AreaNotFound` pro neznámou oblast."""
        with self.service.reading(project):
            view = self.service.view(project, workspace)
            state_stamp = self.state.stamp(project, workspace)
            state = self.state.read(project, workspace)["state"]
        reality = self.reality(project, view["graph"])
        stamp = ("plan-lens", project, workspace, area, view["digest"], list(state_stamp),
                 reality["existing"], reality["sha"], reality["repo"], reality["graphify"], len(reality["links"]))
        key = ("plan-lens", project, workspace, area)
        body = self.service.read_cache.get(key, repr(stamp))
        if body is None:
            body = self.service.read_cache.put(key, repr(stamp), build(view["graph"], state, reality, area,
                                                                       project, workspace))
        return stamp, body
