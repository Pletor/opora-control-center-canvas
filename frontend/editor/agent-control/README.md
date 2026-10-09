# Agent control – záložka Kód

Kód je třetí záložka sekce Agenti v pravém panelu (`AgentNavbar`). Volá přímo HTTP kontrakty LSP (`/api/code-intelligence/*`) a lokálního sémantického hledání (`/api/semantic-search/*`); nic neukládá a nespouští žádný externí proces.

`AgentControlPanel` dostává projekt, pracovní prostor a vybranou kartu v props; pozdní odpověď pro jinou kartu zahodí (`logic/code-query.ts`). `LspControl` a `SemanticQuery` jsou dílky s vlastním formulářem, klíčované podle karty.
