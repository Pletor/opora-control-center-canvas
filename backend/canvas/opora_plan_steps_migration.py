"""Migration: legacy block conditions + desktop-v3 `steps`/`criteria` → DRAFT plan-step proposals.

One spec changeset proposal per card that has no accepted or working steps yet and has
something to migrate. The proposal is never accepted here: a human reviews and accepts it
like any spec change. Dry run is the default and writes nothing.

    uv run python -m backend.canvas.opora_plan_steps_migration --data DATA --project P --workspace W [--apply]

docs/oporahub-plan-steps.md, section "Migrace".
"""
import argparse
import json
import sys
from pathlib import Path

from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_plan_steps import steps_of, validate_steps
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

AUTHOR = {"kind": "orchestrator", "name": "plan-steps-migration"}
MAX_ACCEPTANCE = 20


def _clip(text, limit):
    text = " ".join(str(text or "").split())
    return text[:limit].rstrip()


def draft_steps(node_state):
    """Legacy card memory → validated linear steps (block conditions first, then legacy steps)."""
    sources = []
    blocks = sorted(node_state.get("blocks", []), key=lambda item: [int(part) for part in item["number"].split(".")])
    for block in blocks:
        condition = _clip((block.get("state") or {}).get("condition"), 1000)
        if condition:
            sources.append((_clip(block.get("title"), 200) or condition[:200], [condition]))
    for item in node_state.get("steps", []):
        text = _clip(item.get("text"), 1000)
        if text:
            sources.append((text[:200], [text]))
    criteria = [text for text in (_clip(item.get("text"), 1000) for item in node_state.get("criteria", [])) if text]
    if not sources and criteria:
        sources.append(("Splnit kritéria karty", []))
    if not sources:
        return []
    title, acceptance = sources[-1]
    sources[-1] = (title, list(dict.fromkeys([*acceptance, *criteria]))[:MAX_ACCEPTANCE])
    steps = [{"id": f"s{index}", "order": index, "title": title, "acceptance": acceptance,
              "dependsOn": [f"s{index - 1}"] if index > 1 else []}
             for index, (title, acceptance) in enumerate(sources[:50], start=1)]
    return validate_steps(steps)


def plan(service, project, workspace):
    """Per-card migration plan; reads only."""
    changesets = OporaChangesets(service)
    context = changesets.context(project, workspace)
    if context["acceptedHead"] is None:
        raise ValueError("Migrace kroků vyžaduje přijaté výchozí zadání (baseline).")
    accepted = {item["nodeId"]: item for item in context["acceptedDocuments"]}
    nodes = DesktopV3State(service).read(project, workspace)["state"]["nodes"]
    cards, skipped = [], []
    for document in context["documents"]:
        node = document["nodeId"]
        if node not in accepted:
            skipped.append({"nodeId": node, "reason": "not_in_accepted_spec"})
        elif steps_of(document["fields"]) or steps_of(accepted[node]["fields"]):
            skipped.append({"nodeId": node, "reason": "already_has_steps"})
        elif not (steps := draft_steps(nodes.get(node, {}))):
            skipped.append({"nodeId": node, "reason": "nothing_to_migrate"})
        else:
            cards.append({"nodeId": node, "expectedRevision": document["revision"],
                          "fields": {**document["fields"], "steps": steps}})
    return context, cards, skipped


def migrate(service, project, workspace, *, dry_run=True):
    context, cards, skipped = plan(service, project, workspace)
    proposals = []
    if not dry_run:
        changesets = OporaChangesets(service)
        for card in cards:
            current = changesets.context(project, workspace)
            created = changesets.create({"project": project, "workspace": workspace,
                                         "subject": f"Kroky plánu z legacy podkladů: {card['nodeId']}",
                                         "parentRevision": current["acceptedHead"],
                                         "expectedGraphDigest": current["graphDigest"], "changes": [card]}, AUTHOR)
            proposals.append({"nodeId": card["nodeId"], "proposalId": created["id"], "accepted": created["accepted"]})
    return {"dryRun": dry_run, "acceptedHead": context["acceptedHead"], "cards": cards, "skipped": skipped,
            "proposals": proposals}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Návrhy kroků plánu z legacy podkladů (docs/oporahub-plan-steps.md).")
    parser.add_argument("--data", required=True, help="kořen dat aplikace (složka s registry.sqlite)")
    parser.add_argument("--project", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--apply", action="store_true", help="založit návrhy (bez něj jen report)")
    args = parser.parse_args(argv)
    from backend.canvas.canvas_service import CanvasService

    service = CanvasService(Path(args.data))
    try:
        result = migrate(service, args.project, args.workspace, dry_run=not args.apply)
    finally:
        service.close()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
