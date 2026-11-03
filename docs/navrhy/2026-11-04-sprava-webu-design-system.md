# Správa webu a Design systém

Zadání je v obrázcích člověka `image9.png` a `image10.png` v kořeni repa a v artefaktu Design System (https://claude.ai/artifact/R7npNDzYK1urkfHi35MkVt, typ Design System). Nahrazuje §7 kontraktu plátna 2 a tenké nastavení webu z #282, které se celé maže.

**Princip:** web projektu má jednu globální úroveň nastavení. Říká, jak web funguje, co je předdefinované a jak vypadá. AI ji používá při každém vývoji. Na míru se pak u stránek řeší jen detaily a změny.

**Hotovo, když:**
- Na kartě prostředí „webová stránka“ je vstup „Správa webu“. Otevře stránku Nastavení webové stránky se všemi částmi z `image9.png`.
- Design systém umí totéž co typ Design System: tokeny s tématy, typografii, spacing, radius, stíny, komponenty s náhledem, assety a brand book.
- Dělník dostane `design/tokens.css`, `design/tokens.json` a `design/README.md` do relace a srdce vidí sekci `DESIGN` ve snímku.

## 1. Vstup a obrazovka

- **Vstup:**
  - Hlavní je třetí akce „Správa webu“ na kartě domény v landingu Architektury (`landing/components/DomainCard.tsx`). Je jen u webové domény a druh domény přichází přes `project-capabilities`.
  - Druhý vstup je odkaz v levém panelu mapy domény (`DomainPanel.tsx`).
- **URL:** `projectView=site&domainId=<id>`.
- **Stránka Nastavení webové stránky:** levé menu má tři skupiny z `image9.png` a vedle nich Design System.

| Skupina | Části |
|---|---|
| Nastavení | SEO, Affiliate, E-mail (SMTP) |
| Vzhled | Hlavička webu, Patička webu, Tlačítka webu, Vlastní fonty |
| GDPR | Cookie lišta |
| Design System | Overview, Colors, Typography, Spacing, Corner radius, Shadows, Components, Assets, Files a vyhledávání |

- Nastavení patří doméně, tedy webu. Jedna aplikace může mít web, aplikaci i administraci, každý s vlastním systémem. Vývoj a produkce sdílejí systém domény.

## 2. Datový model

Jeden dokument JSON na doménu: `<projekt>/site/<domainId>.json`, s revizí (optimistický zámek jako u nastavení projektu). Gramatika tokenů je převzatá z otevřeného formátu `tokens.json` typu Design System (`artifact-type/reference/format.md`). Kód typu se nepřebírá.

```jsonc
{
  "v": 1, "revision": 0, "title": "…", "lastChange": {"by", "via": "page|heart", "at", "note"},
  "settings": {
    "seo": {"titleTemplate", "description", "ogImage", "robots", "canonicalHost", "sitemap": true, "structuredData": "…"},
    "affiliate": {"enabled", "param", "cookieDays", "programs": [{"name", "url", "commission"}]},
    "email": {"provider", "host", "port", "secure", "from", "replyTo", "secretRef"},   // heslo nikdy, jen odkaz na tajemství
    "header": {"logoAsset", "nav": "source:pages|manual", "items": [...], "cta": {"label", "pageId"}, "sticky", "variant"},
    "footer": {"columns": [{"title", "links": [...]}], "legal", "social": [...], "variant"},
    "buttons": [{"name", "component": "Button", "variant", "tokens": {...}}],
    "fonts": "→ design.type.fonts",
    "gdpr": {"cookieBar": {"enabled", "position", "text", "categories": ["necessary", "analytics", "marketing"], "policyPageId", "consentDays"}, "contact"}
  },
  "design": {
    "readme": "brand book (markdown, ≤200 KB)", "sections": [{"slug", "title", "markdown"}],
    "tokens": {
      "color":   {"themes": [{"id", "name"}], "tokens": [{"name", "value": "…|{téma: …}|{alias}", "usage"}]},
      "type":    {"fonts": [{"family", "file", "weight", "style"}], "families": {"sans": "…"},
                  "groups": [{"name", "family", "note", "styles": [{"name", "fontSize", "lineHeight", "fontWeight", "letterSpacing", "fontStyle", "sample", "usage"}]}]},
      "spacing": {"note", "tokens": [...]}, "radius": {"note", "tokens": [...]}, "shadow": {"note", "tokens": [...]},
      "<vlastní>": {"note", "tokens": [...]}
    },
    "components": [{"name", "group", "summary", "readme", "preview", "height"}],
    "assetGroups": [{"name", "readme", "files": [{"name", "blob", "size", "type"}]}],
    "cover": {"preview"}
  }
}
```

- **Validace** (`backend/project/site_admin/design_system.py`) platí stejná jako u formátu:
  - jména tokenů a stylů: `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`, jeden sdílený jmenný prostor;
  - barvy: hex nebo funkce s čísly, alias `{token}` (bez cyklu, bez chybějícího cíle, hloubka nejvýš 16), chybějící hodnota v tématu se dědí z prvního tématu;
  - délky, `lineHeight` < 10, `fontWeight` 1–1000, bezpečný stack písma, stín bez `var` a `url`;
  - limity: 8 témat, 600 barev, 12 rodin, 12 skupin a 80 stylů, 60 tokenů na rodinu, note ≤ 400, usage ≤ 1000, sample ≤ 200.
- **Odvozené soubory** generuje server, nikdy se nepíšou ručně:
  - `tokens.css`: `:root, [data-theme=první]`, pak jeden blok na každé další téma, `:root` pro spacing, radius, vlastní rodiny a `--font-*`, třída na každý typografický styl, `@font-face`;
  - `tokens.json`;
  - `README.md`: brand book a generovaná sekce „Jak systém použít“ se seznamem komponent a assetů.
- Assety a fonty jdou jako soubory do `<projekt>/site/<domainId>/assets|fonts/`.

## 3. Rozhraní Design Systemu

Každá sekce je dílek s editorem, rodič drží revizi a ukládá.

| Sekce | Co člověk dělá |
|---|---|
| Overview | Titulek, cover (náhled) a README jako markdown editor s náhledem. Karty „Začít z…“: z GitHubu (import tokenů z repa projektu), od srdce (srdce navrhne systém z podkladů) a z nahraných souborů (loga, fonty, manuál) |
| Colors | Témata (přidat, přejmenovat, pořadí, max 8). Skupiny podle kmene jména. Token má jméno, hodnotu pro každé téma (barva, alias), usage a kontrast proti `on-*` nebo `ink` |
| Typography | Rodiny (stack), fonty (upload woff2/woff/ttf/otf), skupiny a styly (velikost, řádkování, váha, prostrkání, ukázka, usage) s živou ukázkou |
| Spacing / Corner radius / Shadows / vlastní rodiny | Poznámka rodiny, tokeny (jméno, hodnota, usage) s vizuální ukázkou. Stín může mít hodnotu pro každé téma |
| Components | Seznam po skupinách. Náhled v sandbox iframe s načteným `tokens.css`, přepínač tématu a README (props, kdy použít a kdy ne) |
| Assets | Skupiny (New set), přetažení souborů, náhled obrázků a SVG, README skupiny |
| Files | Strom souborů systému, stažení `tokens.css`, `tokens.json` a README |
| Search | Hledání přes tokeny, styly, komponenty a assety |

## 4. AI

- **Snímek srdce:** sekce `DESIGN` (titulek, témata, počty tokenů po rodinách, styly, komponenty, stav nastavení SEO, GDPR a e-mailu) nahrazuje sekci `WEB`.
- **Nástroj srdce:** `opora_heart.py site show|propose`. Srdce smí navrhnout změnu jen jako návrh (revize) a schvaluje ji člověk na stránce, stejně jako záměr stránky.
- **Dělník:** ticket karty na webové doméně nese `machine.design = {domainId, revision}`. Kancelář nebo relace dostane export `design/` do worktree, design jen čte a hodnoty mimo tokeny nepíše.
- **Kontrola mapy:** pravidlo `site.no-design` (webová doména bez design systému).

## 5. Vlak PR

1. **S-1 smazání #282:** modul nastavení webu v `backend/canvas/`, sekce WEB snímku srdce, přebití `seo`/`design` u stránky, `site-settings/` ve frontendu a zmínky v dokumentaci (seznam v inventuře).
2. **S-2 model a API:** dokument domény, validátor, kompilace `tokens.css`, `tokens.json` a README, `GET/PUT /api/site-admin?project=&domain=`, upload a stažení assetů a fontů. Testy.
3. **S-3 stránka a vstup:** `projectView=site`, akce na kartě domény, levé menu a části Nastavení, Vzhled a GDPR. Závisí na S-2.
4. **S-4 Design System editor:** sekce z §3. Závisí na S-2 a jde paralelně s S-3. Může se dělit po sekcích.
5. **S-5 AI:** sekce `DESIGN`, `site show|propose`, `machine.design`, export do relace, `site.no-design`. Závisí na S-2.

Po každém PR: cílený `uv run pytest`, `npm test`, `npm run build` a kontrola v prohlížeči proti `image9.png`.
