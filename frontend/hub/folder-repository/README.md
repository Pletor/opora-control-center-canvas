# folder-repository

Karta nad „Trvalým sledováním GitHub PR“ pro projekt z lokální složky: člověk jednou připojí GitHub repozitář,
na který ukazuje `origin` složky, a větev. Server připojení ověří na disku (`git remote get-url origin`, existence
větve) a uloží ho jako metadata projektu; od té chvíle pro projekt platí sledování PR, review důkazy a merge
(docs/oporahub-github.md, oddíl „Projekt z lokální složky“). Čte `GET /api/oporahub/repository`, zapisuje
`POST` téhož a `POST …/unbind`. U projektu klonovaného z GitHubu (`applies: false`) se karta nezobrazí.
