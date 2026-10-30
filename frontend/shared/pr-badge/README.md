# pr-badge

Odznak PR karty v barvách GitHubu: fialový „Sloučeno · PR #N“ (karta ještě není uzavřená), zelený „PR #N otevřené“,
červený „PR #N zavřené bez sloučení“. Uzavřená karta (`done.confirmed`) odznak nemá.

- `logic/pr-badge.ts` — `prBadge(stage, reason, link, closed) → {tone, label} | null` z `cards[].pr` agent-state
  (`docs/oporahub-agent-state.md`); starší server bez `pr` dostane odznak bez čísla podle etapy. Test vedle.
- `components/PrBadge.tsx` — kreslí hotový odznak (`data-oh-pr-state`).
- `styles/pr-badge.css` — blok `pr-badge`; barvy z tokenů `--pr-open`, `--pr-merged`, `--pr-closed`
  (`frontend/design-tokens/styles/theme-tokens.css`, světlý i tmavý režim).

Kreslí ho tvář karty na plátně (`editor/canvas/card-face`) a fronta „Rozhodnutí pro tebe“ ve Velínu
(`editor/control-tower`). Odznak jen ukazuje, nic nezapisuje.
