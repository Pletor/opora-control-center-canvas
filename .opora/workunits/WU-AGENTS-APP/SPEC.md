# WU-AGENTS-APP — dostupné agentní API

Jeden uzavíraný krok: skutečný create_app připojí existující agentní router před statickým fallbackem. Zachovat Host/Origin/JSON a read-only guards. Datový model ani frontend se v tomto kroku nemění.

Owned: backend/app.py, tests/test_agents_app_integration.py, tento WU adresář.

Důkaz: původní RED404 na /api/agents/sources; GREEN200 se zdrojovými stavy, cizíOrigin403, veřejnéOpenAPI. Dále full backendpytest/Ruff, nezávisléClaude review přesného snapshotu, lokálnícommit a kontrola shody. Repo nemá nakonfigurovaný Gitremote; nevymýšlet PR/CI/push.

Výslovně mimo: frontendové tlačítkoAgenti (jeho nový e2e/agents-integration.spec.ts zůstává rozpracovaný), designvětve, Ample,context,harness,loop, produkčnínasazení.
