# Správa webu: dokument a design systém projektu

Backend Správy webu (`docs/navrhy/2026-11-04-sprava-webu-design-system.md` §2, PR S-2, Vzhled a Tlačítka S-4b).
Jeden dokument na projekt: globální nastavení webu (`settings`) a design systém (`design`). Gramatika tokenů je
převzatá z otevřeného formátu `tokens.json` typu Design System, kód typu ne.

- `tokens.py` – gramatika `design.tokens`: jména, barvy a aliasy (bez cyklu, chybějícího cíle, hloubka ≤ 16,
  chybějící téma dědí z prvního), délky, typografie, stíny, vlastní rodiny a limity. Neplatná hodnota se zahodí
  s poznámkou, chyba tvaru je `SiteAdminInvalid` (422).
- `design_system.py` – celý dokument: skládá části `settings` z modulů níže; `design` (readme, sections,
  components, assetGroups, cover) a `empty()`.
- `site_settings.py` – Nastavení webu `seo`, `affiliate`, `email` (SMTP) a `gdpr` (cookie lišta, kontakt správce):
  celý tvar s výchozími hodnotami, chyba = 422, rady jsou `notes`. Tajemství se odmítne kdekoli (jen `secretRef`).
- `settings_fields.py` – pravidla polí nastavení (text, číslo, volba, seznam, objekt s výchozími hodnotami, odkaz,
  obrázek z Assets) a odmítnutí tajemství; sdílí je `site_settings.py` a `site_chrome.py`.
- `site_chrome.py` – hlavička a patička (`header`, `footer`) a styly `.ds-header`, `.ds-footer`, `.ds-cookie-bar`
  do `components.css`.
- `settings_readme.py` – sekce „Nastavení webu“ generovaného README (SEO, hlavička, patička, cookie lišta, e-mail,
  affiliate s markupem).
- `appearance.py` – Vzhled (viz níže).
- `buttons.py` – tlačítka: validace, komponentní tokeny `--btn-*` a jejich CSS, poznámky k přístupnosti.
- `custom_css.py` – vlastní CSS tlačítek přes tinycss2 (BSD-3-Clause): allowlist, přepis, `@layer custom`.
- `compile.py` – odvozené soubory: `tokens.css` (rozvržení formátu), `components.css`, `tokens.json` a `README.md`
  (brand book a generovaná sekce „Jak systém použít“ včetně „Tlačítka“).
- `store.py` – `projects/<id>/site/design-system.json` s revizí (409 při jiné), assety
  `site/assets/<skupina>/<soubor>`, fonty `site/fonts/<soubor>`, typ podle prvních bajtů a limity velikosti.
- `fixture.py` – zkrácený vzorek systému pro testy.
- Router: `backend/api/project/site_admin_routes.py` (`/api/site-admin…`, včetně `components.css`).

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

## Nastavení webu (SEO, Affiliate, E-mail, Hlavička, Patička, GDPR)

| Část | Pole (výchozí) | Pravidla |
|---|---|---|
| `seo` | `titleTemplate` (`%s`), `siteName`, `description`, `locale` (`cs_CZ`), `canonicalHost`, `ogImage`, `ogType` (website), `twitterCard` (summary_large_image), `twitterSite`, `robots` {index, follow, noarchive, nosnippet, maxImagePreview (large), maxSnippet (-1)}, `sitemap` (ano), `structuredData` | šablona má právě jedno `%s`; `ogImage` je existující asset nebo https; JSON-LD je platný JSON (objekt nebo pole) bez `</`; popis nad 160 znaků a `noindex` jsou poznámky |
| `affiliate` | `enabled`, `param` (ref), `cookieDays` (30, 1–365), `attribution` (last/first), `disclosure`, `programs` [{name, url https, commission, code}] ≤ 50 | zapnutý bez upozornění nebo bez kategorie marketing v cookie liště = poznámka |
| `email` | `provider` (smtp), `host`, `port` (587), `security` (starttls/tls/none), `username`, `from`, `fromName`, `replyTo`, `secretRef` | heslo nikdy (klíč `password`, `heslo`, `token`, `apiKey`… = 422); starší `secure` se převede; 465 + STARTTLS, 587 + TLS a `none` jsou poznámky (RFC 8314, RFC 6409) |
| `header` | `logoAsset`, `logoAlt`, `nav` (source:pages/manual), `items` ≤ 12, `cta` {label, pageId \| url, variant}, `sticky`, `variant` (classic/centered/minimal) | odkaz má popisek a buď `pageId`, nebo URL (`/cesta`, `#kotva`, https, mailto, tel; nikdy `javascript:` ani `//host`); chybějící logo a neznámá varianta CTA se zahodí s poznámkou |
| `footer` | `columns` ≤ 6 × `links` ≤ 12, `legal`, `social` [{name, url https}] ≤ 12, `variant` (columns/simple/centered), `cookieLink` (ano) | bez právního řádku = poznámka |
| `gdpr` | `cookieBar` {enabled, position (bottom/top/bottom-left/bottom-right/center), title, text, categories, categoryInfo, acceptLabel, rejectLabel, settingsLabel, saveLabel, policyPageId, policyUrl, consentDays (180, 1–730), reopen (ano), version}, `contact` {controller, email, dpoEmail, address} | `necessary` je vždy první a vždy zapnutá, ostatní kategorie se nikdy nepředvyplňují (pole pro to neexistuje); přijmout a odmítnout mají v CSS stejnou třídu; bez zásad, nad 13 měsíců nebo bez kontaktu = poznámka |

Zdroje: Google Search Central (title, meta description, robots, canonical, sitemap, JSON-LD), Open Graph, RFC 6409
a 8314, ePrivacy čl. 5 odst. 3, EDPB Guidelines 05/2020, zpráva EDPB Cookie Banner Taskforce (2023) a ÚOOÚ.

Test: `test_site_settings.py`, `test_site_chrome.py`, `test_design_system.py`, `test_appearance.py`, `test_buttons.py`, `test_custom_css.py`, `test_compile.py`,
`test_store.py` (`uv run pytest backend/project/site_admin`).
