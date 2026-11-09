"""Finite Canvas capability CLI; scope and author come from the Heart runtime."""
import json
from pathlib import Path
from urllib.parse import quote

ROOT = "/api/brain/canvas"
FILE_CAPABILITIES = frozenset({"node_routes.upload_material", "site_admin_routes.asset_upload",
                               "site_admin_routes.font_upload", "canvas_routes.save_drawing_file"})


def parser(sub):
    command = sub.add_parser("canvas", help="Discover, describe and invoke scoped native Canvas capabilities",
        epilog='Read a saved graph proposal: canvas describe opora_graph_routes.read; then canvas invoke '
        'opora_graph_routes.read --file INPUT.json where INPUT.json is {"identifier":"PROPOSAL_ID"}. '
        'The response result includes latestProposalId/supersedes when present and contentInputs.researchEvidenceByNode. '
        'Reads need neither --request-id nor proposal --accept. Scope comes from the Heart runtime.')
    actions = command.add_subparsers(dest="action", required=True)
    actions.add_parser("discover")
    describe = actions.add_parser("describe")
    describe.add_argument("capability")
    invoke = actions.add_parser("invoke")
    invoke.add_argument("capability")
    invoke.add_argument("--file", required=True, help="JSON input object; never include scope or actor")
    invoke.add_argument("--request-id", help="Stable native write replay key; preserve the exact input on retry")


def run(args, tool):
    scope = tool.scope()
    if args.action == "discover":
        return tool.call("GET", ROOT + "/capabilities", query=scope)
    if args.action == "describe":
        return tool.call("GET", ROOT + "/capabilities/" + quote(args.capability, safe=""), query=scope)
    if args.action != "invoke":
        raise tool.Failure({"code": "canvas_action", "error": "Unknown Canvas command."})
    try:
        limit = (140 * 1024 * 1024 if args.capability == 'site_admin_routes.proposal_create'
                 else 14_500_000 if args.capability in FILE_CAPABILITIES else 2_000_000)
        with Path(args.file).open("rb") as source:
            raw = source.read(limit + 1)
        if len(raw) > limit:
            raise ValueError(f"Capability input exceeds {limit} bytes.")
        data = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data, dict) or set(data) & {"project", "workspace", "actor", "by", "requestId", "capability"}:
            raise ValueError("Expected input object without scope, author or envelope fields.")
    except (OSError, UnicodeError, ValueError) as error:
        raise tool.Failure({"code": "canvas_input", "error": str(error)}) from error
    body = {**scope, "capability": args.capability, "input": data}
    if args.request_id is not None:
        body["requestId"] = args.request_id
    return tool.call("POST", ROOT + "/invoke", body)
