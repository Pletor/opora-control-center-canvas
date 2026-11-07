/** Hlava celé obrazovky: jeden řádek „VELÍN · LINIE“ a vpravo věta Pletora (táž, kterou panel říká bez výběru). */
export default function LinieFullHead({ say }: { say: string }) {
  return (
    <header className="pletor-dashboard__linie-fullhead">
      <h2 className="pletor-dashboard__linie-fullhead-title">Velín · Linie</h2>
      <p className="pletor-dashboard__linie-fullhead-say" title={say}><strong>Pletor</strong> {say}</p>
    </header>
  );
}
