<h1 align="center">Game Ping &amp; Packet Loss page</h1>

<p align="center"><a href="https://hits.sh/github.com/Plus98ir/Ping/"><img src="https://hits.sh/github.com/Plus98ir/Ping.svg?style=for-the-badge&label=views&color=2563eb" alt="Views"></a> <a href="https://corenetbase.com/#support"><img src="https://img.shields.io/badge/support-buy%20me%20a%20coffee-e11d2a?style=for-the-badge&logo=buymeacoffee&logoColor=white" alt="Support"></a></p>

<div align="center">

[<img src="https://flagcdn.com/w40/us.png" width="20" alt=""> &nbsp;**English**](README.md) &nbsp;&nbsp;|&nbsp;&nbsp; [<img src="https://flagcdn.com/w40/ir.png" width="20" alt=""> &nbsp;**فارسی**](README.fa.md)

</div>

<details>
<summary><b>☕ Support · حمایت</b> — USDT (TRC20) / TRX</summary>
<br>
<p align="center"><img src="https://raw.githubusercontent.com/Plus98ir/.github/main/tron-qr.png" width="200" alt="TRON address QR"></p>

```
TA53aFyGNfSAcrCaJi9QmA9x5W47nPJcf7
```

> [!WARNING]
> **TRON network only.** Sending from ERC20 / BEP20 will lose the funds.<br>
> **فقط شبکه‌ی TRON.** ارسال از ERC20 یا BEP20 پول را از بین می‌برد.

</details>

Three files. Put them anywhere (the example uses `/root/site`) and run on any server.

```
/root/site/index.html    the page   (bilingual FA/EN, dark UI)
/root/site/pingsrv.py    the prober (stdlib Python 3, no pip)
/root/site/games.json    the target table — NEVER served to the browser
```

## Why there is a server part

A browser cannot send ICMP packets. Any ping or packet-loss number a purely
static page showed you would be invented. `pingsrv.py` runs `ping` on the
server and reports what actually happened. It is also what keeps the game
server addresses hidden: the browser only ever sends an opaque id such as
`valorant` + `me_il`, and `/api/games` returns names and ids only — no hosts,
no IPs, nothing to read in devtools.

## Install

```bash
mkdir -p /root/site
# copy index.html, pingsrv.py, games.json into /root/site

# ICMP ping (optional but recommended — without it the page falls back to TCP)
apt install -y iputils-ping        # Debian / Ubuntu
# dnf install -y iputils           # Fedora / RHEL

python3 /root/site/pingsrv.py --check     # diagnose first
python3 /root/site/pingsrv.py             # http://<server-ip>:8088
```

Run it permanently:

```bash
python3 /root/site/pingsrv.py --install-service
systemctl status gameping
```

## Options

| flag | meaning |
|---|---|
| `--host 127.0.0.1` | bind address (default `0.0.0.0`) |
| `--port 8088` | port |
| `--root /root/site` | directory to serve |
| `--games <file>` | target table (default `<root>/games.json`) |
| `--check` | print environment diagnosis and exit |
| `--install-service` | write + enable a systemd unit |
| `--quiet` | no request log |

## Behind a reverse proxy (recommended)

Bind to loopback and let your proxy handle the domain and TLS:

```bash
python3 /root/site/pingsrv.py --host 127.0.0.1 --port 8088
```

Caddy:

```
ping.example.com {
	encode zstd gzip
	reverse_proxy 127.0.0.1:8088
}
```

With Smart-Caddy: `smart-caddy add ping.example.com 8088`

## Editing the game list

`games.json` has two sections:

* `endpoints` — the probe targets. `host` + optional `port` (used only in TCP
  mode) plus an English and a Persian label.
* `games` — a game id, its labels, and which endpoint ids it offers.

The shipped defaults are public regional network endpoints (Vultr / Hetzner
speed-test hosts, plus two anycast resolvers as a baseline) located in the same
data-centre regions the listed games run their servers in. They measure the
quality of this server's route to that region — which is the useful signal —
but they are **not** the games' own servers. Every host was verified to
resolve; nothing was invented. Replace the `host` values with your own
endpoints whenever you have better ones.

Ids must match `[a-z0-9_-]`. The file is re-read automatically when its
modification time changes, so you don't have to restart after an edit.

## If `ping` is missing or ICMP is blocked

The page falls back to timing real TCP handshakes. Min/avg/max/jitter and loss
stay real measurements, but they read a little higher than true ICMP ping
because a handshake is more work than an echo reply. The page says so when it
happens, and the badge in the header shows which mode is active. There is also
a **Force TCP mode** checkbox for a second opinion when a target de-prioritises
ping packets.

## Safety

* The browser never sends a hostname — unknown ids are rejected, so this cannot
  be turned into an open ping relay.
* `*.json` and `*.py` are never served as static files; only html/css/js/images.
* `ping` is invoked as an argv list, never through a shell.
* Per-IP rate limit, a global concurrency cap, and a hard cap of 30 packets.
* No tracking, no external requests, no CDN — the page works with no internet
  access from the browser side.
