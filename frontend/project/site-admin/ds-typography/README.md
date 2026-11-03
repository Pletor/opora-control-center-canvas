# Typography design systému

Sekce Typography Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §3) nad `design.tokens.type = {fonts, families, groups}`.

- `FamiliesEditor`: rodiny písma (klíč → stack, `--font-<klíč>`, nejvýš 12). Přejmenování klíče přepíše odkazy skupin a stylů.
- `FontsEditor`: záznamy `type.fonts` (rodina, váha `400` nebo rozsah `300 800`, řez, soubor) a „Nahrát font“ (woff2, woff, ttf, otf). Soubor nahrává rodič přes `POST /api/site-admin/fonts` a záznam doplní podle jména souboru (`fontFromUpload`); uloží se s dokumentem.
- `TypeGroupEditor` + `TypeStyleRow`: skupiny (název, rodina, poznámka) a styly (velikost, řádkování, váha, prostrkání, řez, rodina, ukázka, usage) s živou ukázkou. Ukázka má třídu stylu z uloženého `tokens.css` (`../ds-preview/`) a navrch rozepsané hodnoty inline.
- `logic/typography.ts` (+ test): úpravy rodin, fontů, skupin a stylů (vlastní jmenný prostor stylů), odhad záznamu fontu a inline styl ukázky.

Dílek nic neukládá: změnu hlásí celým `type` rodiči `SiteAdmin`.
