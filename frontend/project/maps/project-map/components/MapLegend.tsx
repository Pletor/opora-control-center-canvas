/** Legenda: co znamená velikost bubliny, tloušťka čáry a barva. */
export default function MapLegend({shownEdges,totalEdges,truncated}:{shownEdges:number;totalEdges:number;truncated:boolean}){
  return <dl className="project-map-legend" aria-label="Legenda mapy">
    <div className="project-map-legend__row"><dt className="project-map-legend__key project-map-legend__key--size"/><dd>Bublina = oblast kódu, která drží pohromadě; velikost a číslo = počet uzlů (soubory, třídy, funkce).</dd></div>
    <div className="project-map-legend__row"><dt className="project-map-legend__key project-map-legend__key--line"/><dd>Čára = vazby mezi oblastmi; čím silnější, tím víc volání a importů. Zobrazeno {shownEdges} nejsilnějších z {totalEdges}.</dd></div>
    <div className="project-map-legend__row"><dt className="project-map-legend__key project-map-legend__key--tone"/><dd>Barva jen odlišuje sousední oblasti, nenese význam. Kolečko přibližuje, tahem posouváte, klik vybere.</dd></div>
    {truncated&&<div className="project-map-legend__row"><dt className="project-map-legend__key"/><dd>Graf je velký: zobrazujeme jen největší oblasti a nejsilnější vazby.</dd></div>}
  </dl>;
}
