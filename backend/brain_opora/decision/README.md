# decision: layer 2 of the brain

This is the second layer of the brain, the decision model. It asks JEV (TypeSafe) for typed answers (`choice` / `score`
/ `noul`) and never writes text. It decides who has to deal with an event, so the heart only wakes for judgement.

Present modules:
- `sources.py`: ranks canvas sections against a query with one JEV `choice` call (`rank`, moved from
  `claude_code/assistant/rlm_rank.py` in H2b2a). The client comes injected; without a key or on failure it answers
  `{status: "unavailable"}`. Route `POST /api/rlm/rank` (`backend/api/editor/rlm_routes.py`, loopback only).

Planned modules (H3):
- `gatekeeper.py`: maps an event to `auto` | `heart` | `human` | `none`.
- `commit_match.py`: matches a commit without an `Opora-Node` trailer to a card (`score`).
- `sources.py` also picks the sources for the heart (taking over the route hint of `claude_code/assistant/router.py`).

Rule: any JEV failure answers `None` and the layer above falls back to determinism. Nothing here imports `heart`.
