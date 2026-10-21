# oporahub-mirror

Zobrazuje strojové zrcadlo dat pohledu OporaHubu: `<script type="application/json" id="oh-…">`, které agent
čte místo obrazovky (kontrakt `docs/oporahub-ui.md`). Dále sdílené jednorázové čtení JSON pro detaily
(`logic/hub-read.ts`, hook `logic/use-hub-read.ts`); data bere z endpointů `/api/oporahub/*`.
