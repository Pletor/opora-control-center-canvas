# Návrh srdce ve Správě webu

Binární návrh používá stejný pruh a lidské Přijmout / Zamítnout. Seznam příloh ukazuje přidání, nahrazení či
odstranění, MIME, velikost a původní/nový SHA-256. Odkaz stahuje immutable navržený soubor ze scoped
`GET /api/site-admin/proposals/{id}/attachments/{index}?project=…` (attachment, octet-stream, nosniff), nikoli živý soubor.
Stav `pending-attachments` starší runtime nepřijme; dokumentové návrhy zůstávají `pending`.
Přerušené přijetí se zobrazuje i po reloadu s reálným stavem každého cíle. Tlačítko dokončení opakuje stejný
native accept; konflikt s cizí změnou zůstane zablokovaný, Zamítnout nepředstírá rollback již změněných souborů.

Pruh „Srdce navrhuje změnu“ pod hlavičkou Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §4). Srdce dokument nezapisuje: `opora_heart.py site propose` uloží návrh (`backend/project/site_admin/proposals.py`) a člověk ho tady přijme, nebo zamítne.

- `components/SiteProposals.tsx`: poznámka srdce, revize, ze které návrh vyšel, rozdíl po polích (cesta · předtím · potom, nejvýš 12 řádků a „… a další“) a tlačítka Přijmout / Zamítnout. Rozhodnutí hlásí nahoru.
- `logic/site-proposals.ts` (+ test): čtení čekajícího návrhu, `POST …/proposals/{id}/accept` nad revizí stránky a `…/reject`, texty rozdílu.
- `logic/use-site-proposals.ts`: stav pro rodiče `SiteAdmin`; po přijetí rodič načte dokument znovu. Neuložené změny na stránce rodič před přijetím potvrdí. Zastaralý návrh (dokument se mezitím změnil) je 409 a srdce musí navrhnout znovu.
