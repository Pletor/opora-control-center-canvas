---
name: restart-opora
description: "Restart lokálního serveru OPORY na portu 8740 po změně Pythonu (server nemá hot reload)."
disable-model-invocation: true
---

# restart-opora

## Kdy použít

Po sloučení nebo úpravě kódu v `backend/`, když běžící `uv run opora` na `127.0.0.1:8740` drží starý kód.
Neprovádět, dokud v témže pracovním stromu pracuje subagent (server běží z pracovního stromu).

## Postup

1. Zastav běžící server: ukonči proces `opora.exe` z `.venv` repozitáře i s jeho podprocesy
   (PowerShell: `Get-Process opora | Where-Object Path -like "*\.venv\*" | Stop-Process -Force`).
2. V kořeni repozitáře spusť na pozadí `uv run opora --no-open --no-build`.
3. Opakovaně (nejvýš asi 60 s) zkoušej `GET http://127.0.0.1:8740/api/bootstrap`.

## Ověření

Hotovo je až ve chvíli, kdy `/api/bootstrap` vrátí HTTP 200. Když nevrátí, ukaž poslední řádky výstupu serveru
a nic dalšího nespouštěj.
