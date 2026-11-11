import { useEffect, useRef, useState } from "react";
import "../styles/plan-scan.css";

type Props = { onStart: (url: string, note: string) => void; onClose: () => void };

/** Okno Skenovat web: adresa webu (povinná, http/https) a nepovinná poznámka „co z webu převzít“. Spustit předá obojí
 * rodiči a okno zavře; průběh a návrh ukáže panel skenu vedle plátna. Esc a Zrušit zavřou. */
export default function ScanDialog({ onStart, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [url, setUrl] = useState("https://");
  const [note, setNote] = useState("");
  useEffect(() => { const element = dialog.current!; element.showModal(); return () => element.close(); }, []);
  const valid = /^https?:\/\/[^\s/]+/i.test(url.trim());
  return <dialog ref={dialog} className="plan-scan__dialog" aria-labelledby="plan-scan-title" data-testid="architecture-scan-dialog"
    onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <form className="plan-scan__form" onSubmit={(event) => { event.preventDefault(); if (valid) { onStart(url, note); onClose(); } }}>
      <h2 id="plan-scan-title" className="plan-scan__title">Skenovat web</h2>
      <p className="plan-scan__lead">Výzkumník projde web a navrhne layout stránky z boxů i prvky logiky. Návrh se ukáže vedle současného layoutu; nic se nepřepíše, dokud ho nepřevezmete.</p>
      <label className="plan-scan__field">Adresa webu
        <input type="url" autoFocus required maxLength={2048} value={url} data-testid="architecture-scan-url" onChange={(event) => setUrl(event.target.value)}/></label>
      <label className="plan-scan__field">Co z webu převzít <small>(nepovinné)</small>
        <textarea rows={2} maxLength={500} value={note} placeholder="Třeba jen hlavičku a výzvu k nákupu" onChange={(event) => setNote(event.target.value)}/></label>
      <div className="plan-scan__actions">
        <button type="submit" disabled={!valid} data-testid="architecture-scan-start">Spustit sken</button>
        <button type="button" onClick={onClose}>Zrušit</button>
      </div>
    </form>
  </dialog>;
}
