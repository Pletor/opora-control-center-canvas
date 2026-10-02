Pop-up tvorby sektoru a uzlu (kontrakt `docs/kontext-karet-a-index.md` §7). App ho otevře tlačítkem „+ Sektor“ / „+ Uzel“ uvnitř svého modálního okna, podá mu hotová data a přijme výsledek callbackem; ukládání (`save` grafu a potom zadání sektoru přes `saveNodeSpec` → `POST /api/node-spec`) zůstává v App.

**Tvar formuláře** (shora dolů, na první pohled jen to, bez čeho karta nevznikne):

1. **Název** (autofocus).
2. U uzlu mimo sektor **Cílový sektor**.
3. U uzlu **Vrstva**: řada čipů FE · BE · DB · Knihovna (`role="radiogroup"`, nepovinná, druhý klik výběr zruší).
4. **Původ**: segmentový přepínač na jeden řádek Myšlenka · Existující zdroj · Nový návrh; zakázaná varianta má v `title` důvod.
5. Pole podle původu: existující zdroj → strom zdrojů, nový návrh → zamýšlená cesta a u uzlu Složka / Soubor (čipy) na jednom řádku. Pod tím jeden textarea **Popis** s placeholderem podle původu.
6. U sektoru sbalená sekce **Zadání sektoru (nepovinné)**: cíl, co nedělat, hotovo když; v hlavičce, co je vyplněné.
7. U uzlu sbalená sekce **Pro agenta (nepovinné)**: stav, model, effort, termín ve dvou sloupcích; v hlavičce vybrané hodnoty (`ready · sonnet/medium`).
8. **Vytvořit**, pod ním při neaktivním tlačítku „Chybí: …“ (`data-testid="create-missing"`).

**Dílky**

- `components/CreateDialog.tsx` — rodič: drží rozepsaný formulář, skládá dílky a po odeslání ohlásí `onCreate({ node, spec })`. Dostává `kind`, `project`, `workspace`, `parent`, `nodes`, `ancestorSector`, `sectors`, `legacyFree` (ze `project-capabilities`, druh projektu dialog nezná) a `busy`.
- `components/LayerChips.tsx` — čipy vrstvy. Znovu ho používá detail karty (`editor/node-detail/card-fields/`).
- `components/OriginSwitch.tsx` — segmentový přepínač původu.
- `components/CreateSourceFields.tsx` — přepínač původu a pole k němu (`SourceExplorer`, u sektoru jen kořenové složky, u uzlu v rozsahu cesty sektoru; zamýšlená cesta s druhem).
- `components/PurposeField.tsx` — jediné pole Popis (`purpose`), povinné u myšlenky a návrhu, jinak nepovinné.
- `components/FoldSection.tsx` — sbalitelná sekce (`<details>`, výchozí sbalená) se souhrnem v hlavičce.
- `components/AgentFields.tsx` — stav (draft / ready), model, effort, termín. Znovu ho používá detail karty.
- `components/SectorSpecFields.tsx` — zadání sektoru: cíl (`goal`), co nedělat (`non_goals`), hotovo když (`acceptance`).

**Logika** (bez Reactu, s testy vedle):

- `logic/create-form.ts` (+ `create-form.test.ts`), pravidla přenesená z App.tsx beze změny: `createRules(form, ctx)` — `requiresTargetSector` (uzel v připojeném projektu bez sektoru, ne u myšlenky), `requiresModeChoice` (legacy-free sektor ani volný uzel bez zdroje volbu nemají), `existingAllowed` (existující zdroj u uzlu jen v sektoru s existujícím `sourceRef`), popis návrhu sektoru nejméně 12 znaků, zamýšlená cesta uzlu jen v sektoru, který ji ukotví. `missingFields` (prázdné právě tehdy, když `canCreate` vrací true; test to hlídá přes všechny kombinace), `showsPurpose`, `specSummary`, přechody `changeTargetSector` a `chooseOrigin` a `buildCreated(form, ctx, scope)` — hotový uzel: rodič je cílový sektor nebo vrstva, zamýšlená cesta uzlu je prefixovaná cestou sektoru, popis se ukládá vždy, prázdná karta se do uzlu nedává (`normalizeCard` ze `shared/card-context`), sektor kartu nemá a nese `spec` (jen když je něco vyplněné).
- `logic/card-draft.ts` (+ `card-draft.test.ts`): rozepsaná karta (`emptyCard`, `cardDraftOf`, `sameCardDraft`), `toggleLayer` (druhý klik zruší) a `agentSummary` (souhrn sekce Pro agenta).

**Styl** — `styles/create-dialog.css`, blok `create-dialog` v BEM s příběhovými komentáři (`__group`, `__chip`, `__segment-option`, `__row`, `__fold`, `__agent`, `__foot`, `__missing`); barvy a rytmus z tokenů tématu (`--sp-*`, `--fs-*`, `--accent-*`, `--line`). Pole a strom zdrojů si dál berou společné třídy dialogů (`field`, `create-source-picker`, `create-source-note`, `create-source-picked`).
