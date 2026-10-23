# oporahub-review-gate

Logika kroku Review v detailu karty (zobrazuje ji záložka Review v `hub/oporahub-card-drawer`): stav brány merge, pravidlo, které ji drží, otevřené důležité
nálezy, bezpečnostní review, počet ověřených lidí proti požadovaným schválením, vlastní kontroly agenta,
zastarání proti cílové větvi a neúplnou šablonu PR. Data bere z `GET /api/oporahub/review-jobs/gates`
(docs/oporahub-review-jobs.md, `logic/review-gate.ts`) a pohled skládá `logic/gate-view.ts`. Samostatná
komponenta `CardReviewGate` a její styl byly odebrány, protože je nic nepřipojovalo.

Doklady po krocích plánu (`evidence.steps`: stav kroku, kontroly, commity, poznámka, kroky bez dokladu)
parsuje a skládá `logic/step-evidence.ts`; `GateView.steps` je hotový pohled pro záložku Review.
