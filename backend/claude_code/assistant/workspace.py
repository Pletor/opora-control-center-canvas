"""Kde asistent běží: kořen zdroje projektu z `WorkspaceSources.root` (docs/asistent.md §3).

Výchozí workspace je u git projektu `main`, jinak `draft`. Proto se v cwd načte CLAUDE.md
projektu a jeho `.claude/skills`.
"""

from __future__ import annotations

from backend.project.workspace.workspace_sources import WorkspaceSources

NO_ROOT = "Projekt nemá připojenou složku se zdrojem. Asistent potřebuje pracovní složku projektu; připojte ji v nastavení projektu."
MAX_WORKSPACE = 128


def default_workspace(source_kind):
    return "main" if source_kind == "git" else "draft"


def project_locator(service):
    """`locate(project, workspace)` → `(workspace, kořen)`; chyby jsou české `ValueError`."""
    sources = WorkspaceSources(service)

    def locate(project, workspace=None):
        item = service.project_hub.settings(project)["project"]
        chosen = workspace or default_workspace(item.get("sourceKind"))
        if not isinstance(chosen, str) or len(chosen) > MAX_WORKSPACE:
            raise ValueError("Neplatný pracovní prostor.")
        try:
            root = sources.root(project, chosen)
        except (KeyError, LookupError) as exc:
            raise ValueError("Pracovní prostor neexistuje.") from exc
        if root is None or not root.is_dir():
            raise ValueError(NO_ROOT)
        return chosen, root

    return locate
