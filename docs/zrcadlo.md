# Zrcadlo (BioCortexAI) – vývojový sidecar

Stav: **kontrakt K8** (2026-10-14). Jen pro vývoj v OPORA, ne pro produkt (Tajemstvi-opory) ani pro jiné uživatele. Navazuje na [schranka-neurony.md](schranka-neurony.md) §3.

## Proč

Brány `synthesized` a `verified` už ukládají předpověď a skutečnost a server počítá predikční chybu. Zrcadlo k tomu přidá druhý, nezávislý pohled: malý lokální model BioCortexAI (Digital Mirror) se z výsledků bran učí a jeho přesnost a „nálada“ ukazují, kde se vývoj odchyluje od očekávání. Je to orientační ukazatel, nikdy rozhodovací signál.

## Hranice

- Kód i model zůstávají v `I:\1. Projekty\12_Memory\BioCortexAI` (licence CC-BY-NC-4.0, autor OpenTechLab). Do repa OPORA se nic z něj nekopíruje a OPORA nedostane žádnou novou závislost (torch atd.).
- Zrcadlo běží jako samostatný proces jen na `127.0.0.1`. Adresa a zapnutí jen v `opora.local.toml` (`[mirror] url = "http://127.0.0.1:8750"`, `enabled = true`); bez toho je klient no-op.
- **Data jen z OPORA:** Zrcadlo dostává jen text fragmentu, disciplínu, mikrokrok, předpověď a skutečnost brány. `perceptor.py` a `harvest_history.py` (čtou všechny relace Claude Code a export z Telegramu) se s OPORA nepoužívají.
- Výjimka běhu modelu (CLAUDE.md, [asistent.md](asistent.md) §1): **čtvrté místo**, lokální vývojový model, volaný jen při zápisu brány `synthesized` / `verified`, kterou zapnul agent nebo člověk; výchozí vypnuto.
- Zrcadlo **nikdy neblokuje** bránu: timeout 2 s, výpadek nebo chyba = brána projde bez údaje Zrcadla.

## Rozhraní služby (v repu BioCortexAI)

- `POST /predict {fragmentId, discipline, title, text, microstep}` → `{predictionId, expected: {tests, criticRounds}, confidence}`
- `POST /observe {predictionId, actual: {tests, criticRounds, unexpected}}` → `{predictionError, hormones: {dopamin, serotonin, kortizol, oxytocin}, accuracy}`
- `GET /health` → `{ok, model, events}`

Služba je tenká vrstva nad `generate` a `mirror_integration`; stav PlantNet ukládá do vlastního souboru ve složce BioCortexAI.

## OPORA

- `backend/integrations/mirror_client.py` (+ test s falešnou službou): `predict(...)`, `observe(...)`, oba vrací `None` při vypnutí nebo poruše, nikdy nevyhodí.
- Tabulka `brief_mirror_events(event_id, project_id, workspace_id, fragment_id, revision, cycle, kind, request, result, created_at)`, append-only. `event_id` = sha256(projekt, workspace, fragment, cyklus, druh), takže opakování je idempotentní.
- Brána `synthesized`: **po** potvrzení transakce brány zavolá `predict` a výsledek uloží jako událost `predict` (cyklus = revize se `synthesized`).
- Brána `verified`: zavolá `observe` jen s `predictionId` stejného cyklu (jinak přeskočí) a uloží událost `observe` (`predictionError`, `hormones`, `accuracy`). Do revize fragmentu se nic dodatečně nezapisuje.
- Klient vynucuje host `127.0.0.1`/`localhost`, žádné přesměrování a zapnutí pro konkrétní projekt (`[mirror] projects = [...]`).
- Schránka (Přehled) ukáže přesnost Zrcadla po disciplínách a poslední hormony jako malý orientační panel „Zrcadlo“, jen když je zapnuté.

## Ověření

Testy klienta s falešnou službou (zapnuto / vypnuto / timeout / neplatná odpověď), test, že výpadek nezablokuje bránu, `uv run pytest backend tools`, `npm test`, `npm run build`. Živě jen se spuštěnou službou na 127.0.0.1.
