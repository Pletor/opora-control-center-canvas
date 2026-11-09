export default function StoryboardReview({ disabled, busy, href, error, onPropose }: {
  disabled: boolean; busy: boolean; href: string; error: string; onPropose: () => void;
}) {
  return <>
    {href ? <a href={href}>Otevřít návrh přijetí v OporaHubu</a>
      : <button type="button" disabled={disabled || busy} onClick={onPropose} title="Uložená scéna se předloží jako stávající změna obsahu. Uložení samo není přijetí.">
        {busy ? "Připravuji návrh…" : "Navrhnout přijetí"}</button>}
    {error && <span className="storyboard__status storyboard__status--conflict" role="alert">{error}</span>}
  </>;
}
