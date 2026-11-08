"""Scoped CLI calls for native task proposals and ticket feedback research."""
import json
from pathlib import Path
from urllib.parse import quote

ACTIONS = ("reviews", "tasks", "task-status", "reconcile", "ticket-branch", "ticket-answer")


def run(args, tool):
    scope = tool.scope()
    if args.action == "reviews":
        return tool.call("GET", "/api/research/decision-reviews", query={**scope, "decisionId": args.decision})
    if args.action in ("ticket-branch", "ticket-answer"):
        body = {**scope, "ticketId": args.ticket, "feedbackId": args.feedback}
        if args.action == "ticket-answer":
            body.update(cardId=args.card, revision=args.revision, text=args.text)
        return tool.call("POST", "/api/research/tickets/" + ("branch" if args.action == "ticket-branch" else "answer"), body)
    path = "/api/research/decision-reviews/" + quote(args.review, safe="")
    if args.action == "task-status":
        return tool.call("GET", path + "/tasks", query=scope)
    if args.action == "reconcile":
        return tool.call("POST", path + "/reconcile", scope)
    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or set(data) != {"tasks"}:
            raise ValueError("Soubor musí obsahovat pouze tasks; scope určuje prostředí srdce.")
    except (OSError, ValueError) as error:
        raise tool.Failure({"code": "research_tasks_file", "error": str(error)}) from error
    return tool.call("POST", path + "/tasks", {**data, **scope})
