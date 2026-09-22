#!/usr/bin/env python3
# =============================================================================
#  gameping - server-side ping / packet-loss probe for the local HTML page
#
#  Why a backend at all: a browser cannot send ICMP. Any number a pure static
#  page shows would be invented. This runs `ping` on the server (or, if ICMP is
#  blocked, times real TCP handshakes) and reports what actually happened.
#
#  Stdlib only. No pip, no internet needed to run. Works on any Linux server.
#
#  Quick start
#  -----------
#      mkdir -p /root/site
#      # put index.html, pingsrv.py, games.json in /root/site
#      python3 /root/site/pingsrv.py            # -> http://0.0.0.0:8088
#
#  Options
#  -------
#      --host 127.0.0.1     bind address        (default 0.0.0.0)
#      --port 8088          port                (default 8088)
#      --root /root/site    directory to serve  (default: this file's folder)
#      --games <file>       target table        (default <root>/games.json)
#      --install-service    write+enable a systemd unit, then exit
#      --check              print environment diagnosis, then exit
#
#  Security notes
#  --------------
#  * The browser never sends a hostname. It sends opaque ids that must exist in
#    games.json; anything else is rejected. So this cannot be used as an open
#    ping relay, and the addresses never leave the server.
#  * games.json / *.py are never served as static files.
#  * ping is invoked as an argv list - never through a shell.
#  * Per-IP throttle: one test at a time, minimum gap between tests, hard caps
#    on packet count.
# =============================================================================

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

VERSION = "1.0.0"

# ---- limits -----------------------------------------------------------------
COUNT_MIN, COUNT_MAX, COUNT_DEF = 4, 30, 12
PER_IP_GAP = 1.5          # seconds a single IP must wait between tests
GLOBAL_CONCURRENCY = 6    # simultaneous probes across all clients
MAX_BODY = 4096

# =============================================================================
#  target table
# =============================================================================

_tbl_lock = threading.Lock()
_tbl = {"mtime": 0.0, "endpoints": {}, "games": []}

ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$")


def load_table(path, force=False):
    """Re-read games.json when it changes. Returns (endpoints, games)."""
    with _tbl_lock:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = -1.0
        if not force and mtime == _tbl["mtime"] and _tbl["games"]:
            return _tbl["endpoints"], _tbl["games"]

        if mtime < 0:
            raise RuntimeError("games.json not found at %s" % path)

        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

        eps_in = raw.get("endpoints") or {}
        endpoints = {}
        for eid, e in eps_in.items():
            if not ID_RE.match(eid):
                continue
            host = str(e.get("host", "")).strip()
            if not host or not HOST_RE.match(host):
                continue
            try:
                port = int(e.get("port", 443))
            except (TypeError, ValueError):
                port = 443
            if not (1 <= port <= 65535):
                port = 443
            endpoints[eid] = {
                "host": host,
                "port": port,
                "en": str(e.get("en", eid)),
                "fa": str(e.get("fa", e.get("en", eid))),
            }

        games, seen = [], set()
        for g in raw.get("games") or []:
            gid = str(g.get("id", ""))
            if not ID_RE.match(gid) or gid in seen:
                continue
            regions = [r for r in (g.get("regions") or []) if r in endpoints]
            if not regions:
                continue
            seen.add(gid)
            games.append({
                "id": gid,
                "en": str(g.get("en", gid)),
                "fa": str(g.get("fa", g.get("en", gid))),
                "regions": regions,
            })

        if not games:
            raise RuntimeError("games.json has no usable game entries")

        _tbl.update({"mtime": mtime, "endpoints": endpoints, "games": games})
        return endpoints, games


def public_games(endpoints, games):
    """What the browser is allowed to see: ids and labels. No addresses."""
    return [{
        "id": g["id"], "en": g["en"], "fa": g["fa"],
        "regions": [{"id": r, "en": endpoints[r]["en"], "fa": endpoints[r]["fa"]}
                    for r in g["regions"]],
    } for g in games]


# =============================================================================
#  measurement
# =============================================================================

PING_BIN = shutil.which("ping")

RE_RTT = re.compile(
    r"(?:rtt|round-trip)\s+min/avg/max(?:/(?:mdev|stddev))?\s*=\s*"
    r"([\d.]+)/([\d.]+)/([\d.]+)(?:/([\d.]+))?")
RE_LOSS = re.compile(r"([\d.]+)%\s*packet loss")
RE_TX = re.compile(r"(\d+)\s+packets transmitted.*?(\d+)\s+(?:packets\s+)?received",
                   re.S)
RE_BUSYBOX = re.compile(r"min/avg/max\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)")


def _stats(samples, sent):
    """min/avg/max/jitter/loss from a list of per-packet RTTs (ms)."""
    recv = len(samples)
    out = {"sent": sent, "recv": recv,
           "loss": round((sent - recv) * 100.0 / sent, 1) if sent else 100.0}
    if recv:
        avg = sum(samples) / recv
        out.update({
            "min": round(min(samples), 2),
            "avg": round(avg, 2),
            "max": round(max(samples), 2),
            "jitter": round(sum(abs(s - avg) for s in samples) / recv, 2),
        })
    return out


def run_icmp(host, count):
    """ICMP ping. Returns a stats dict, or None when ICMP is unusable."""
    if not PING_BIN:
        return None

    deadline = int(count * 0.3) + 6
    variants = [
        [PING_BIN, "-n", "-c", str(count), "-i", "0.25", "-W", "1", "-w", str(deadline), host],
        [PING_BIN, "-n", "-c", str(count), "-W", "1", host],          # no -i (needs privilege on some builds)
        [PING_BIN, "-c", str(count), host],                            # busybox
    ]
    last = ""
    for cmd in variants:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=deadline + 8)
        except (subprocess.TimeoutExpired, OSError) as exc:
            last = str(exc)
            continue
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        last = out.strip()[-400:]

        # DNS failure or permission problem -> try the next variant / give up
        low = out.lower()
        if "unknown host" in low or "name or service not known" in low:
            return {"error": "dns"}
        if "operation not permitted" in low or "socket: permission denied" in low:
            return None
        if "invalid argument" in low or "bad option" in low or "usage:" in low:
            continue

        sent = recv = None
        m = RE_TX.search(out)
        if m:
            sent, recv = int(m.group(1)), int(m.group(2))

        loss = None
        m = RE_LOSS.search(out)
        if m:
            loss = float(m.group(1))

        rtt = RE_RTT.search(out) or RE_BUSYBOX.search(out)
        if rtt is None and not recv:
            # no replies at all: could be a filtered host rather than a broken ping
            if sent:
                return {"mode": "icmp", "sent": sent, "recv": 0,
                        "loss": 100.0, "filtered": True}
            continue

        res = {"mode": "icmp",
               "sent": sent if sent is not None else count,
               "recv": recv if recv is not None else 0}
        if rtt:
            g = rtt.groups()
            res["min"] = round(float(g[0]), 2)
            res["avg"] = round(float(g[1]), 2)
            res["max"] = round(float(g[2]), 2)
            if len(g) > 3 and g[3]:
                res["jitter"] = round(float(g[3]), 2)
            else:
                res["jitter"] = round(max(0.0, res["max"] - res["min"]) / 2.0, 2)
        res["loss"] = loss if loss is not None else _stats([], res["sent"])["loss"]
        return res

    return {"error": "ping_failed", "detail": last} if last else None


def run_tcp(host, port, count):
    """Fallback: time real TCP handshakes. A refused/timed-out connect counts
    as a lost packet. Slightly higher than ICMP because it is a full handshake,
    but the jitter and loss figures are still real."""
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return {"error": "dns"}
    if not infos:
        return {"error": "dns"}
    af, st, proto, _, sa = infos[0]

    samples = []
    for i in range(count):
        s = socket.socket(af, st, proto)
        s.settimeout(1.5)
        t0 = time.perf_counter()
        try:
            s.connect(sa)
            samples.append((time.perf_counter() - t0) * 1000.0)
        except (socket.timeout, OSError):
            pass
        finally:
            try:
                s.close()
            except OSError:
                pass
        if i + 1 < count:
            time.sleep(0.15)

    res = _stats(samples, count)
    res["mode"] = "tcp"
    return res


_sem = threading.BoundedSemaphore(GLOBAL_CONCURRENCY)
_last_seen = {}
_seen_lock = threading.Lock()


def throttled(ip):
    now = time.time()
    with _seen_lock:
        if len(_last_seen) > 4096:
            for k, v in list(_last_seen.items()):
                if now - v > 300:
                    _last_seen.pop(k, None)
        prev = _last_seen.get(ip, 0.0)
        if now - prev < PER_IP_GAP:
            return True
        _last_seen[ip] = now
        return False


def measure(host, port, count, prefer):
    if prefer != "tcp":
        res = run_icmp(host, count)
        if res and not res.get("error") and not res.get("filtered"):
            return res
        if res and res.get("error") == "dns":
            return res
        # ICMP unavailable or the host does not answer ICMP -> TCP
        tcp = run_tcp(host, port, count)
        if not tcp.get("error") and tcp.get("recv"):
            tcp["note"] = "icmp_blocked" if res is None else "icmp_filtered"
            return tcp
        return res or tcp
    return run_tcp(host, port, count)


# =============================================================================
#  HTTP
# =============================================================================

class Handler(BaseHTTPRequestHandler):
    server_version = "gameping/" + VERSION
    protocol_version = "HTTP/1.1"

    # -- helpers --------------------------------------------------------------
    def _send(self, code, body, ctype="application/json; charset=utf-8",
              extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _client_ip(self):
        return self.client_address[0] if self.client_address else "?"

    def log_message(self, fmt, *args):
        if self.server.verbose:
            sys.stderr.write("%s - %s\n" % (self._client_ip(), fmt % args))

    # -- static ---------------------------------------------------------------
    SAFE = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
    TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
             ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
             ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".webp": "image/webp", ".ico": "image/x-icon",
             ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        if ".." in rel or not self.SAFE.match(rel):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        ext = os.path.splitext(rel)[1].lower()
        if ext not in self.TYPES:                       # blocks .py / .json / anything else
            return self._send(404, "not found", "text/plain; charset=utf-8")
        full = os.path.realpath(os.path.join(self.server.root, rel))
        if not full.startswith(self.server.root + os.sep) or not os.path.isfile(full):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        try:
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            return self._send(404, "not found", "text/plain; charset=utf-8")
        self._send(200, data, self.TYPES[ext])

    # -- routes ---------------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/games":
            try:
                eps, games = load_table(self.server.games_path)
            except Exception as exc:
                return self._json(500, {"ok": False, "error": str(exc)})
            return self._json(200, {
                "ok": True, "version": VERSION,
                "icmp": bool(PING_BIN),
                "count": {"min": COUNT_MIN, "max": COUNT_MAX, "default": COUNT_DEF},
                "games": public_games(eps, games),
            })
        if path == "/api/health":
            return self._json(200, {"ok": True, "version": VERSION,
                                    "icmp": bool(PING_BIN),
                                    "ping_bin": PING_BIN or None})
        return self._static(path)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/test":
            return self._json(404, {"ok": False, "error": "not found"})

        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_BODY:
            return self._json(400, {"ok": False, "error": "bad_body"})
        try:
            req = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return self._json(400, {"ok": False, "error": "bad_json"})
        if not isinstance(req, dict):
            return self._json(400, {"ok": False, "error": "bad_json"})

        gid = str(req.get("game", ""))
        rid = str(req.get("region", ""))
        mode = "tcp" if str(req.get("mode", "")) == "tcp" else "auto"
        try:
            count = int(req.get("count", COUNT_DEF))
        except (TypeError, ValueError):
            count = COUNT_DEF
        count = max(COUNT_MIN, min(COUNT_MAX, count))

        try:
            eps, games = load_table(self.server.games_path)
        except Exception as exc:
            return self._json(500, {"ok": False, "error": str(exc)})

        game = next((g for g in games if g["id"] == gid), None)
        if game is None or rid not in game["regions"]:
            # unknown id -> nothing to ping. This is what keeps it from being
            # used as an open relay.
            return self._json(400, {"ok": False, "error": "unknown_target"})

        if throttled(self._client_ip()):
            return self._json(429, {"ok": False, "error": "too_fast"})

        ep = eps[rid]
        if not _sem.acquire(timeout=20):
            return self._json(503, {"ok": False, "error": "busy"})
        t0 = time.time()
        try:
            res = measure(ep["host"], ep["port"], count, mode)
        except Exception as exc:                       # never leak a traceback
            res = {"error": "internal", "detail": type(exc).__name__}
        finally:
            _sem.release()

        if res is None:
            res = {"error": "no_method"}
        if res.get("error"):
            return self._json(200, {"ok": False, "error": res["error"],
                                    "detail": res.get("detail", ""),
                                    "game": gid, "region": rid})

        res.update({"ok": True, "game": gid, "region": rid,
                    "took": round(time.time() - t0, 2)})
        return self._json(200, res)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# =============================================================================
#  CLI
# =============================================================================

UNIT = """[Unit]
Description=gameping - game ping / packet loss probe
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={py} {script} --host {host} --port {port} --root {root}
Restart=always
RestartSec=3
StartLimitBurst=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full

[Install]
WantedBy=multi-user.target
"""


def install_service(args, script):
    if os.geteuid() != 0:
        sys.exit("--install-service needs root")
    if not shutil.which("systemctl"):
        sys.exit("systemd not found on this system")
    unit = UNIT.format(py=sys.executable, script=script, host=args.host,
                       port=args.port, root=args.root)
    path = "/etc/systemd/system/gameping.service"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(unit)
    os.chmod(path, 0o644)
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "enable", "--now", "gameping"], check=False)
    print("installed  -> %s" % path)
    print("status     -> systemctl status gameping")
    print("open       -> http://<server-ip>:%d/" % args.port)


def check(args):
    print("gameping %s" % VERSION)
    print("python        : %s" % sys.version.split()[0])
    print("ping binary   : %s" % (PING_BIN or "MISSING  (install iputils-ping)"))
    print("root          : %s" % args.root)
    print("games.json    : %s" % args.games)
    try:
        eps, games = load_table(args.games, force=True)
        print("targets       : %d games / %d endpoints" % (len(games), len(eps)))
    except Exception as exc:
        print("targets       : ERROR - %s" % exc)
        return 1
    host = eps[games[0]["regions"][0]]
    print("probe test    : %s" % host["host"])
    res = measure(host["host"], host["port"], 4, "auto")
    print("result        : %s" % json.dumps(res, ensure_ascii=False))
    if not PING_BIN:
        print()
        print("NOTE: ICMP ping is unavailable, so the page will fall back to TCP")
        print("      handshake timing. Numbers stay real but read a little higher")
        print("      than true ICMP ping. Install it with:")
        print("        apt install -y iputils-ping     # Debian/Ubuntu")
        print("        dnf install -y iputils          # Fedora/RHEL")
    return 0


def main():
    script = os.path.realpath(__file__)
    here = os.path.dirname(script)

    ap = argparse.ArgumentParser(add_help=True,
                                 description="server-side game ping probe")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--root", default=here)
    ap.add_argument("--games", default=None)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--install-service", action="store_true")
    args = ap.parse_args()

    args.root = os.path.realpath(args.root)
    args.games = os.path.realpath(args.games or os.path.join(args.root, "games.json"))

    if args.check:
        sys.exit(check(args))
    if args.install_service:
        return install_service(args, script)

    try:
        eps, games = load_table(args.games, force=True)
    except Exception as exc:
        sys.exit("cannot start: %s" % exc)

    srv = Server((args.host, args.port), Handler)
    srv.root, srv.games_path, srv.verbose = args.root, args.games, not args.quiet

    print("gameping %s  ->  http://%s:%d/" % (VERSION, args.host, args.port))
    print("  serving   : %s" % args.root)
    print("  targets   : %d games / %d endpoints" % (len(games), len(eps)))
    print("  icmp ping : %s" % (PING_BIN or "MISSING - falling back to TCP mode"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
