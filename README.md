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
- Lokální přepisy mimo git: `opora.local.toml` se stejnou strukturou. Tajemství (API klíče) patří do proměnných prostředí, ne do TOML.

## Kde co je

- Pravidla umístění nového souboru: [docs/pravidla-struktury.md](docs/pravidla-struktury.md).
- Produktový kontrakt: [docs/PRODUCT-CONTRACT.md](docs/PRODUCT-CONTRACT.md).
