# heart: layer 3 of the brain

This is the third layer of the brain, the resident model of a project. It is Claude Code under the subscription, with
Haiku as the main model and Opus as the advisor. While OPORA runs on localhost it sleeps, and no process runs. A batch
of events or a human message wakes it up. It is the only writer of the canvas: it plans, writes tasks for workers and
answers their requests. It never writes application code.

Planned modules (H2, H2b):
- `supervisor.py`: sleep and wake-up, 60 s batches, daily caps, `rate_limit_event`.
- `command.py`: builds the CLI (`--model haiku --advisor opus`, stream-json, the wall settings, no `ANTHROPIC_API_KEY`).
- `process.py`: the process inside a Windows job (moved from `claude_code/assistant/session_process.py`).
- `stream.py`: maps stream-json to events (moved from `claude_code/assistant/stream.py` and `event_log.py`).
- `session.py`: session id, resume, and rotation above 60k tokens of context.
- `prompt.md`: the heart's role, when to consult the advisor, and what it must not do.
- `opora_heart.py`: the heart's only tool. Each intent is one call.
- `human_channel.py`: messages from the assistant panel, which take priority over workers and queue during a running turn.

Rule: the heart writes to OPORA only through `opora_heart.py`, with its role token.
