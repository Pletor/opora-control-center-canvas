Podněty k dalšímu vývoji (záložka Podněty v detailu uzlu): stav uzlu `ideas` z Desktop v3 — ne-blokující nálezy review, kritiků a lidí. Review a kritik selhávají jen na blokátor (MVP, proces, data, bezpečnost, regrese); vše ostatní projde a odloží se sem jako podnět (`agent-output.output.ideas`, bez duplicit podle textu, `backend/editor/agent_memory/card_ideas.py`).

- `logic/ideas-model.ts` — typ `CardIdea`, popisky zdroje, počet otevřených (odznak na záložce i na kartě plátna), řazení a zásahy člověka `setIdeaStatus` / `removeIdea`.
- `components/IdeasPanel.tsx` — seznam se zaškrtávátkem (hotovo / vrátit) a smazáním odškrtnutého. Dílek nic neukládá; rodič (App) zapisuje přes `desktop.mutate(...)`. Agent podnět odškrtnout ani smazat nesmí (server 403).
- Styl `styles/ideas.css` v BEM. Kontrakt: `docs/karta-pro-agenty.md` → Pipeline karty, Podněty k dalšímu vývoji.
