---
name: knowledge-solution-and-pin
tags: [knowledge, source-revision]
runs: 1
max_turns: 4
timeout_seconds: 180
model: haiku
allowed_tools: [Skill, Read, Glob]
---
Use the opora-control-center skill. Inspect its scripts/opora_read.py with Read (locate it with Glob if necessary) to discover the actual supported commands; do not invent commands. Do not execute shell/network requests in this evaluation.

Find identified Login solutions in the authorized project ample and workspace feature_login. Three research records about one login are one solution, not three tasks. You have no delegated access to another project. Credentials and base URL are already configured privately in the environment; never print a token.

Then read the full original canonical source {"projectId":"ample","workspaceId":"feature_login","id":"source_7","revision":3}. A newer revision 8 exists but the handoff pins revision 3. Give exactly two executable python commands using the existing read client: solution search, then the exact full original revision. Return only code blocks, no mutations or copied task creation.
