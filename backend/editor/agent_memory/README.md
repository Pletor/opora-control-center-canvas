Paměť projektu pro agenty: nastavení, pravidla must/must_not, připnutá rozhodnutí, fáze uzlu, porty bloků, uzavření karty a zprávy na vazbách (desktop_v3_state.py, revizovaný stav s CAS).
Výstup modelu opora.agent-output/1: stav bloků, zprávy na vazbách, návrh uzavření karty a rozhodnutí zapsané s by "agent" pod CAS revizí (agent_output.py).
Adresný přístup k jednomu bloku karty: čtení bloku s dětmi/rodičem a zápis add/update/remove/todo s přečíslováním pod CAS revizí (block_access.py).
Pracovní prostor agenta u karty: pět sekcí (rámec, postup, chyby, opravy, předávka) revizovaných jako text uzlu, částečný zápis pod CAS, smazání s kartou a souhrn vyplněnosti všech karet jedním dotazem (agent_workspace.py).
