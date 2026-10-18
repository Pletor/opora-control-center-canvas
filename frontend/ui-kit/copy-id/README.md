Tichý čip „ID“ pro technický identifikátor (doména, stránka, uzel). ID se nečte v textu karty: je v `title` čipu a kliknutím se zkopíruje do schránky (čip na chvíli řekne „Zkopírováno“). Člověk ho potřebuje zřídka, typicky když ho předává agentovi.

- `components/CopyIdButton.tsx`: props `id` a `label` (například „ID domény“); nic neukládá, jen kopíruje.
- `styles/copy-id.css`, blok `copy-id`.
