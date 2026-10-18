Ohraničený LSP adaptér nad jedním workspace: dotazy na jazykový server pro prostředí Editor. Router je v `backend/api/editor/code_intelligence_routes.py`, nástroj pro terminál v `tools/opora_code_intelligence.py`.

- `scoped_lsp.py` spouští jazykový server jen nad vybraným podstromem a vrací omezené odpovědi (`CodeIntelligence`, `QueryRequest`).
