# Tlačítka webu

Část „Tlačítka webu“ Správy webu podle `image.png` (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §0 bod 3, §2) nad `settings.buttons` a `settings.customCss.button`. Backend: `backend/project/site_admin/buttons.py` a `custom_css.py` (validace, `--btn-*`, sanitizace, poznámky přístupnosti).

- `components/ButtonsSection.tsx` (rodič dílku): varianty, náhled, styl varianty, záložky stavů Tlačítko / Hover / Active / Focus / Disabled, vlastní CSS a velikosti. Změnu hlásí jako `{buttons, customCss}`; ukládá `SiteAdmin`. Odebraná varianta bere s sebou i své vlastní CSS (jinak 422).
- `components/VariantList.tsx`: štítky variant, odebrání, přidání podle jména; prázdný systém nabídne předvolby primary, secondary, outline, ghost, link.
- `components/StateEditor.tsx` + `StateDetails.tsx`: pozadí (barva nebo přechod), barva písma, šířka, zaoblení (předvolby a vlastní), stín, font, rámeček, focus ring (jen Focus) a přechod. Mimo „Tlačítko“ je prázdné pole zděděné.
- `components/GradientEditor.tsx`: úhel a 2–8 zastávek. `components/SizesEditor.tsx`: sm / md / lg.
- `components/ButtonsPreview.tsx`: náhled v `.ds-scope.ds-web` nad uloženým `components.css` (bez vrstvy custom), rozepsanými tlačítky a rozepsaným vlastním CSS; stavy vynucené třídou `ds-btn--is-<stav>`, přepínač „Omezit pohyb“.
- `components/CustomCssEditor.tsx`: textarea s čísly řádků, chyba náhledu a chyba serveru 422 (`{message, path, line, reason}`) na řádku, poznámky serveru k variantě.
- `logic/button-model.ts` (+ test): tvar, předvolby, přidání a odebrání, úprava pole stavu, zděděný stav, poznámky varianty.
- `logic/button-gradient.ts` (+ test), `logic/button-css.ts` (+ test, `--btn-*` jako server), `logic/custom-css-preview.ts` (+ test, přepis `:scope`, `@keyframes` a url jako server, odmítnutí s řádkem).
