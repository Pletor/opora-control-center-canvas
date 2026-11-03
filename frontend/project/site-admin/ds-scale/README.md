# Spacing, Corner radius a Shadows

Jeden dílek pro tři rodiny tokenů `design.tokens.spacing|radius|shadow = {note?, tokens: [{name, value, usage?}]}` (kontrakt Správy webu §3).

- `components/ScaleSection.tsx`: poznámka rodiny, řádky tokenů a „+ Přidat token“ (nejvýš 60, volné jméno `space-1`, `radius-sm`, `shadow-sm`…).
- `components/ScaleTokenRow.tsx`: jméno (sdílený jmenný prostor), hodnota, usage a ukázka. Spacing a radius mají délku (číslo = px), stín řetězec `box-shadow` nebo hodnotu pro každé téma; prázdná hodnota v jiném než prvním tématu dědí.
- `logic/scale-tokens.ts` (+ test): přidání, úprava, odebrání, poznámka a styl ukázky (pruh mezery, roh, stín v tématu).

Ukázka stojí v `TokensScope` (`../ds-preview/`) a bere hodnotu z rozepsaného dokumentu, takže se mění hned. Dílek nic neukládá.
