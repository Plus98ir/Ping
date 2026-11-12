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

<div dir="rtl" align="right">

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
