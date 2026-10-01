// Kdo na kartě naposledy pracoval, jedním žetonem: robot = agent, postava = člověk, prázdné kolečko =
// paměť karty je zatím prázdná. Dílek dostane hotový stav a jen ho nakreslí; barvy nese CSS.
import type { WorkState } from "@/editor/node-detail/agent-workspace/logic/agent-overview";
import Icon from "@/ui-kit/icon/components/Icon";
import type { IconName } from "@/ui-kit/icon/logic/icon-paths";
import "@/editor/node-detail/agent-summary/styles/agent-summary.css";

const WORK: Record<WorkState, { icon: IconName; label: string; title: string }> = {
  agent: { icon: "bot", label: "agent", title: "Do paměti karty naposledy psal agent." },
  human: { icon: "user", label: "člověk", title: "Do paměti karty naposledy psal člověk." },
  empty: { icon: "circle", label: "prázdná", title: "Paměť karty je zatím prázdná." },
};

export default function WorkChip({ state }: { state: WorkState }) {
  const work = WORK[state];
  return (
    <span className={`agent-summary__work agent-summary__work--${state}`} title={work.title} data-testid="work-chip">
      <Icon name={work.icon} size={16} />
      {work.label}
    </span>
  );
}
