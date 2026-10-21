import { useEffect, useState } from "react";
import type { OverviewModels } from "../logic/models";
import { acceptedPlan, pendingDecisions, observedExecutionLabel, nextExecutionStep, type DetailTarget } from "../logic/overview";
import { checkLabels } from "@/hub/git-evidence/logic/git-evidence";
import "../styles/oporahub-overview.css";

export default function OporaHubOverview({ models, open }: { models: OverviewModels; open: (target: DetailTarget) => void }) {
  const { graphProposals: graph, changes, executions, evidence, reconciliation, reviewPolicy } = models;
  const plan = acceptedPlan(graph.context, changes.context);
  const decisions = pendingDecisions(graph.items, changes.items, plan.head, plan.basisKnown);
  const uncertain = graph.busy || changes.busy || !!graph.error || !!changes.error || !!plan.warning;
  const loaded = `${graph.items.length} návrhů grafu · ${changes.items.length} zadání · limit 100 na historii`;
  const [clock, setClock] = useState(() => performance.now());
  const [observation, setObservation] = useState({ items: executions.executions, at: performance.now() });
  useEffect(() => { setObservation({ items: executions.executions, at: performance.now() }); }, [executions.executions]);
  useEffect(() => { const timer = setInterval(() => setClock(performance.now()), 1000); return () => clearInterval(timer); }, []);
  const elapsed = observation.items === executions.executions ? Math.max(0, clock - observation.at) / 1000 : 0;
  const work = executions.executions.slice(0, 6);
  const items = evidence.items;
  const events = [
    ...graph.items.map(item => ({ key: item.id, time: item.createdAt, text: `${item.by.name}: ${item.subject}`, target: { kind: "graph" as const, id: item.id, title: item.subject }, source: "Návrh grafu" })),
    ...changes.items.map(item => ({ key: item.id, time: item.createdAt, text: `${item.by.name}: ${item.subject}`, target: { kind: "changes" as const, id: item.id, title: item.subject }, source: "Návrh zadání" })),
    ...executions.executions.filter(item => item.createdAt).map(item => ({ key: item.executionId, time: item.createdAt!, text: `${item.owner ?? "Neznámý vlastník"}: vytvořen běh`, target: { kind: "executions" as const, id: item.executionId, title: "Podrobnosti běhu" }, source: "Execution" })),
    ...items.map(item => ({ key: item.snapshot.id, time: item.snapshot.observedAt, text: `GitHub: PR #${item.snapshot.pr?.number ?? item.snapshot.prNumber ?? "?"} · ${item.snapshot.complete ? checkLabels[item.evaluation.checks.status] : "neúplné pozorování"}`, target: { kind: "evidence" as const, id: item.snapshot.id, title: "Důkazy z GitHubu" }, source: "Pozorování GitHubu" })),
  ].filter(item => Number.isFinite(Date.parse(item.time))).sort((a, b) => Date.parse(b.time) - Date.parse(a.time)).slice(0, 5);
  const sourceErrors = [graph.error && "návrhy grafu", changes.error && "zadání", executions.error && "běhy", evidence.error && "GitHub", reconciliation.error && "sledování", reviewPolicy.error && "pravidla review"].filter(Boolean);
  return <div className="oporahub-overview">
    <header className="oporahub-overview__identity"><div><h1>OporaHub</h1><p>Přehled aktuálního pracovního prostoru</p></div>
      <div className="oporahub-overview__revision"><span>Přijatý plán</span><code>{plan.head?.slice(0, 12) ?? "Nezaložen / nedostupný"}</code>
        <span className="oporahub-overview__working">{plan.differs === null ? "Pracovní rozdíl nezjištěn" : plan.differs ? "Pracovní verze se liší" : "Pracovní verze odpovídá"}</span></div>
      <button type="button" className="oporahub-overview__primary" onClick={() => open({ kind: "graph", title: "Kontrola přijatého plánu" })}>{!plan.head ? "Zkontrolovat základ plánu" : "Nový návrh plánu"}</button>
    </header>
    {(plan.warning || sourceErrors.length > 0) && <p className="oporahub-overview__warning" role="status">{plan.warning} {sourceErrors.length > 0 && `Nedostupné zdroje: ${sourceErrors.join(", ")}. Zobrazený přehled není úplný.`}</p>}
    <section className="oporahub-overview__stages" aria-label="Od plánu ke kontrole">
      <button onClick={() => open({ kind: "graph", title: "Plán a návrhy" })}><strong>Plán <small>Canvas vlastní plány</small></strong><b>{uncertain ? "Podklady čekají na kontrolu" : `${decisions.length} načtených návrhů k rozhodnutí`}</b><span>{loaded}</span></button>
      <button onClick={() => open({ kind: "executions", title: "Práce agentů" })}><strong>Práce <small>Agent Office provádí</small></strong><b>{executions.busy ? "Načítám běhy…" : executions.error ? "Běhy nejsou dostupné" : `${executions.executions.length} načtených běhů`}</b><span>Nejvýše 100 · {executions.nodeId ? "vybraná karta" : "všechny karty prostoru"}</span></button>
      <button onClick={() => open({ kind: "evidence", title: "Důkazy z GitHubu" })}><strong>Důkaz <small>GitHub vlastní kód · jen čtení</small></strong><b>{evidence.busy ? "Načítám důkazy…" : evidence.error ? "Důkazy nejsou dostupné" : `${items.length} načtených pozorování PR`}</b><span>Nahlášený výsledek vyžaduje nezávislé ověření.</span></button>
      <button onClick={() => open({ kind: "policy", title: "Pravidla nezávislé kontroly" })}><strong>Kontrola <small>Rozhoduje člověk</small></strong><b>{reviewPolicy.busy ? "Načítám pravidla…" : reviewPolicy.error ? "Pravidla nejsou dostupná" : reviewPolicy.context?.policy ? "Pravidla review nastavena" : "Pravidla review nedoložena"}</b><span>{reconciliation.context ? `${reconciliation.context.items.length} načtených vazeb sledování` : "Sledování není doloženo"} · merge není nasazení.</span></button>
    </section>
    <div className="oporahub-overview__columns"><div className="oporahub-overview__main">
      <section className="oporahub-overview__panel oporahub-overview__panel--decisions"><header><h2>Potřebuje rozhodnutí</h2><span>{uncertain ? "Neúplné podklady" : `${decisions.length} v načtené historii`}</span></header>
        {decisions.slice(0, 3).map(item => <article className="oporahub-overview__decision" key={item.id}><div><strong>{item.title}</strong> <span className={item.stale ? "oporahub-overview__tag oporahub-overview__tag--warning" : "oporahub-overview__tag"}>{item.stale === null ? "Základ neověřen" : item.stale ? "Zastaralé · jiný základ" : item.kind === "graph" ? "Změna grafu" : "Změna zadání"}</span><p>{item.author} · {item.impact}</p></div><button type="button" onClick={() => open(item)}>Zkontrolovat změnu</button></article>)}
        {!decisions.length && <p className="oporahub-overview__empty">{uncertain ? "Před rozhodnutím načtěte úplné podklady." : "V načtené historii nejsou nové nepřijaté návrhy."}</p>}
        {decisions.length > 3 && <button className="oporahub-overview__more" onClick={() => open({ kind: "history", title: "Historie a všechny návrhy" })}>Zobrazit další načtené návrhy ({decisions.length - 3})</button>}
      </section>
      <section className="oporahub-overview__panel"><header><h2>Práce agentů</h2><span>6 posledních z nejvýše 100 načtených</span></header>
        <div className="oporahub-overview__table"><div className="oporahub-overview__table-head"><span>Karta a vlastník</span><span>Stav oprávnění</span><span>Další krok</span><span>Pokus</span></div>
          {work.map(item => <button type="button" className="oporahub-overview__work" key={item.executionId} onClick={() => open({ kind: "executions", id: item.executionId, title: `Běh · ${executions.choices.find(node => node.id === item.nodeId)?.name ?? item.nodeId}` })}>
            <span><strong>{executions.choices.find(node => node.id === item.nodeId)?.name ?? "Odstraněná / nedostupná karta"}</strong><small>{item.owner ?? "Vlastník není doložen"}</small></span><span>{observedExecutionLabel(item, elapsed)}<small>{item.acceptedRevision !== plan.head ? "Jiná / neověřená revize plánu" : "Aktuální přijatá revize"}</small></span><span>{nextExecutionStep(item, elapsed)}<small>PR nenavázáno</small></span><span>{item.budget ? `#${item.budget.attempt}` : "v1 · limit neznámý"}</span>
          </button>)}</div>
        {!work.length && <p className="oporahub-overview__empty">{executions.busy ? "Načítám běhy…" : executions.error ? "Historie běhů není dostupná." : "Zatím žádné běhy v tomto výběru."}</p>}
        <button className="oporahub-overview__more" onClick={() => open({ kind: "executions", title: "Všechny načtené běhy a výsledky" })}>Historie, výsledky a zrušení běhu</button>
      </section>
    </div><aside className="oporahub-overview__aside">
      <section className="oporahub-overview__panel"><header><h2>Co se stane dál</h2></header><ul className="oporahub-overview__next">
        <li><span>Vy</span><button onClick={() => open({ kind: "graph", title: "Plán a rozhodnutí" })}>{!plan.head ? "Zkontrolujte výchozí plán a přijměte jeho přesný obsah." : decisions.length ? "Zkontrolujte návrhy; zastaralé nejprve převeďte na aktuální základ." : "Můžete navrhnout další změnu plánu."}</button></li>
        <li><span>Agent</span><button onClick={() => open({ kind: "budgets", title: "Pravidla a limity běhů" })}>Před převzetím načte přijaté zadání, oprávnění a zbývající pokusy.</button></li>
        <li><span>Vy</span><button onClick={() => open({ kind: "evidence", title: "Nezávislé důkazy a kontrola" })}>Nahlášené výsledky porovnejte s důkazy pro přesný commit.</button></li>
        <li><span>GitHub</span><button onClick={() => open({ kind: "tracking", title: "Zdraví sledování GitHubu" })}>Stav PR a zdraví sledování jsou samostatné od review a nasazení.</button></li>
      </ul></section>
      <section className="oporahub-overview__panel"><header><h2>Poslední aktivita</h2><span>Načtené zdroje</span></header><ul className="oporahub-overview__activity">{events.map(item => <li key={item.key}><time dateTime={item.time}>{new Date(item.time).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" })}</time><button onClick={() => open(item.target)}>{item.text}<small>{item.source} · {new Date(item.time).toLocaleDateString("cs-CZ")}</small></button></li>)}</ul>{!events.length && <p className="oporahub-overview__empty">V načtených zdrojích nejsou doložené časové události.</p>}</section>
    </aside></div>
    <section className="oporahub-overview__api"><strong>Pro agenty</strong>{["Číst přijatý plán", "Navrhnout změnu", "Převzít zadání a limity", "Odevzdat nahlášený výsledek"].map((text, index) => <span key={text}><b>{index + 1}</b>{text}</span>)}<button onClick={() => open({ kind: "api", title: "Rozhraní pro agenty" })}>Ukázat API</button></section>
    <footer className="oporahub-overview__footer"><button onClick={() => open({ kind: "changes", title: "Návrh změny zadání" })}>Upravit zadání karty</button><button onClick={() => open({ kind: "budgets", title: "Pravidla kontroly a limity karet" })}>Limity běhů</button><button onClick={() => open({ kind: "policy", title: "Pravidla review" })}>Pravidla review</button><button type="button" onClick={() => open({ kind: "formal", title: "Formální podklady" })}>Formální podklady</button><button onClick={() => open({ kind: "history", title: "Starší historie a původní formuláře" })}>Starší historie a původní formuláře</button><button onClick={() => { graph.refresh(); changes.refresh(); executions.refresh(); evidence.refresh(); reconciliation.refresh(); reviewPolicy.refresh(); models.formalVerification.refresh(); models.onRefresh(); }}>Obnovit podklady</button></footer>
  </div>;
}
