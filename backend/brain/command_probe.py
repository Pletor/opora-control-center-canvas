"""Exercise the trusted CLI parser and dispatch with an isolated, network-free collector."""
import importlib.util
from types import SimpleNamespace


def probe(script, argv):
    spec = importlib.util.spec_from_file_location("opora_cli_probe", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.os = SimpleNamespace(environ={"OPORA_BASE_URL": "http://127.0.0.1:9", "OPORA_GATE_TOKEN": "probe-only"})
    module.print = lambda *args, **kwargs: None
    calls = []

    def request(base, route, params=None, binary=False, headers=None):
        if route == "/api/health":
            return {"status": "ok", "product": "Opora Canvas"}
        calls.append({"method": "GET", "route": route, "arguments": params})
        return {"card": {"content": "canonical"}}

    def post(base, route, payload, headers=None):
        calls.append({"method": "POST", "route": route, "arguments": payload})
        return {}

    module.request, module.post_query = request, post
    # Older baselines have a no-argument main. Use its private argparse module proxy,
    # never process-global sys.argv, environment, network or model-supplied Python.
    original = module.argparse.ArgumentParser
    parsed = {}
    class Parser(original):
        def parse_args(self, args=None, namespace=None):
            result = super().parse_args(argv, namespace)
            if result.command not in ("node-brief", "research-context", "knowledge-search", "research-card"):
                raise ValueError("Not a supported scoped read capability.")
            if result.base_url is not None or result.api_base is not None or result.out is not None:
                raise ValueError("Connection and output overrides are not allowed.")
            parsed.update(vars(result))
            return result
    module.argparse = SimpleNamespace(ArgumentParser=Parser)
    try:
        status = module.main()
    except SystemExit as error:
        raise ValueError("CLI parser rejected the command.") from error
    if status != 0 or len(calls) != 1:
        raise ValueError("CLI did not produce one successful scoped read.")
    return {**calls[0], "parsed": parsed}
