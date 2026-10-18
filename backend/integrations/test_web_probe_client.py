import json
import socket
import ssl

from backend.integrations import web_probe_client as client
from backend.integrations.web_probe_client import probe_host

PUBLIC = "93.184.216.34"


class FakeResponse:
    def __init__(self, status, body=b"", headers=None):
        self.status, self.body, self.headers = status, body, headers or {}
        self.requested = None

    def getheader(self, name):
        return self.headers.get(name)

    def read(self, amount):
        self.requested = amount
        return self.body[:amount]


class FakeConnection:
    def __init__(self, routes, host, ip, error=None):
        self.routes, self.host, self.ip, self.error = routes, host, ip, error
        self.sock = object()
        self.paths = []
        self.response = None

    def request(self, method, path, headers=None):
        self.paths.append(path)
        if self.error:
            self.sock = None if isinstance(self.error, ConnectionRefusedError) else self.sock
            raise self.error

    def getresponse(self):
        self.response = self.routes[self.paths[-1]]
        return self.response

    def close(self):
        pass


def run(routes=None, error=None, addresses=(PUBLIC,), health=None, host="app.example.cz"):
    seen = []

    def factory(h, ip, timeout):
        connection = FakeConnection(routes or {}, h, ip, error)
        seen.append(connection)
        return connection

    def resolver(h):
        return list(addresses)

    return probe_host(host, health, resolver=resolver, connection_factory=factory), seen


def test_dns_missing_when_resolver_fails():
    def resolver(host):
        raise socket.gaierror(11001, "nenalezeno")
    assert probe_host("x.example.cz", resolver=resolver)["state"] == "dns_missing"


def test_dns_no_web_when_no_addresses():
    assert run(addresses=())[0]["state"] == "dns_no_web"


def test_private_loopback_and_mixed_addresses_rejected_without_connecting():
    for address in ("10.0.0.5", "127.0.0.1", "169.254.1.1", "::1", "224.0.0.1", "192.168.1.1"):
        result, seen = run(addresses=(address,))
        assert result["state"] == "unreachable" and result["detail"] == "privátní adresa odmítnuta"
        assert seen == []
    assert run(addresses=(PUBLIC, "10.0.0.1"))[0]["state"] == "unreachable"


def test_connection_pinned_to_verified_ip_with_host_name():
    result, seen = run({"/": FakeResponse(200)})
    assert result["state"] == "up" and seen[0].ip == PUBLIC and seen[0].host == "app.example.cz"


def test_refused_443_is_dns_no_web():
    assert run(error=ConnectionRefusedError())[0]["state"] == "dns_no_web"


def test_tls_error_and_5xx_are_unreachable():
    assert run(error=ssl.SSLError("bad cert"))[0]["state"] == "unreachable"
    result, _ = run({"/": FakeResponse(502)})
    assert result["state"] == "unreachable" and result["httpStatus"] == 502


def test_read_timeout_is_unreachable():
    assert run(error=TimeoutError())[0]["state"] == "unreachable"


def test_200_up_and_redirect_not_followed_with_location():
    assert run({"/": FakeResponse(200)})[0]["state"] == "up"
    result, seen = run({"/": FakeResponse(301, headers={"Location": "https://www.example.cz/"})})
    assert result["state"] == "up" and "https://www.example.cz/" in result["detail"]
    assert seen[0].paths == ["/"]


def test_read_is_capped_at_64_kb():
    response = FakeResponse(200, b"x" * 200000)
    run({"/": response})
    assert response.requested == 64 * 1024


def health_routes(status, payload):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return {"/": FakeResponse(200), "/h": FakeResponse(status, body)}


def test_health_states():
    assert run(health_routes(200, {"status": "ok"}), health="/h")[0]["state"] == "up"
    degraded = run(health_routes(200, {"status": "degradovano"}), health="/h")[0]
    assert degraded["state"] == "degraded" and degraded["health"] == "degradovano"
    assert run(health_routes(503, {"status": "nedostupno"}), health="/h")[0]["state"] == "unreachable"
    assert run(health_routes(503, b"oops"), health="/h")[0]["state"] == "unreachable"


def test_unparsable_health_with_2xx_is_up_with_detail():
    result, _ = run(health_routes(200, b"<html>"), health="/h")
    assert result["state"] == "up" and "health" in result["detail"]


def test_public_address_helper():
    assert client.is_public_address(PUBLIC) and not client.is_public_address("::ffff:10.0.0.1")
