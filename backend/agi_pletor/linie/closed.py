"""Uzavření řádku po začlenění (docs/navrhy/2026-11-06-linie-rebrand.md §10.2): čistě nad daty boardu.

Řádek větve je uzavřený, když má aspoň jednu kuličku a všechny jsou začleněné (osa i stav kuličky `merged`; stav
`merged` už vylučuje commit po začlenění), nemá živý pruh worktree, všechny jeho řádky-děti jsou uzavřené (kaskáda
zdola) a špička větve je předkem špičky cíle. Nový commit na větvi nebo nová nezačleněná kulička uzavření ruší.
Git je jen jedna otázka `contains(branch, sha, target)`, volaná až po datových podmínkách (git na Windows je pomalý).
"""
from backend.agi_pletor.linie import rows as rows_mod
from backend.agi_pletor.linie import tree


def closed_rows(rows, balls, worktrees, contains):
    """`{rowId: {at, sha, target, by, balls} | None}`. `contains(branch, sha, target) -> bool`: je špička `branch`
    (bez refu `sha` posledního merge) předkem špičky `target`; nedostupný git = False, tedy neuzavřeno."""
    heads = {row["branch"] for row in rows if row.get("branch")}
    live = {w.get("branch") for w in worktrees if (w.get("binding") or {}).get("live")} | {
        w["binding"].get("ticketId") for w in worktrees if (w.get("binding") or {}).get("live")}
    kids = {}
    for row in rows:
        if row.get("branch") and not row.get("planned"):  # řádky bez větve na konci nejsou děti
            kids.setdefault(tree.parent(row["branch"], heads), []).append(row["branch"])
    found, by_branch = {}, {}
    for row in reversed(rows):  # depth-first pořadí pozpátku: děti před rodičem
        found[row["id"]] = None
        branch = row.get("branch")
        if not branch or row.get("planned") or row.get("fixed") or branch in rows_mod.MAPPING:
            continue
        mine = [ball for ball in balls if ball["rowId"] == row["id"]]
        integ = [ball["axes"]["integration"] for ball in mine]
        if (not mine or any(ball.get("state") != "merged" for ball in mine)
                or any(axis.get("state") != "merged" for axis in integ)
                or branch in live or any(ball["ticketId"] in live for ball in mine)
                or any(by_branch.get(kid) is None for kid in kids.get(branch, []))):
            continue
        last = max(integ, key=lambda axis: axis.get("at") or "")
        target = tree.parent(branch, heads)
        # OP-A064F3.1: špička v cíli kryje i nový commit po merge; squash ji v cíli nemá, důkazem jsou začleněné kuličky
        if last.get("mode") != "squash" and not contains(branch, last.get("sha"), target):
            continue
        found[row["id"]] = by_branch[branch] = {"at": last.get("at"), "sha": last.get("sha"), "target": target,
                                                "by": "merge", "balls": len(mine)}
    return found
