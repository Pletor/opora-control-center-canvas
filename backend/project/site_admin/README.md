# Správa webu: dokument a design systém projektu

Backend Správy webu (`docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2, PR S-2, Vzhled a Tlačítka S-4b).
Jeden dokument na projekt: globální nastavení webu (`settings`) a design systém (`design`). Gramatika tokenů je
převzatá z otevřeného formátu `tokens.json` typu Design System, kód typu ne.

- `tokens.py` – gramatika `design.tokens`: jména, barvy a aliasy (bez cyklu, chybějícího cíle, hloubka ≤ 16,
  chybějící téma dědí z prvního), délky, typografie, stíny, vlastní rodiny a limity. Neplatná hodnota se zahodí
  s poznámkou, chyba tvaru je `SiteAdminInvalid` (422).
- `design_system.py` – celý dokument: `settings` (seo, affiliate, email, header, footer, gdpr) se ověřuje podle
  pevného schématu, tajemství se odmítne (jen `secretRef`); `appearance`, `buttons` a `customCss` mají vlastní
  moduly; `design` (readme, sections, components, assetGroups, cover) a `empty()`.
- `appearance.py` – Vzhled (viz níže).
- `buttons.py` – tlačítka: validace, komponentní tokeny `--btn-*` a jejich CSS, poznámky k přístupnosti.
- `custom_css.py` – vlastní CSS tlačítek přes tinycss2 (BSD-3-Clause): allowlist, přepis, `@layer custom`.
- `compile.py` – odvozené soubory: `tokens.css` (rozvržení formátu), `components.css`, `tokens.json` a `README.md`
  (brand book a generovaná sekce „Jak systém použít“ včetně „Tlačítka“).
- `store.py` – `projects/<id>/site/design-system.json` s revizí (409 při jiné), assety
  `site/assets/<skupina>/<soubor>`, fonty `site/fonts/<soubor>`, typ podle prvních bajtů a limity velikosti.
- `button_component.py` – komponenta `Button` jako pohled na `settings.buttons` (viz níže).
- `fixture.py` – zkrácený vzorek systému pro testy.
- Router: `backend/api/project/site_admin_routes.py` (`/api/site-admin…`, včetně `components.css`).

## Komponenty a assety (M2)

`design.components[] = {name, group?, summary?, readme, preview, height}`: jméno podle gramatiky tokenů
(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`, unikátní), README markdown ≤ 200 KB, `preview` HTML fragment ≤ 256 KB, výška
40–4000 (jinak 120 s poznámkou), nejvýš 200 komponent. Server náhled nikdy nespouští, jen ho uloží jako text; stránka
ho ukáže v iframu `sandbox=""` (bez skriptů) s `tokens.css` a `components.css`. Náhled se `<script`, obsluhou `on…=`,
`javascript:`, `&#`, `<iframe>`, `<embed>`, `<object>` nebo `<foreignObject>` je 422 – stejný filtr `UNSAFE_MARKUP`
jako u SVG assetu (`store.UNSAFE_SVG`).

`Button` se needituje: `button_component.component` ho při každém uložení složí z variant Tlačítek webu (náhled všech
variant, velikostí a nedostupného stavu, README s variantami a třídami) a dá ho na první místo; poslaná komponenta
`Button` se zahodí. Bez variant `Button` není.

`design.assetGroups[] = {name, readme, files: [{name, blob: "assets/<skupina>/<soubor>", size, type}]}`; soubor se
nahraje `POST /api/site-admin/assets` a záznam z odpovědi se přidá do skupiny. **Odebrání souboru nebo celé skupiny
z dokumentu soubor na disku nemaže.** Je to nejmenší bezpečná cesta: uložení může skončit 409 nebo 422 a pak by
smazaný soubor chyběl dokumentu, který ho dál drží; nahrání stejného jména do skupiny soubor jen přepíše. Fyzicky maže
jen `DELETE /api/site-admin/assets` (soubory na disku se počítají do limitu 5000). `README.md` systému vypíše komponenty
(summary nebo první věta README) a skupiny assetů s cestami.

## Vzhled: pohled na tokeny, ne druhý zdroj pravdy

Kontrakt říká, že každé pole Vzhledu zapisuje sémantický token nebo typografický styl. Proto `settings.appearance`
nemá vlastní data: server ho při každém čtení spočítá z `design.tokens` a při uložení zapíše změněná pole zpátky do
tokenů. Druhá cesta (samostatná sekce převedená v compile na proměnné) by dala dvě místa pro tutéž barvu odkazu
a editor Colors by ji neviděl. Mapa polí je tabulka `FIELDS`:

| Vzhled | Token |
|---|---|
| `background.color`, `colors.text`, `textInverse`, `link`, `linkHover`, `focus` | barvy `surface`, `ink`, `ink-inverse`, `link`, `link-hover`, `focus` (první téma; ostatní témata zůstanou) |
| `background.pattern.color`, `background.overlay.color`, `lists.color` | barvy `pattern`, `overlay`, `list-marker` |
| `background.image.*`, `pattern.preset`, `pattern.scale`, `overlay.opacity` | rodina `background`: `bg-image`, `bg-size`, `bg-position`, `bg-repeat`, `bg-attachment`, `bg-pattern`, `bg-pattern-scale`, `bg-overlay-opacity` |
| `text.heading.font`, `text.subheading.font`, `text.body.font` | rodiny písma `heading`, `subheading`, `body` |
| `text.subheading.size`, `text.body.size` | styly `subheading`, `body` (skupina „Text“) |
| `headings.h1`–`h6`: `size`, `weight`, `lineHeight`, `letterSpacing` | styly `h1`–`h6` (skupina „Nadpisy“) |
| `lists.marker`, `lists.indent` | rodina `list`: `list-style`, `list-indent` |
| `layout.contentSize`, `wideSize`, `gutter` | rodina `layout`: `layout-content`, `layout-wide`, `layout-gutter` |

Zápis porovnává s pohledem na **uložené** tokeny (`normalize(document, base)`, `store.write` předá uložený
dokument). Pole, které v těle chybí nebo se nezměnilo, token nepřepíše, takže zastaralý pohled neschová úpravu
z Colors. `null` token smaže, u velikosti stylu celý styl. Když se ve stejném uložení změní token i pole Vzhledu,
vyhraje Vzhled. `components.css` z těchto tokenů skládá `@layer base` (`body`, `h1`–`h6`, `a`, `:focus-visible`,
seznamy, `.ds-container`, `.ds-container--wide`, `.ds-inverse`); pravidlo vznikne jen pro token, který existuje.

## Tlačítka

`settings.buttons = {sizes: {sm|md|lg: {paddingX, paddingY, minHeight, fontSize}}, variants: {<slug>: {label?,
preset: solid|outline|ghost|link, states: {default, hover, active, focusVisible, disabled}}}}`. Stav kromě
`default` ukládá jen rozdíl. `components.css` dává `.ds-btn` základ nad proměnnými `--btn-*`, velikost a varianta je
jen přepíšou a stavy (`:hover`, `:active` mimo disabled, `:focus-visible`, `:disabled`/`[aria-disabled="true"]`)
mění jen proměnné. Barva i délka smí být `{token}` → `var(--token)`.

```html
<button class="ds-btn ds-btn--primary" type="button">Objednat</button>
<button class="ds-btn ds-btn--secondary ds-btn--sm" type="button">Víc</button>
<button class="ds-btn ds-btn--ghost ds-btn--lg" type="button" aria-disabled="true">Později</button>
<a class="ds-btn ds-btn--link" href="/kontakt">Kontakt</a>
```

Přístupnost jsou poznámky v `notes`, uložit jde i s nimi: text proti pozadí ≥ 4,5:1 ve stavech default, hover,
active a focusVisible (u gradientu každý konec, průhledné pozadí = barva `surface`; disabled je podle WCAG výjimka),
rámeček a focus ring proti `surface` ≥ 3:1, `minHeight` ≥ 24 px, focus ring vypnutý bez stínu.

## Vlastní CSS

`settings.customCss = {button: {<varianta>: "css"}}`. Uloží se zdroj, jak ho člověk napsal; ověří se při každém
uložení (chyba 422 s `{message, path, line, reason}`) a sanitizovaná verze se skládá až v `components.css`.
Pravidla: at-rules jen `@keyframes`, `@media`, `@supports`, `@container` (vnoření ≤ 3); zakázané `@import`,
`@font-face` a jiné at-rules, `!important`, `expression(`, `behavior`, `-moz-binding`, `javascript:`, `<` (tedy
`</style`, `<!--`), `\` (escapes), vlastní proměnné, vnořená pravidla, `position: fixed`, selektory `html`, `body`,
`:root`, `:host`, `*`; `url()` jen `assets/<skupina>/<soubor>`. Selektor dostane kořen `.ds-btn--<varianta>`
(`:scope` se nahradí), `@keyframes x` se přejmenuje na `ds-btn-<varianta>-x`, vše jde do `@layer custom` s blokem
`prefers-reduced-motion: reduce`. Limity: 16 KB na variantu, 64 KB celkem, 200 deklarací, `animation-duration` ≥
100 ms.

Test: `test_design_system.py`, `test_appearance.py`, `test_buttons.py`, `test_custom_css.py`, `test_compile.py`,
`test_store.py` (`uv run pytest backend/project/site_admin`).
