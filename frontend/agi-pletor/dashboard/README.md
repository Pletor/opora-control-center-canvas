# agi-pletor/dashboard

VelĂ­n AGI Pletor: strĂˇnka `?screen=pletor` s levou navigacĂ­ po ÄŤĂˇstech (kontrakt `docs/navrhy/2026-11-05-pletor-opora-dashboard.md`).

- `components/PletorDashboard.tsx`: rodiÄŤ; drĹľĂ­ aktivnĂ­ ÄŤĂˇst (`part=` v adrese), Esc a titulek s focusem. SklĂˇdĂˇ dĂ­lky `DashboardOverview`, `DashboardBrain`, `DashboardVoice` a vklĂˇdĂˇ `PletorWorkshop`.
- `logic/dashboard-route.ts`: ÄŤĂˇsti, parsovĂˇnĂ­ a zĂˇpis `part=`; `overview-cards.ts`: stav Pletora na karty PĹ™ehledu; `use-voice-list.ts`: hlasy serveru.
- `styles/pletor-dashboard.css`: blok `pletor-dashboard`.

MilnĂ­k V1: PĹ™ehled, Mozek a LLM, Hlas, DĂ­lna. Srdce a Podklady (V2), Monitoring a Rozhovor (V3), NastavenĂ­ (V4) jsou zatĂ­m jen mĂ­sto s hlĂˇĹˇkou.

Dluh V1: ÄŤĂˇst Hlas je jen ke ÄŤtenĂ­. VĂ˝bÄ›r hlasu a â€žVyzkouĹˇetâ€ś jsou v `usePletorVoice`, kterĂ˝ drĹľĂ­ jen `PletorWindow`; vĂ˝bÄ›r zĹŻstĂˇvĂˇ v kokpitu (ozubenĂ© kolo). VyĹ™eĹˇit vytaĹľenĂ­m hlasu do sdĂ­lenĂ©ho kontextu.

`logic/dashboard-nav.ts`: zasunutí levého menu do ikon (`localStorage` `pletor.nav`, klávesa `[`).
