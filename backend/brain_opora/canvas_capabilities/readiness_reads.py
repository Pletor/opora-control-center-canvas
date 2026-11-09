"""Readiness and work ownership use the same domain views as Desktop v3."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.scenario_history import scenario_history
from backend.editor.agent_memory.usage import usage_summary
from backend.editor.agent_memory.assignment_status import assignment_status
from backend.editor.agent_memory.pipeline_routing import profiles
from backend.editor.agent_packet.work_overview import work_overview
from backend.canvas.source_realization import source_status

CONTRACTS = {"desktop_v3_routes." + name: contract(output=output) for name, output in (
    ("read_scenario_history", "Native scenario history"), ("read_work_overview", "Native work overview and readiness"),
    ("read_source_status", "Native source realization status"), ("read_leases", "Scoped active lease ownership summary"),
    ("read_usage", "Native usage summary; unknown remains unknown"), ("read_assignment_status", "Native assignment status"),
    ("read_pipeline_profiles", "Native supported pipeline profiles"), ("read_state", "Desktop state and revision"))}


def read(service, project, workspace, name):
    if name == "desktop_v3_routes.read_scenario_history":
        return scenario_history(service, project, workspace)
    if name == "desktop_v3_routes.read_work_overview":
        return work_overview(service, project, workspace)
    if name == "desktop_v3_routes.read_source_status":
        return source_status(service, project, workspace)
    if name == "desktop_v3_routes.read_leases":
        return CardLeases(service).summary(project, workspace)
    if name == "desktop_v3_routes.read_usage":
        return usage_summary(service, project, workspace)
    if name == "desktop_v3_routes.read_assignment_status":
        return assignment_status(service, project, workspace)
    if name == "desktop_v3_routes.read_pipeline_profiles":
        return profiles()
    if name == "desktop_v3_routes.read_state":
        return DesktopV3State(service).read(project, workspace)
    raise RuntimeError("No readiness read adapter.")
