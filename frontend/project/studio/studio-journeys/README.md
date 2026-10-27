# Cesty zákazníka ve Studiu

Pás pod plátnem na úrovni domény (dá se sbalit). Přesunuto z pohledu Studio na mapě domény (etapa 9, `docs/architektura-pro-agenty.md` §7): jedna cesta = vodorovná dráha se zastávkami (stránky kroků) a přechody obarvenými podle posledního ověření (`lastRun`, `docs/brana-cesty.md` §4).

- `components/StudioJourneys.tsx` – pás a jeho sbalení (stav drží rodič).
- `components/StudioLane.tsx` – dráha: název, odznak ověření (`JourneyBadge.tsx`, sdílená logika `journey-verification.ts`), proměna A → B, zastávky; klik na zastávku hlásí stránku (`onOpen`), Studio ji vybere na plátně.
- `components/StudioTransition.tsx` – přechod: signál `via`, stav (prošel, neprošel, zastaralé, neověřeno), realizace na mapě.
- `logic/studio-lanes.ts` (test vedle): `transitionState`, `studioLanes`, `TRANSITION_TEXT`.
- `styles/studio-journeys.css`, blok `studio-journeys`.
