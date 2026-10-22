# Záložka Lens

Obal prostoru `frontend/hub/review-lens/` v detailu karty (mezi Kroky a Běh, jen u karet, ne u sektorů). Data čte `CardDrawer` přes `useReviewLens` jednou při otevření a po „Obnovit“, protože je potřebuje i odznak záložky (krátká hlava PR, nebo „plán“, když je jen mapa oblasti před kódem) a zrcadlo `script#oh-card-drawer` (`lens: {kind, headSha, nodes, edges}`). Přímý odkaz: `?ohCard=<id>&ohTab=lens`. Na záložce Lens se drawer rozšíří, aby plátno uneslo celý diagram.
