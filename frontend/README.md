Vše, co vidí uživatel; žádná aplikační logika, ta patří do backend/.

Strom kopíruje cestu uživatele: `project-setup/` (přiřazení repozitářů, vytvoření projektu) → tři prostředí `project/` | `editor/` | `live-run/`, každé se svými nástroji. Společné: `app/` (vstup a skládání), `layout/` (kostra obrazovky), `design-tokens/`, `shared/` (stav a typy bez závislosti na prostředích), `ui-kit/` (prvky bez domény).

Uvnitř každé feature složky: `components/` = .tsx, `logic/` = .ts, `styles/` = .css, README = co složka zobrazuje a odkud bere data. Podrobný plán a tabulka přesunů: STRUCTURE-PLAN.md.
