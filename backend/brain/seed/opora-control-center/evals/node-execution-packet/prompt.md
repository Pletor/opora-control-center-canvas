---
name: node-execution-packet
tags: [execution, scope]
runs: 1
max_turns: 4
timeout_seconds: 180
model: haiku
allowed_tools: [Skill, Read, Glob]
---
Use the opora-control-center skill. Read its supported read-client commands if needed. Do not execute shell or network requests.

Project ample, workspace feature_login, node login: obtain the node's execution briefing, assignment and local work packet. This request is about the node's implementation work, not its thematic research sources. The sibling tenant node is unrelated. OPORA_BASE_URL is privately configured.

Return exactly one executable command using the existing scripts/opora_read.py with explicit project, workspace and node. A shell command or a Python subprocess call with a literal argv list is supported. Return only a code block. Never include credential values, mutations or project discovery.
