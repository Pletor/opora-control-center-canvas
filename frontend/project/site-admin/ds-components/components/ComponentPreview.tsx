import { previewDocument } from "../logic/components";

/** Živý náhled komponenty v iframu `sandbox=""` (bez skriptů, formulářů a navigace) nad CSS uložené revize. */
export default function ComponentPreview({ name, html, height, theme, project, tokensCss, componentsCss }: {
  name: string; html: string; height: number; theme: string; project: string; tokensCss: string; componentsCss: string;
}) {
  const doc = previewDocument({ html, tokensCss, componentsCss, theme, project, origin: location.origin });
  return <iframe className="ds-components__frame" title={"Náhled komponenty " + name} sandbox="" srcDoc={doc}
    style={{ height }} loading="lazy" tabIndex={-1} data-testid={"ds-component-frame-" + name}/>;
}
