# Game Ping &amp; Packet Loss page

**English** · [فارسی](#فارسی)

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

---

<div dir="rtl" align="right">

## فارسی

<a name="فارسی"></a>

سه فایل. هر جایی می‌توانید بگذارید (در مثال `/root/site`) و روی هر سروری اجرا می‌شود.

</div>

```
/root/site/index.html    صفحه (دوزبانه فارسی/انگلیسی، قالب تیره)
/root/site/pingsrv.py    اندازه‌گیر (پایتون ۳ استاندارد، بدون pip)
/root/site/games.json    جدول مقصدها — هرگز به مرورگر داده نمی‌شود
```

<div dir="rtl" align="right">

### چرا بخش سروری لازم است

مرورگر نمی‌تواند بستهٔ ICMP بفرستد. هر عدد پینگ یا پکت‌لاسی که یک صفحهٔ کاملاً
ایستا نشان بدهد، ساختگی است. `pingsrv.py` دستور `ping` را روی سرور اجرا می‌کند
و همان چیزی را گزارش می‌دهد که واقعاً اتفاق افتاده. همین بخش است که آدرس
سرورهای بازی را هم پنهان نگه می‌دارد: مرورگر فقط یک شناسهٔ بی‌معنا مثل
`valorant` و `me_il` می‌فرستد، و پاسخ `/api/games` تنها شامل نام و شناسه است —
نه هاست، نه آی‌پی، هیچ چیزی که در devtools خوانده شود.

### نصب

</div>

```bash
mkdir -p /root/site
# فایل‌های index.html و pingsrv.py و games.json را در /root/site بگذارید

# نصب ping (اختیاری ولی توصیه می‌شود — بدون آن صفحه به حالت TCP برمی‌گردد)
apt install -y iputils-ping        # دبیان / اوبونتو
# dnf install -y iputils           # فدورا / RHEL

python3 /root/site/pingsrv.py --check     # اول تشخیص وضعیت
python3 /root/site/pingsrv.py             # http://<server-ip>:8088
```

<div dir="rtl" align="right">

اجرای دائمی:

</div>

```bash
python3 /root/site/pingsrv.py --install-service
systemctl status gameping
```

<div dir="rtl" align="right">

### گزینه‌ها

| سوییچ | توضیح |
|---|---|
| `--host 127.0.0.1` | آدرس bind (پیش‌فرض `0.0.0.0`) |
| `--port 8088` | پورت |
| `--root /root/site` | پوشه‌ای که سرو می‌شود |
| `--games <file>` | جدول مقصدها (پیش‌فرض `<root>/games.json`) |
| `--check` | تشخیص وضعیت و خروج |
| `--install-service` | ساخت و فعال‌سازی سرویس systemd |
| `--quiet` | بدون لاگ درخواست |

### پشت ریورس‌پروکسی (توصیه‌شده)

روی لوکال‌هاست bind کنید و دامنه و TLS را به پروکسی بسپارید:

</div>

```bash
python3 /root/site/pingsrv.py --host 127.0.0.1 --port 8088
```

```
ping.example.com {
	encode zstd gzip
	reverse_proxy 127.0.0.1:8088
}
```

<div dir="rtl" align="right">

با Smart-Caddy فقط همین: `smart-caddy add ping.example.com 8088`

### ویرایش لیست بازی‌ها

فایل `games.json` دو بخش دارد:

* `endpoints` — مقصدهای اندازه‌گیری. `host` و در صورت نیاز `port` (فقط در حالت
  TCP استفاده می‌شود) به‌همراه برچسب انگلیسی و فارسی.
* `games` — شناسهٔ بازی، برچسب‌هایش، و این‌که کدام ریجن‌ها را نشان بدهد.

مقصدهای پیش‌فرض، نقاط شبکهٔ عمومی منطقه‌ای هستند (هاست‌های تست سرعت Vultr و
Hetzner، به‌علاوهٔ دو resolver انی‌کست به‌عنوان خط پایه) که در همان ریجن‌های
دیتاسنتری قرار دارند که بازی‌های فهرست‌شده سرورهایشان را در آن‌ها اجرا می‌کنند.
این‌ها کیفیت مسیر این سرور تا آن ریجن را می‌سنجند — که همان سیگنال به‌دردخور
است — ولی **سرور خود بازی‌ها نیستند**. resolve شدن همهٔ هاست‌ها بررسی شده و
هیچ آدرسی از خودم نساخته‌ام. هر وقت آدرس بهتری داشتید، مقدار `host` را عوض کنید.

شناسه‌ها باید با الگوی `[a-z0-9_-]` بخوانند. فایل با تغییر زمان ویرایش
به‌صورت خودکار دوباره خوانده می‌شود، پس لازم نیست سرویس را ری‌استارت کنید.

### اگر `ping` نصب نباشد یا ICMP بسته باشد

صفحه به زمان‌گیری دست‌دادن واقعی TCP برمی‌گردد. کمینه/میانگین/بیشینه/جیتر و
پکت‌لاس همچنان اندازه‌گیری واقعی هستند، ولی کمی بالاتر از پینگ واقعی ICMP نشان
می‌دهند، چون یک handshake سنگین‌تر از یک echo reply است. صفحه در همین حالت
خودش تذکر می‌دهد و نشانگر بالای صفحه نشان می‌دهد کدام حالت فعال است. یک تیک
**اجبار به حالت TCP** هم هست، برای وقتی که مقصدی بسته‌های پینگ را کم‌اولویت
می‌کند و می‌خواهید نظر دوم بگیرید.

### امنیت

* مرورگر هرگز هاست‌نیم نمی‌فرستد — شناسهٔ ناشناس رد می‌شود، پس این سرویس به
  یک ping relay باز تبدیل نمی‌شود.
* فایل‌های `*.json` و `*.py` هرگز به‌عنوان فایل استاتیک سرو نمی‌شوند؛ فقط
  html/css/js/تصویر.
* دستور `ping` به‌صورت لیست آرگومان اجرا می‌شود، هیچ‌وقت از طریق شل.
* محدودیت نرخ به‌ازای هر آی‌پی، سقف هم‌زمانی کلی، و سقف سخت ۳۰ بسته.
* بدون ترک، بدون درخواست بیرونی، بدون CDN — صفحه حتی بدون دسترسی اینترنت از
  سمت مرورگر کار می‌کند.

</div>
