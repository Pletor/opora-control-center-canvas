"""Ověří integritu syntézy; není to test produkčních funkcí editoru."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import subprocess
import sys

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[2]


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = load("source-manifest.json")
    source = Path(manifest["source"])
    assert sha(source) == manifest["source_sha256"], "Původní zdroj se změnil"
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == manifest["line_count"]
    coverage = Counter()
    decisions = []
    for name in ("bridge", "connector", "voice", "vision"):
        review = load(f"reviews/{name}.json")
        for interval in review["coverage"]:
            coverage.update(range(interval["start"], interval["end"] + 1))
        decisions.extend(review["prompt_dispositions"])
        for contract in review["contracts"]:
            start, end = contract["source_lines"]
            assert 1 <= start <= end <= len(lines), contract["id"]
    assert set(coverage) == set(range(1, len(lines) + 1))
    assert all(count == 1 for count in coverage.values())
    expected = {p["id"]: p for p in manifest["prompts"]}
    counts = Counter(p["id"] for p in decisions)
    assert set(counts) == set(expected) and all(n == 1 for n in counts.values())
    assert load("prompt-decisions.json") == sorted(decisions, key=lambda p: p["id"])
    for decision in decisions:
        item = expected[decision["id"]]
        assert decision["source_start"] == item["start"], decision["id"]
        assert decision["source_start"] <= decision["source_end"] <= item["end"]
    reference_files = 0
    for ref in load("reference-sources.json"):
        for entry in ref["files"]:
            path = Path(ref["root"]) / entry["path"]
            assert sha(path) == entry["sha256"], f"Změněný podklad: {path}"
            for start, end in entry["read_ranges"]:
                assert 1 <= start <= end <= entry["line_count"], str(path)
            reference_files += 1
    assert len(load("reference-sources.json")) == 6
    spec = (OUT / "EDITOR-SPEC.md").read_text(encoding="utf-8-sig")
    modules = re.findall(r"^\| (M\d\d) \|", spec, re.M)
    assert modules == [f"M{i:02}" for i in range(1, 13)]
    gates = (OUT / "DELIVERY-GATES.md").read_text(encoding="utf-8-sig")
    slices = re.findall(r"^\| (R\d\d) \|", gates, re.M)
    assert slices == [f"R{i:02}" for i in range(9)]
    citations = set()
    checked_links = 0
    for path in OUT.glob("*.md"):
        text = path.read_text(encoding="utf-8-sig")
        assert sum(line.startswith("```") for line in text.splitlines()) % 2 == 0, path.name
        assert not any(ord(c) < 32 and c not in "\n\r\t" for c in text)
        body = text.split("## Sources", 1)[0]
        citations.update(int(x) for x in re.findall(r"\[(\d+)\]", body))
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if ":" not in link and not link.startswith("#"):
                assert (path.parent / link.split("#")[0]).exists(), (path.name, link)
                checked_links += 1
    assert citations == set(range(1, 24)), sorted(citations)
    browser = load("system-map.visual-check.json")
    assert browser["status"] == "pass"
    assert sha(OUT / "system-map.html") == browser["artifact"]["sha256"]
    assert len(browser["containment"]["viewports"]) == 4
    assert all(v["ok"] for v in browser["containment"]["viewports"])
    for capture in browser["captures"]["screenshots"]:
        assert (OUT / capture["file"]).exists()
    diff = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--"], check=False)
    assert diff.returncode == 0, "Změněné sledované soubory projektu"
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    result = {
        "artifact_integrity": "pass", "source_unchanged": True,
        "source_sha256": sha(source), "lines_accounted_for": len(coverage),
        "unique_prompts": len(counts), "reference_projects": 6,
        "unchanged_reference_files": reference_files,
        "modules": len(modules), "delivery_slices_including_onboarding": len(slices),
        "citation_ids_used_across_documents": len(citations),
        "local_links_checked": checked_links,
        "code_head": head, "tracked_application_files_unchanged": True,
        "diagram_browser_evidence": browser["status"],
        "diagram_specification_sha256": sha(OUT / "system-map.json"),
        "diagram_artifact_sha256": sha(OUT / "system-map.html"),
        "scope_note": "Integrity checks over reported complete-read coverage and design artifacts; not implemented editor tests or production certification."
    }
    final = OUT / "reviews/synthesis-final.json"
    if final.exists():
        review = load("reviews/synthesis-final.json")
        assert review["passed"] and not review["remaining_blockers"]
        result["design_reverification"] = review["verdict"]
    else:
        result["design_reverification"] = "pending"
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
