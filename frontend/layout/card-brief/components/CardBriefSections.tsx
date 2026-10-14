// Tělo zadání: pět sekcí ve stejném pořadí, v jakém balíček čte model — cíl a konec, harness,
// smyčka, předávky, pracovní prostor. Každá je rámeček s hlavičkou (žeton s ikonou, název, tiché
// číslo vpravo) a tělem pod ní. Barva žetonu jde na kategorii, jejíž barevný tón sekci nejlíp
// vystihuje (cíl → workflows, harness → pipelines, smyčka → pravidla, předávky → hooky, prostor →
// agenti), takže si čtyři z pěti barev z katalogu půjčí i zadání karty. Ikona ale mluví o obsahu
// sekce, ne o kategorii: terč (kam mířím), čip (čím to udělám), smyčka (co zbývá), šipky tam a zpět
// (od koho komu) a složka (co si u karty vedu). Všechno je jen ke čtení:
// žádné pole, žádný zápis, žádné spouštění. Dílek dostane hotový pohled z `briefSummary` a nic si
// nedopočítává kromě drobných součtů pro tiché číslo v hlavičce sekce.
//
// Rámeček sekce, dvojice klíč–hodnota, odškrtnutí a soused jsou vlastní dílky (`CardBriefParts`);
// tenhle soubor jen říká, co kam patří a v jakém pořadí se to čte.
import { Check, Hand, Kv, Section } from "@/layout/card-brief/components/CardBriefParts";
import type { BriefSummary } from "@/layout/card-brief/logic/card-brief-view";

export default function CardBriefSections({ summary }: { summary: BriefSummary }) {
  const { goal, harness, loop, handoffs, workspace } = summary;
  const noGoal = !goal.goal && !goal.criteria.length && !goal.stopConditions.length;
  const noHarness = !harness.actions.length && !harness.steps.length;
  const noHands = !handoffs.incoming.length && !handoffs.outgoing.length && !handoffs.parent && !handoffs.children;
  const noSpace = !workspace.frame && !workspace.handoff;
  // Tichá čísla do hlavičky sekce — jen součet toho, co sekce už stejně vypisuje, na první pohled.
  const goalMeta = goal.criteria.length
    ? `${goal.criteria.filter((c) => c.checked).length}/${goal.criteria.length} splněno`
    : "";
  const harnessMeta = harness.actions.length
    ? `${harness.actions.length} ${harness.actions.length === 1 ? "akce" : "akcí"}`
    : harness.steps.length
      ? `${harness.steps.filter((s) => s.done).length}/${harness.steps.length} hotovo`
      : "";
  const loopMeta = loop.openBlocks > 0 ? `${loop.openBlocks} ${loop.openBlocks === 1 ? "blok" : "bloky"}` : "";
  const handoffCount = handoffs.incoming.length + handoffs.outgoing.length + (handoffs.parent ? 1 : 0);
  const handoffMeta = handoffCount > 0 ? `${handoffCount} ${handoffCount === 1 ? "vazba" : "vazby"}` : "";
  return (
    <div className="card-brief__brief-body" data-testid="card-brief-sections">
      <Section title="Cíl a konec" category="workflows" icon="target" meta={goalMeta} empty={noGoal}>
        {goal.goal && <p className="card-brief__section-text">{goal.goal}</p>}
        {goal.criteria.length > 0 && (
          <ul className="card-brief__checks">
            {goal.criteria.map((criterion, index) => (
              <Check key={criterion.id || index} text={criterion.text} checked={criterion.checked} />
            ))}
          </ul>
        )}
        {goal.stopConditions.length > 0 && (
          <ul className="card-brief__lines">
            {goal.stopConditions.map((condition, index) => (
              <li className="card-brief__line card-brief__line--stop" key={index}>
                {condition}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Harness" category="pipelines" icon="cpu" meta={harnessMeta} empty={noHarness}>
        {harness.actions.map((action, index) => (
          <div className="card-brief__action" key={action.id || index}>
            <span className="card-brief__action-label">{action.label}</span>
            {action.pipelineId && <code className="card-brief__action-pipeline">{action.pipelineId}</code>}
            {action.params.map((param) => (
              <Kv key={param.key} label={param.key} value={param.value} />
            ))}
          </div>
        ))}
        {harness.steps.length > 0 && (
          <ul className="card-brief__checks">
            {harness.steps.map((step, index) => (
              <Check key={step.id || index} text={step.text} checked={step.done} />
            ))}
          </ul>
        )}
      </Section>

      <Section title="Smyčka" category="rules" icon="repeat" meta={loopMeta}>
        <Kv label="Otevřené bloky" value={String(loop.openBlocks)} />
        {loop.lastReport ? (
          <p className="card-brief__section-text">{loop.lastReport}</p>
        ) : (
          <p className="card-brief__section-empty">Zatím žádná zpráva na vazbě.</p>
        )}
      </Section>

      <Section title="Předávky" category="hooks" icon="arrow-left-right" meta={handoffMeta} empty={noHands}>
        {handoffs.parent && (
          <ul className="card-brief__hands">
            <Hand icon="arrow-up" name={handoffs.parent.name} handoff={handoffs.parent.handoff} />
          </ul>
        )}
        {handoffs.incoming.length > 0 && (
          <ul className="card-brief__hands">
            {handoffs.incoming.map((item, index) => (
              <Hand key={item.id || index} icon="arrow-left" name={item.name} handoff={item.handoff} />
            ))}
          </ul>
        )}
        {handoffs.outgoing.length > 0 && (
          <ul className="card-brief__hands">
            {handoffs.outgoing.map((item, index) => (
              <Hand key={item.id || index} icon="arrow-right" name={item.name} handoff={item.handoff} />
            ))}
          </ul>
        )}
        <Kv label="Karty uvnitř" value={String(handoffs.children)} />
      </Section>

      <Section title="Pracovní prostor" category="agents" icon="folder" empty={noSpace}>
        {workspace.frame && (
          <p className="card-brief__space">
            <span className="card-brief__space-label">Rámec</span>
            {workspace.frame}
          </p>
        )}
        {workspace.handoff && (
          <p className="card-brief__space">
            <span className="card-brief__space-label">Předávka</span>
            {workspace.handoff}
          </p>
        )}
      </Section>
    </div>
  );
}
