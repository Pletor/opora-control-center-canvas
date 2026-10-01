import io
import json

from tools.opora_code_intelligence import main


class Reply:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self._data


def test_cli_calls_status_with_encoded_project_workspace_and_prints_json(capsys):
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return Reply({"providers": []})

    code = main(["--endpoint", "http://127.0.0.1:8740", "status", "--project", "p one", "--workspace", "draft"], opener=opener)

    assert code == 0
    assert captured == {"url": "http://127.0.0.1:8740/api/code-intelligence/status?project=p+one&workspace=draft", "method": "GET", "timeout": 15}
    assert json.loads(capsys.readouterr().out) == {"providers": []}


def test_cli_posts_exact_query_json(capsys):
    captured = {}

    def opener(request, timeout):
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return Reply({"status": "empty", "results": []})

    code = main(["query", "--project", "p", "--workspace", "draft", "--language", "python", "--path", "one.py", "--operation", "hover", "--line", "0", "--character", "0"], opener=opener)

    assert code == 0
    assert captured["method"] == "POST"
    assert captured["body"] == {"project": "p", "workspace": "draft", "language": "python", "path": "one.py", "operation": "hover", "line": 0, "character": 0}
    assert json.loads(capsys.readouterr().out)["status"] == "empty"
