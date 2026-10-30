# brief-panel (Velín: výslech srdce u požadavku)

Dílek pohledu „Požadavky a plán“ (`../`). Kontrakt: `docs/navrhy/2026-10-30-vyslech-srdce.md` §3, §7 a §10, řez 3.

Co člověk vidí u požadavku:

- **Se spisem výslechu** (`brief` z `GET /api/intake`):
  - stav jednou větou: srdce skládá podklady, dohledává, potřebuje vaši odpověď, zapracovává odpovědi, nebo jasno;
  - otevřené otázky: otázka, co srdce doporučuje a proč; tlačítka **Potvrdit doporučení** a **Odpovědět jinak**
    (textové pole a **Odeslat**);
  - co srdce pochopilo (rozbalovací, otevřené, když srdce na nic nečeká): cíl, pro koho, části s původem
    (od vás / z rešerše / odvozeno), kritéria přijetí s tím, čím se ověří, a co se dělat nebude;
  - co do jasna ještě chybí, česky bez technických klíčů;
  - vaše dřívější odpovědi (rozbalovací).
- **Bez spisu** jen tlačítko **Vyslechni mě k tomu**.

V hlavním textu nejsou ID požadavků ani otázek; ID nese jen `data-oh-*` pro agenty.

Data a události: panel dostane hotový model (`BriefView`) a `actions` (`BriefActions`: `busy`, `errors`, `onAnswer`,
`onStart`) od rodiče `IntakePlan`, který posílá `POST /api/intake/brief/answer` a `/brief/start`
(`../logic/intake-api.ts`) a po úspěchu načte pohled znovu. `onAnswer(..., null)` = potvrzené doporučení. Rozepsaný
text odpovědi drží `BriefQuestion` sám.

Soubory:

- `logic/brief-model.ts`: `briefView` (brief → model panelu), `statusText`, `missingText`, `briefKey`, typy.
  Test `brief-model.test.ts`, vzor `logic/brief-fixture.ts`.
- `components/BriefPanel.tsx` (skládá dílky, test `BriefPanel.test.ts`), `BriefQuestion.tsx`, `BriefSynthesis.tsx`.
- `styles/brief-panel.css`: blok `brief-panel`.
