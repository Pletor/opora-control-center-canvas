Lokální sémantické vyhledávání bez sítě nad výslovně vybraným podstromem workspace, pro prostředí Editor. Router je v `backend/api/editor/semantic_routes.py`.

- `service.py` (`SemanticRetrieval`) sebere soubory podstromu, rozdělí je na úseky a pošle je s dotazem lokálnímu workeru; `status` řekne, zda je model k dispozici.
