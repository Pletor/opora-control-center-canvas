---
name: knowledge-local-context
tags: [knowledge, scope]
runs: 1
max_turns: 4
timeout_seconds: 180
model: haiku
allowed_tools: [Skill, Read, Glob]
---
Use the opora-control-center skill. Inspect its scripts/opora_read.py with Read (locate it with Glob if necessary) to discover the actual supported commands; do not invent an API or command. Do not execute shell/network requests in this evaluation.

You are working in project ample, workspace feature_login, entered scope login. Read only the thematic research context: its local, inherited and explicitly shared research sources and canonical bindings. This is not the node's execution briefing or work packet. The sibling tenant scope is unrelated. OPORA_BASE_URL and OPORA_GATE_TOKEN are already configured privately in the environment. Never print credential values or put a token on the command line.

Return exactly one executable command for the existing read client, with explicit project, workspace and node arguments. A shell command or a Python subprocess call with literal argv is supported. Use a code block. Do not ask for global project discovery or create/copy tasks.
