# Projekt a navigace

## Nezaměň tři druhy kontextu

1. **Cwd tvého procesu** — kořen zdroje projektu, nad kterým běžíš (např.
   `<kořen-zdroje-projektu>`). Soubory čti Read/Glob/Grep.
2. **Projekt v OPORA** — ID z `opora_read.py projects`, nikoli název složky.
   Hodnota `<projectId>` se bere z `<opora_context>.projectId` (mimo aplikaci z `opora_read.py projects`).
3. **Workspace projektu** — `main`, `draft` nebo ID pracovního stromu (výchozí je `main` u git projektu a jinak `draft`)
   (`<opora_context>.workspace`). Zda jde zapisovat, říká `view.readOnly`;
   u `readOnly: true` nic nezapisuj.

Pořadí: `status`, `projects`, pro zvolený projekt `workspaces --project ID`,
teprve potom `view --project ID --workspace ID`. Není-li ID jasné, nevol
náhodný projekt. Příklad:

```text
python <cesta>/opora_read.py view --project <projectId> --workspace <workspace>
```

`--base-url` netřeba, adresa je v `OPORA_BASE_URL`.

## Co dělá člověk

Připojení složky jako projektu, přepínání projektu a workspace v horním výběru,
odpojení projektu a Nastavení aplikace dělá člověk v UI; ty nemůžeš spustit.
Plátno, zadání a karty žijí v OPORA, ne v repu projektu. Kód projektu
neměníš (Edit je zakázaný); větve, commity a push dělá člověk.

Po změně projektu nebo workspace (nové `<opora_context>`) znovu načti stav;
starý vybraný uzel ani dřívější odpověď nepřenášej do nového kontextu.

## Přímé odkazy

Odkaz do aplikace vrací `opora_read.py view` v poli `links` (pro `project`,
`editor`, `live`), tvar `/?screen=canvas&project=ID&workspace=<workspace>&environment=editor&mode=structure`.
Neskládej ho ručně z názvu projektu.

Filtrace stromu není mazání. Skryté/ignorované soubory nepřidávej automaticky
mezi reference; obsah `.env`, klíče a autentizační soubory nečti ani nepřikládej.
