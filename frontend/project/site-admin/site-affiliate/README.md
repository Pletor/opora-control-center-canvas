# Affiliate webu

Část „Affiliate“ ve skupině Nastavení Správy webu (`image9.png`) nad `settings.affiliate`. Backend: `backend/project/site_admin/site_settings.py`.

- `components/AffiliateSection.tsx` (rodič dílku): zapnutí, parametr odkazu (`ref`), platnost cookie 1–365 dní, atribuce (poslední / první klik), upozornění pro návštěvníky a programy (jméno, https adresa, provize, kód), nejvýš 50. Vpravo ukázkový odkaz partnera a varování, když cookie lišta nemá kategorii Marketing. Celý nový Affiliate hlásí `onChange`; ukládá `SiteAdmin`.
- `logic/affiliate.ts` (+ test): tvar, kontrola parametru a programu jako server, odkaz partnera, věta o atribuci.
