import { describe, expect, it } from "vitest";
import { clampHeight, componentNameProblem, groupComponents, newComponent, previewDocument, previewProblem } from "./components";

const item = (name: string, group?: string) => ({ name, group, readme: "", preview: "", height: 120 });

describe("komponenty design systému", () => {
  it("skupiny drží pořadí a bez skupiny jdou na konec", () => {
    const groups = groupComponents([item("Note"), item("Button", "Actions"), item("Card", "Layout"), item("Link", "Actions")]);
    expect(groups.map((group) => [group.group, group.items.map((one) => one.name)])).toEqual([
      ["Actions", ["Button", "Link"]], ["Layout", ["Card"]], ["Ostatní", ["Note"]]]);
  });

  it("jméno podle gramatiky tokenů, Button je serveru", () => {
    expect(componentNameProblem("card.small-2", [])).toBe("");
    expect(componentNameProblem("-card", [])).toMatch(/Jméno/);
    expect(componentNameProblem("Card", ["Card"])).toMatch(/už v systému/);
    expect(componentNameProblem("Card", ["Card"], "Card")).toBe("");
    expect(componentNameProblem("Button", [])).toMatch(/Tlačítek webu/);
    expect(newComponent(["Component"]).name).toBe("Component-2");
  });

  it("náhled odmítne totéž co server", () => {
    for (const bad of ["<script>x</script>", '<img onerror="x">', '<a href="javascript:x">', "<iframe>", "&#106;", '<div\nONclick = "x">'])
      expect(previewProblem(bad)).not.toBe("");
    expect(previewProblem('<button class="ds-btn">Online</button>')).toBe("");
    expect([clampHeight(10), clampHeight(5000), clampHeight(Number.NaN), clampHeight(88.4)]).toEqual([40, 4000, 120, 88]);
  });

  it("dokument náhledu: CSP, téma, fonty a assety z API", () => {
    const doc = previewDocument({
      html: '<img src="assets/Logos/mark.svg" alt="">', theme: 'dark"', project: "p1", origin: "http://127.0.0.1:5193",
      tokensCss: ':root, [data-theme="light"] {\n  --ink: #000;\n}\n@font-face {\n  src: url("fonts/inter.woff2") format("woff2");\n}\n',
      componentsCss: 'body {\n  background-image: url("assets/Bg/a.png");\n}\n</style><script>',
    });
    expect(doc).toContain('<html data-theme="dark&#34;">');
    expect(doc).toContain("default-src 'none'; style-src 'unsafe-inline'; img-src http://127.0.0.1:5193 data:");
    expect(doc).toContain('url("http://127.0.0.1:5193/api/site-admin/fonts/inter.woff2?project=p1")');
    expect(doc).toContain('url("http://127.0.0.1:5193/api/site-admin/assets/Bg/a.png?project=p1")');
    expect(doc).toContain('<img src="http://127.0.0.1:5193/api/site-admin/assets/Logos/mark.svg?project=p1" alt="">');
    expect(doc).not.toContain("</style><script>");
  });
});
