"""All audited native operations stay visible; unsupported entries are never dispatchable."""
import json
from pathlib import Path
from copy import deepcopy

from backend.canvas.payload_errors import InvalidPayload
from backend.brain_opora.canvas_capabilities.contracts import CONTRACTS
from backend.brain_opora.canvas_capabilities.canvas_reads import CONTRACTS as READS
from backend.brain_opora.canvas_capabilities.readiness_reads import CONTRACTS as READINESS

from backend.brain_opora.canvas_capabilities.site_reads import CONTRACTS as SITE
from backend.brain_opora.canvas_capabilities.research_reads import CONTRACTS as RESEARCH

from backend.brain_opora.canvas_capabilities.proposal_writes import CONTRACTS as WRITES

from backend.brain_opora.canvas_capabilities.vault_reads import CONTRACTS as VAULT

from backend.brain_opora.canvas_capabilities.flow_reads import CONTRACTS as FLOW

from backend.brain_opora.canvas_capabilities.flow_inspect import CONTRACTS as INSPECT

from backend.brain_opora.canvas_capabilities.library_reads import CONTRACTS as LIBRARY
from backend.brain_opora.canvas_capabilities.library_actions import CONTRACTS as LIBRARY_ACTIONS

from backend.brain_opora.canvas_capabilities.draft_writes import CONTRACTS as DRAFTS

from backend.brain_opora.canvas_capabilities.research_actions import CONTRACTS as RESEARCH_ACTIONS

from backend.brain_opora.canvas_capabilities.changeset_actions import CONTRACTS as CHANGESETS

from backend.brain_opora.canvas_capabilities.desktop_reads import CONTRACTS as DESKTOP

from backend.brain_opora.canvas_capabilities.research_tasks import CONTRACTS as RESEARCH_TASKS

from backend.brain_opora.canvas_capabilities.site_actions import CONTRACTS as SITE_ACTIONS

from backend.brain_opora.canvas_capabilities.flow_drafts import CONTRACTS as FLOW_DRAFTS

from backend.brain_opora.canvas_capabilities.desktop_evidence_reads import CONTRACTS as DESKTOP_EVIDENCE

from backend.brain_opora.canvas_capabilities.desktop_packet_actions import CONTRACTS as PACKETS

from backend.brain_opora.canvas_capabilities.node_materials import CONTRACTS as MATERIALS

from backend.brain_opora.canvas_capabilities.version_actions import CONTRACTS as VERSIONS

from backend.brain_opora.canvas_capabilities.layout_actions import CONTRACTS as LAYOUT

from backend.brain_opora.canvas_capabilities.revise_actions import CONTRACTS as REVISE

from backend.brain_opora.canvas_capabilities.desktop_memory_actions import CONTRACTS as MEMORY

from backend.brain_opora.canvas_capabilities.design_reads import CONTRACTS as DESIGN
from backend.brain_opora.canvas_capabilities.research_ticket_actions import CONTRACTS as TICKETS

from backend.brain_opora.canvas_capabilities.flow_actions import CONTRACTS as FLOW_ACTIONS

from backend.brain_opora.canvas_capabilities.lease_actions import CONTRACTS as LEASES

from backend.brain_opora.canvas_capabilities.research_review_actions import CONTRACTS as REVIEW_PROPOSALS

from backend.brain_opora.canvas_capabilities.desktop_work_actions import CONTRACTS as DESKTOP_WORK

from backend.brain_opora.canvas_capabilities.source_realization_action import CONTRACTS as REALIZATION

from backend.brain_opora.canvas_capabilities.desktop_review_actions import CONTRACTS as DESKTOP_REVIEW

from backend.brain_opora.canvas_capabilities.changeset_review_actions import CONTRACTS as CHANGESET_REVIEW

from backend.brain_opora.canvas_capabilities.working_graph_actions import CONTRACTS as WORKING_GRAPH
from backend.brain_opora.canvas_capabilities.brief_actions import CONTRACTS as BRIEF_ACTIONS

from backend.brain_opora.canvas_capabilities.research_continuation_actions import CONTRACTS as CONTINUATIONS

VERSION = 1
from backend.brain_opora.canvas_capabilities import knowledge_actions, storyboard_actions, content_actions
INVENTORY = json.loads(Path(__file__).with_name("inventory.json").read_text(encoding="utf-8"))
INVENTORY += [{"id": "session_view." + action, "contract": "session-view", "nativeRoute": None,
               "source": "backend/brain_opora/canvas_capabilities/session_view.py", "nativeCalls": action}
              for action in ("read", "update")]

INVENTORY += [{"id": "opora_graph_routes.revise", "contract": "graph-proposal-revision",
    "nativeRoute": "POST /api/oporahub/graph-proposals/{identifier}/revise",
    "source": "backend/api/editor/opora_graph_routes.py", "nativeCalls": "OporaGraphProposals.revise"}]

INVENTORY += [{"id": "library_review_routes." + name, "contract": "library-review",
    "nativeRoute": route, "source": "backend/api/flow/library_review_routes.py", "nativeCalls": name}
    for name, route in (("reviews", "GET /api/library/reviews"), ("review", "GET /api/library/reviews/{identifier}"),
                        ("decide", "POST /api/library/reviews/{identifier}/{action}"))]

INVENTORY += [{"id": "flow_routes.review", "contract": "flow-review", "nativeRoute": "GET /api/flow/review",
               "source": "backend/api/flow/flow_routes.py", "sourceSymbol": "workflow_review", "nativeCalls": "review.observe"}]

INVENTORY += [{"id": "site_admin_routes.proposal_attachment", "contract": "site-staged-attachment",
    "nativeRoute": "GET /api/site-admin/proposals/{proposal_id}/attachments/{index}",
    "source": "backend/api/project/site_admin_routes.py", "nativeCalls": "proposal_attachments.content"}]
INVENTORY += [{"id": "brief_vault_review_routes." + name, "contract": "brief-vault-review",
    "nativeRoute": route, "source": "backend/api/editor/brief_vault_review_routes.py", "nativeCalls": name}
    for name, route in (("read", "GET /api/brief-vault/reviews/{identifier}"),
                        ("decide", "POST /api/brief-vault/reviews/{identifier}/{action}"))]

INVENTORY += [{"id": "research_review_proposal_routes." + name, "contract": "research-review-proposal",
    "nativeRoute": route, "source": "backend/api/editor/research_review_proposal_routes.py", "nativeCalls": name}
    for name, route in (("prepare", "POST /api/research/review-proposals"), ("listing", "GET /api/research/review-proposals"),
                        ("read", "GET /api/research/review-proposals/{identifier}"),
                        ("decide", "POST /api/research/review-proposals/{identifier}/{action}"))]

INVENTORY += [{"id": "desktop_review_routes." + name, "contract": "desktop-review",
    "nativeRoute": route, "source": "backend/api/editor/desktop_review_routes.py", "nativeCalls": name}
    for name, route in (("review", "GET /api/desktop-reviews/{identifier}"),
                        ("decide", "POST /api/desktop-reviews/{identifier}/apply"))]

INVENTORY += [{"id": "opora_changeset_routes.baseline_preparation", "contract": "baseline-preparation",
    "nativeRoute": "GET /api/oporahub/baseline-preparations/{identifier}",
    "source": "backend/api/editor/opora_changeset_routes.py", "nativeCalls": "baseline_preparation"}]

INVENTORY += [{"id": "working_review_routes." + name, "contract": "working-review",
    "nativeRoute": route, "source": "backend/api/editor/working_review_routes.py", "nativeCalls": name}
    for name, route in (("read", "GET /api/working-reviews/{operation}/{identifier}"),
                        ("apply", "POST /api/working-reviews/{operation}/{identifier}/apply"))]


INVENTORY += [{"id": "research_continuation_routes." + name, "contract": "research-original-continuation",
    "nativeRoute": route, "source": "backend/api/editor/research_continuation_routes.py", "nativeCalls": native}
    for name, route, native in (("listing", "GET /api/research/continuations", "continuations.listing"),
        ("original", "GET /api/research/originals/{identifier}", "originals.read"),
        ("materialize", "POST /api/research/originals/{identifier}/materialize", "originals.materialize"))]


for module, source, routes in (
    (knowledge_actions, "research_knowledge_routes", {"context": "GET /api/research/context", "search": "POST /api/research/knowledge-search", "bind": "POST /api/research/bindings"}),
    (storyboard_actions, "storyboard_routes", {"storyboard_read": "GET /api/storyboard", "storyboard_write": "POST /api/storyboard"}),
    (content_actions, "opora_content_routes", {"listing": "GET /api/oporahub/content-changes", "detail": "GET /api/oporahub/content-changes/{identifier}", "create": "POST /api/oporahub/content-changes", "accept": "POST /api/oporahub/content-changes/{identifier}/accept"}),
):
    INVENTORY += [{"id": identifier, "contract": "native-scoped-content", "nativeRoute": routes[identifier.rsplit(".", 1)[1]],
        "source": "backend/api/editor/" + source + ".py", "nativeCalls": identifier.rsplit(".", 1)[1]} for identifier in module.CONTRACTS]


def discover():
    return {"catalogVersion": VERSION, "organizationModel": "not_present",
            "scopeBoundary": "authenticated Heart project and workspace",
            "operations": [describe(item["id"]) for item in INVENTORY]}


def describe(identifier):
    item = next((item for item in INVENTORY if item["id"] == identifier), None)
    if item is None:
        raise InvalidPayload("Unknown finite capability.", field="capability")
    configured = {**CONTRACTS, **READS, **READINESS, **SITE, **RESEARCH, **WRITES, **VAULT, **FLOW, **INSPECT, **LIBRARY, **LIBRARY_ACTIONS, **DRAFTS, **RESEARCH_ACTIONS, **CHANGESETS, **DESKTOP, **RESEARCH_TASKS, **SITE_ACTIONS, **FLOW_DRAFTS, **DESKTOP_EVIDENCE, **PACKETS, **MATERIALS, **VERSIONS, **LAYOUT, **REVISE, **MEMORY, **DESIGN, **TICKETS, **FLOW_ACTIONS, **LEASES, **REVIEW_PROPOSALS, **DESKTOP_WORK, **REALIZATION, **DESKTOP_REVIEW, **CHANGESET_REVIEW, **WORKING_GRAPH, **BRIEF_ACTIONS, **CONTINUATIONS}.get(identifier)
    configured = configured or knowledge_actions.CONTRACTS.get(identifier) or storyboard_actions.CONTRACTS.get(identifier) or content_actions.CONTRACTS.get(identifier)
    return {**deepcopy(item), "implemented": configured is not None,
            "adapter": deepcopy(configured) if configured else None,
            "status": "implemented" if configured else "awaiting_adapter_and_contract_tests"}
