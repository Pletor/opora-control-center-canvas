# Zrcadlo po zápisu brány: podstata podle symbolů (zkušební dokument)

Symbolová mapa slouží Zrcadlu; cestu práce od zadání ke commitu nese vodotisk `OP-…` (`docs/navrhy/2026-11-06-linie-vodotisk-cesty.md`).

Tento dokument popisuje podstatu věci přes **LSP symboly**, ne přes čísla řádků. Symbol se dá dohledat (`workspaceSymbol`, `goToDefinition`) a jeho volající a čtenáře dá `findReferences` / `incomingCalls`. Řádky se mění, symboly drží. Kontrakt Zrcadla je v `docs/zrcadlo.md`; tady je jen mapa „podstata → symbol“.

Zápis symbolu: `` `soubor::symbol` `` (soubor od kořene repozitáře).

## Podstata 1: Zrcadlo nikdy neblokuje bránu

Brána zapíše fragment a teprve potom, mimo svůj zámek, zavolá Zrcadlo. Výsledek ani porucha Zrcadla odpověď brány nemění.

- Volající: `backend/editor/brief_vault/brief_vault.py::BriefVault.apply` (po transakci brány volá `after_gate`).
- Obal, který nikdy nevyhodí výjimku: `backend/editor/brief_vault/brief_vault_mirror.py::after_gate`.
- Vlastní práce: `backend/editor/brief_vault/brief_vault_mirror.py::_after_gate`.

## Podstata 2: volá se jen po bráně `synthesized` / `verified`

- Mapa bran na akce klienta: `backend/editor/brief_vault/brief_vault_mirror.py::MIRROR_GATES` (`synthesized` → `predict`, `verified` → `observe`).
- Akce klienta: `backend/integrations/mirror_client.py::MirrorClient.predict`, `backend/integrations/mirror_client.py::MirrorClient.observe`.

## Podstata 3: výchozí vypnuto, zapnutí pro konkrétní projekt

- Rozhodnutí „klient, nebo nic“: `backend/integrations/mirror_client.py::client_for` (vrací `None`, když je vypnuto nebo projekt není v seznamu).
- Nastavení z prostředí: `backend/integrations/mirror_client.py::settings`.
- Jen loopback: `backend/integrations/mirror_client.py::loopback_url`.

## Podstata 4: tvrdý strop čekání

- Strop (2 s): `backend/integrations/mirror_client.py::TIMEOUT_SECONDS`.
- Jediné místo sítě a chyb: `backend/integrations/mirror_client.py::MirrorClient._call`.

## Jak dokument ověřit

Pro každý symbol výše musí `documentSymbol` uvedeného souboru obsahovat jeho jméno (u `Třída.metoda` třídu a metodu pod ní). `workspaceSymbol` je jen fuzzy hledání a vrací i testy s podobným názvem, takže soubor z cesty v dokumentu je při kontrole povinný filtr. Symbol, který LSP v souboru nenajde, je v dokumentu zastaralý (přejmenovaný nebo smazaný) a dokument se opraví. Testy a volající symbolu dá `findReferences`, v dokumentu je proto nepíšeme.
