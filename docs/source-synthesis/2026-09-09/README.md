# Výsledek zpracování podkladů OporaCC

2026-09-09 — citovaná produktová a technická syntéza. **Návrh, ne hotová rozšířená aplikace.**

## Začni zde

1. [EDITOR-SPEC.md](EDITOR-SPEC.md) — účel, uživatelský průchod, 12 modulů, datový model, autority, výkon a rozdíl proti dnešnímu Canvasu.
2. [TUNNEL-AND-CONTEXT.md](TUNNEL-AND-CONTEXT.md) — přesný scope, compiler, supervizoři, CLI/MCP, STOP, restart, budget a učení.
3. [INTEGRATIONS.md](INTEGRATIONS.md) — výběr principů a komponent ze všech šesti lokálních projektů, licence a neověřené předpoklady.
4. [DELIVERY-GATES.md](DELIVERY-GATES.md) — vstupní onboarding a osm malých implementačních řezů, konkrétní první kandidát a průkazná akceptace.
5. [system-map.html](system-map.html) — interaktivní Archify přehled navrženého hlavního toku. Je to mapa návrhu, nikoli UI hotové aplikace; české popisky, pevné ovládání vieweru je anglické.

## Podstata doporučení

Jeden sémantický model → více pracovních pohledů → přesný zmrazený context bundle → schválený terminálový run → skutečná evidence → přijatá zkušenost / komponenta.

Canvas uzel je trvalé místo pro význam a materiály. WorkUnit je jeden konkrétní řez. Supervisor je role a binding, ne stále běžící placený model. Terminál je vykonavatel, ne druhé místo, kde musí člověk znovu vysvětlovat celý projekt.

## Dohledatelnost

- [PROMPT-DECISIONS.md](PROMPT-DECISIONS.md): každý z 63 promptů zvlášť; ponechat/upravit/odložit/nepřebírat.
- `source-manifest.json`: originál, hash, rozsahy promptů a snapshot.
- `coverage.json`: programová kontrola všech 10 524 řádků a unikátních 63 ID.
- `reference-sources.json`: šest lokálních zdrojů, cíleně čtené soubory, skutečné hashe a Git base revize.
- `reviews/`: plné sekční rozbory; nadřazená rozhodnutí a rozpory řeší EDITOR-SPEC.
- `citations.json`: mechanicky přidělené odkazy na skutečné lokální zdroje.
- `verification.json`: závěrečná kontrola artefaktů, zdrojů, odkazů a mapy.

Originální prompty a referenční projekty se nemění. Žádné skutečné GitHub repo se automaticky nepřipojuje; produkční Canvas se touto dokumentací neplní a agenti pro vývoj produktu se nespouštějí.
