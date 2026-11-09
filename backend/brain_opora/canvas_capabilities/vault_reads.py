"""Original versioned materials use native vault readers without copying content."""
from backend.api.editor.brief_vault_routes import _bad_request
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.brief_vault.brief_vault_duel import duel_view, vision_view
from backend.editor.brief_vault.brief_vault_next import lessons, next_work

CONTRACTS = {
    "brief_vault_routes.brief_vault_tree": contract(optional=("scope", "discipline")),
    "brief_vault_routes.brief_vault_disciplines": contract(),
    "brief_vault_routes.brief_vault_next": contract(optional=("discipline",)),
    "brief_vault_routes.brief_vault_lessons": contract(optional=("discipline", "versionId")),
    "brief_vault_routes.brief_vault_duel": contract(("id",)),
    "brief_vault_routes.brief_vault_vision": contract(optional=("scopeNodeId",)),
    "brief_vault_routes.brief_vault_fragment": contract(("id",), ("revision",), types={"revision": "integer"}),
    "brief_vault_routes.brief_vault_history": contract(optional=("scope", "limit"), types={"limit": "integer"}),
    "brief_vault_routes.brief_vault_research_brief": contract(("fragment",)),
    "brief_vault_routes.brief_vault_mirror": contract(),
    "brief_vault_routes.brief_vault_plan": contract(("fragmentIds",), types={"fragmentIds": "json"},
        output="Native dry-run plan, source revisions, scope digest and skipped fragments; no Canvas write"),
}
for _name in ("brief_vault_mirror", "brief_vault_plan"):
    CONTRACTS["brief_vault_routes." + _name]["test"] = "backend/api/brain_opora/test_canvas_capability_vault_extras.py"


def read(service, project, workspace, capability, data):
    vault = BriefVault(service)
    actions = {
        "brief_vault_routes.brief_vault_tree": lambda: vault.tree(project, workspace, data.get("scope"), data.get("discipline")),
        "brief_vault_routes.brief_vault_disciplines": lambda: vault.disciplines(project, workspace),
        "brief_vault_routes.brief_vault_next": lambda: next_work(service, project, workspace, data.get("discipline")),
        "brief_vault_routes.brief_vault_lessons": lambda: lessons(service, project, workspace, data.get("discipline"), data.get("versionId")),
        "brief_vault_routes.brief_vault_duel": lambda: duel_view(service, project, workspace, data["id"]),
        "brief_vault_routes.brief_vault_vision": lambda: vision_view(service, project, workspace, data.get("scopeNodeId", "")),
        "brief_vault_routes.brief_vault_fragment": lambda: vault.fragment(project, workspace, data["id"], data.get("revision")),
        "brief_vault_routes.brief_vault_history": lambda: vault.history(project, workspace, data.get("scope"), data.get("limit", 300)),
        "brief_vault_routes.brief_vault_research_brief": lambda: vault.research_brief(project, workspace, data["fragment"]),
        "brief_vault_routes.brief_vault_mirror": lambda: vault.mirror_overview(project, workspace),
        "brief_vault_routes.brief_vault_plan": lambda: vault.plan(
            {"project": project, "workspace": workspace, "fragmentIds": data["fragmentIds"]}, actor="agent"),
    }
    return _bad_request(actions[capability])
