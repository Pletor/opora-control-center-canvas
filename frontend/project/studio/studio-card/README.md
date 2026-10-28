# Karta Studia

`components/StudioCard.tsx` – uzel React Flow 260 × 150 ve vzhledu TechViz: hlavička s ikonou druhu, názvem a štítkem stavu, podtitulek (host domény, cesta stránky, role sekce, technologie komponenty), účel, pata se souhrnem („4/7 stojí · 1 se staví“), odznakem „cíl z MODELu“ (na kartu váže uzel modelu domény, `docs/studio.md` §4a), odznakem děr, odznakem strážců (`studio-guards/`, součet nálezů karty a potomků) a počtem dětí. Porty (`Handle`) vstup vlevo, výstup vpravo, nepřipojitelné. Rám nese stav: plán, staví se (jemné dýchání rámu, vypnuté při `prefers-reduced-motion`), hotovo, ověřeno, díra. `components/StudioGroup.tsx` – rám skupiny „bez sekce“.

- `logic/card-view.ts` – co karta ukáže (popisky stavů a druhů, ikona, souhrn, podtitulek).
- `logic/model-targets.ts` – id karet, na které váže uzel modelu domény (`binding.nodeId`); `logic/use-model-targets.ts` je načte ze `GET /api/studio/model` jen ve Skutečnosti, bez katalogu a simulace MODELu (ty zůstávají v líném chunku).
- `logic/studio-icons.ts` – ikony Lucide převzaté z prototypu (`icons.mjs`) jako data SVG; licence v `LUCIDE-LICENSE` (ISC, ikona `monitor` z Feather pod MIT).
- `styles/studio-card.css`, bloky `studio-card` a `studio-group`.
