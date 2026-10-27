# Detail Studia

Panel vpravo jako Inspector v TechViz; ve Skutečnosti jen čtení (`docs/studio.md` §3). Bez výběru ukazuje otevřenou úroveň (u ní všechny vazby úrovně), s výběrem kartu.

- `components/StudioDetail.tsx` – identita (druh, název, adresa, stav, souhrn), tlačítko „Otevřít v Editoru stránky“ / „Otevřít mapu domény“ (`onOpenEditor(params)`), účel.
- `components/DetailSections.tsx` – vazby, díry mapy (karty a všeho pod ní) a cesty zákazníka s odznakem ověření (sdílená logika `domain-map/logic/journey-verification.ts`).
- `logic/detail-model.ts` – hotová data panelu.
- `styles/studio-detail.css`, blok `studio-detail`.
