# decision: layer 2 of the brain

This is the second layer of the brain, the decision model. It asks JEV (TypeSafe) for typed answers (`choice` / `score`
/ `noul`) and never writes text. It decides who has to deal with an event, so the heart only wakes for judgement.

Present modules:
- `sources.py`: ranks canvas sections against a query with one JEV `choice` call (`rank`, moved from
  the old assistant in H2b2a). The client comes injected; without a key or on failure it answers
  `{status: "unavailable"}`. Route `POST /api/rlm/rank` (`backend/api/editor/rlm_routes.py`, loopback only).
- `intake.py` (intake gate slice 2, `docs/navrhy/2026-10-30-vstupni-brana.md` §4, §7): classifies a `pending` intake
  entry with one JEV call and two `choice` questions: the verdict over `done | extends_in_progress | fix_for_milestone |
  changes_intent | later_extension | needs_info` (fixed criteria text) and the area over canvas nodes `kind: area`
  (id → name; left out when there are none). The sentence goes only as `state`, never into instructions.
  `classify_pending` runs in the heart batch right before the message is built (node `decision.jev`, `backend/flow/catalogs/heart/nodes.py`), never in an
  HTTP request: only with the project permission `settings.brain.intake.jev` (default off,
  `determinism/intake_setting.py`), only entries of the current UTC day that JEV was not asked yet, the batch's
  entries first, at most 5 per batch and at most `jevPerDay` (default 200) calls a day, counted as the sum of
  `jev_calls` of entries written that UTC day. Confidence below 0.6, no key, a failure or a hallucinated choice keep
  `pending` (layer `jev`, `jev_calls` 1, so it is not asked again) and the heart decides. A result never overwrites a
  verdict the heart already gave. Any error is logged and the batch goes on unchanged.

Planned modules (H3):
- `gatekeeper.py`: maps an event to `auto` | `heart` | `human` | `none`.
- `commit_match.py`: matches a commit without an `Opora-Node` trailer to a card (`score`).
- `sources.py` also picks the sources for the heart (the old assistant's route hint, deleted in H2b2b).

## JEV client and key

- `backend/integrations/typesafe_client.py`: `evaluate(state, questions, *, key, timeout=3.0, post=...)` returns
  `answers` or `None`. No key, an HTTP error (401, 422, 429, 529), a timeout or an invalid answer give `None` and never
  raise. Model `jev-latest`, endpoint `https://api.typesafe.ai/v1/systemone`.
- Provider (`typesafe` | `celeris`) comes from `[jev] provider` in `opora.local.toml` (default `typesafe`; an unknown
  value falls back to `typesafe` with a log warning).
- The key is stored once per app (`app_settings` keys `typesafe.apiKey` / `celeris.apiKey`, fallback env
  `TYPESAFE_API_KEY` / `CELERIS_API_KEY`; a stored key wins). It is read on every call, so a change applies without a
  restart, and it never reaches a `claude` child process.
- Routes (`backend/api/brain_opora/jev_routes.py`, loopback only, 403 through the tunnel):
  - `GET /api/brain/jev` → `{configured, provider, keys: {typesafe, celeris}}` (booleans only);
  - `POST /api/brain/jev/key {key: text | null, provider?}` stores or deletes a key (human only); the key is never
    returned;
  - `GET|POST /api/brain/jev/gate-check {project, provider, allowed}`: permission for the external gate check (write
    by the human only, see `docs/schranka-neurony.md` §7).
- UI: Settings → Jev (`frontend/settings/components/JevKeySetting.tsx`, rules in `frontend/settings/logic/jev-key.ts`):
  a masked field per provider, Save, Delete, status in words only. An env key shows as set and Delete cannot remove it.

## RLM: recursive search

Pattern of [Recursive Language Models](https://arxiv.org/abs/2512.24601): a large context is not put into the prompt.
The canvas is a corpus split into sections (cards); the model peeks at it piece by piece and sends sub-questions to
cheaper calls. No arbitrary code runs.

1. **Corpus as a variable.** `opora_read.py index --project --workspace [--layer]` lists sections without content
   `{id, name, parentId, kind, chars}`. One section is read with `node-brief` / `node-text`; `search` searches across.
2. **Cheap sub-call: ranking via JEV.** `opora_read.py rank --project --workspace --query [--layer] [--top 10]` builds
   candidates from the index (id → name and the first 300 characters of the card text, at most 255) and sends
   `POST /api/rlm/rank {project, workspace, query, candidates: [{id, text}], top}`. The route
   (`backend/api/editor/rlm_routes.py`, loopback only) calls `sources.rank`, which asks JEV `choice` with
   `criteria = {id: text}` and answers `{status: "ok", ranked: [{id, p}]}` sorted by probability, at most `top`.
   Without a key or on a JEV failure it answers `{status: "unavailable"}` and the caller goes on with step 3.
3. **Recursion: subagents.** The root model splits the question by sections or folders and hands each piece to a
   read-only subagent, which returns condensed findings with `file:line` or a card id.

The skill recipe is `.claude/skills/opora-control-center/references/rlm.md`: `index` → `rank` (or `search`) → read only
the best 2–5 sections → split and delegate where that is not enough → answer with source links.

Rule: any JEV failure answers `None` and the layer above falls back to determinism. Nothing here imports `heart`.
