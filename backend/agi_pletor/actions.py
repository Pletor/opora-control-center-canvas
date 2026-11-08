"""Deterministická kontrola akcí z odpovědi modelu Pletora: model navrhuje, backend rozhoduje.

Povolené jsou jen `heart_message`, `vault_note`, `heart_question`, `heart_question_close` a `heart_escalation_answer`
s neprázdným textem do `TEXT_LIMIT` znaků, nejvýš `MAX_ACTIONS`; `heart_escalation_answer` nese navíc neprázdné `ticketId`.
Cokoli jiného (neznámý typ, přes limit, prázdný text) se nevykoná a vrátí s `ok: false` a důvodem.
"""
TYPES = ("heart_message", "vault_note", "heart_question", "heart_question_close", "heart_escalation_answer")
TICKET_LIMIT = 100
MAX_ACTIONS = 3
TEXT_LIMIT = 8000  # stejný strop jako zpráva srdci (`heart_routes.TEXT_LIMIT`)


def _problem(index, kind, text, ticket=None):
    if index >= MAX_ACTIONS:
        return f"Přes limit {MAX_ACTIONS} akcí na odpověď."
    if kind not in TYPES:
        return "Neznámý typ akce."
    if not isinstance(text, str) or not text.strip() or len(text) > TEXT_LIMIT or "\0" in text:
        return f"Text akce je neprázdný text do {TEXT_LIMIT} znaků."
    if kind == "heart_escalation_answer" and not (isinstance(ticket, str) and ticket.strip() and len(ticket) <= TICKET_LIMIT):
        return "ticketId je neprázdné ID otázky srdce (gt_…)."
    return None


def validate(raw):
    """`[(akce, problém | None)]` z pole `actions` modelu; akce je `{type, text}` (+ `ticketId` u odpovědi na eskalaci).
    Nepole = žádné akce."""
    if not isinstance(raw, list):
        return []
    checked = []
    for index, item in enumerate(raw):
        item = item if isinstance(item, dict) else {}
        kind, text = item.get("type"), item.get("text")
        problem = _problem(index, kind, text, item.get("ticketId"))
        action = {"type": str(kind)[:40], "text": text.strip() if problem is None else str(text or "")[:500]}
        if kind == "heart_escalation_answer":
            action["ticketId"] = str(item.get("ticketId") or "").strip()[:TICKET_LIMIT]
        checked.append((action, problem))
    return checked
