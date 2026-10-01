Panel Asistent: chat s Claude Code přímo v OPOŘE (kontrakt `docs/asistent.md`, fáze 1: čti a naváděj).

- `components/AssistantButton.tsx`: tlačítko v pravém rohu horní lišty.
- `components/AssistantPanel.tsx`: rodič, přes `useAssistant` drží spojení a konverzaci, skládá dílky `SessionTabs`, `MessageList` (s `ToolCallRow`) a `Composer`.
- `logic/assistant-events.ts`: čistý reducer událostí SSE a zpracování přepisu (test `assistant-events.test.ts`).
- `logic/assistant-api.ts`: volání `/api/assistant/*`. `logic/use-assistant.ts`: React vazba (přepis, pak EventSource od `lastSeq`).
- `logic/assistant-prefs.ts`: výchozí model, jednou pro aplikaci (`localStorage` klíč `opora:assistant:v1`), nikdy per projekt.
- Kontext plátna (projekt, workspace, vrstva, výběr, prostředí) dodá App; panel ho ke každé zprávě přiloží.
