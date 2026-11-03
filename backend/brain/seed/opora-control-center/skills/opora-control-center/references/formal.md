# Formální ověření: protipříklad → šetření → návrh opravy

Kdy mě číst: agent-state nabízí `verification.investigate` nebo `verification.fix`, nebo rozhodnutí
`verification_counterexample` / `verification_failed`. Kontrakt: `docs/oporahub-verification.md`.
Lean v CI dokazuje jen čisté jádro OporaHubu, ne kód karet (mezera `lean_verification`).

## `verification.investigate`

Nejnovější CI kontrola běhu (`formal/tlc`, `formal/lean`, `formal-trusted/*`) skončila
`counterexample`, `failed` nebo `inconclusive`.

1. `GET /api/oporahub/verifications/{id}`: požadavek (tvrzení, předpoklady, konfigurace) a výsledek.
2. Artefakty jen přes `GET /api/oporahub/verifications/{id}/artifacts/{sha256}` (stažení, nic nespouštěj;
   HTML ani SVG neotvírej). Protipříklad je stopa stavů: najdi první stav, který porušil tvrzení.
3. Rozliš: chyba modelu nebo konfigurace (meze, fairness), chyba kódu, nebo jen `runner_error`
   (infrastruktura, žádná oprava plánu). Zapiš závěr jako data, ne jako změnu.
4. Kniha důkazů pro souvislosti: `GET /api/oporahub/verifications/ledger`.

## `verification.fix`

`POST /api/oporahub/verifications/{id}/fix-proposal` (jen `project`, `workspace`) idempotentně založí
**návrh** karty „Opravit formální ověření“. Druhé volání nový návrh nevytvoří.

```bash
python "<SKILL_DIR>/scripts/opora_write.py" /api/oporahub/verifications/VER_ID/fix-proposal --project P --workspace W --json "{}"
```

Pak doplň do návrhu kroky ([planner.md](planner.md)): první krok reprodukuje protipříklad (selhávající
kontrola), další opravují, poslední znovu spustí ověření. Přijímá člověk; běh opravy je běžný claim
([hub-loop.md](hub-loop.md)). Nový požadavek ověření (`/api/oporahub/verifications/requests`) a jeho
výsledek posílá vykonavatel s tokenem běhu (CI nebo agent-office), ne ručně.
