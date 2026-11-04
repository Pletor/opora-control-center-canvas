import "../styles/pletor-listener.css";
import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent, type MouseEvent, type ReactNode } from "react";
import type { HudState } from "../logic/hud-state";
import type { PletorMessage } from "../logic/pletor-client";
import { readListenPrefs, writeListenPrefs, type ListenPrefs } from "../logic/listen-prefs";
import { clampPosition, defaultPosition, type Size } from "../logic/popup-position";
import PletorListenerBody from "./PletorListenerBody";
import PletorListenSwitch from "./PletorListenSwitch";

type Props = {
  state: HudState; label: string; level: () => number | null; interim: string; messages: PletorMessage[]; error: string;
  onListening: (on: boolean) => void; onInterrupt: () => void; onFullscreen: () => void; settings: ReactNode;
};

const LOG_SIZE = 6;
const DRAG_PX = 4; // menší pohyb je klik (na jádro = přerušit řeč), ne přetažení

/**
 * Plovoucí popup „Pletor poslouchá“ (přepínač Poslech zapnutý a HUD zavřený): po ruce ukazuje, co Pletor dělá,
 * bez pevného chatu. Jádro, stav, živý přepis a poslední odpověď skládá PletorListenerBody; přepis zpráv je
 * sbalený pod tlačítkem. Přetahuje se za záhlaví nebo jádro (myš i dotyk), drží se v okně, poloha se pamatuje
 * pro aplikaci (listen-prefs); dvojklik na záhlaví ho vrátí do výchozího rohu. V záhlaví vedle přepínače Poslech
 * stojí ozubené kolo nastavení (`settings` od rodiče), kde je i volba „jen na oslovení“.
 */
export default function PletorListener({ state, label, level, interim, messages, error, onListening, onInterrupt, onFullscreen, settings }: Props) {
  const ref = useRef<HTMLElement>(null);
  const [prefs, setPrefs] = useState<ListenPrefs>(readListenPrefs);
  const [size, setSize] = useState<Size>({ w: 0, h: 0 });
  const [viewport, setViewport] = useState<Size>(() => ({ w: window.innerWidth, h: window.innerHeight }));
  const [log, setLog] = useState(false);
  const drag = useRef<{ dx: number; dy: number; x: number; y: number; moved: boolean } | null>(null);
  const dragged = useRef(false);
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const measure = () => setSize({ w: element.offsetWidth, h: element.offsetHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const resize = () => setViewport({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  const at = prefs.position ? clampPosition(prefs.position, size, viewport) : defaultPosition(size, viewport);
  // Ukládá jen polohu nad tím, co je v úložišti: „jen na oslovení“ mezitím mohlo změnit nastavení.
  const save = (next: ListenPrefs) => { setPrefs(next); writeListenPrefs({ ...readListenPrefs(), position: next.position }); };

  function down(event: PointerEvent<HTMLElement>) {
    if (event.button !== 0 || !(event.target as Element).closest("[data-drag]")) return;
    if ((event.target as Element).closest("[role=switch], [data-pletor-settings-toggle], .pletor-listener__button")) return;
    dragged.current = false;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { dx: event.clientX - at.x, dy: event.clientY - at.y, x: event.clientX, y: event.clientY, moved: false };
  }
  function move(event: PointerEvent<HTMLElement>) {
    const current = drag.current;
    if (!current) return;
    if (!current.moved && Math.hypot(event.clientX - current.x, event.clientY - current.y) < DRAG_PX) return;
    current.moved = true;
    setPrefs((old) => ({ ...old, position: clampPosition({ x: event.clientX - current.dx, y: event.clientY - current.dy }, size, viewport) }));
  }
  function up() {
    dragged.current = !!drag.current?.moved;
    if (dragged.current) save(prefsRef.current);
    drag.current = null;
  }
  // Klik po přetažení (pustit myš nad jádrem) nesmí utnout řeč.
  function click(event: MouseEvent) {
    if (dragged.current) event.stopPropagation();
    dragged.current = false;
  }

  const reply = [...messages].reverse().find((message) => message.role === "pletor")?.text ?? "";
  return (
    <section ref={ref} className="pletor-listener" aria-label="Pletor poslouchá" style={{ left: at.x, top: at.y }}
      onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onClickCapture={click}>
      <header className="pletor-listener__head" data-drag title="Táhni pro přesun, dvojklik = výchozí roh"
        onDoubleClick={() => save({ ...prefs, position: null })}>
        <strong className="pletor-listener__title">Pletor poslouchá</strong>
        <PletorListenSwitch on onChange={onListening} />
        {settings}
      </header>
      <PletorListenerBody state={state} label={label} level={level} interim={interim} reply={reply} onInterrupt={onInterrupt} />
      {error && <p className="pletor-listener__error" role="alert">{error}</p>}
      <div className="pletor-listener__tools">
        <button type="button" className="pletor-listener__button" aria-expanded={log} onClick={() => setLog((open) => !open)}>Přepis</button>
        <button type="button" className="pletor-listener__button" disabled={state !== "speaking"} onClick={onInterrupt}>Přerušit</button>
        <button type="button" className="pletor-listener__button" aria-label="Plná obrazovka" title="Plná obrazovka (HUD)" onClick={onFullscreen}>⛶</button>
      </div>
      {log && (
        <ol className="pletor-listener__log" aria-label="Poslední zprávy">
          {messages.length === 0 && <li className="pletor-listener__entry">Zatím nic.</li>}
          {messages.slice(-LOG_SIZE).map((message, index) => (
            <li key={index} className={`pletor-listener__entry pletor-listener__entry--${message.role}`}>{message.text}</li>
          ))}
        </ol>
      )}
    </section>
  );
}
