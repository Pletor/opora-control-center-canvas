# Další přípustný krok

Pruh pod plátnem 2 (`docs/navrhy/2026-11-10-platno-2.md`).

- `components/PlanBar.tsx` dostane hotový krok `NextStep` z `../logic/plan-progress.ts` (`nextAdmissible`: první neověřený prvek logiky stránky, jehož všechny vstupy `requires` jsou aspoň hotové) a ukáže „Doplnit …“ s tlačítkem **Otevřít v Editoru →** (`onOpenEditor` = plátno 3 nad ID prvku). Bez kroku „Vše ověřeno“, „Čeká na vstup: …“ nebo výzvu vložit první prvek ve vrstvě Logika.
- `styles/plan-bar.css`, předpona `plan-bar`.
