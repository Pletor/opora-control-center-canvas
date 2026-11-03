# Colors design systému

Sekce Colors Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §3). Edituje `design.tokens.color = {themes, tokens}` v gramatice formátu Design System.

- **Témata** (`ThemeBar`): přidat (nejvýš 8, `id` z názvu), přejmenovat, posunout, odebrat. První téma je výchozí (`:root`) a zdroj dědění; `logic/color-themes.ts` (+ test) při přesunu či odebrání prvního tématu doplní hodnoty, aby žádná barva nezměnila barvu.
- **Barvy** po skupinách podle kmene jména (`bg-100` → `bg`, `on-ember` → `ember`). Řádek (`ColorTokenRow`): jméno (sdílený jmenný prostor, přejmenování přepíše i aliasy), hodnota pro každé téma (`ColorValueCell`: color picker + text, alias `{token}` výběrem, „dědí z výchozího“), usage.
- **Kontrast** WCAG proti dvojici (`on-x` ↔ `x`, `ink` na `surface`, `surface`/`bg` pod `ink`, ostatní na `surface`) v každém tématu jako odznak AAA / AA / ✕. `logic/color-contrast.ts` (+ test) čte hex, `rgb()` a `hsl()`; jiné funkce kontrast nemají.
- `logic/color-tokens.ts` (+ test): rozbalení aliasů jako v serveru (cyklus, chybějící cíl, hloubka 16), skupiny, dvojice, přejmenování.

Dílek nic neukládá: změnu hlásí celou rodinou `onChange` rodiči `SiteAdmin`.
