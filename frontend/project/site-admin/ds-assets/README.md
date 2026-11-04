# Assets design systému

Sekce Assets Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §3): `design.assetGroups[{name, readme, files[{name, blob, size, type}]}]`.

- `components/AssetsSection.tsx`: „+ New set“, drop kamkoli do sekce (do první skupiny, bez skupin do nové „New set“), chyby souborů, které server nepřijme, a stav nahrávání.
- `components/AssetGroupCard.tsx`: jméno skupiny (přejmenovat jde jen prázdnou, soubor má skupinu v cestě `assets/<skupina>/<soubor>`), „Nahrát soubory“, drop na kartu, dlaždice s náhledem obrázků a SVG jen přes `<img>` (`GET /api/site-admin/assets/…`), README skupiny, odebrání souboru a skupiny.
- `logic/assets.ts` (+ test): jméno nové skupiny, gramatika jmen a typů a limity jako server (10 MB, SVG 2 MB), zápis nahraného záznamu (stejné jméno přepíše, chybějící skupina vznikne), odebrání, přejmenování.

Nahrává rodič (`use-site-admin.uploadAssets` → `POST /api/site-admin/assets`) a záznam zapíše do rozepsaného dokumentu; uloží až Uložit. **Odebrání souboru nebo skupiny mění jen dokument, soubor na disku zůstane** (nejmenší bezpečná cesta, popis v `backend/project/site_admin/README.md`).
