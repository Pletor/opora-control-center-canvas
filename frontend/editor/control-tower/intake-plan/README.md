# intake-plan (Velín: Požadavky a plán)

Druhý pohled Velínu (přepínač „Karty | Požadavky a plán“ v liště `ControlTower`). Kontrakt:
`docs/navrhy/2026-10-30-vstupni-brana.md` §6 a `docs/navrhy/2026-10-30-metriky-a-spoustece.md` §7, řez 4.

Co člověk vidí:

- **Souhrn vstupů** nahoře: nové vstupy (z posledních 50 `entries` ty, které srdce ještě nepotvrdilo, tj. vrstva
  není `heart`), `pending` a `duplicates` ze serveru.
- **Jeden dílek na oblast** (`kind: area` na plátně prostoru): jméno; aktivní milník s pruhem postupu (`progress` %)
  a kritérii jako checklist (✓/○, karty kritéria jsou odkazy a otevřou detail karty přes `onOpen` Velínu);
  návrhy milníků od srdce s tlačítky **Aktivovat** a **Zamítnout**; otevřené požadavky; odložené požadavky
  s podmínkou otevření (ID známého milníku se přeloží na jeho název). Prázdná oblast řekne jednu větu.
- **Požadavky bez oblasti** dole, jen když nějaké jsou.
- **Výslech srdce u každého požadavku** (dílek `brief-panel/`, `docs/navrhy/2026-10-30-vyslech-srdce.md` §7, řez 3):
  stav, otázky s doporučením a tlačítky **Potvrdit doporučení** / **Odpovědět jinak**, co srdce pochopilo a co chybí;
  bez spisu tlačítko **Vyslechni mě k tomu**.

Data a zápis:

- `GET /api/intake?project=&workspace=` každých 30 s (`logic/use-intake-plan.ts`, sdílený `usePolling`).
- `POST /api/intake/milestone {project, workspace, milestoneId, action}` sdíleným klientem `api` (cookie člověka
  `opora_ui`, stejný Origin; server pouští jen člověka, `require_human`). Po úspěchu se data načtou znovu; chyba
  se ukáže česky pod tlačítky (`role="alert"`), nikdy `alert()`. Zápis se neopakuje.
- `POST /api/intake/brief/answer {project, workspace, requirement, question, answer | accept: true}` a
  `POST /api/intake/brief/start {project, workspace, requirement}`: stejný klient a stejné chování jako rozhodnutí
  o milníku (jeden zápis najednou, klíč `briefKey`, chyba česky pod tlačítky, po úspěchu nové načtení).
- Zrcadlo pro agenty: `script#oh-velin-plan` (model pohledu).

Soubory:

- `logic/intake-plan.ts`: `parseIntake`, `intakePlan` (odpověď → model pohledu), `summaryParts`, `criteriaDone`.
  Test `intake-plan.test.ts` (vzor odpovědi `logic/intake-fixture.ts` sdílí test komponenty).
- `logic/intake-api.ts`: `readIntake`, `decideMilestone`, `decisionError`, `answerBrief`, `startBrief`, `briefError`.
  Test `intake-api.test.ts`.
- `logic/use-intake-plan.ts`: čtení s pollerem a `reload()`.
- `components/IntakePlan.tsx` (rodič: data, probíhající rozhodnutí, chyby), `IntakeSummary`, `IntakeArea`
  (test `IntakeArea.test.ts`), `IntakeMilestone` (+ `IntakeCriteria`), `IntakeProposal`, `IntakeRequirements`.
- `styles/intake-plan.css`: blok `intake-plan`.
- `brief-panel/`: panel výslechu srdce (vlastní `README.md`).
