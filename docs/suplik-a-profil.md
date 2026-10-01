# Šuplík Knihovna/Agenti u levého okraje a profil projektu

Kontrakt 2026-10-01. Nahrazuje „Dílek 2: zavěšené panely“ a „Co se nemění“ (v části obsahu panelů) v [rozvrzeni-editoru.md](rozvrzeni-editoru.md). Návrh je v artefaktu „OPORA – asistent a panely Editoru“ (artboardy 2 až 4): https://claude.ai/artifact/C6jQswc2bWSgcBUj5bmUfg

## Proč

Zavěšený panel visel pod svým tlačítkem, a protože tlačítka stojí za záložkami módů, otevíral se uprostřed stránky. Knihovna (asi 44 prvků) ani Agenti (asi 26 postupů) nevěděli nic o projektu. Monolit, mikroslužby a multitenantní aplikace tak dostávaly stejný seznam. Cíl je jedno pevné místo u okraje, jasně patřící k projektu, s výběrem jen toho, co projekt potřebuje.

## 1. Profil projektu (data)

Nastavení projektu (`/api/project-settings`, `backend/project_setup/project_hub.py`) dostane dvě pole:

```
settings: { goal, platform, architecture, tenancy }
architecture: "" | "monolith" | "modular" | "microservices" | "serverless"
tenancy:      "" | "single" | "multi"
```

- `""` znamená nenastaveno. To je výchozí hodnota a nic se nefiltruje.
- Starší uložená nastavení bez nových klíčů se čtou s doplněnými výchozími hodnotami.
- Zápis vyžaduje celou sadu klíčů jako dnes. Neplatná hodnota vrátí českou chybu.
- Profil patří **projektu**, protože popisuje projekt, ne vzhled. Vzhled a ovládání panelu se dál ukládají jednou pro aplikaci.
- Nastavení → Projekt (`ProjectHome` / formulář nastavení projektu) má obě pole jako volby s krátkým popisem.

## 2. Co z profilu plyne (jen `project-capabilities`)

`frontend/shared/project-capabilities/logic/project-capabilities.ts` dostane čistou funkci:

```ts
export type ProjectProfile = { architecture: Architecture | ""; tenancy: Tenancy | ""; platform: Platform };
export function catalogProfile(settings: { architecture?: string; tenancy?: string; platform?: string } | null): ProjectProfile;
```

Dílek nikdy nečte nastavení ani `sourceKind` sám. Šuplík dostane hotový `profile` v props od App.

## 3. Prvky katalogů nesou, kam patří

Položky `library-catalog.ts` i `agent-catalog.ts` dostanou volitelné pole:

```ts
fits?: { architecture?: Architecture[]; tenancy?: Tenancy[] }
```

- Bez `fits` je prvek univerzální a patří všem.
- Logika je v `frontend/editor/component-library/library-catalog/logic/catalog-fit.ts` + `catalog-fit.test.ts`:
  - `fitsProfile(item, profile)`: chybějící pole profilu (`""`) znamená, že podle něj se nefiltruje.
  - `splitByProfile(items, profile) → { fitting, outside }`
  - `fitReason(item, profile)`: text „kvůli profilu: multitenant“ nebo `null` u univerzálních.
- Doplnit prvky, které dnes chybí:
  - Knihovna:
    - kategorie **Multitenance** (`tenancy: ["multi"]`): kontext tenanta v požadavku, izolace dat podle tenanta, konfigurace a limity tenanta;
    - **mikroslužby** (`architecture: ["microservices"]`): API gateway, broker zpráv, vlastní databáze služby, distribuované trasování;
    - **modulární monolit** (`["modular"]`): hranice modulu;
    - **serverless** (`["serverless"]`): funkce, spravovaná fronta.
  - Agenti: pravidla „Každý dotaz nese tenanta“ (multi), „Moduly si nesahají do dat“ (modular), „Služba vlastní svá data“ (microservices) a postup „Saga přes služby“ (microservices).
  - Existující prvky, které jsou zjevně jen pro jednu architekturu, dostanou `fits`. Ostatní zůstávají univerzální.
  - Žádné vymyšlené prvky navíc.

## 4. Šuplík u levého okraje (`frontend/layout/panel-dock/`)

- `PanelDropdown` se nahradí dílkem `PanelDrawer`. Je absolutně v `editor-frame`: `left: 0; top: 0; bottom: 0; width: 380px`, nad plátnem (`z-index: 20`), pravá hrana s linkou a stínem do plátna. Žádná šipka, žádné měření tlačítka. `dropdownPlacement` a jeho test se smažou.
- Nahoře je segmentový přepínač **Knihovna | Agenti a postupy**, který volá stávající `dock.toggle`/`open`. Tlačítka v liště zůstávají a fungují stejně. Zkratky, Esc i zavření klikem mimo panel zůstávají; klik na plátno panel nezavře, protože šuplík plátno nezakrývá.
- *(Zrušeno 2026-10-01, viz menu-a-katalog.md: projekt a profil jsou jen v Nastavení.)* Pod přepínačem byla **hlavička projektu**: název projektu a profil slovy („Web · Modulární monolit · Multitenant“) s odkazem **Změnit**. Ten rozbalí kartu profilu ve šuplíku.
- **Karta profilu** (artboard 4) se zobrazí, když profil není nastavený (`architecture` i `tenancy` jsou `""`):
  - dvě skupiny voleb, „Uložit pro projekt“ a „Teď ne, ukázat vše“;
  - „Teď ne“ kartu sbalí do lišty jen pro toto sezení;
  - ukládá rodič (App) přes `/api/project-settings` s `expected_revision`, šuplík jen hlásí volbu callbackem.
- **Filtr:** přepínač „Pro tento projekt N“ / „Vše M“.
  - Ve výchozím stavu se ukazuje jen `fitting`.
  - Na konci seznamu je řádek „Mimo profil: K prvků (…) · zobrazit“, který dočasně ukáže i `outside`, ztlumeně.
  - Skupiny, které jsou ve výběru jen kvůli profilu, nesou štítek „kvůli profilu“.
  - Volba filtru se ukládá app-globálně.
- Obsah Knihovny (OBSAH/STRÁNKA, Elementy/Bloky, hledání, tažení) a Agentů (Katalog/Agenti/Hook) zůstává. Mění se jen rám, hlavička a filtrování seznamu. Hledání prohledává i položky mimo profil a výsledek mimo profil označí.
- Sloupec náhledů Knihovny (`__previews`) vyčnívá vpravo ze šuplíku na plátno. To je v pořádku.
- Pod 900 px šířky okna má šuplík `width: 100%`.

## 5. Hotovo, když

- `uv run pytest backend`, `npm test` a `npm run build` procházejí.
- V aplikaci se Knihovna i Agenti otevírají u levého okraje pod lištou. Přepínač mezi nimi funguje a tažení na plátno funguje.
- Projekt bez profilu ukáže kartu profilu. Po uložení se seznam zúží a hlavička ukazuje profil.
- Multitenantní modulární projekt vidí Multitenanci a hranice modulu, ale ne API gateway (ta je pod „Mimo profil“).
