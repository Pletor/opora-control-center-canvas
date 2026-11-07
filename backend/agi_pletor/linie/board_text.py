"""Textový přehled Linie pro agenta (docs/navrhy/2026-11-06-linie-rebrand.md §9 L8b): týž snímek jako `GET /board`.

`render(board, mine=, journal=, open_requests=)` jen čte hotový snímek (žádné čtení gitu ani evidence) a řadí ho jako
obrazovku: Pletor a stáří zdrojů, stanice, „Čeká na člověka“ (`queues.human[]` beze změny pořadí i věty), řádky
s kuličkami a deník. Čisté UTF-8 bez barev; jedna kulička = jeden řádek, aby šla grepovat. Chybějící zdroj je „nevím“.

`mine=<agent>`: snímek nenese práci kuličky, jen vazby pracovních stromů, proto kulička patří agentovi, když ji
`worktrees[].binding` (`ticketId`, `agent`) váže na něj; ostatní kuličky a řádky bez nich v sekci Řádky zmizí.

Uzavřený řádek (`row.closed`, §10.2) je jedna řádka „⊕ název · uzavřeno HH:MM → cíl (N kuliček)“ bez kuliček;
`all=True` ho vypíše celý.
"""
from datetime import datetime

JOURNAL = 20
NOSOURCE = "— (nedostupné)"
SOURCES = (("git", "git"), ("prs", "PR"), ("checks", "kontroly"), ("sessions", "relace"), ("deploy", "nasazení"))


def _plural(n, one, few, many):
    return f"{n} {one if n == 1 else few if 2 <= n <= 4 else many}"


def _count(value, one, few, many):
    return NOSOURCE if value is None else _plural(value, one, few, many)


def _age(then, now):
    try:
        seconds = int((datetime.fromisoformat(now.replace("Z", "+00:00"))
                       - datetime.fromisoformat(then.replace("Z", "+00:00"))).total_seconds())
    except (AttributeError, ValueError):
        return "nevím"
    return f"před {seconds} s" if seconds < 90 else f"před {seconds // 60} min" if seconds < 5400 else f"před {seconds // 3600} h"


def _sources(snapshot):
    built, found = snapshot.get("builtAt"), snapshot.get("sources") or {}
    out = []
    for key, label in SOURCES:
        source = found.get(key) or {}
        age = _age(source.get("verifiedAt"), built) if built else "nevím"
        out.append(f"{label} {age}" if source.get("ok", True) else f"{label} nedostupné (poslední čtení {age})")
    return out


def _journal(events, marks):
    lines = []
    for event in events[-JOURNAL:]:
        refs, data = event.get("refs") or {}, event.get("data") or {}
        bits = [f"krok {data['k']}" if data.get("k") else "", refs.get("env") or "", (refs.get("sha") or "")[:7],
                refs.get("request") or "", data.get("why") or data.get("reason") or ""]
        kind = (event.get("kind") or "").removeprefix("linie.")
        by = event.get("by") or ""
        who = "člověk" if by == "human" else by.removeprefix("agent:") if by.startswith("agent:") else "služba OPORY"
        ticket = refs.get("ticket")
        lines.append(" ".join(filter(None, [event.get("at") or "?", who, kind, " · ".join(b for b in bits if b),
                                           f"[{marks.get(ticket, ticket)}]" if ticket else ""])))
    return lines


def _clock(at):
    try:
        return datetime.fromisoformat(at).astimezone().strftime("%H:%M")  # místní čas jako obrazovka
    except (AttributeError, ValueError):
        return "?"


def render(board, *, mine=None, journal=None, open_requests=None, all=False):  # `?all=1` / `--all`
    balls, queues, snapshot = board.get("balls") or [], board.get("queues") or {}, board.get("snapshot") or {}
    marks = {ball["ticketId"]: ball.get("mark") or ball["ticketId"] for ball in balls}
    human = queues.get("human") or []
    said = f"Na plátně {_plural(len(balls), 'kulička', 'kuličky', 'kuliček')}; " + (
        f"na člověka čeká {_plural(len(human), 'rozhodnutí', 'rozhodnutí', 'rozhodnutí')}." if human else "nic nečeká na člověka.")
    out = [f"Pletor: {said}",
           f"snímek {snapshot.get('builtAt') or 'nevím'} · zdroje: " + ", ".join(_sources(snapshot)),
           "", "Stanice:"]
    plans = queues.get("plansWaiting")
    for label, text in (
            ("Člověk", _count(queues.get("humanDecisions"), "rozhodnutí", "rozhodnutí", "rozhodnutí")),
            ("Pletor", _count(open_requests, "otevřená žádost", "otevřené žádosti", "otevřených žádostí")),
            ("Srdce", _count(plans, "plán", "plány", "plánů")),
            ("Tickety", _count(queues.get("ticketsTodo"), "ticket", "tickety", "ticketů")),
            ("Kancelář", _count(queues.get("officeTasks"), "úkol", "úkoly", "úkolů")),
            ("Git", _count(queues.get("gitQueue"), "PR", "PR", "PR"))):
        out.append(f"  {label}: {text}")
    out += ["", "Čeká na člověka:"]
    out += [f"  {r['order']}. {r.get('mark') or r['ticketId']} {r['title']} · {r['branch']} → {r['target']} · "
            f"{r['state']} · {(r.get('sha') or '')[:7] or '-'} · {r['sentence']}" for r in human] or ["  Nic nečeká na člověka."]
    owned = None if mine is None else {
        (w.get("binding") or {}).get("ticketId") for w in board.get("worktrees") or []
        if (w.get("binding") or {}).get("agent") == mine}
    shown = [b for b in balls if owned is None or b["ticketId"] in owned]
    by_row = {}
    for ball in shown:
        by_row.setdefault(ball["rowId"], []).append(ball)

    def ball_line(ball, indent):
        summary = ball.get("summary") or {}
        return (f"{indent}{ball.get('mark') or ball['ticketId']} {ball['title']} · {summary.get('text') or ball['state']} · "
                f"{ball.get('headSha7') or '-'} · další: {summary.get('next') or '-'}")

    out += ["", "Řádky:" if mine is None else f"Řádky (jen {mine}):"]
    known = {row["id"] for row in board.get("rows") or []}
    for row in board.get("rows") or []:
        if owned is not None and row["id"] not in by_row:
            continue
        pad = "  " * (row.get("depth") or 0)
        shut = None if all else row.get("closed")
        if shut:
            out.append(f"{pad}⊕ {row['name']} · uzavřeno {_clock(shut.get('at'))} → {shut['target']} "
                       f"({_plural(shut['balls'], 'kulička', 'kuličky', 'kuliček')})")
            continue
        out.append(f"{pad}{row['name']}" + (f" [{row['branch']}]" if row.get("branch") else "")
                   + (f" → {row['target']}" if row.get("target") else ""))
        out += [ball_line(ball, pad + "  ") for ball in by_row.get(row["id"], [])]
    loose = [ball for ball in shown if ball["rowId"] not in known]
    if loose:
        out += ["", "Bez řádku:"] + [ball_line(ball, "  ") for ball in loose]
    if journal is not None:
        out += ["", f"Deník (posledních {JOURNAL}):"] + ["  " + line for line in _journal(journal, marks)]
    return "\n".join(out) + "\n"
