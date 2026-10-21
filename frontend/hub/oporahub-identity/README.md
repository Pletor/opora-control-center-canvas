# oporahub-identity

Zobrazuje registr lidských identit pro review (drawer „Lidé v review“ z paty OporaHubu): nárok, ověřovací řádek
`Opora-Identity: <id> <nonce>` ke zkopírování na GitHub, ověření, seznam ověřených lidí, operátora a zrušení.
Data bere z `/api/oporahub/review-identities` (docs/oporahub-review-identity.md). Jen pro člověka: ověřovací
řádek se nikdy nedostane do `data-oh-*` ani do zrcadla `oh-review-identities`.
