# Hlavička webu

Část „Hlavička webu“ ve skupině Vzhled Správy webu (`image9.png`) nad `settings.header`. Backend a styl: `backend/project/site_admin/site_chrome.py` (`.ds-header` v `components.css`).

- `components/HeaderSection.tsx` (rodič dílku): logo z Assets a jeho alternativní text, rozvržení (klasické, na střed, kompaktní), přilepení, zdroj menu (hlavní stránky z mapy domény / ruční), odkazy menu (`LinkListEditor` ze `site-fields/`, nejvýš 12) a CTA (text, stránka nebo URL, varianta z Tlačítek webu). Celou hlavičku hlásí `onChange`; ukládá `SiteAdmin`.
- `components/HeaderPreview.tsx`: výřez webu (`ds-preview/components/WebStage.tsx`, `.ds-scope.ds-web`) s hlavičkou a kusem stránky; menu `source:pages` ukazuje zástupné stránky.
- `logic/header.ts` (+ test): tvar, položky menu náhledu, BEM třídy, CTA a jeho kontrola jako server.
