# Studio · MODEL · scénáře

Knihovna výukových scénářů (`docs/studio.md` §4, etapa S6b; prototyp „Knihovna scénářů“). Otevírá se tlačítkem
„Scénáře“ v liště RUN i v nabídce prázdného modelu.

- `components/ScenarioLibrary.tsx` – panel přes plátno: hledání, kategorie, karty s pravidly a omezeními, „Otevřít v nové modelové doméně“.
- `logic/scenario-library.ts` – filtr, kategorie, klíč modelové domény `scenario:<id>` a její název `MODEL · <název>`.
- `styles/studio-model-scenarios.css`, blok `studio-model-scenarios`.

Otevření přepne MODEL na doménu `scenario:<id>` (`studio-model/logic/use-model-domain.ts`): nikdy neuložená se naplní
scénářem jako neuložený obsah, uložená se jen otevře; model domény architektury se nemění. Backend bere jakýkoli klíč
domény 1–128 znaků, změna backendu nebyla potřeba.
