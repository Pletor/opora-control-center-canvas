"""Kontrola jednoho hosta přes HTTPS: jediné místo, kde Opora sahá na cizí web (docs/domeny-a-worktree.md §8).

Jen stdlib. Disciplína jako u `openviking_client.py`: bez proxy, bez sledování přesměrování, explicitní
timeouty a strop odpovědi 64 KB. Navíc ochrana proti SSRF: host se přeloží, privátní/loopback/link-local/
multicast/rezervované adresy se odmítnou a spojení se připne na ověřenou IP (SNI a Host zůstávají jménem hosta).

Výsledek je slovník `{state, httpStatus, health, latencyMs, detail}`; stavy: dns_missing, dns_no_web,
unreachable, up, degraded. Nic se nenahrazuje odhadem: nejistý překlad jména je `dns_missing`.
"""

import http.client
import ipaddress
import json
import socket
import ssl
import time

MAX_RESPONSE_BYTES = 64 * 1024
CONNECT_TIMEOUT_SECONDS = 3.0
TOTAL_TIMEOUT_SECONDS = 5.0
HTTPS_PORT = 443

# getaddrinfo: NXDOMAIN, SERVFAIL i jméno bez A/AAAA končí gaierror (na Windows 11001/11004 bez rozlišení),
# proto každé selhání resolveru hlásíme jako dns_missing; dns_no_web vzniká jen z prázdného seznamu adres.
# 4xx znamená, že server odpovídá, takže je to "up" (stav webu, ne správnost cesty).


def _result(state, detail, http_status=None, health=None, started=None):
    latency = None if started is None else int((time.monotonic() - started) * 1000)
    return {"state": state, "httpStatus": http_status, "health": health, "latencyMs": latency, "detail": detail}


def default_resolver(host):
    return [info[4][0] for info in socket.getaddrinfo(host, HTTPS_PORT, type=socket.SOCK_STREAM)]


def is_public_address(value):
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if getattr(address, "ipv4_mapped", None):
        address = address.ipv4_mapped
    return not (address.is_private or address.is_loopback or address.is_link_local
                or address.is_multicast or address.is_reserved or address.is_unspecified)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS spojení na pevnou IP; SNI a Host jsou jméno hosta, ověřuje se certifikát toho jména."""

    def __init__(self, host, ip, timeout, context):
        super().__init__(host, HTTPS_PORT, timeout=timeout, context=context)
        self._pinned_ip = ip

    def connect(self):
        sock = socket.create_connection((self._pinned_ip, HTTPS_PORT), timeout=CONNECT_TIMEOUT_SECONDS)
        sock.settimeout(self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _default_connection_factory(host, ip, timeout):
    return PinnedHTTPSConnection(host, ip, timeout, ssl.create_default_context())


def _fetch(connection, path):
    connection.request("GET", path, headers={"Host": connection.host, "User-Agent": "opora-web-probe", "Connection": "close", "Accept": "application/json, */*"})
    response = connection.getresponse()
    body = response.read(MAX_RESPONSE_BYTES)
    return response.status, response.getheader("Location"), body


def _parse_health(body):
    try:
        status = json.loads(body.decode("utf-8", "replace")).get("status")
    except (ValueError, AttributeError):
        return None
    return status if status in {"ok", "degradovano", "nedostupno"} else None


def probe_host(host, health_path=None, resolver=default_resolver, connection_factory=_default_connection_factory):
    started = time.monotonic()
    try:
        addresses = resolver(host)
    except (socket.gaierror, UnicodeError, OSError):
        return _result("dns_missing", "DNS jméno neexistuje nebo ho nelze přeložit", started=started)
    if not addresses:
        return _result("dns_no_web", "DNS bez záznamu A/AAAA", started=started)
    if not all(is_public_address(address) for address in addresses):
        return _result("unreachable", "privátní adresa odmítnuta", started=started)
    ip = addresses[0]
    try:
        connection = connection_factory(host, ip, TOTAL_TIMEOUT_SECONDS)
    except OSError as error:
        return _result("unreachable", f"spojení nelze založit: {error}", started=started)
    try:
        try:
            status, location, _ = _fetch(connection, "/")
        except ssl.SSLError as error:
            return _result("unreachable", f"chyba TLS: {error}", started=started)
        except (ConnectionRefusedError, socket.timeout, TimeoutError) as error:
            if connection.sock is None:
                return _result("dns_no_web", "port 443 odmítnut nebo bez odpovědi", started=started)
            return _result("unreachable", f"vypršelo čtení: {error}", started=started)
        except (OSError, http.client.HTTPException) as error:
            return _result("dns_no_web" if connection.sock is None else "unreachable", f"spojení selhalo: {error}", started=started)
        if status >= 500:
            state, detail = "unreachable", f"HTTP {status}"
        else:
            state, detail = "up", (f"HTTP {status}, přesměrování na {location}" if 300 <= status < 400 and location else f"HTTP {status}")
        result = _result(state, detail, http_status=status, started=started)
        if health_path and state == "up":
            _apply_health(result, host, ip, health_path, connection_factory)
        return result
    finally:
        connection.close()


def _apply_health(result, host, ip, health_path, connection_factory):
    started = time.monotonic()
    connection = connection_factory(host, ip, TOTAL_TIMEOUT_SECONDS)
    try:
        status, _, body = _fetch(connection, health_path)
    except (OSError, http.client.HTTPException) as error:
        result.update(state="unreachable", detail=f"health selhal: {error}")
        return
    finally:
        connection.close()
    health = _parse_health(body)
    result["health"] = health
    if health == "ok":
        result["state"] = "up"
    elif health == "degradovano":
        result["state"] = "degraded"
    elif health == "nedostupno" or status == 503:
        result["state"] = "unreachable"
    elif 200 <= status < 300:
        result["state"] = "up"
        result["detail"] += "; health bez čitelného stavu"
        return
    else:
        result["state"] = "unreachable"
    result["detail"] += f"; health HTTP {status}"
