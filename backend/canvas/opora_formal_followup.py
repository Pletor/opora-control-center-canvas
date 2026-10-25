"""Counterexample -> actionable: a failing formal check proposes a "fix verification" card.

The proposal is an ordinary immutable graph addition (author `orchestrator` named
`system · formal verification`); it changes nothing until a human accepts it, exactly like
any other proposal. The new card's specification carries the failing evidence: check,
head SHA, failure kinds, the counterexample payload and the verification detail path where
`counterexample.json` downloads. One proposal per verification record (the subject carries
its id), so loop re-reads, restarts and the explicit `verification.fix` action never
duplicate it. Runner/infrastructure-only failures (`runner_error`) propose nothing.
Contract: docs/oporahub-verification.md "Protipříklad → návrh opravy".
"""
import json
import logging

from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_verifications import OporaVerifications

LOGGER = logging.getLogger(__name__)
AUTHOR = {"kind": "orchestrator", "name": "system · formal verification"}
ACTIONABLE = {"counterexample", "failed"}
INFRASTRUCTURE = {"runner_error"}


def marker(verification_id):
    return f"[verification {verification_id[:12]}]"


def actionable(record):
    if record.get("domain", "formal") != "formal":
        return False
    report, origin = record.get("report") or {}, record.get("origin") or {}
    if report.get("outcome") not in ACTIONABLE:
        return False
    kinds = set(origin.get("failureKinds") or [])
    return report["outcome"] == "counterexample" or not kinds or bool(kinds - INFRASTRUCTURE)


def _existing(graphs, project, workspace, verification_id):
    tag = marker(verification_id)
    return next((item for item in graphs.list(project, workspace)["items"] if tag in (item.get("subject") or "")), None)


def plan(record, project, workspace):
    origin, report = record.get("origin") or {}, record["report"]
    check, sha = origin.get("checkName", record["verification"]["tool"]["name"]), origin.get("headSha", "")
    detail = f"/api/oporahub/verifications/{record['id']}?project={project}&workspace={workspace}"
    counterexample = next((item for item in report["artifacts"] if item["role"] == "counterexample"), None)
    evidence = {"verificationId": record["id"], "check": check, "headSha": sha, "outcome": report["outcome"],
                "failureKinds": origin.get("failureKinds", []), "executionId": record["executionId"],
                "cardId": record["nodeId"], "detail": detail,
                "counterexample": None if counterexample is None else
                f"/api/oporahub/verifications/{record['id']}/artifacts/{counterexample['sha256']}"}
    goal = (f"Opravit chybu, kterou našla formální kontrola {check} na {sha[:12]} u karty {record['nodeId']}: "
            f"{report['summary']}\nDůkaz (protipříklad a metadata běhu): {json.dumps(evidence, ensure_ascii=False)}")
    return {"nodes": [{"ref": "fix", "kind": "node", "name": f"Opravit formální ověření: {record['nodeId']}"[:120],
                       "purpose": "Oprava chyby nalezené strojovou kontrolou modelu nebo důkazu.",
                       "spec": {"goal": goal[:3500],
                                "non_goals": "Neoslabovat model, invariant, konfiguraci ani důkaz jen proto, aby "
                                             "kontrola prošla. Změna specifikace patří člověku jako zvláštní návrh.",
                                "acceptance": f"Check {check} na nové hlavě PR je zelený; původně selhávající případ "
                                              "projde; negativní konfigurace dál selhávají deklarovaným invariantem; "
                                              "Lean audit axiomů je čistý."}}]}


def propose(service, project, workspace, verification_id):
    """Create (or return) the follow-up proposal; None when the record is not actionable."""
    record = OporaVerifications(service).read(verification_id, project, workspace)
    if not actionable(record):
        return None
    graphs = OporaGraphProposals(service)
    existing = _existing(graphs, project, workspace, verification_id)
    if existing is not None:
        return {"proposalId": existing["id"], "created": False, "accepted": existing["accepted"]}
    context = graphs.context(project, workspace)
    subject = f"Opravit formální ověření {record['nodeId']} {marker(verification_id)}"
    created = graphs.create({"project": project, "workspace": workspace, "parentRevision": context["acceptedHead"],
                             "expectedGraphDigest": context["graphDigest"], "subject": subject,
                             "plan": plan(record, project, workspace)}, AUTHOR)
    return {"proposalId": created["id"], "created": True, "accepted": False}


def propose_quietly(service, project, workspace, record):
    """Loop hook: never lets a proposal failure (read-only space, moved head) break ingestion."""
    if not record or not actionable(record):
        return None
    try:
        return propose(service, project, workspace, record["id"])
    except (ValueError, KeyError, TypeError) as error:
        LOGGER.info("Formal follow-up proposal for %s skipped: %s", record.get("id"), error)
        return None
