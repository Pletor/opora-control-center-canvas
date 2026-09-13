import { Component, type ReactNode } from "react";
export default class WorkspaceBoundary extends Component<
  { children: ReactNode; onExit: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="drawing-unavailable" role="alert">
        <h2>Pracovní plocha není dostupná</h2>
        <p>
          Kreslicí modul se nepodařilo načíst nebo vykreslit. Chyba nevyvolává
          automatické mazání dat. Pro nový pokus lze po uložení ostatní práce
          obnovit stránku.
        </p>
        <button onClick={this.props.onExit}>Vrátit se do Struktury</button>
      </div>
    );
  }
}
