# SEO webu

Část „SEO“ ve skupině Nastavení Správy webu (`image9.png`, kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2) nad `settings.seo`. Backend a pravidla: `backend/project/site_admin/site_settings.py` (tabulka polí v jeho README).

- `components/SeoSection.tsx` (rodič dílku): titulek a popis (šablona s `%s`, název webu, jazyk, popis s počítadlem 160 znaků), indexování (robots index/follow/noarchive/nosnippet, náhled obrázku, délka úryvku, kanonický host, sitemap), sdílení (og:image z Assets nebo https, og:type, Twitter karta a účet) a JSON-LD se vzorem WebSite + Organization. Celé nové SEO hlásí `onChange`; ukládá `SiteAdmin`.
- `components/SeoPreview.tsx`: výsledek vyhledávání a karta sdílení s ukázkovou stránkou (titulek a cesta jdou přepsat).
- `logic/seo.ts` (+ test): tvar a výchozí hodnoty, titulek podle šablony, ořez jako ve výsledcích, obsah `robots`, kontrola šablony, hostu a JSON-LD stejně jako server, vzor JSON-LD.
