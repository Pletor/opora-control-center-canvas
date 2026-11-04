# Návrh srdce ve Správě webu

Pruh „Srdce navrhuje změnu“ pod hlavičkou Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §4). Srdce dokument nezapisuje: `opora_heart.py site propose` uloží návrh (`backend/project/site_admin/proposals.py`) a člověk ho tady přijme, nebo zamítne.

- `components/SiteProposals.tsx`: poznámka srdce, revize, ze které návrh vyšel, rozdíl po polích (cesta · předtím · potom, nejvýš 12 řádků a „… a další“) a tlačítka Přijmout / Zamítnout. Rozhodnutí hlásí nahoru.
- `logic/site-proposals.ts` (+ test): čtení čekajícího návrhu, `POST …/proposals/{id}/accept` nad revizí stránky a `…/reject`, texty rozdílu.
- `logic/use-site-proposals.ts`: stav pro rodiče `SiteAdmin`; po přijetí rodič načte dokument znovu. Neuložené změny na stránce rodič před přijetím potvrdí. Zastaralý návrh (dokument se mezitím změnil) je 409 a srdce musí navrhnout znovu.
