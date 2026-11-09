"""Committed project design reference; authenticated scope is supplied by the capability boundary."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.project.design import design_system

CONTRACTS = {
    "design_system_routes.read": contract(output="Native committed DESIGN.md revision, blob, sha256 and bounded markdown, or unavailable"),
}
CONTRACTS["design_system_routes.read"]["test"] = "backend/api/brain_opora/test_canvas_capability_vault_extras.py"


def read(service, project, capability, data):
    return design_system.read(service, project)
