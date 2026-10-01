// Pracovní prostor agenta u jedné karty: nahoře přehled (kde stojím, co čeká, co dál), pod ním
// start pro nového agenta, komunikace a teprve nakonec pět složených polí, do kterých si model vede
// rámec, postup, co se nepovedlo, úspěšné opravy a předávku dál (docs/karta-pro-agenty.md). Člověk
// sem smí psát, ale prostor patří modelu — nic v něm není zadání. Rodič dodá jen souřadnice karty
// (project, workspace, nodeId) a to, jestli je uzavřená; o načtení a ukládání se stará
// useAgentWorkspace, node-brief se načte jednou zde a rozdá se dílcům v props. Rozepsaný text je
// lokální komponentě a ukládá se při opuštění pole (blur); při změně uzlu rodič komponentu
// remountuje přes `key`, takže se draft nikdy netáhne mezi kartami. Stejný obsah umí stát ve dvou
// rozloženích: „stack“ je dnešní sloupec do inspektoru, „segments“ rozprostře tytéž celky po ploše
// Agenti — tam rozbalení nedrží prostor, ale deska nad ním.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  SECTIONS,
  clampSection,
  sectionLink,
  type AgentWorkspaceSections,
  type SectionKey,
} from "@/editor/node-detail/agent-workspace/logic/agent-workspace";
import {
  briefReadOnlyFlags,
  overviewModel,
  sectionsOpenByDefault,
} from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import { useAgentOrientation } from "@/editor/node-detail/agent-workspace/logic/use-agent-orientation";
import { useAgentWorkspace } from "@/editor/node-detail/agent-workspace/logic/use-agent-workspace";
import AgentCommunication from "@/editor/node-detail/agent-workspace/components/AgentCommunication";
import AgentMemoryPanel from "@/editor/node-detail/agent-workspace/memory/components/AgentMemoryPanel";
import AgentMemorySections from "@/editor/node-detail/agent-workspace/components/AgentMemorySections";
import AgentOrientation from "@/editor/node-detail/agent-workspace/components/AgentOrientation";
import AgentOverview from "@/editor/node-detail/agent-workspace/components/AgentOverview";
import AgentSegmentsLayout from "@/editor/node-detail/agent-workspace/segments/components/AgentSegmentsLayout";
import type { SegmentId, SegmentOpen } from "@/editor/node-detail/agent-workspace/segments/logic/agent-segments";
import "@/editor/node-detail/agent-workspace/styles/agent-workspace.css";

const COPIED_MS = 1500;

/** Jen pět pojmenovaných polí, bez updatedAt/by — tvar, který drží draft i „nezměnilo se“ porovnání. */
function sectionValues(source: AgentWorkspaceSections): AgentWorkspaceSections {
  const out = {} as AgentWorkspaceSections;
  for (const { key } of SECTIONS) out[key] = source[key];
  return out;
}

function fmtUpdatedAt(value: string): string {
  if (!value) return "Zatím neuloženo";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("cs-CZ");
}

export default function AgentWorkspace({
  project, workspace, nodeId, readOnly,
  layout = "stack", open, onToggle, onGoTo, onExpandAll, onCollapseAll, onMemoryDefaults,
  agentRole = null, onRoleChange,
}: {
  project: string;
  workspace: string;
  nodeId: string;
  /** Uzavřená karta nebo main bez zápisu: rodič to pozná (done.confirmed / readOnly view) a pošle sem. */
  readOnly: boolean;
  /** „stack“ = sloupec do inspektoru (výchozí), „segments“ = pojmenované celky na ploše Agenti. */
  layout?: "stack" | "segments";
  /** Jen pro „segments“: co je rozbalené, drží deska pro celou aplikaci. */
  open?: SegmentOpen;
  onToggle?: (id: SegmentId, open: boolean) => void;
  /** Odkaz z přehledu do segmentu: deska ho cestou rozbalí, ať kotva nemíří do zavřeného celku. */
  onGoTo?: (id: SegmentId) => void;
  onExpandAll?: () => void;
  onCollapseAll?: () => void;
  /** Které pole paměti už něco nese; deska z toho složí výchozí rozbalení pro nově vybranou kartu. */
  onMemoryDefaults?: (memory: Record<SectionKey, boolean>) => void;
  /** Role karty (`agentRole` ze stavu Desktop v3); bez ní se paměť role nečte ani nezapisuje. */
  agentRole?: string | null;
  /** Uloží roli na uzel deska, která drží stav a revizi; bez callbacku je výběr role jen ke čtení. */
  onRoleChange?: (role: string | null) => void;
}) {
  const { record, loading, error, readOnly: recordReadOnly, save } = useAgentWorkspace(project, workspace, nodeId);
  const orientation = useAgentOrientation(project, workspace, nodeId);
  const locks = briefReadOnlyFlags(orientation.brief);
  const disabled = readOnly || recordReadOnly || loading;
  const segments = layout === "segments";
  const [drafts, setDrafts] = useState<AgentWorkspaceSections>(() => sectionValues(record));
  const baseline = useRef<AgentWorkspaceSections>(sectionValues(record));
  const [localOpen, setLocalOpen] = useState<Record<SectionKey, boolean>>(() => sectionsOpenByDefault(record));
  const [copied, setCopied] = useState<SectionKey | null>(null);
  const copiedTimer = useRef<number | null>(null);
  const sectionOpen: Record<SectionKey, boolean> = segments && open ? open : localOpen;
  // Zavřený panel komunikace ještě nic nenačetl; kolik věcí čeká, ví zatím jen brief.
  const pendingHint = useMemo(() => {
    const { communication } = overviewModel(orientation.brief, record, { closed: locks.closed, mainReadOnly: locks.mainReadOnly });
    return communication.awaitingReceipt + communication.needsClarification;
  }, [orientation.brief, record, locks.closed, locks.mainReadOnly]);

  // Sesouhlasení s tím, co přišlo ze serveru: pole, které uživatel nezměnil, dostane novou hodnotu;
  // rozepsané pole (liší se od dosavadního baseline) se nepřepíše, ani po konfliktu při ukládání.
  useEffect(() => {
    const next = sectionValues(record);
    setDrafts((current) => {
      const merged = { ...current };
      for (const { key } of SECTIONS) if (current[key] === baseline.current[key]) merged[key] = next[key];
      return merged;
    });
    baseline.current = next;
  }, [record]);

  // Které sekce jsou rozbalené, rozhoduje uživatel; sám se přehled poskládá jen ve chvíli, kdy
  // dorazí uložený stav ze serveru (loading spadne na false) — jinak by zavřená sekce ožila při psaní.
  useEffect(() => {
    if (loading) return;
    const memory = sectionsOpenByDefault(record);
    setLocalOpen(memory);
    onMemoryDefaults?.(memory);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  useEffect(() => () => { if (copiedTimer.current) window.clearTimeout(copiedTimer.current); }, []);

  function edit(key: SectionKey, value: string) {
    if (disabled) return;
    setDrafts((current) => ({ ...current, [key]: clampSection(value) }));
  }

  function blur(key: SectionKey) {
    if (disabled || drafts[key] === baseline.current[key]) return;
    void save({ [key]: drafts[key] });
  }

  function toggleSection(key: SectionKey, isOpen: boolean) {
    if (segments && onToggle) onToggle(key, isOpen);
    else setLocalOpen((current) => (current[key] === isOpen ? current : { ...current, [key]: isOpen }));
  }

  async function copyLink(key: SectionKey) {
    try {
      await navigator.clipboard.writeText(sectionLink(nodeId, key));
      setCopied(key);
      if (copiedTimer.current) window.clearTimeout(copiedTimer.current);
      copiedTimer.current = window.setTimeout(() => setCopied(null), COPIED_MS);
    } catch {
      // Schránka nemusí být dostupná (oprávnění, kontext bez HTTPS) — odkaz jde přečíst i z title atributu.
    }
  }

  const head = <header className="agent-workspace__head">
    <span className={"agent-workspace__by" + (record.by === "agent" ? " agent-workspace__by--agent" : "")}>
      {record.by === "agent" ? "Naposledy psal agent" : "Naposledy psal člověk"}
    </span>
    <span className="agent-workspace__updated">{loading ? "Načítám…" : fmtUpdatedAt(record.updatedAt)}</span>
  </header>;
  const overview = <AgentOverview
    brief={orientation.brief} workspaceRecord={record} loading={orientation.loading} error={orientation.error}
    closed={locks.closed} mainReadOnly={locks.mainReadOnly} nodeId={nodeId}
    onGoTo={onGoTo} onExpandAll={onExpandAll} onCollapseAll={onCollapseAll}
  />;
  // Dokud brief nedorazil, zámek nepojmenováváme: víme jen, že zápis nejde, ne proč.
  const lockNote = (readOnly || recordReadOnly) && !loading && !orientation.brief && !orientation.loading
    ? <p className="agent-workspace__readonly muted">Zápis je zamčený; důvod se přečte z briefu karty.</p>
    : null;
  const errorNote = error ? <div className="agent-workspace__error" role="alert">{error}</div> : null;
  const start = <AgentOrientation
    nodeId={nodeId} brief={orientation.brief} loading={orientation.loading}
    error={orientation.error} reload={orientation.reload}
  />;
  // Potvrzené převzetí i odeslaná zpráva mění počty v přehledu, proto se brief načte znovu.
  const communication = <AgentCommunication
    project={project} workspace={workspace} nodeId={nodeId} readOnly={readOnly || recordReadOnly}
    pendingHint={pendingHint} onChanged={orientation.reload}
  />;
  const memory = <AgentMemorySections
    nodeId={nodeId} drafts={drafts} open={sectionOpen} disabled={disabled} copied={copied}
    onEdit={edit} onBlur={blur} onCopyLink={(key) => void copyLink(key)}
    onToggle={toggleSection} layout={layout}
  />;

  // Paměť role sahá na cizí službu (OpenViking) a potřebuje na obrazovce místo na výběr role, dotaz,
  // skupiny výsledků a dva formuláře. Proto stojí jen na ploše Agenti; úzký sloupec inspektoru ji
  // nedostane a nic se tam kvůli ní nenačítá.
  const roleMemory = segments ? <AgentMemoryPanel
    project={project} workspace={workspace} nodeId={nodeId} readOnly={readOnly || recordReadOnly}
    brief={orientation.brief} agentRole={agentRole} onRoleChange={onRoleChange}
  /> : null;

  if (segments) return <AgentSegmentsLayout
    nodeId={nodeId} open={open} onToggle={onToggle} start={start} communication={communication}
    roleMemory={roleMemory} memory={memory}
    overview={<>{head}{errorNote}{overview}{lockNote}</>}
  />;

  return (
    <section className="agent-workspace" aria-label="Pracovní prostor agenta" data-testid="agent-workspace">
      {head}
      {errorNote}
      {overview}
      {lockNote}
      {start}
      {communication}
      {memory}
    </section>
  );
}
