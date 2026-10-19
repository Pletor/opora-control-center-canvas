# Opora Canvas

Plátno projekt → sektor → uzel pro řízení agentů: struktura práce, zadání uzlů, podklady a běhy na jednom místě.

## Spuštění jedním příkazem

```sh
npm ci && uv sync      # jednou
uv run opora           # nebo: npm start
```

Nastavení běhu je v [opora.toml](opora.toml): port, adresář dat, sestavení frontendu, profily a integrace.
`uv run opora` sestaví frontend, když chybí nebo je starší než zdroje, spustí backend na http://127.0.0.1:8740/ a otevře prohlížeč.

- `uv run opora --profile preview` – náhled nad kopií dat (port 8790, `.data/preview`).
- `uv run opora --profile dev` – jen backend pro `npm run dev` (Vite proxuje `/api`).
- `uv run opora --check` – vypíše výslednou konfiguraci bez spuštění.
- `uv run opora --port 8791 --data .data/kopie --no-open --no-build` – jednorázové přepisy.
- `[app] embed_origins` – přesné původy, které smí Oporu zobrazit ve svém `<iframe>` (viz níže). Výchozí `[]` = rámování zakázané.
- Lokální přepisy mimo git: `opora.local.toml` se stejnou strukturou (např. `[app] data` mimo repozitář; přesun dat: `uv run python tools/move_data_root.py <starý> <nový> [--dry-run]`). Tajemství (API klíče) patří do proměnných prostředí, ne do TOML.

## Vložení do jiné lokální aplikace (`embed_origins`)

Opora se normálně nedá vložit do `<iframe>` (`X-Frame-Options: DENY`, CSP `frame-ancestors 'none'`), aby ji cizí stránka nemohla překrýt a podstrčit uživateli kliknutí (clickjacking). Chcete-li ji zobrazit ve vlastní lokální aplikaci, například v 3D kanceláři agent-office, vyjmenujte její původ v `opora.local.toml`:

```toml
[app]
embed_origins = ["http://localhost:4600"]
```

- Každá položka je přesný původ: schéma `http`/`https`, host a volitelně port. Cesta, dotaz, hvězdička ani `null` nejsou dovolené; neplatná položka zastaví start s českou hláškou (`uv run opora --check` ji ukáže hned).
- Neprázdný seznam vynechá `X-Frame-Options` a pošle `frame-ancestors 'self' <původy…>`. Ostatní CSP i hranice zůstávají: povolené Hosty, stejný Origin pro zápisy, cookie člověka `SameSite=Strict`, lease karet.
- **Bezpečnost:** nastavení uvolňuje ochranu proti clickjackingu jen pro vyjmenované původy. Uvádějte jen loopback původy (`localhost`, `127.0.0.1`) aplikací, které sami provozujete; nikdy veřejnou adresu.
- Cookie člověka je `SameSite=Strict`, takže zápisy z vložené Opory fungují jen tehdy, když je rám ze stejného webu jako rodič: z `http://localhost:4600` vkládejte `http://localhost:8740`, ne `http://127.0.0.1:8740`.
- Vložená Opora předává rodiči Escape, který sama neobsloužila (`preventDefault`): `window.parent.postMessage({ type: "opora:escape" }, <původ z document.referrer>)`. Bez referreru ani mimo rám se nic neposílá. Rodič má zprávu přijmout jen od původu Opory a sám rozhodne, co zavře. Panely Opory, které Escape zavírají bez `preventDefault`, ho předají také.

## Kde co je

- Pravidla umístění nového souboru: [docs/pravidla-struktury.md](docs/pravidla-struktury.md).
- Produktový kontrakt: [docs/PRODUCT-CONTRACT.md](docs/PRODUCT-CONTRACT.md).
- Kontrakt identity a logického členství v oblasti (pro Agent Office a Harness): [docs/kontrakt-identity.md](docs/kontrakt-identity.md).
