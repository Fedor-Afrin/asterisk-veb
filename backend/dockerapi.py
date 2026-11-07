"""Минимальный клиент Docker Engine API через unix-сокет (только стандартная библиотека).

Не зависит от docker CLI и его версии: backend говорит с сокетом напрямую.
"""
import http.client
import json
import socket
import urllib.parse

SOCKET_PATH = "/var/run/docker.sock"


class DockerError(Exception):
    pass


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def request(method, path, body=None, timeout=5, socket_path=None):
    """Возвращает (status, bytes). Ошибки соединения превращает в DockerError."""
    conn = _UnixConnection(socket_path or SOCKET_PATH, timeout)
    try:
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read()
    except (OSError, http.client.HTTPException) as exc:
        raise DockerError(f"cannot reach Docker socket: {exc}") from exc
    finally:
        conn.close()


def _json(method, path, body=None, **kw):
    status, raw = request(method, path, body, **kw)
    if status >= 400:
        try:
            msg = json.loads(raw).get("message", "")
        except Exception:
            msg = raw.decode(errors="replace")
        raise DockerError(f"Docker API {status}: {msg}".strip())
    return json.loads(raw) if raw else {}


def inspect_container(name_or_id, **kw):
    return _json("GET", "/containers/" + urllib.parse.quote(name_or_id, safe="") + "/json", **kw)


def list_containers(label=None, **kw):
    query = {"all": "1"}
    if label:
        query["filters"] = json.dumps({"label": [label]})
    return _json("GET", "/containers/json?" + urllib.parse.urlencode(query), **kw)


def exec_output(container, cmd, timeout=10, **kw):
    """Выполняет команду в контейнере (аналог docker exec) и возвращает её вывод."""
    created = _json("POST", "/containers/" + urllib.parse.quote(container, safe="") + "/exec",
                    {"Cmd": cmd, "AttachStdout": True, "AttachStderr": True, "Tty": True},
                    timeout=timeout, **kw)
    status, raw = request("POST", "/exec/" + created["Id"] + "/start",
                          {"Detach": False, "Tty": True}, timeout=timeout, **kw)
    if status >= 400:
        raise DockerError(f"Docker API {status}: {raw.decode(errors='replace')}")
    return raw.decode(errors="replace")
