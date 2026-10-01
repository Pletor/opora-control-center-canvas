// Jedna položka paměti role: odkud je, jak blízko byla dotazu a co v ní stojí. Dílek nic nenačítá
// ani neukládá — dostane hotovou položku v props. Původ je štítek, ne dekorace: půjčka od jiné role
// se nikdy nesmí číst jako vlastní zkušenost karty, proto má vlastní barvu i vlastní slovo.
import { formatScore, type MemoryItem } from "@/editor/node-detail/agent-workspace/memory/logic/agent-memory";

type OriginTone = "self" | "project" | "lent" | "unknown";

const ORIGIN_LABEL: Record<OriginTone, string> = {
  self: "Vlastní", project: "Projekt", lent: "Půjčka", unknown: "Neurčeno",
};

function toneOf(origin: string): OriginTone {
  if (origin === "self" || origin === "project") return origin;
  return origin.startsWith("lent:") ? "lent" : "unknown";
}

export default function AgentMemoryItem({ item }: { item: MemoryItem }) {
  const tone = toneOf(item.origin);
  return (
    <li className="agent-memory__item">
      <p className="agent-memory__item-head">
        <span className={`agent-memory__origin agent-memory__origin--${tone}`}>{ORIGIN_LABEL[tone]}</span>
        <span className="agent-memory__score">{formatScore(item.score)}</span>
        <code className="agent-memory__uri" title={item.uri}>{item.uri}</code>
      </p>
      {item.text
        ? <p className="agent-memory__text">{item.text}</p>
        : <p className="agent-memory__text agent-memory__text--empty">Položka nese jen adresu, žádný text.</p>}
    </li>
  );
}
