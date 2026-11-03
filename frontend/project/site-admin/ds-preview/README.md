# Náhled nad tokeny projektu

Náhledy design systému (typografie, stíny, ukázky) stojí na vygenerovaném `tokens.css` uložené revize z `GET /api/site-admin/tokens.css?project=`. Soubor je psaný pro web projektu, ne pro OPORU, proto ho `logic/tokens-scope.ts` (+ test) uzavře do `.ds-scope`:

- `:root` → `.ds-scope`, `[data-theme="x"]` → `.ds-scope[data-theme="x"]`, třída stylu `.body` → `.ds-scope .body`;
- `url("fonts/<soubor>")` → `/api/site-admin/fonts/<soubor>?project=`.

`components/TokensScope.tsx`: `TokensStyle` vloží CSS jednou na stránku (`<style>`), `TokensScope` je obal náhledu s `data-theme` zvoleného tématu. Neuložené úpravy dílky ukazují navíc inline stylem; po Uložit rodič načte nový `tokens.css`.
