# Návrh: oddělený ověřovatel buňky (k review, neimplementováno)

Stav: NÁVRH, rozhodne člověk po review. Navazuje na `docs/schranka-bunka.md` §5 (BLOCKED: atestace).

## Problém

`verified.actual.run` dnes podává agent pod deklarovaným jménem (`X-Opora-Actor`). Server ověří jen to, že je záznam
konzistentní. Neověří, že běh proběhl, nad jakými testy a nad jakým artefaktem. Writer, tedy navrhovatel nebo
vykonavatel na stejném stroji pod stejným uživatelem OS, může:
- změnit testy,
- podvrhnout výstup,
- podepsat se cizím jménem.

Proto platí: `run` = **reported / untrusted**. Nedává právo schválit ani uzavřít kartu a netvrdí bezpečné ověření.

## Co musí atestace zaručit

1. **Připnuté testy:** otisk stromu zdrojů kontrol (`testsDigest`) se uloží už v `synthesized`, tedy před výkonem.
   Testy se mezi koly nemění, stejně jako `checks`.
2. **Připnutý artefakt:** vykonavatel před ověřením odevzdá otisk artefaktu (`artifactDigest`: strom souborů, nebo git
   commit/tree). Ověřovatel běží jen nad obsahem s tímto otiskem.
3. **Mimo vliv writera:** proces ověřovatele, jeho testy i klíč leží tam, kam writer nemůže zapisovat ani číst.
4. **Doklad svázaný s kontextem:** podpis přes `(project, fragmentId, revision, testsDigest, artifactDigest, checks,
   exitCodes, outputSha256, at)`. Server podpis ověří a teprve pak uloží `trust: "attested"`.
5. **Žádná tajemství v repu:** klíč vzniká lokálně mimo repo i mimo datový kořen čitelný agenty. Do konfigurace
   (`opora.local.toml`, mimo git) jde jen veřejný klíč.

## Varianty

| Varianta | Mimo vliv writera | Cena / zásah | Poznámka |
|---|---|---|---|
| A. Lokální ověřovatel pod **jiným účtem Windows** (ACL na testy a klíč), podpis Ed25519 | jen s odděleným sandboxem bez klíče (viz Rozpor z review) | malá až střední: CLI + sandbox + ověření podpisu v `brief_vault_cell`, nová konfigurace veřejného klíče | kandidát, až po vyřešení rozporu |
| B. CI runner (GitHub Actions) nad pushnutým commitem, podpis/odkaz na běh | ano | vyžaduje push a síť, dnes zakázáno | vhodné později pro skutečné projekty |
| C. Server spouští kontroly sám | ne (server = stejný stroj/uživatel) | porušuje §10 („spouštění kontrol serverem“ nestavět) | nedoporučeno |
| D. Stejný účet, jen HMAC klíč v souboru | **ne**, writer klíč přečte | malá | falešný pocit bezpečí, zamítnout |

## Rozpor z review (Hermes, 2026-10-15): jiný účet sám nestačí

Ve variantě A by ověřovatel spouštěl **nedůvěryhodný artefakt** pod účtem, který čte podpisový klíč. Testovaný kód
by pak klíč mohl přečíst a podpis zfalšovat. Atestace proto potřebuje dvě oddělené části:

- **Spouštěcí sandbox:**
  - nemá klíč, síť ani přístup k živým datům;
  - nesmí měnit připnuté testy;
  - vrací jen výstupy běhu.
- **Podepisovač / ověřovatel:**
  - drží klíč a nikdy nespouští cizí kód;
  - porovná manifest a výstupy sandboxu a podepíše je.
- **Pevný manifest** obsahuje víc než testy a artefakt:
  - přesné příkazy a jejich závislosti (interpret, verze balíčků / lockfile);
  - vazbu na kontext proti přehrání (replay): `project`, `fragmentId`, `revision`, jednorázová hodnota, čas.

Varianta A v podobě z tabulky výše je proto **nedostatečná**. Řez níže platí jen s tímto oddělením. Implementační
rozhodnutí (nový runtime, auth, konfigurace) zůstává na review. `reported` zůstává untrusted a neodemyká schválení
ani uzavření karty.

## Minimální řez varianty A (po schválení, jen s oddělením výše)

- **`synthesized`:** `testsDigest` (64 hex). CLI ho spočítá z `--tests` při návrhu.
- **Nová operace `op: "submit-artifact"` od vykonavatele:** `{fragmentId, expectedRevision, artifactDigest}`.
  Append-only záznam bez nové tabulky: payload v historii revizí, jako `note`.
- **`opora_verify.py` pod účtem ověřovatele:**
  1. zkopíruje artefakt;
  2. ověří `artifactDigest` a `testsDigest`;
  3. spustí `checks`;
  4. podepíše výsledek privátním klíčem z profilu účtu ověřovatele.
- **Server:** ověří podpis veřejným klíčem z `[verifier] public_key` v `opora.local.toml`. Platný podpis znamená
  `trust: "attested"`, bez podpisu zůstává `"reported"`. Změna konfigurace = rozhodnutí člověka.

## Otevřené otázky pro review

- Smí kontrola atestovaná ověřovatelem někdy nahradit lidské uzavření karty? Návrh: ne, jen změní štítek.
- Jaký formát má mít otisk artefaktu: git tree, nebo vlastní manifest? Rozhoduje to, zda pískoviště musí být git repo.
- Kdo spravuje účet ověřovatele a rotaci klíče?
