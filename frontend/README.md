Vše, co vidí uživatel; žádná aplikační logika, ta patří do backend/.

Strom kopíruje cestu uživatele: `project-setup/` (přiřazení repozitářů, vytvoření projektu) → tři prostředí `project/` | `editor/` | `hub/` (OporaHub: plán a dokumentace 1:1 s kódem), každé se svými nástroji. Společné: `app/` (vstup a skládání), `layout/` (kostra obrazovky), `design-tokens/`, `shared/` (stav a typy bez závislosti na prostředích), `ui-kit/` (prvky bez domény).

`settings/` = nastavení aplikace z levého dolního rohu (dnes sekce Connectors), `layout/account-corner/` = tlačítko a popup menu v rohu.

Uvnitř každé feature složky: `components/` = .tsx, `logic/` = .ts, `styles/` = .css, README = co složka zobrazuje a odkud bere data. Podrobný plán a tabulka přesunů: STRUCTURE-PLAN.md.
