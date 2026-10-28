# decision: layer 2 of the brain

This is the second layer of the brain, the decision model. It asks JEV (TypeSafe) for typed answers (`choice` / `score`
/ `noul`) and never writes text. It decides who has to deal with an event, so the heart only wakes for judgement.

Planned modules (H3):
- `gatekeeper.py`: maps an event to `auto` | `heart` | `human` | `none`.
- `commit_match.py`: matches a commit without an `Opora-Node` trailer to a card (`score`).
- `sources.py`: picks the sources for the heart (moved from `claude_code/assistant/router.py` and `rlm_rank.py`).

Rule: any JEV failure answers `None` and the layer above falls back to determinism. Nothing here imports `heart`.
