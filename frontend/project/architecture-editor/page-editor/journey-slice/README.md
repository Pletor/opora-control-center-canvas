# Úsek cesty zákazníka

Pás mezi pruhem navigace a plátnem Editoru stránky (návrh `docs/cesta-zakaznika-a-brief.md` §5.1): co se od aktivní stránky na cestě zákazníka očekává a jak na sebe stránky navazují. Cesty se tu jen čtou; zakládají a mění se v trychtýři na Mapě domény, sekce v Detailu prvku (záložka Stránka).

- `components/JourneySlice.tsx` skládá hlavičku (název cesty, při více cestách přepínač „cesta · krok“, přerušená cesta varovně, **Upravit cestu**), `SliceRow` a `SectionStrip`. Stránka mimo cesty má jen tichou větu s odkazem na Mapu domény.
- `components/SliceRow.tsx`: **odkud** (předchozí krok: role + stránka, pod tím signál `via` jako věta, odbočka, „chybí vazba“) → **tato stránka** (krok N/M, role, Posun, Námitka; pod tím Pro: aktér, A ▸ / B ▸ na jeden řádek) → **kam** (další kroky včetně odboček, každý se svým signálem). Soused se stránkou v mapě je tlačítko, které přepne rozsah editoru; Menu a zmizelá stránka odkazem nejsou.
- `components/SectionStrip.tsx`: sekce stránky (role · název · čím posouvá) s počtem komponent, které je realizují (`card.section`); sekce bez komponenty je čárkovaná s „⚠ 0“. Klik vybere stránku v Detailu prvku (`PageEditor` sloupec Detailu znovu otevře, aby začal záložkou Stránka).
- `logic/page-slice.ts` (test vedle): `pageSlices(site, pageId, nodes, derived)` – kroky všech cest domény na stránce, předchozí krok (`previousStepId`, i odbočka `after`), další kroky (ty, které na krok navazují), signál (`stepSignal`) a nerealizovaný přechod z odvození backendu (`derivedStepState`); `sectionChips(graph, pageId)` – počet komponent, jejichž nejbližší stránka je tato (podstránka se nepočítá).
- Data dodává `PageEditor` (cesty z `domain.site.journeys`, `derivedJourneys` od `ArchitectureEditor`); hlášení nahoru: `onOpenPage`, `onOpenJourneys(journeyId | null)` (rodič otevře Mapu domény a jednorázově editor té cesty v `CustomerJourneys`), `onSelectPage`. Nic neukládá.
- `styles/journey-slice.css`, předpona `journey-slice__`.
