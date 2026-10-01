"""HTTP DTO for explicitly confirmed per-workspace VS Code Hook installation."""

from fastapi import APIRouter, HTTPException

from backend.agent_installation.vscode_installer import VscodeHookInstaller


def create_hook_install_router(service, *, binding_lookup):
    """Factory contract: binding_lookup(binding_id) returns a public HookBinding dict."""
    installer = VscodeHookInstaller(service, binding_lookup)
    router = APIRouter(prefix="/api/agent-hooks", tags=["agent-hooks"])

    @router.get("/vscode")
    def vscode_status(bindingId: str):
        return installer.status(bindingId)

    @router.post("/vscode")
    def vscode_apply(payload: dict):
        expected = {"bindingId", "expectedBindingRevision", "expectedSettingsDigest", "action", "confirmed"}
        if not isinstance(payload, dict) or set(payload) != expected:
            raise HTTPException(status_code=409, detail="VS Code Hook vyžaduje přesný potvrzený formát.")
        return installer.apply(payload["bindingId"], payload["expectedBindingRevision"], payload["expectedSettingsDigest"],
                               payload["action"], payload["confirmed"])

    return router
