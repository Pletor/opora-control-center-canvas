Editor globálního nastavení a designu webu (`settings.site`, docs/navrhy/2026-11-03-platno-2-zamer-stranky.md §7) na stránce Projekt.

- `components/SiteSettingsCard.tsx` – čtyři sbalené skupiny SEO, Právní, E-mail a Design; dostane `site` a změnu hlásí `onChange`. Ukládá rodič `ProjectHome` jedním tlačítkem s ostatním nastavením a revizí.
- `logic/site-settings.ts` – pole skupin se stropy znaků (stejné drží server v `backend/canvas/site_settings.py`), čtení a změna pole podle cesty.
- Tajemství (heslo SMTP) sem nepatří; pole, které vypadá jako heslo nebo token, server odmítne.
- Stránka smí přebít `seo` a `design.header` / `design.footer` ve svém `site` na plátně; tady se edituje jen nastavení celého webu.
