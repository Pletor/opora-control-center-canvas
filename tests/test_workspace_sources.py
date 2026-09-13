from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"


def attach(client, source):
    response = client.post("/api/local-project", headers={"origin": ORIGIN}, json={
        "name": "Source project", "path": str(source), "confirmed": True,
    })
    assert response.status_code == 200
    return response.json()["id"]


def test_tree_reads_exact_lazy_children_without_changing_source(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / ".git").mkdir()
    (source / "README.md").write_text("untouched", encoding="utf-8")
    (source / "src" / "hello.py").write_text("private contents", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        response = client.get("/api/workspace/tree", params={"project": pid, "workspace": "draft"})
        assert response.status_code == 200
        tree = response.json()
        assert tree["path"] == "" and tree["root"] == str(source.resolve())
        assert [(x["path"], x["kind"]) for x in tree["entries"]] == [("src", "directory"), ("README.md", "file")]
        assert tree["hasMore"] is False and tree["total"] == 2
        child = client.get("/api/workspace/tree", params={"project": pid, "workspace": "draft", "path": "src"})
        assert child.status_code == 200
        assert [x["path"] for x in child.json()["entries"]] == ["src/hello.py"]
        assert "private contents" not in child.text
    assert (source / "README.md").read_text(encoding="utf-8") == "untouched"
    assert {x.name for x in source.iterdir()} == {"src", ".git", "README.md"}


def test_tree_paginates_without_hiding_the_remaining_entries(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ["a.py", "b.py", "c.py"]:
        (source / name).touch()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        params = {"project": pid, "workspace": "draft", "limit": 2}
        first = client.get("/api/workspace/tree", params=params).json()
        assert [x["name"] for x in first["entries"]] == ["a.py", "b.py"]
        assert first["total"] == 3 and first["hasMore"] is True and first["nextOffset"] == 2
        last = client.get("/api/workspace/tree", params={**params, "offset": first["nextOffset"]}).json()
        assert [x["name"] for x in last["entries"]] == ["c.py"]
        assert last["hasMore"] is False and last["nextOffset"] is None
        for update in [{"limit": 0}, {"offset": -1}, {"limit": 501}]:
            assert client.get("/api/workspace/tree", params={**params, **update}).status_code == 422
