import type { PletorAction } from "../logic/linie-actions";
import { newsLines, trialButton, trialSentence, triedSentence, type Trial } from "../logic/linie-trial";
import LinieTrialButton from "./LinieTrialButton";
import LinieTrialSteps from "./LinieTrialSteps";

type Props = {
  trial: Trial; actions: PletorAction[]; onAct: (id: string) => void;
  /** Souhrn ukáže novinky od poslední zkoušky, Git obnovu dat z ostrých. */
  news?: boolean; fresh?: boolean;
};
const NO_START = { enabled: false, why: "pravidlo spuštění náhledu teď nenabízí" };

/**
 * Náhled kuličky v detailu: stav jednou větou, adresa, evidence zkoušky a tlačítko Vyzkoušet. Spustit náhled smí jen
 * akce `preview` z `allowed`; otevření běžícího náhledu hlásí `tried`, obnova dat `fresh`. Vše jde nahoru přes `onAct`.
 */
export default function LinieTrial({ trial: t, actions, onAct, news, fresh }: Props) {
  const lines = news ? newsLines(t) : [];
  return (
    <div className="pletor-dashboard__linie-detail-card linie-trial">
      <h3 className="pletor-dashboard__linie-detail-h">Náhled · zkouška</h3>
      <p className="linie-trial__state">{trialSentence(t)}{t.url && <> · <a href={t.url} target="_blank" rel="noreferrer">{t.url}</a></>}</p>
      <p className="linie-trial__tried">{triedSentence(t)}</p>
      <LinieTrialButton button={trialButton(t, actions.find((a) => a.id === "preview") ?? NO_START)} url={t.url} onStart={() => onAct("preview")} onTried={() => onAct("tried")} />
      <LinieTrialSteps steps={t.steps} />
      {lines.length > 0 && (
        <>
          <h3 className="pletor-dashboard__linie-detail-h">Nového od poslední zkoušky</h3>
          <ul className="linie-trial__news">{lines.map((line) => <li key={line}>{line}</li>)}</ul>
        </>
      )}
      {fresh && t.state !== "none" && (
        <p className="linie-trial__fresh">
          <button type="button" className="pletor-dashboard__button" disabled={t.state === "building"} onClick={() => onAct("fresh")}>Obnovit data z ostrých</button>
          <span className="linie-trial__note">Náhled dostane čerstvou kopii ostrých dat; co jsi v něm vytvořil nebo změnil, se zahodí.</span>
        </p>
      )}
    </div>
  );
}
