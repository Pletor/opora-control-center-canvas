# Soukromý pohled srdce

Člověk výslovně připojí kartu prohlížeče ke konkrétní živé relaci srdce. Připojení ukládá tajemství pouze do sessionStorage. Backend ukládá otisk, krátký pronájem a potvrzení skutečně zobrazené revize.

Rozhraní `/api/canvas-view-attachments`: GET `sessions`, POST `attach`, `poll`, `pending`, `ack`, `detach`. Vše vyžaduje lidskou UI relaci; agent nemůže potvrdit vlastní zobrazení. Potvrzení váže scope, attachmentId, secret, revision, renderEpoch a view. Kamera, výběr a textový filtr nemění sdílené rozložení karet.

Nevykreslitelný výběr v jiné vrstvě se nepotvrzuje. Člověk otevře vrstvu a zvolí Použít znovu. Ruční pohyb nebo výběr zneplatní potvrzení; další revize srdce se zobrazuje znovu. Odpojení zachová uložený záměr srdce, ale zruší oprávnění tohoto prohlížeče potvrzovat zobrazení.
