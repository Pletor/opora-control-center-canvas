# Cookie lišta (GDPR)

Část „Cookie lišta“ ve skupině GDPR Správy webu (`image9.png`) nad `settings.gdpr` (`cookieBar` a `contact`). Backend: `backend/project/site_admin/site_settings.py`, styl `.ds-cookie-bar` a `.ds-cookie-reopen` v `components.css` (`site_chrome.py`).

Pravidla podle ePrivacy čl. 5 odst. 3, EDPB Guidelines 05/2020, zprávy EDPB Cookie Banner Taskforce (2023) a ÚOOÚ: nezbytné cookies jsou vždy zapnuté a souhlas nepotřebují; ostatní kategorie má návštěvník **předem vypnuté** (pole pro předvyplnění neexistuje); Přijmout a Odmítnout jsou na první vrstvě se stejnou třídou; zavření lišty není souhlas; souhlas jde kdykoli změnit (plovoucí tlačítko, odkaz v patičce) a po zvýšení verze se web ptá znovu.

- `components/CookieBarSection.tsx` (rodič dílku): zapnutí, umístění, nadpis a text, popisky tlačítek, zásady (stránka nebo URL), platnost souhlasu 1–730 dní, plovoucí tlačítko, verze a kontakt správce. Celé GDPR hlásí `onChange`; ukládá `SiteAdmin`.
- `components/CategoriesEditor.tsx`: kategorie necessary / preferences / analytics / marketing s vlastním názvem a popisem.
- `components/CookieBarPreview.tsx`: výřez webu s funkční lištou a přepínačem kategorií (nic neukládá).
- `logic/cookie-bar.ts` (+ test): tvar, výchozí texty kategorií, zapnutí kategorie, výchozí odmítnutí, přepínání, BEM třída a rady jako server.
