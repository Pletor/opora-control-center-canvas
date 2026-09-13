# Opora Canvas

Plátno projekt → sektor → uzel pro řízení agentů: struktura práce, zadání uzlů, podklady a běhy na jednom místě.

## Sestavení

```sh
npm ci && uv sync
npm run build
```

## Náhled

```sh
uv run python tools/serve-preview.py --port 8790 --data .data/preview
```

## Kde co je

- Pravidla umístění nového souboru: [docs/pravidla-struktury.md](docs/pravidla-struktury.md).
- Produktový kontrakt: [docs/PRODUCT-CONTRACT.md](docs/PRODUCT-CONTRACT.md).
