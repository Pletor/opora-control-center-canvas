import { jsonTokens } from "../logic/json-tokens";

/** JSON se zvýrazněnými klíči, řetězci a čísly; žádné innerHTML, tokeny jsou obyčejné <span>. */
export default function JsonBlock({ value, tall }: { value: unknown; tall?: boolean }) {
  return <pre className={`live-card__pre${tall ? " live-card__pre--tall" : ""}`}>
    {jsonTokens(value).map((token, index) => token.kind === "plain" ? token.text
      : <span key={index} className={`live-card__json-${token.kind}`}>{token.text}</span>)}
  </pre>;
}
