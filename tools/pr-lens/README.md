# PR Lens CLI (připnutá verze)

PR Lens CLI, kterou pracovníci používají pro `validate` a `render` diagramů k PR (viz
[Čistá linie §4](../../docs/cista-linie.md)). Za běhu nepotřebuje síť ani API klíč.

## Instalace

```
cd tools/pr-lens
npm ci --ignore-scripts
```

## Ověření

```
node_modules/.bin/pr-lens --help
```

## Napojení na agent-office

Nastav `AGENT_OFFICE_PR_LENS_HOME=<absolutní cesta k tools/pr-lens>`.

## Proč jsou verze připnuté

- `@coldtea/pr-lens-cli` 0.13.2 deklaruje schéma `^0.7.0`, proto je schéma 0.7.0 i v `overrides`.
- `@coldtea/pr-lens-renderer` 0.3.3 až 0.3.5 byly 22. 10. 2026 publikované rozbité nebo příliš čerstvé, proto držíme 0.3.2.
- Žádné `^` ani `~`; `package-lock.json` je zafixovaný a instaluje se `npm ci --ignore-scripts` (žádné skripty při instalaci).
