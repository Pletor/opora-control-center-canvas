# Patička webu

Část „Patička webu“ ve skupině Vzhled Správy webu (`image9.png`) nad `settings.footer`. Backend a styl: `backend/project/site_admin/site_chrome.py` (`.ds-footer` v `components.css`).

- `components/FooterSection.tsx` (rodič dílku): rozvržení (sloupce, jeden řádek, na střed), odkaz „Nastavení cookies“ (odvolání souhlasu), právní řádek s `{rok}`, sloupce odkazů (nejvýš 6 × 12, `LinkListEditor` ze `site-fields/`) a sociální sítě (https, nejvýš 12). Celou patičku hlásí `onChange`; ukládá `SiteAdmin`.
- `components/FooterPreview.tsx`: výřez webu (`ds-preview/components/WebStage.tsx`) s koncem stránky a patičkou.
- `logic/footer.ts` (+ test): tvar, BEM třída, právní řádek s rokem, kontrola sítí a rada jako server.
