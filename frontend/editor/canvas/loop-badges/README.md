# loop-badges

Zobrazuje na plátně Editoru u každé karty malý odznak etapy smyčky OporaHubu (etapa + značka zdraví).
Data bere ze sdíleného čtení `GET /api/oporahub/agent-state` (`cards[]`, jeden poller s ETagem společný
s přehledem OporaHubu, `hub/oporahub-agent-state/logic/agent-state-store.ts`). Klik otevře drawer karty
v OporaHubu. Zapíná a vypíná se v Nastavení → Plátno („Odznaky etap OporaHubu“). Zrcadlo pro agenty:
`script#oh-card-stages` (`cards[]`).
