# WU-DELETE-01 / T-01

2026-09-09T12:32:50.938001+00:00

Autor: Astra v Hermesu, jediný produkční writer v interním worktree. Uživatelský prompt a SPEC jsou součástí této karty. Před změnami základ main 000947d; skutečné produkční položky nebyly při testování mazány. RED příčiny a gate evidence v RESULT.md. Žádné credentials ani externí služby nejsou pro testy potřeba.

## Ověřený výsledek před integrací
35 Python testů PASS; 14 Playwright PASS; build, Ruff a statická bezpečnostní kontrola PASS. REVIEW.json PASS s přesnými source hashi; přidaný test historie nemění žádný kontrolovaný produkční soubor. 2 existující dependency warnings zachované.
