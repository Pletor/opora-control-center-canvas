"""Federated knowledge reads authorize both destination and every canonical origin."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.api.editor.research_routes import _authorize, _workspace
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.research import knowledge, model


def create_research_knowledge_router(service):
    router = APIRouter(prefix="/api/research", tags=["research-knowledge"])
    def authorizer(request):
        def authorize(project, workspace, write=False):
            model.identifier(project); model.identifier(workspace)
            _authorize(service, request, project, workspace, write)
            if not service.project_exists(project) or (project != "draft" and service.removals.archived(project)):
                model.fail("Research source is unavailable.", 404, "research_source")
        return authorize
    def call(fn):
        try:
            return fn()
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        except ValueError:
            return JSONResponse({"error": "Research context is unavailable."}, status_code=404)

    @router.get("/context")
    def context(request: Request, project: str, workspace: str, scopeNodeId: str = ""):
        def run():
            selected = _workspace(service, project, workspace)
            return {**knowledge.context(service, project, selected, scopeNodeId, authorizer(request)), "workspace": selected}
        return call(run)

    @router.post("/bindings")
    def bind(request: Request, payload: dict):
        def run():
            model.shape(payload, {"project", "workspace", "scopeNodeId", "source", "expectedRevision", "archived"})
            selected = _workspace(service, payload["project"], payload["workspace"])
            authorize = authorizer(request)
            authorize(payload["project"], selected, True)
            source = knowledge.reference(payload["source"])
            # Persist the resolved origin, never the moving main alias.
            authorize(source["projectId"], source["workspaceId"], False)
            source["workspaceId"] = _workspace(service, source["projectId"], source["workspaceId"])
            return knowledge.bind(service, payload["project"], selected, payload["scopeNodeId"], source,
                                  payload["expectedRevision"], payload["archived"], authorize, request.state.agent or request.state.actor)
        return call(run)

    @router.post("/knowledge-search")
    def search(request: Request, payload: dict):
        def run():
            model.shape(payload, {"project", "workspace", "scopes", "query"}, {"kinds", "verification", "limit", "resultType"})
            authorize = authorizer(request)
            authorize(payload["project"], payload["workspace"], False)
            scopes = payload["scopes"]
            if not isinstance(scopes, list) or not 1 <= len(scopes) <= 30:
                model.fail("Search requires 1 to 30 explicit scopes.")
            resolved = []
            for scope in scopes:
                model.shape(scope, {"project", "workspace"}, {"scopeNodeId", "includeDescendants"})
                authorize(scope["project"], scope["workspace"], False)
                resolved.append({**scope, "workspace": _workspace(service, scope["project"], scope["workspace"])})
            result_type = payload.get("resultType", "research")
            if result_type not in ("research", "solution"):
                model.fail("Unknown search result type.")
            if result_type == "solution":
                if payload.get("kinds") or payload.get("verification"):
                    model.fail("Research kind and verification filters require research results.")
                return knowledge.solutions(service, resolved, payload["query"], payload.get("limit",30), authorize)
            return knowledge.search(service, resolved, payload["query"], payload.get("kinds", []),
                                    payload.get("verification", []), payload.get("limit", 30), authorize)
        return call(run)
    return router
