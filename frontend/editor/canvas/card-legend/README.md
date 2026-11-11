# card-legend

Legenda plátna 3 (Editor) podle návrhu „Neonový dashboard OPORA: Editor“: jeden pruh dole uprostřed plátna
(`Board` ho vkládá jako React Flow `Panel` `bottom-center`), ne na každé kartě. Položky: Pracovní krok,
Kontrakt (rozhraní), Ověření / test, Rozhodnutí, Závislost / tok, Milník. Barvy jsou tokeny `--card-step`,
`--card-contract`, `--card-verify`, `--card-decision` z `design-tokens/styles/theme-tokens.css`, tytéž, které nese
rám karty (`card-face`, třída `node-card--family-*`). Dílek je bez props a bez logiky; nic neukládá.
