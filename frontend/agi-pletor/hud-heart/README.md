Panel Srdce v Pletorovi: na první pohled říká, co Srdce dělá a jestli má člověk čekat, nebo mluvit.
Stav srdce je `GET /api/brain/heart/status` (docs/brain-heart-channel.md §1 bod 3), klient a typy z `frontend/layout/heart-channel/logic/heart-api.ts`.
Data načítá poller Pletora (`hud/logic/pletor-poll.ts`, `heartOn` jen při viditelném HUD nebo okně, 3 s při práci, jinak 5 s); panel jen čte props.

- `components/PletorHeartPanel.tsx`: dílek, `place="hud"` pod readoutem PRJ/MOZEK v kokpitu, `place="window"` menší (3 kroky) nad řádkem otázky v okně. Během práce tiká po vteřině.
- `logic/heart-panel.ts` (test vedle): `heartPanel` vybere stav s předností odpověď připravená > pracuje > fronta > chyba > spí; selhaný dotaz = „Stav srdce nedostupný“. Pracuje: čas od `startedAt`, obvyklá délka z `typicalMs`, co srdce probudilo (`wakeReason` + zkrácený první vstup), posledních 6 kroků `current.steps`. `pollMs` dává rytmus polleru.
- `styles/pletor-heart.css`: blok `pletor-heart`; puls při práci, krátké naskočení a záře u připravené odpovědi, bez animací při `prefers-reduced-motion`.
