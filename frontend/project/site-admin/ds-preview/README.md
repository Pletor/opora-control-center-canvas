# Náhled nad tokeny projektu

Náhledy design systému (typografie, stíny, ukázky) stojí na vygenerovaném `tokens.css` uložené revize z `GET /api/site-admin/tokens.css?project=`. Soubor je psaný pro web projektu, ne pro OPORU, proto ho `logic/tokens-scope.ts` (+ test) uzavře do `.ds-scope`:

- `:root` → `.ds-scope`, `[data-theme="x"]` → `.ds-scope[data-theme="x"]`, třída stylu `.body` → `.ds-scope .body`;
- `url("fonts/<soubor>")` → `/api/site-admin/fonts/<soubor>?project=`.

`components/TokensScope.tsx`: `TokensStyle` vloží CSS jednou na stránku (`<style>`), `TokensScope` je obal náhledu s `data-theme` zvoleného tématu. Neuložené úpravy dílky ukazují navíc inline stylem; po Uložit rodič načte nový `tokens.css`.

Vzhled a Tlačítka stojí i na `components.css` (`GET /api/site-admin/components.css?project=`). `logic/components-scope.ts` (+ test) ho uzavře do `.ds-web` (náhled webu, stejný prvek jako `.ds-scope`): `body` je kořen náhledu, ostatní selektory jeho potomci, vrstvy `@layer` se rozbalí (vrstvený styl by prohrál s nevrstveným stylem OPORY) a `url("assets/…")` míří na `GET /api/site-admin/assets/<skupina>/<soubor>?project=`. `PreviewStyle` takový CSS vloží do stránky.
