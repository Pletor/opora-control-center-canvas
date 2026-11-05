type Props = { onDiscard: () => void; onKeep: () => void };

/** Inline varování místo blokujícího dialogu: člověk chce jinam, ale editor má neuloženou změnu. */
export default function WorkshopPending({ onDiscard, onKeep }: Props) {
  return (
    <div className="pletor-workshop__pending" role="alert">
      <span className="pletor-workshop__pending-text">Neuložená změna. Uložit, nebo zahodit a přejít?</span>
      <button type="button" className="pletor-workshop__button pletor-workshop__button--danger" onClick={onDiscard}>Zahodit</button>
      <button type="button" className="pletor-workshop__button" onClick={onKeep}>Zůstat</button>
    </div>
  );
}
