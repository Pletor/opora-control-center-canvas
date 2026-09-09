# Závislosti a distribuce

Excalidraw 0.18.1 (MIT) je lazy-loaded. Fonty jsou lokální nezměněné soubory z npm balíčku, s původními embedded notices; jejich textová kopie a MIT notice jsou v public/third-party-notices.txt a jsou součástí buildu. Nejde o tvrzení, že všechny fonty jsou MIT.

Npm audit po přidání knihovny nalezl chyby v transitive nanoid/lodash-es. Scoped overrides: Excalidraw nanoid 3.3.18, mermaid converter nanoid 5.1.16, lodash-es 4.18.1. Následný production audit: 0 vulnerabilities. Npm hlásí starší peer deklarace Radix vůči React19; skutečné kreslení/persistence/tvůrčí nástroje se proto ověřují v UI testech. Vite upozorňuje na velké lazy chunks; nesnižujeme kontrolu, ale ověřujeme oddělení od počátečního bootu.

Archify je v tomto řezu exportní integrace typed JSON. Runtime mapa používá aktuální graph data a React Flow, nikoli vložený Archify viewer. Fixture export byl skutečně validován Archify CLI (standard, 9 kontrol, 0 chyb/varování); nejde o garanci layoutu libovolného hustého grafu.
