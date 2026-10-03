# -*- coding: utf-8 -*-
"""
مولّد الموقع — يحوّل data/ إلى صفحات HTML ثابتة جاهزة للنشر.

لا Next.js ولا Node ولا خطوة بناء: المحرّك يملك المحتوى كاملًا، وما
يلزم هو صفحات بروابط دائمة ووسوم SEO صحيحة. صفحة ثابتة أسرع من أي
إطار على شبكات الموبايل، وتُنشر مجانًا على Cloudflare Pages أو
GitHub Pages، وتُفتح محليًا بلا خادم.

  python engine/site.py [https://altrendat.com]

البنية الناتجة:
  site/index.html                    الصفحة الرئيسة
  site/eg/index.html                 الأكثر بحثًا اليوم في مصر
  site/eg/archive/index.html         فهرس كل الأيام
  site/eg/<date>/index.html          يوم واحد
  site/eg/<date>/<slug>/index.html   صفحة ترند — رابط دائم مؤرّخ
  site/e/<slug>/index.html           صفحة كيان (الذاكرة التراكمية)
  site/sitemap.xml · feed.xml
"""
import html
import json
import os
import shutil
import sys
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from itertools import zip_longest
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entities  # noqa: E402
import dedup  # noqa: E402
import jobs  # noqa: E402
import sources  # noqa: E402
import config  # noqa: E402
import photos  # noqa: E402
import evergreen  # noqa: E402
import idphoto  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site")
E = html.escape

SITE_NAME = config.SITE_NAME
SITE_NAME_EN = config.SITE_NAME_EN
ROBOTS_INDEX = "index, follow, max-image-preview:large, max-snippet:-1"
ROBOTS_NOINDEX = "noindex, follow"
# مركز WebSub العام من جوجل: تُعلن عنه الخلاصتان، ويُخطَر بعد كل نشر
WEBSUB_HUB = "https://pubsubhubbub.appspot.com/"


def indexed(country):
    """هل تُفهرس صفحات هذه النسخة؟ (config.INDEXED_EDITIONS)"""
    return country in config.INDEXED_EDITIONS


def has_hubs(country):
    """صفحات المواضيع (/e/) عربية؛ النسخة الإنجليزية لا تدخلها، فلا يختلط
    خبر إنجليزي بصفحة عربية ولا يُحوَّل رابطه إلى موضوع عربي."""
    return indexed(country) and country != "world"


def format_time(dt_str, is_en=False, country="eg"):
    """تحويل التاريخ ISO إلى توقيت مقروء بالساعة والدقيقة بتوقيت المنطقة."""
    if not dt_str:
        return ""
    try:
        s = dt_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    except Exception:
        return ""

    offset_hours = 0 if (is_en or country == "world") else 3
    tz = timezone(timedelta(hours=offset_hours))
    local_dt = dt.astimezone(tz) if dt.tzinfo else (dt + timedelta(hours=offset_hours)).replace(tzinfo=tz)

    h = local_dt.strftime("%I:%M").lstrip("0")
    if is_en or country == "world":
        ampm = local_dt.strftime("%p")
        return f"{h} {ampm} UTC"
    else:
        ampm = "م" if local_dt.hour >= 12 else "ص"
        return f"{h} {ampm}"

# رمز Cloudflare Web Analytics — اتركه فارغًا.
#
# Cloudflare يحقن السكربت تلقائيًا عند الحافة لكل طلب من متصفح حقيقي
# (تحقّقنا 2026-09-23: يظهر مع ترويسة متصفح، ويغيب عن curl العادي).
# ملء هذا الرمز يُضيف نسخة ثانية فتُحسب كل زيارة مرتين.
# لا يُملأ إلا إن أُطفئ الإعداد التلقائي في لوحة Cloudflare.
CF_BEACON_TOKEN = ""


def analytics_tag():
    if not CF_BEACON_TOKEN:
        return ""
    beacon = json.dumps({"token": CF_BEACON_TOKEN})
    return ('<script defer src="https://static.cloudflareinsights.com/'
            "beacon.min.js\" data-cf-beacon='" + beacon + "'></script>")


# يُستبدل بالنطاق الحقيقي فور حجزه — يمرَّر كوسيط للسكربت
BASE = "https://altrendat.com"

SHELL = """<!DOCTYPE html>
<html lang="{lang}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- max-image-preview:large شرط Google Discover؛ وnoindex للصفحات خارج الفهرسة -->
<meta name="robots" content="{robots}">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{ogtype}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{site}">
<meta property="og:locale" content="{locale}">
{ogimage}
<meta name="twitter:card" content="summary_large_image">
{jsonld}
<link rel="icon" type="image/x-icon" href="{root}favicon.ico">
<link rel="icon" type="image/png" sizes="48x48" href="{root}favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="{root}icon-192.png">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="alternate" type="application/rss+xml" title="{site}" href="{root}feed.xml">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="site">
  <a class="brand" href="{brand_href}">
    <img src="{root}logo.png" alt="{site}" class="brand-logo" width="56" height="56">
    <span class="brand-text">{site}</span>
  </a>
  <nav>{nav}</nav>
</header>
<main>{body}</main>
<footer class="site">
  <nav class="flinks">
    {flinks}
  </nav>
  <p>{fdesc}</p>
  <p class="fine">{ffine}</p>
</footer>
{floating_bar}
{notif_prompt}
{analytics}
</body>
</html>"""

STYLE = """
:root{
  --bg:#0a0d14;--bg2:#111622;--card:#151b29;--line:#222b3d;
  --txt:#e8ecf4;--mut:#8b96ab;--gold:#f5c542;--acc:#5aa9ff;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:var(--bg);color:var(--txt);
  font-family:Cairo,system-ui,sans-serif;line-height:1.85;
}
html[dir="ltr"] body{
  direction:ltr;text-align:left;
}
html[dir="ltr"] .flinks, html[dir="ltr"] footer.site{
  text-align:center;
}
html[dir="ltr"] .lead, html[dir="ltr"] .meta, html[dir="ltr"] .item{
  text-align:left;
}
a{color:inherit}
header.site,footer.site{
  max-width:1040px;margin:0 auto;padding:20px 18px;
  display:flex;align-items:center;justify-content:space-between;gap:14px;
}
footer.site{display:block;border-top:1px solid var(--line);margin-top:48px;
  color:var(--mut);font-size:.82rem;text-align:center}
.fine{font-size:.74rem;margin-top:6px}
.flinks{justify-content:center;margin-bottom:12px}
.flinks a{text-decoration:none;color:var(--mut);font-size:.8rem;
  border:1px solid var(--line);border-radius:99px;padding:4px 13px}
.flinks a:hover{color:var(--txt);border-color:var(--acc)}
article ul{margin:0 0 16px;padding-inline-start:22px}
article li{margin-bottom:7px;color:#dfe6f0}
article a{color:var(--acc)}
article{max-width:820px;margin:0 auto}
.brand{
  display:inline-flex;align-items:center;gap:13px;text-decoration:none;
}
.brand-logo{
  width:56px;height:56px;border-radius:50%;object-fit:cover;flex-shrink:0;
  box-shadow:0 0 18px rgba(255,159,104,.45), 0 2px 10px rgba(0,0,0,.6);
  border:1.5px solid rgba(255,159,104,.45);
  display:block;
  transition:transform .2s ease, box-shadow .2s ease;
}
.brand:hover .brand-logo{
  transform:scale(1.05);
  box-shadow:0 0 24px rgba(255,159,104,.65), 0 3px 12px rgba(0,0,0,.7);
}
.brand-text{
  font-size:1.68rem;font-weight:800;
  background:linear-gradient(95deg,var(--gold),#ff9f68);
  -webkit-background-clip:text;background-clip:text;color:transparent;
  letter-spacing:-.3px;
}
nav{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
nav a{
  font-size:.92rem;text-decoration:none;color:var(--mut);font-weight:600;
  border:1px solid var(--line);border-radius:99px;padding:7px 17px;
  transition:.2s;
}
nav a:hover{color:var(--txt);border-color:var(--acc)}
main{max-width:1040px;margin:0 auto;padding:8px 18px 30px}
h1{font-size:2rem;font-weight:800;line-height:1.4;margin-bottom:12px;
  letter-spacing:-.4px}
h2{font-size:1.25rem;font-weight:800;margin:28px 0 10px}
.meta{color:var(--mut);font-size:.8rem;margin-bottom:20px}
/* الكارت صُنع لمعاينة المشاركة على فيسبوك وواتساب، لا للعرض هنا.
   بحجمه الكامل كان يأكل نصف الشاشة بصورة فارغة تكرّر ما بحث عنه
   الزائر أصلًا، فيضطر للتمرير ليصل إلى الإجابة. */
.hero{width:100%;height:150px;object-fit:cover;object-position:center 32%;
  border-radius:14px;border:1px solid var(--line);
  margin:14px 0 20px;display:block;opacity:.85}
.lead{
  font-size:1.12rem;font-weight:600;color:var(--gold);line-height:1.75;
  background:rgba(245,197,66,.07);border:1px solid rgba(245,197,66,.22);
  border-radius:14px;padding:15px 18px;margin-bottom:22px;
}
.article-photo{
  margin:18px 0 24px;border-radius:16px;overflow:hidden;
  border:1px solid var(--line);background:var(--card);
}
.article-photo img{
  width:100%;height:auto;max-height:480px;object-fit:cover;
  display:block;
}
.article-photo figcaption{
  font-size:.78rem;color:var(--mut);padding:8px 14px;
  background:rgba(255,255,255,.02);border-top:1px solid var(--line);
}
article p{margin-bottom:16px;text-align:start;font-size:1.05rem;
  line-height:1.95;color:#dfe6f0}
article p:first-child{font-size:1.12rem;color:var(--txt)}
.list{display:grid;gap:12px;margin-top:8px}
.item{
  background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px solid var(--line);border-radius:16px;padding:15px 17px;
  text-decoration:none;display:block;transition:.2s;
}
.item:hover{border-color:var(--acc);transform:translateY(-2px)}
.item h3{font-size:1.04rem;font-weight:700;margin-bottom:5px}
.item .sub{color:var(--mut);font-size:.8rem}
.rank{color:var(--gold);font-weight:800;margin-inline-end:8px}

/* --- شبكة كروت الأخبار والترندات الاحترافية (Trends Grid) --- */
.trends-grid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));
  gap:20px;margin:22px 0 36px;
}
.trend-card{
  background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px solid var(--line);border-radius:18px;overflow:hidden;
  display:flex;flex-direction:column;transition:all .25s cubic-bezier(.16,1,.3,1);
  position:relative;
}
.trend-card:hover{
  border-color:var(--acc);transform:translateY(-4px);
  box-shadow:0 14px 30px rgba(0,0,0,.4);
}
.trend-card-link{
  text-decoration:none;color:inherit;display:flex;flex-direction:column;height:100%;
}
.trend-card-media{
  position:relative;width:100%;height:185px;background:#0d121c;overflow:hidden;
}
.trend-card-media img{
  width:100%;height:100%;object-fit:cover;display:block;transition:transform .4s ease;
}
.trend-card:hover .trend-card-media img{
  transform:scale(1.04);
}
.trend-card-badges{
  position:absolute;top:10px;right:10px;display:flex;gap:6px;flex-wrap:wrap;z-index:2;
}
.badge-cat,.badge-traffic{
  font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:99px;
  backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  box-shadow:0 2px 8px rgba(0,0,0,.3);
}
.badge-cat{background:rgba(10,13,20,.85);border:1px solid rgba(255,255,255,.15);color:var(--c,var(--gold))}
.badge-traffic{background:rgba(245,197,66,.92);color:#0a0d14}
.trend-card-rank{
  position:absolute;bottom:8px;left:10px;font-size:.78rem;font-weight:800;
  padding:2px 9px;border-radius:8px;background:rgba(10,13,20,.85);
  border:1px solid rgba(255,255,255,.12);color:var(--gold);z-index:2;
}
.trend-card-body{
  padding:16px 18px 18px;display:flex;flex-direction:column;flex-grow:1;
}
.trend-card-meta{
  display:flex;align-items:center;gap:8px;font-size:.78rem;color:var(--mut);margin-bottom:8px;
}
.trend-country-pill{
  font-weight:700;color:#c9d5e8;display:inline-flex;align-items:center;gap:4px;
}
.trend-card-title{
  font-size:1.08rem;font-weight:800;line-height:1.5;color:var(--txt);margin-bottom:8px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  transition:color .2s ease;
}
.trend-card:hover .trend-card-title{color:var(--acc)}
.trend-card-summary{
  font-size:.86rem;color:#a6b4c9;line-height:1.6;margin-bottom:14px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  flex-grow:1;
}
.trend-card-footer{
  display:flex;align-items:center;justify-content:space-between;
  border-top:1px solid rgba(255,255,255,.05);padding-top:12px;margin-top:auto;font-size:.78rem;
}
.trend-sources-tag{color:var(--mut)}
.trend-arrow{color:var(--gold);font-weight:700;transition:transform .2s}
.trend-card:hover .trend-arrow{transform:translateX(-3px)}

/* --- كارت القصة المتصدرة المميزة (Spotlight) --- */
.hero-spotlight{
  background:linear-gradient(165deg,rgba(21,27,41,.95),rgba(13,17,27,.95));
  border:1px solid rgba(90,169,255,.35);border-radius:20px;overflow:hidden;
  margin:18px 0 26px;display:grid;grid-template-columns:1.1fr 1fr;transition:all .25s ease;
}
.hero-spotlight:hover{
  border-color:var(--acc);box-shadow:0 16px 36px rgba(0,0,0,.45);
}
.hero-spotlight-media{
  position:relative;min-height:260px;overflow:hidden;background:#0d121c;
}
.hero-spotlight-media img{
  width:100%;height:100%;object-fit:cover;display:block;transition:transform .4s ease;
}
.hero-spotlight:hover .hero-spotlight-media img{transform:scale(1.03)}
.hero-spotlight-content{
  padding:24px 26px;display:flex;flex-direction:column;justify-content:space-between;
}
.spotlight-top-badge{
  display:inline-flex;align-items:center;gap:6px;font-size:.76rem;font-weight:800;
  color:#ff9f68;background:rgba(255,159,104,.12);border:1px solid rgba(255,159,104,.3);
  padding:4px 12px;border-radius:99px;align-self:flex-start;margin-bottom:12px;
}
.hero-spotlight-title{
  font-size:1.32rem;font-weight:800;line-height:1.45;color:#fff;margin-bottom:10px;
}
.hero-spotlight-desc{
  font-size:.92rem;color:#b8c6d8;line-height:1.7;margin-bottom:18px;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;
}
.hero-spotlight-cta{
  display:inline-flex;align-items:center;gap:8px;
  background:linear-gradient(135deg,var(--acc),#3d8bff);
  color:#0a0d14!important;font-weight:800;font-size:.88rem;
  padding:9px 20px;border-radius:99px;text-decoration:none;align-self:flex-start;
  transition:.2s;
}
.hero-spotlight-cta:hover{
  transform:translateY(-2px);box-shadow:0 6px 18px rgba(90,169,255,.35);
}
@media(max-width:768px){
  .hero-spotlight{grid-template-columns:1fr}
  .hero-spotlight-media{min-height:190px}
  .hero-spotlight-content{padding:18px}
  .hero-spotlight-title{font-size:1.15rem}
  .trends-grid{grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px}
}

table{width:100%;border-collapse:collapse;font-size:.92rem;margin:14px 0;
  display:block;overflow-x:auto;white-space:nowrap;
  background:rgba(255,255,255,.02);border:1px solid var(--line);
  border-radius:14px}
tbody tr:nth-child(even){background:rgba(255,255,255,.022)}
th{color:var(--mut);font-size:.78rem;font-weight:600;text-align:start;
  padding:10px 13px;border-bottom:1px solid var(--line)}
td{padding:10px 13px;border-bottom:1px solid rgba(255,255,255,.05);
  font-variant-numeric:tabular-nums;font-weight:600}
td:first-child{color:var(--acc);font-weight:600}
.src{font-size:.75rem;color:var(--mut);margin-top:-8px;margin-bottom:18px}
.tags{display:flex;flex-wrap:wrap;gap:7px;margin:18px 0}
.tag{background:rgba(255,255,255,.05);border:1px solid var(--line);
  color:var(--mut);font-size:.76rem;padding:3px 11px;border-radius:99px}
.sources{list-style:none;display:grid;gap:9px;margin-top:10px}
.sources a{
  display:block;text-decoration:none;background:rgba(255,255,255,.03);
  border:1px solid var(--line);border-radius:12px;padding:11px 13px;
}
.sources a:hover{border-color:var(--acc)}
.sources .name{color:var(--gold);font-size:.74rem;display:block}
.sources .t{font-size:.9rem;font-weight:600}
.sources .d{font-size:.8rem;color:var(--mut);margin-top:3px}
.when{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:6px}
.chip{font-size:.74rem;color:var(--mut);border:1px solid var(--line);
  border-radius:99px;padding:2px 11px}
.channel-cta{
  background:linear-gradient(135deg,rgba(34,158,217,.12),rgba(90,169,255,.08));
  border:1px solid rgba(90,169,255,.35);border-radius:16px;
  padding:18px 20px;margin:26px 0 28px;
  display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;
}
.channel-cta h4{font-size:1.05rem;font-weight:800;color:#fff;margin-bottom:4px}
.channel-cta p{font-size:.86rem;color:var(--mut);margin:0!important;line-height:1.55}
.btn-tg,.btn-gold-app{
  background:linear-gradient(135deg,#f5c542,#d49b1a);color:#0a0d14!important;font-weight:800;font-size:.88rem;
  padding:9px 20px;border-radius:99px;text-decoration:none;
  display:inline-flex;align-items:center;gap:6px;transition:.2s;white-space:nowrap;box-shadow:0 4px 14px rgba(245,197,66,.25);
}
.btn-tg:hover,.btn-gold-app:hover{background:linear-gradient(135deg,#ffe071,#e5aa20);transform:translateY(-2px);box-shadow:0 6px 18px rgba(245,197,66,.45)}
.gold-pulse-dot{
  width:9px;height:9px;border-radius:50%;background:#f5c542;display:inline-block;
  box-shadow:0 0 0 0 rgba(245,197,66,.7);animation:goldPulse 1.8s infinite;
}
@keyframes goldPulse{
  0%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(245,197,66,.7)}
  70%{transform:scale(1);box-shadow:0 0 0 7px rgba(245,197,66,0)}
  100%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(245,197,66,0)}
}
.floating-cta{
  position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:999;
  background:rgba(17,22,34,.95);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid rgba(245,197,66,.35);box-shadow:0 8px 24px rgba(0,0,0,.5);
  border-radius:99px;padding:6px 14px;display:flex;align-items:center;gap:10px;max-width:92%;
}
.floating-cta span{font-size:.8rem;font-weight:600;color:var(--txt);white-space:nowrap}
@media(max-width:560px){
  .brand{gap:10px;}
  .brand-logo{width:46px;height:46px;}
  .brand-text{font-size:1.4rem;}
  h1{font-size:1.45rem}
  .channel-cta{flex-direction:column;align-items:stretch;text-align:center}
  .btn-tg,.btn-gold-app{justify-content:center}
  nav{gap:8px}
  nav a{font-size:.86rem;padding:6px 14px}
  .nav-lang-btn{font-size:.92rem;padding:7px 16px}
}

/* --- نظام رادار وذكاء الترندات (Trend Intelligence System) --- */
.trend-intel-box{
  background:linear-gradient(150deg,rgba(21,27,41,.98),rgba(14,18,29,.98));
  border:1px solid rgba(245,197,66,.28);border-radius:18px;
  padding:20px 22px;margin:18px 0 24px;position:relative;overflow:hidden;
}
.trend-intel-box::before{
  content:"";position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ff5c7c,var(--gold),var(--acc));
}
.trend-intel-header{
  display:flex;align-items:center;margin-bottom:12px;
}
.trend-intel-badge{
  display:inline-flex;align-items:center;gap:6px;font-size:.76rem;font-weight:800;
  color:var(--gold);background:rgba(245,197,66,.12);border:1px solid rgba(245,197,66,.3);
  padding:3px 12px;border-radius:99px;
}
.trend-why-title{
  font-size:1.15rem;font-weight:800;color:#fff;margin-bottom:8px;display:flex;align-items:center;gap:8px;
}
.trend-why-desc{
  font-size:1.02rem;line-height:1.75;color:#f0f4fa;margin:0;font-weight:600;
}

/* --- بطاقات الأسئلة الأكثر بحثًا (FAQ Cards / People Also Ask) --- */
.trend-faq-section{
  margin:28px 0;border-top:1px solid var(--line);padding-top:22px;
}
.trend-faq-section h3{
  font-size:1.15rem;font-weight:800;color:#fff;margin-bottom:14px;display:flex;align-items:center;gap:8px;
}
.faq-grid{
  display:grid;gap:12px;
}
.faq-card{
  background:rgba(255,255,255,.025);border:1px solid var(--line);
  border-radius:14px;padding:14px 16px;transition:.2s;
}
.faq-card:hover{
  border-color:rgba(90,169,255,.4);background:rgba(255,255,255,.035);
}
.faq-question{
  font-size:.94rem;font-weight:700;color:var(--acc);margin-bottom:6px;display:flex;align-items:center;gap:6px;
}
.faq-answer{
  font-size:.88rem;color:#b8c7db;line-height:1.65;margin:0;
}

/* --- بطاقة ترويج تطبيق الذهب والمستثمر الذكي (Gold App Promo CTA) --- */
.gold-promo-cta,.trend-follow-cta{
  background:linear-gradient(135deg,rgba(245,197,66,.12),rgba(20,25,37,.95));
  border:1px solid rgba(245,197,66,.38);border-radius:18px;
  padding:18px 22px;margin:24px 0 28px;position:relative;overflow:hidden;
}
.gold-promo-badge{
  display:inline-block;background:rgba(245,197,66,.18);border:1px solid rgba(245,197,66,.4);
  color:var(--gold);font-size:.76rem;font-weight:800;padding:3px 10px;border-radius:99px;margin-bottom:10px;
}
.gold-promo-content{
  display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;
}
.gold-promo-text strong,.trend-follow-text strong{display:block;font-size:1.02rem;color:#fff;margin-bottom:4px}
.gold-promo-text p,.trend-follow-text span{font-size:.86rem;color:var(--mut);margin:0!important;line-height:1.55}
.btn-follow-tg{
  background:linear-gradient(135deg,#f5c542,#d49b1a);color:#0a0d14!important;font-size:.86rem;font-weight:800;
  padding:8px 18px;border-radius:99px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;
}
.btn-follow-tg:hover{background:linear-gradient(135deg,#ffe071,#e5aa20)}

/* --- صفحات التوثيق والأسئلة الشائعة وتطبيق الذهب --- */
.faq-nav-pills{display:flex;gap:10px;margin:16px 0 24px;flex-wrap:wrap}
.faq-nav-pill{background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:99px;padding:8px 18px;color:#fff;text-decoration:none;font-size:.9rem;font-weight:700;display:inline-flex;align-items:center;gap:6px;transition:.2s}
.faq-nav-pill:hover,.faq-nav-pill.active{background:rgba(90,169,255,.18);border-color:var(--acc);color:var(--acc)}
.faq-grid{display:grid;gap:18px;margin:24px 0 36px}
.faq-card{
  background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px solid var(--line);border-radius:16px;padding:22px 24px;transition:.2s;
}
.faq-card:hover{border-color:rgba(90,169,255,.45);box-shadow:0 6px 20px rgba(0,0,0,.35)}
.faq-card h3{font-size:1.15rem;font-weight:800;color:#fff;margin-bottom:12px;display:flex;align-items:center;gap:10px}
.faq-card p{font-size:.96rem;color:#dfe6f0;line-height:1.85;margin-bottom:10px}
.faq-card ul{padding-inline-start:20px;margin-bottom:10px}
.faq-card li{font-size:.92rem;color:var(--mut);margin-bottom:6px;line-height:1.65}
.faq-badge{background:rgba(90,169,255,.15);color:var(--acc);font-size:.75rem;padding:3px 9px;border-radius:99px;font-weight:700}
.faq-authority-box{
  background:linear-gradient(135deg,rgba(90,169,255,.08),rgba(61,220,151,.08));
  border:1px solid rgba(90,169,255,.3);border-radius:18px;padding:22px;margin:24px 0;
}
.faq-en-section{margin-top:48px;border-top:1px solid var(--line);padding-top:34px}
.faq-card[dir="ltr"]{direction:ltr;text-align:left}
.faq-card[dir="ltr"] h3{direction:ltr;text-align:left;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.faq-card[dir="ltr"] p,.faq-card[dir="ltr"] li{direction:ltr;text-align:left;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.faq-card[dir="ltr"] ul{padding-left:22px;padding-right:0}
/* زر اللغة (English/العربية) أبرز أزرار القائمة عمدًا: هو الطريق
   الوحيد من نسخة لغة إلى الأخرى، فحجمه الصغير كان يخفيه بين البلاد. */
.nav-lang-btn{
  border:1.5px solid rgba(90,169,255,.5);background:rgba(90,169,255,.14);
  border-radius:99px;padding:8px 19px;font-weight:800;transition:.2s;
  font-size:1rem;display:inline-flex;align-items:center;gap:6px;
  color:#fff!important;
}
.nav-lang-btn:hover{background:rgba(90,169,255,.28);border-color:var(--acc);
  transform:translateY(-1px)}

/* --- تصميم وهوية تطبيق جولدكس الفاخر (Goldex App Luxury Theme) --- */
.goldex-container{
  background:radial-gradient(ellipse at 50% -20%, #1e2640 0%, #0a0e21 65%, #050711 100%);
  border:1px solid rgba(255,215,0,.35);border-radius:24px;
  padding:36px 30px;margin:20px 0 36px;
  box-shadow:0 16px 48px rgba(0,0,0,.6), 0 0 30px rgba(255,215,0,.08);
  position:relative;overflow:hidden;
}
.goldex-container::before{
  content:"";position:absolute;top:0;left:0;right:0;height:4px;
  background:linear-gradient(90deg,#ffd700,#ffa000,#e8cc6e,#ffd700);
  background-size:200% 100%;animation:goldShimmer 4s ease infinite;
}
@keyframes goldShimmer{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
.goldex-hero-header{
  display:flex;align-items:center;gap:24px;flex-wrap:wrap;margin-bottom:28px;
}
.goldex-logo-img{
  width:96px;height:96px;border-radius:22px;object-fit:cover;
  border:2px solid rgba(255,215,0,.5);box-shadow:0 10px 28px rgba(255,215,0,.28);
  background:#0d111d;flex-shrink:0;
}
.goldex-brand-title{font-size:2.25rem;font-weight:900;color:#fff;line-height:1.25;margin-bottom:6px}
.goldex-brand-title span{
  background:linear-gradient(135deg,#ffd700 0%,#ffa000 50%,#fff1a8 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.goldex-pill{
  display:inline-flex;align-items:center;gap:6px;background:rgba(255,215,0,.15);
  border:1px solid rgba(255,215,0,.35);color:#ffd700;font-size:.78rem;font-weight:800;
  padding:4px 12px;border-radius:99px;margin-bottom:10px;
}
.goldex-rating{display:flex;align-items:center;gap:8px;color:#ffd700;font-size:.88rem;font-weight:700;margin-top:6px}
.goldex-features-grid{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px;margin:28px 0;
}
.goldex-feat-card{
  background:linear-gradient(160deg,rgba(44,36,22,.65),rgba(20,25,38,.85));
  border:1px solid rgba(255,215,0,.22);border-radius:16px;padding:20px 22px;
  transition:.25s;position:relative;backdrop-filter:blur(6px);
}
.goldex-feat-card:hover{
  border-color:rgba(255,215,0,.55);transform:translateY(-3px);
  box-shadow:0 10px 24px rgba(255,215,0,.12);
}
.goldex-feat-card h4{color:#ffd700;font-size:1.05rem;font-weight:800;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.goldex-feat-card p{color:#d5dce8;font-size:.89rem;line-height:1.65;margin:0}
.goldex-cta-banner{
  background:linear-gradient(135deg,rgba(255,215,0,.14),rgba(26,26,46,.95));
  border:1px solid rgba(255,215,0,.4);border-radius:20px;padding:28px 24px;
  text-align:center;margin:32px 0 16px;box-shadow:0 8px 30px rgba(0,0,0,.45);
}
.btn-play-store{
  display:inline-flex;align-items:center;gap:14px;
  background:#0d111d;color:#fff!important;border:1.5px solid rgba(255,215,0,.6);
  border-radius:14px;padding:12px 28px;text-decoration:none;
  box-shadow:0 6px 20px rgba(0,0,0,.5),0 0 20px rgba(255,215,0,.25);
  transition:.25s;text-align:start;
}
.btn-play-store:hover{
  background:#141a2c;transform:translateY(-2px);border-color:#ffd700;
  box-shadow:0 10px 30px rgba(255,215,0,.45);
}
/* --- قسم الوظائف (Jobs Section) --- */
.nav-jobs{
  background:linear-gradient(135deg,rgba(245,197,66,.18),rgba(255,159,104,.15));
  border-color:rgba(245,197,66,.5)!important;color:var(--gold)!important;
  font-weight:800;
}
.jobs-hero{margin:10px 0 24px}
.jobs-lead{font-size:1.08rem;color:var(--txt);line-height:1.75;margin-top:6px}

.safety-box{
  background:rgba(90,169,255,.07);border:1px solid rgba(90,169,255,.3);
  border-radius:14px;padding:14px 18px;margin:20px 0;display:flex;gap:14px;align-items:flex-start;
}
.safety-icon{font-size:1.6rem;line-height:1}
.safety-text strong{color:var(--acc);display:block;margin-bottom:3px;font-size:.92rem}
.safety-text p{font-size:.85rem;color:var(--mut);margin:0;line-height:1.6}

/* --- المؤشرات الذكية بالأعلى (Jobs Matrix) --- */
.jobs-matrix{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:12px;margin:22px 0 26px;
}
.matrix-card{
  background:linear-gradient(145deg,rgba(21,27,41,.95),rgba(17,22,34,.95));
  border:1px solid var(--line);border-radius:16px;padding:15px 18px;
  cursor:pointer;transition:all .25s ease;position:relative;overflow:hidden;
}
.matrix-card::after{
  content:"";position:absolute;top:0;left:0;right:0;height:3px;
  background:var(--m-color,var(--acc));opacity:.8;
}
.matrix-card:hover{
  border-color:var(--m-color,var(--acc));transform:translateY(-3px);
  box-shadow:0 8px 24px rgba(0,0,0,.35);
}
.matrix-card.active{
  border-color:var(--m-color,var(--acc));
  background:linear-gradient(145deg,rgba(30,40,60,.95),rgba(20,28,44,.95));
  box-shadow:0 0 0 1px var(--m-color,var(--acc)),0 8px 20px rgba(0,0,0,.3);
}
.matrix-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.matrix-icon{font-size:1.4rem}
.matrix-count{
  font-size:.76rem;font-weight:800;padding:2px 8px;border-radius:99px;
  background:rgba(255,255,255,.07);color:var(--m-color,var(--gold));
}
.matrix-title{font-size:1.02rem;font-weight:800;color:var(--txt);margin-bottom:4px}
.matrix-sub{font-size:.78rem;color:var(--mut);line-height:1.45;margin:0}

/* --- صندوق البحث الذكي (Job Search Box) --- */
.job-search-box{
  background:linear-gradient(165deg,rgba(21,27,41,.95),rgba(13,17,27,.95));
  border:1px solid rgba(90,169,255,.35);border-radius:18px;
  padding:20px 22px;margin:24px 0 28px;
  box-shadow:0 12px 28px rgba(0,0,0,.3);
}
.search-input-wrapper{
  position:relative;display:flex;align-items:center;width:100%;
}
.search-icon{
  position:absolute;right:16px;font-size:1.15rem;color:var(--mut);pointer-events:none;
}
#jobSearchInput{
  width:100%;background:rgba(10,13,20,.85);border:1px solid var(--line);
  border-radius:12px;padding:14px 46px 14px 44px;
  color:var(--txt);font-family:inherit;font-size:.98rem;
  transition:all .2s ease;outline:none;
}
#jobSearchInput:focus{
  border-color:var(--acc);box-shadow:0 0 0 3px rgba(90,169,255,.2);
  background:#0d121c;
}
#jobSearchInput::placeholder{color:#6b7891;font-size:.88rem}
.clear-search-btn{
  position:absolute;left:14px;background:rgba(255,255,255,.1);border:none;
  color:var(--mut);width:26px;height:26px;border-radius:50%;
  display:inline-flex;align-items:center;justify-content:center;
  cursor:pointer;font-size:.82rem;transition:.2s;
}
.clear-search-btn:hover{background:rgba(255,255,255,.2);color:#fff}

.search-meta-row{
  display:flex;align-items:center;justify-content:space-between;
  gap:14px;margin-top:14px;flex-wrap:wrap;
}
.results-count{font-size:.84rem;color:var(--mut)}
.results-count strong{color:var(--gold)}
.quick-tags{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.quick-tags-label{font-size:.76rem;color:var(--mut);margin-inline-end:4px}
.quick-tag{
  background:rgba(255,255,255,.05);border:1px solid var(--line);
  color:var(--txt);font-size:.74rem;font-family:inherit;
  padding:3px 10px;border-radius:99px;cursor:pointer;transition:.2s;
}
.quick-tag:hover{border-color:var(--acc);color:var(--acc);background:rgba(90,169,255,.1)}

/* --- شريط الفلاتر المزدوج (Dual Filters) --- */
.job-filters-wrap{
  background:rgba(17,22,34,.7);border:1px solid var(--line);
  border-radius:16px;padding:16px 18px;margin:20px 0 24px;
}
.filter-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.filter-label{font-size:.82rem;font-weight:700;color:var(--mut);min-width:65px}
.filter-pills{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.pill-btn{
  background:var(--card);border:1px solid var(--line);color:#c9d5e8;
  padding:5px 13px;border-radius:99px;font-family:inherit;font-size:.82rem;
  cursor:pointer;transition:all .2s ease;
}
.pill-btn:hover{border-color:var(--acc);color:#fff}
.pill-btn.active{
  background:linear-gradient(135deg,var(--acc),#3d8bff);
  border-color:var(--acc);color:#0a0d14;font-weight:800;
  box-shadow:0 3px 10px rgba(90,169,255,.3);
}

/* --- بطاقات الوظائف المحسنة (Job Cards) --- */
.jobs-list{display:grid;gap:18px;margin:26px 0 34px}
.job-card{
  background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px solid var(--line);border-radius:18px;padding:22px 24px;
  transition:all .25s cubic-bezier(.16,1,.3,1);position:relative;
}
.job-card:hover{
  border-color:rgba(90,169,255,.6);transform:translateY(-3px);
  box-shadow:0 12px 28px rgba(0,0,0,.35);
}
.job-header{
  display:flex;align-items:center;justify-content:space-between;
  gap:10px;margin-bottom:12px;flex-wrap:wrap;
}
.job-header-left{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.job-badge{
  font-size:.76rem;font-weight:800;padding:3px 11px;border-radius:99px;
  background:rgba(255,255,255,.06);color:var(--c,var(--gold));
  border:1px solid rgba(255,255,255,.1);
}
.job-country{
  font-size:.82rem;font-weight:700;color:#c9d5e8;
  background:rgba(255,255,255,.04);border:1px solid var(--line);
  padding:2px 10px;border-radius:99px;
}
.job-type-pill{
  font-size:.74rem;color:#3ddc97;background:rgba(61,220,151,.1);
  border:1px solid rgba(61,220,151,.25);padding:2px 8px;border-radius:99px;font-weight:700;
}
.job-title{font-size:1.25rem;font-weight:800;line-height:1.45;margin-bottom:14px}
.job-title a{text-decoration:none;color:var(--txt);transition:color .2s}
.job-title a:hover{color:var(--acc)}

.job-fast-facts{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
  gap:10px;margin-bottom:14px;
}
.fact-item{
  background:rgba(10,13,20,.6);border:1px solid rgba(255,255,255,.05);
  border-radius:10px;padding:8px 12px;font-size:.82rem;color:#c0cce0;
  display:flex;align-items:center;gap:6px;
}
.fact-item strong{color:#fff;font-weight:700}

.job-summary{font-size:.92rem;color:#b0c0d6;line-height:1.7;margin-bottom:16px}
.job-reqs-preview{
  display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:16px;
}
.req-tag{
  background:rgba(245,197,66,.07);border:1px solid rgba(245,197,66,.2);
  color:var(--gold);font-size:.76rem;padding:2px 9px;border-radius:6px;
}

.job-footer{
  display:flex;align-items:center;justify-content:space-between;
  border-top:1px solid rgba(255,255,255,.05);padding-top:14px;margin-top:14px;
  flex-wrap:wrap;gap:10px;
}
.btn-job-details{
  font-size:.88rem;font-weight:800;color:#0a0d14;text-decoration:none;
  background:linear-gradient(135deg,var(--gold),#ffb347);
  padding:8px 18px;border-radius:99px;transition:.2s;display:inline-flex;align-items:center;gap:6px;
}
.btn-job-details:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(245,197,66,.35)}
.btn-job-apply-direct{
  font-size:.84rem;font-weight:700;color:var(--acc);text-decoration:none;
  border:1px solid rgba(90,169,255,.35);padding:7px 16px;border-radius:99px;
  transition:.2s;background:rgba(90,169,255,.05);
}
.btn-job-apply-direct:hover{background:rgba(90,169,255,.15);border-color:var(--acc);color:#fff}

/* --- حالة عدم وجود نتائج (No Results Box) --- */
.no-results-box{
  background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px dashed var(--line);border-radius:18px;padding:36px 20px;
  text-align:center;margin:30px 0;
}
.no-results-icon{font-size:2.4rem;margin-bottom:12px}
.no-results-box h3{font-size:1.25rem;font-weight:800;margin-bottom:8px;color:#fff}
.no-results-box p{font-size:.9rem;color:var(--mut);max-width:540px;margin:0 auto 18px;line-height:1.6}
.btn-reset-filters{
  background:var(--acc);color:#0a0d14;border:none;font-family:inherit;
  font-weight:800;font-size:.86rem;padding:9px 22px;border-radius:99px;cursor:pointer;
  transition:.2s;
}
.btn-reset-filters:hover{background:#3d8bff;transform:translateY(-2px)}

.breadcrumb{font-size:.82rem;color:var(--mut);margin-bottom:18px}
.breadcrumb a{text-decoration:none;color:var(--mut)}
.breadcrumb a:hover{color:var(--acc)}
.job-single-header{margin-bottom:20px}
.job-single-meta{display:flex;gap:16px;flex-wrap:wrap;color:var(--mut);font-size:.82rem;margin-top:8px}

.job-quick-facts{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:22px 0 28px;
}
.fact-box{
  background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
  display:flex;flex-direction:column;gap:4px;
}
.fact-icon{font-size:1.3rem}
.fact-title{font-size:.76rem;color:var(--mut);font-weight:600}
.fact-val{font-size:.92rem;font-weight:700;color:var(--txt)}
.active-status{color:#3ddc97}

.apply-cta-box{
  background:linear-gradient(135deg,rgba(61,220,151,.1),rgba(90,169,255,.08));
  border:1px solid rgba(61,220,151,.35);border-radius:16px;padding:24px;text-align:center;margin:30px 0;
}
.apply-cta-box h3{font-size:1.25rem;color:#fff;margin-bottom:8px}
.apply-cta-box p{font-size:.92rem;color:var(--mut);margin-bottom:18px}
.btn-apply-main{
  display:inline-block;background:#3ddc97;color:#0a0d14!important;font-weight:800;
  font-size:1rem;padding:12px 28px;border-radius:99px;text-decoration:none;transition:.2s;
}
.btn-apply-main:hover{background:#32be82;transform:scale(1.02)}

/* نافذة طلب الإشعارات بعد 20 ثانية */
.notif-toast-wrap{
  position:fixed;bottom:75px;left:20px;z-index:99999;
  max-width:380px;width:calc(100% - 40px);
  animation:slideUpNotif .4s cubic-bezier(.16,1,.3,1);
}
html[dir="rtl"] .notif-toast-wrap{left:auto;right:20px}
.notif-toast-card{
  background:rgba(17,22,34,.96);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border:1px solid rgba(245,197,66,.35);border-radius:14px;padding:16px;
  box-shadow:0 12px 36px rgba(0,0,0,.6), 0 0 20px rgba(245,197,66,.15);
}
.notif-toast-header{display:flex;align-items:flex-start;gap:12px;margin-bottom:12px}
.notif-toast-icon{
  font-size:24px;line-height:1;background:rgba(245,197,66,.15);
  border:1px solid rgba(245,197,66,.3);border-radius:10px;padding:8px;
}
.notif-toast-info{flex:1}
.notif-toast-title{display:block;font-size:14px;color:#fff;font-weight:700;margin-bottom:4px}
.notif-toast-desc{font-size:12px;color:var(--mut);line-height:1.5;margin:0}
.notif-toast-actions{display:flex;gap:10px;justify-content:flex-end}
.btn-notif-allow{
  background:linear-gradient(135deg,#f5c542,#e5b026);color:#0a0d14;border:none;
  padding:8px 16px;border-radius:8px;font-size:12.5px;font-weight:700;cursor:pointer;
  transition:transform .15s,box-shadow .15s;font-family:inherit;
}
.btn-notif-allow:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(245,197,66,.4)}
.btn-notif-close{
  background:rgba(255,255,255,.07);color:#cbd5e1;border:1px solid rgba(255,255,255,.1);
  padding:8px 14px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;
  font-family:inherit;transition:background .15s;
}
.btn-notif-close:hover{background:rgba(255,255,255,.14);color:#fff}
@keyframes slideUpNotif{from{transform:translateY(30px);opacity:0}to{transform:translateY(0);opacity:1}}
@media(max-width:600px){
  .notif-toast-wrap{bottom:70px;left:10px;right:10px;width:auto}
  html[dir="rtl"] .notif-toast-wrap{left:10px;right:10px}
}

/* --- الكروت النصية: العنوان والملخص هما المحتوى --- */
.trend-card{border-top:3px solid var(--c,var(--gold))}
.trend-card .trend-card-meta{flex-wrap:wrap}
.cat-chip{font-size:.74rem;font-weight:700;padding:2px 10px;border-radius:99px;
  background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:var(--c,var(--gold))}
.trend-card-title{-webkit-line-clamp:3}
.trend-card-summary{-webkit-line-clamp:3}

/* --- صفحة الخبر --- */
.byline{color:var(--mut);font-size:.86rem;margin:-4px 0 16px}
.byline a{color:var(--txt);text-decoration:none;border-bottom:1px solid var(--line)}
.byline a:hover{border-color:var(--acc)}
.story{margin-top:8px}
.facts{background:linear-gradient(165deg,var(--card),var(--bg2));border:1px solid var(--line);
  border-radius:16px;padding:16px 18px;margin:0 0 24px}
.facts h2{font-size:1rem;margin:0 0 10px;color:var(--gold)}
.facts dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px 18px;margin:0}
.facts .fact{display:grid;gap:2px}
.facts dt{font-size:.78rem;color:var(--mut)}
.facts dd{margin:0;font-weight:700;font-variant-numeric:tabular-nums}
aside.gold-promo-cta{margin-top:30px}

/* --- صفحات المواضيع --- */
.topic-list{list-style:none;padding:0;margin:18px 0;display:grid;gap:10px}
.topic-list a{display:grid;gap:4px;text-decoration:none;background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px solid var(--line);border-radius:14px;padding:13px 16px}
.topic-list a:hover{border-color:var(--acc)}
.topic-list .t{font-weight:700;line-height:1.6}
.topic-list .d{font-size:.8rem;color:var(--mut)}

/* --- الرئيسية والأسئلة --- */
.home-head{margin-bottom:18px}
.home-head h1{font-size:2.1rem;margin-bottom:8px}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap;margin:32px 0 14px}
.section-head h2{margin:0;font-size:1.45rem}
.faq-list{display:grid;gap:14px;margin:20px 0}
.faq-item{background:linear-gradient(165deg,var(--card),var(--bg2));border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.faq-item h2{font-size:1.05rem;margin:0 0 6px}
.faq-item p{margin:0;color:#dfe6f0}
@media(max-width:560px){.home-head h1{font-size:1.5rem}}

/* --- أدلة الوظائف --- */
.safety-text ul{margin:6px 0 0;padding-inline-start:18px;display:grid;gap:4px}
.safety-text li{font-size:.85rem;color:var(--mut);line-height:1.6}
.guide ul{margin:0 0 16px;padding-inline-start:22px}
.sources .t,.sources .d{display:block}
.sources .t{overflow-wrap:anywhere}
.list .item .chip{display:inline-block;margin-bottom:6px}

/* --- سطر مصدر الصورة (شرط رخصة ويكيميديا) --- */
.photo-credit{position:absolute;inset-inline:0;bottom:0;font-size:.7rem;line-height:1.5;
  color:#e8ecf4;background:linear-gradient(transparent,rgba(0,0,0,.78));padding:18px 12px 7px}
.photo-credit a,.article-photo figcaption a{color:inherit;text-decoration:underline}
/* الصورة كاملة بلا قص: صور الأشخاص طولية، والقص من المنتصف يقطع الوجه */
.article-photo img{max-height:460px;object-fit:contain;background:#0d121c}
.hero-spotlight-media img{object-position:center 22%}
.trend-card-media img{object-position:center 22%}
.trend-card-media .photo-credit{font-size:.62rem;padding:14px 10px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* --- قسم الوظائف: بحث وتصفية، وشروط وخطوات تقديم واضحة --- */
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.jobs-hero{background:radial-gradient(120% 140% at 100% 0%,rgba(245,197,66,.13),transparent 55%),
  linear-gradient(165deg,var(--card),var(--bg2));border:1px solid var(--line);border-radius:20px;
  padding:26px 22px 16px;margin:10px 0 16px}
.jobs-hero h1{margin:0 0 8px;font-size:1.65rem;line-height:1.45}
.jobs-sub{color:var(--mut);margin:0 0 16px;line-height:1.85}
.job-search{position:relative;display:flex;gap:8px}
.job-search::before{content:"🔍";position:absolute;inset-inline-start:14px;top:50%;
  transform:translateY(-50%);opacity:.7;pointer-events:none;font-size:.95rem}
.job-search input{flex:1;min-width:0;background:var(--bg);border:1px solid var(--line);border-radius:14px;
  color:var(--txt);font:inherit;font-size:1rem;padding:13px 14px;padding-inline-start:42px;outline:none;
  transition:border-color .2s,box-shadow .2s}
.job-search input:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(245,197,66,.18)}
.job-search button{background:var(--gold);color:#1a1405;border:0;border-radius:14px;font:inherit;
  font-weight:800;padding:0 20px;cursor:pointer}
.job-search.mini{margin:22px 0 6px}
.job-filters{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.job-filter{background:rgba(255,255,255,.04);border:1px solid var(--line);color:var(--txt);border-radius:99px;
  padding:7px 15px;font:inherit;font-size:.86rem;font-weight:700;cursor:pointer;transition:.2s}
.job-filter:hover{border-color:rgba(245,197,66,.55)}
.job-filter[aria-pressed=true]{background:var(--gold);border-color:var(--gold);color:#1a1405}
.job-count{color:var(--mut);font-size:.85rem;margin:12px 0 0;min-height:1.3em}
.job-group[hidden],.job-card[hidden]{display:none}
.job-grid{display:grid;gap:14px;grid-template-columns:1fr}
@media(min-width:760px){.job-grid{grid-template-columns:1fr 1fr}}
.job-card{display:flex;flex-direction:column;gap:8px;background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px solid var(--line);border-radius:16px;padding:16px 18px;color:var(--txt);text-decoration:none;
  transition:border-color .2s,transform .2s}
.job-card:hover{border-color:rgba(245,197,66,.55);transform:translateY(-2px)}
.job-card-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:.8rem;color:var(--mut)}
.job-flag{font-size:1.3rem;line-height:1}
.job-kind{margin-inline-start:auto;background:rgba(90,169,255,.1);color:var(--acc);border-radius:99px;
  padding:2px 10px;font-weight:700;font-size:.74rem}
.job-card h3{margin:0;font-size:1.04rem;line-height:1.65}
.job-card p{margin:0;color:var(--mut);font-size:.88rem;line-height:1.75;display:-webkit-box;
  -webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.job-card-meta{margin-top:auto;padding-top:10px;display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.79rem;
  color:var(--mut);border-top:1px dashed var(--line)}
.job-go{margin-inline-start:auto;color:var(--gold);font-weight:800}
.job-empty{text-align:center;color:var(--mut);padding:30px 12px;border:1px dashed var(--line);
  border-radius:16px;margin-top:12px}
.job-safety{display:block;padding:12px 18px}
.job-safety summary{cursor:pointer;display:flex;align-items:center;gap:10px;list-style:none}
.job-safety summary::-webkit-details-marker{display:none}
.job-safety summary strong{color:var(--acc);font-size:.95rem}
.job-safety summary::after{content:"▾";margin-inline-start:auto;color:var(--mut)}
.job-safety[open] summary::after{content:"▴"}
.job-safety ul{margin:10px 0 2px;padding-inline-start:22px;color:var(--mut);font-size:.9rem;line-height:1.8}
.job-facts{display:grid;gap:10px;grid-template-columns:1fr;margin:0 0 18px}
@media(min-width:700px){.job-facts{grid-template-columns:repeat(3,1fr)}}
.job-fact{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.job-fact span{display:block;color:var(--mut);font-size:.78rem;margin-bottom:4px}
.job-fact strong{font-size:.92rem;line-height:1.65;display:block}
.job-fact a{color:var(--gold)}
.job-block{background:linear-gradient(165deg,var(--card),var(--bg2));border:1px solid var(--line);
  border-radius:18px;padding:4px 18px 16px;margin:0 0 16px}
.job-block h2{margin:16px 0 14px}
.job-checks,.job-docs{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.job-checks li,.job-docs li{position:relative;padding-inline-start:34px;line-height:1.85}
.job-checks li::before{content:"✓";position:absolute;inset-inline-start:0;top:.25em;width:23px;height:23px;
  border-radius:50%;background:rgba(74,222,128,.14);color:#4ade80;font-weight:900;font-size:.8rem;
  display:grid;place-items:center}
.job-docs li::before{content:"📄";position:absolute;inset-inline-start:2px;top:0}
.job-steps{list-style:none;counter-reset:step;margin:0;padding:0}
.job-steps li{counter-increment:step;position:relative;padding-inline-start:48px;padding-bottom:18px;line-height:1.85}
.job-steps li::before{content:counter(step);position:absolute;inset-inline-start:0;top:0;width:33px;height:33px;
  border-radius:50%;background:var(--gold);color:#1a1405;font-weight:900;display:grid;place-items:center}
.job-steps li::after{content:"";position:absolute;inset-inline-start:16px;top:36px;bottom:2px;width:2px;
  background:var(--line)}
.job-steps li:last-child{padding-bottom:4px}
.job-steps li:last-child::after{display:none}
.job-apply{display:flex;align-items:center;justify-content:center;gap:8px;margin:14px 0 8px;
  background:linear-gradient(95deg,var(--gold),#ff9f68);color:#1a1405!important;font-weight:900;
  border-radius:14px;padding:14px 18px;text-decoration:none;text-align:center;line-height:1.6}
.job-apply:hover{filter:brightness(1.06)}
.job-apply-note{color:var(--mut);font-size:.8rem;text-align:center;margin:0}
.job-notes{background:rgba(255,160,60,.07);border:1px solid rgba(255,160,60,.32);border-radius:16px;
  padding:12px 18px;margin:0 0 16px}
.job-notes strong{color:#ffb454}
.job-notes ul{margin:6px 0 0;padding-inline-start:20px;line-height:1.8}
"""


CAT_EN = {
    "سياسة": "Politics",
    "طقس": "Weather",
    "اقتصاد": "Finance",
    "رياضة": "Sports",
    "تقنية": "Tech",
    "فن ومشاهير": "Entertainment",
    "ديني": "Faith",
    "تعليم": "Education",
    "أبراج وفلك": "Horoscope",
    "فضول عام": "Curiosity",
    "دول وأماكن": "Places",
    "شخصية": "People",
    "عام": "General",
    "حوادث وقضايا": "Legal & Crime",
}


def notification_prompt_tag(is_en=False, root="./"):
    is_en_js = "true" if is_en else "false"
    return f"""<script src="https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js" defer></script>
<script>
window.OneSignalDeferred = window.OneSignalDeferred || [];
OneSignalDeferred.push(async function(OneSignal) {{
  try {{
    await OneSignal.init({{
      appId: "a624b9fa-0c01-46de-a5c2-99e05d1a5bb5",
      serviceWorkerParam: {{ scope: "/" }},
      serviceWorkerPath: "/OneSignalSDKWorker.js",
      allowLocalhostAsSecureOrigin: true,
      autoRegister: false
    }});
  }} catch(e) {{}}
}});

(function() {{
  var STORAGE_KEY = "altrendat_notif_prompt_v1";
  var dismissed = localStorage.getItem(STORAGE_KEY);
  if (dismissed && (Date.now() - parseInt(dismissed, 10) < 7 * 86400 * 1000)) return;
  if (window.Notification && Notification.permission === "granted") return;

  setTimeout(function() {{
    if (window.Notification && Notification.permission === "granted") return;
    if (document.getElementById("notif-toast-prompt")) return;

    var wrap = document.createElement("div");
    wrap.id = "notif-toast-prompt";
    wrap.className = "notif-toast-wrap";
    wrap.setAttribute("role", "alertdialog");

    var isEn = {is_en_js};
    var title = isEn ? "🔔 Enable Live Notifications" : "🔔 تفعيل الإشعارات الفورية";
    var desc = isEn
      ? "Get instant breaking news, trending updates, and live gold & currency alerts as they happen."
      : "احصل على تنبيهات عاجلة بأهم التريندات وأسعار الذهب والأنباء العاجلة فور حدوثها.";
    var allowText = isEn ? "Allow Notifications" : "تفعيل الإشعارات";
    var closeText = isEn ? "Later" : "لاحقاً";

    wrap.innerHTML = '<div class="notif-toast-card">' +
      '<div class="notif-toast-header">' +
        '<div class="notif-toast-icon">⚡</div>' +
        '<div class="notif-toast-info">' +
          '<strong class="notif-toast-title">' + title + '</strong>' +
          '<p class="notif-toast-desc">' + desc + '</p>' +
        '</div>' +
      '</div>' +
      '<div class="notif-toast-actions">' +
        '<button type="button" class="btn-notif-close" id="btn-notif-dismiss">' + closeText + '</button>' +
        '<button type="button" class="btn-notif-allow" id="btn-notif-request">' + allowText + '</button>' +
      '</div>' +
    '</div>';

    document.body.appendChild(wrap);

    document.getElementById("btn-notif-dismiss").addEventListener("click", function() {{
      localStorage.setItem(STORAGE_KEY, Date.now().toString());
      wrap.remove();
    }});

    document.getElementById("btn-notif-request").addEventListener("click", async function() {{
      try {{
        if (window.OneSignalDeferred) {{
          window.OneSignalDeferred.push(async function(OneSignal) {{
            try {{
              await OneSignal.Notifications.requestPermission();
              await OneSignal.User.addTags({{
                news_lang: isEn ? "en" : "ar",
                site: "altrendat"
              }});
            }} catch(err) {{}}
          }});
        }} else if (window.Notification && Notification.requestPermission) {{
          await Notification.requestPermission();
        }}
      }} catch(e) {{}}
      localStorage.setItem(STORAGE_KEY, Date.now().toString());
      wrap.remove();
    }});
  }}, 20000);
}})();
</script>"""


def page(path, title, desc, body, canonical, nav="", image=None,
         ogtype="website", jsonld=None, depth=0, is_en=False, robots=ROBOTS_INDEX):
    root = "../" * depth if depth else "./"
    og_img = image or (BASE + "/og-default.jpg")
    ogimage = '<meta property="og:image" content="{img}">\n<meta name="twitter:image" content="{img}">'.format(img=E(og_img))
    ld = ('<script type="application/ld+json">{}</script>'.format(
        json.dumps(jsonld, ensure_ascii=False)) if jsonld else "")

    lang = "en" if is_en else "ar"
    direction = "ltr" if is_en else "rtl"
    locale = "en_US" if is_en else "ar_AR"
    site_brand = SITE_NAME_EN if is_en else SITE_NAME

    if is_en:
        flinks = ('<a href="{r}about/">About Us</a>'
                  '<a href="{r}editorial-policy/">Editorial Policy</a>'
                  '<a href="{r}privacy/">Privacy Policy</a>'
                  '<a href="{r}terms/">Terms</a>'
                  '<a href="{r}gold-app/">Goldex App</a>'
                  '<a href="{r}contact/">Contact</a>').format(r=root)
        fdesc = "{site} — What people are searching for, explained with sources.".format(site=E(site_brand))
        ffine = "News stories are attributed and linked to their original publishers."
    else:
        flinks = ('<a href="{r}about/">من نحن</a>'
                  '<a href="{r}{ed}/">المحرر</a>'
                  '<a href="{r}editorial-policy/">سياسة التحرير</a>'
                  '<a href="{r}faq/">الأسئلة الشائعة</a>'
                  '<a href="{r}privacy/">سياسة الخصوصية</a>'
                  '<a href="{r}terms/">شروط الاستخدام</a>'
                  '<a href="{r}gold-app/">تطبيق Goldex</a>'
                  '<a href="{r}gold-price/egypt/">سعر الذهب في مصر</a>'
                  '<a href="{r}gold-price/saudi/">سعر الذهب في السعودية</a>'
                  '<a href="{r}saudi-payment-dates/">مواعيد الصرف في السعودية</a>'
                  '<a href="{r}passport-photo/">صور الجواز والتأشيرة</a>'
                  '<a href="{r}contact/">اتصل بنا</a>').format(r=root, ed=config.EDITOR_PATH)
        fdesc = "{site} — ما يبحث عنه الناس في مصر والسعودية، مشروحًا بمصادره.".format(site=E(site_brand))
        ffine = "الأخبار منسوبة إلى مصادرها وروابطها، والأرقام إلى جهاتها."

    if is_en:
        floating_bar = f"""<div class="floating-cta">
  <span class="gold-pulse-dot"></span>
  <span>🪙 Goldex App: Live Gold & Currencies:</span>
  <a class="btn-gold-app" href="{root}gold-app/">Get Goldex 📱</a>
</div>"""
    else:
        floating_bar = f"""<div class="floating-cta">
  <span class="gold-pulse-dot"></span>
  <span>🪙 تطبيق Goldex: أسعار الذهب والعملات:</span>
  <a class="btn-gold-app" href="{root}gold-app/">حمّل Goldex 📱</a>
</div>"""

    brand_href = f"{root}world/" if is_en else root

    out = SHELL.format(
        lang=lang, dir=direction, locale=locale, robots=robots,
        title=E(title), desc=E(desc[:300]), canonical=E(canonical),
        site=E(site_brand), brand_href=brand_href, ogimage=ogimage, ogtype=ogtype, jsonld=ld,
        nav=nav, body=body, root=root, flinks=flinks, fdesc=fdesc, ffine=ffine,
        floating_bar=floating_bar,
        notif_prompt=notification_prompt_tag(is_en=is_en, root=root),
        analytics=analytics_tag())

    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(out)
    return canonical


def data_table(d):
    if not d:
        return ""
    head = "".join("<th>{}</th>".format(E(c)) for c in d["columns"])
    rows = "".join(
        "<tr><td>{}</td>{}</tr>".format(
            E(r["city"]),
            "".join("<td>{}</td>".format(E(r["times"][c]))
                    for c in d["columns"]))
        for r in d["rows"])
    return ("<h2>{}</h2><table><thead><tr><th>—</th>{}</tr></thead>"
            "<tbody>{}</tbody></table><p class='src'>{}</p>").format(
        E(d["title"]), head, rows, E(d.get("source", "")))


def sources_list(news, is_en=False):
    items = []
    default_src = "Source" if is_en else "مصدر"
    # بلا مواقع بث مقرصن وبلا صفحات رئيسية — انظر sources.good_sources
    for n in sources.good_sources(news):
        desc = (n.get("og_desc") or "").strip()
        if len(desc) > 200:
            desc = desc[:200].rsplit(" ", 1)[0] + "…"
        items.append(
            "<li><a href='{u}' target='_blank' rel='noopener nofollow'>"
            "<span class='name'>{s}</span><span class='t'>{t}</span>"
            "<span class='d'>{d}</span></a></li>".format(
                u=E(n["url"]), s=E(n.get("source") or default_src),
                t=E(n["title"]), d=E(desc)))
    if not items:
        return ""
    title = "Sources & Coverage" if is_en else "المصادر"
    return "<h2>{}</h2><ul class='sources'>{}</ul>".format(title, "".join(items))


# صور الصحف لا تُستخدم في أي مكان: لا في الموقع ولا التطبيق ولا تليجرام.
# عليها علامات ناشريها المائية وحقوقهم. البديل: كارت الموقع، أو صورة حرة
# الرخصة من ويكيميديا مع سطر مصدرها (photos.py و photo_figure).


def get_card_thumb_url(t, root="./"):
    """كارت الموقع نفسه (1200×675) — صورة نملكها، ولا نستعير صور الصحف."""
    if t.get("card"):
        return "{}cards/{}".format(root, os.path.basename(t["card"]))
    return "{}og-default.jpg".format(root)


def render_trend_card(t, href, rank, country_name, flag, time_str, root="./", is_en=False):
    art = t.get("article") or {}
    headline = art.get("headline") or t.get("title", "")
    summary = art.get("summary") or ""
    if not summary and art.get("body"):
        summary = art["body"].split("\n")[0][:130]

    cat_label = CAT_EN.get(t.get("category", ""), t.get("category", "")) if is_en else t.get("category", "")
    cat_color = t.get("color", "var(--gold)")
    n_sources = len(sources.good_sources(t.get("news", [])))

    # صورة الخبر نفسه (حرة الرخصة من photos.py) وإلا كارت الموقع — لا صور الصحف.
    # سطر المصدر نص بلا رابط (الكارت كله رابط)، والرابط الكامل في صفحة المقال.
    photo = art.get("photo") or {}
    card_url = get_card_thumb_url(t, root=root)
    if photo.get("url"):
        img_url = photo["url"].replace("/1280px-", "/500px-")
        # المصدر (ويكيميديا كومنز) جزء من سطر الحقوق: شرط الرخصة، والحارس يرفض
        # صفحة فيها صورة ويكيميديا بلا ذكره
        if photo.get("ai"):
            credit_txt = "AI-generated image" if is_en else "صورة مولّدة بالذكاء الاصطناعي"
        else:
            credit_txt = "{}{} {} · {} · {}".format(
                ("Illustrative photo · " if is_en else "صورة تعبيرية · ") if photo.get("stock") else "",
                "Photo:" if is_en else "تصوير:", photo.get("artist", ""), photo.get("license", ""),
                "Wikimedia Commons" if is_en else "ويكيميديا كومنز")
        credit = "<span class='photo-credit'>{}</span>".format(E(credit_txt))
    else:
        img_url, credit = card_url, ""
    media = ('<div class="trend-card-media"><img src="{u}" alt="{a}" loading="lazy" '
             'decoding="async" width="500" height="281" '
             'onerror="this.onerror=null;this.src=\'{c}\'">{cr}</div>').format(
        u=E(img_url), a=E(headline), c=E(card_url), cr=credit)
    time_html = f"<span class='trend-time-tag'>🕒 {E(time_str)}</span>" if time_str else ""
    sources_text = f"{n_sources} sources" if is_en else f"{n_sources} مصادر"
    read_more = "Details →" if is_en else "التفاصيل ←"

    return f'''
    <article class="trend-card" style="--c:{cat_color}">
      <a class="trend-card-link" href="{href}">
        {media}
        <div class="trend-card-body">
          <div class="trend-card-meta">
            <span class="cat-chip">{t.get('icon', '🔥')} {E(cat_label)}</span>
            <span class="trend-country-pill">{flag} {E(country_name)}</span>
            {time_html}
          </div>
          <h3 class="trend-card-title">{E(headline)}</h3>
          <p class="trend-card-summary">{E(summary)}</p>
          <div class="trend-card-footer">
            <span class="trend-sources-tag">📎 {sources_text}</span>
            <span class="trend-arrow">{read_more}</span>
          </div>
        </div>
      </a>
    </article>'''


def render_hero_spotlight(t, href, country_name, flag, time_str, root="./", is_en=False):
    art = t.get("article") or {}
    headline = art.get("headline") or t.get("title", "")
    summary = art.get("summary") or ""
    if not summary and art.get("body"):
        summary = art["body"].split("\n")[0][:180]

    cat_label = CAT_EN.get(t.get("category", ""), t.get("category", "")) if is_en else t.get("category", "")
    traffic = t.get("traffic", "")
    photo = art.get("photo")
    img_url = photo["url"] if photo else get_card_thumb_url(t, root=root)
    credit = ("<span class='photo-credit'>{}</span>".format(photo_credit(photo, is_en))
              if photo else "")
    n_sources = len(sources.good_sources(t.get("news", [])))

    tag_text = "🔥 Top story" if is_en else "🔥 الأكثر بحثًا الآن"
    cta_text = "اقرأ الخبر ←" if not is_en else "Read the story →"
    traffic_label = f"🔍 {E(traffic)} searches" if is_en else f"🔍 {E(traffic)} بحث"
    sources_label = f"📎 {n_sources} sources" if is_en else f"📎 {n_sources} مصادر"

    return f'''
    <div class="hero-spotlight">
      <div class="hero-spotlight-media">
        <img src="{E(img_url)}" alt="{E(headline)}" loading="eager" decoding="async" onerror="this.onerror=null;this.src='{E(get_card_thumb_url(t, root=root))}'">
        {credit}
      </div>
      <div class="hero-spotlight-content">
        <div>
          <span class="spotlight-top-badge">{tag_text}</span>
          <div class="trend-card-meta" style="margin-bottom:10px;">
            <span class="trend-country-pill">{flag} {E(country_name)}</span>
            <span>·</span>
            <span>{t.get('icon', '🔥')} {E(cat_label)}</span>
            <span>·</span>
            <span style="color:var(--gold);font-weight:700;">{traffic_label}</span>
          </div>
          <h2 class="hero-spotlight-title">{E(headline)}</h2>
          <p class="hero-spotlight-desc">{E(summary)}</p>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:16px;flex-wrap:wrap;gap:12px;">
          <a class="hero-spotlight-cta" href="{href}">{cta_text}</a>
          <span style="font-size:0.8rem;color:var(--mut);">{sources_label}</span>
        </div>
      </div>
    </div>'''


def photo_credit(photo, is_en=False):
    """سطر المصدر الذي تشترطه رخصة الصورة: المصوّر والرخصة ورابط الملف.
    ويسبقه من في الصورة، أو أنها تعبيرية — فلا يظنها القارئ من الحدث نفسه."""
    if photo.get("ai"):
        return "AI-generated image" if is_en else "صورة مولّدة بالذكاء الاصطناعي"
    if photo.get("stock"):
        who = "Illustrative photo · " if is_en else "صورة تعبيرية · "
    elif photo.get("wiki_title"):
        who = ("Pictured: {} · " if is_en else "في الصورة: {} · ").format(E(photo["wiki_title"]))
    else:
        who = ""
    return "{}{} {} · {} · <a href='{}' target='_blank' rel='noopener'>{}</a>".format(
        who, "Photo:" if is_en else "تصوير:", E(photo.get("artist", "")),
        E(photo.get("license", "")), E(photo.get("file_page", "")),
        "Wikimedia Commons" if is_en else "ويكيميديا كومنز")


def photo_srcset(url):
    """مقاسات ويكيميديا القياسية للصورة نفسها، ليأخذ الهاتف الأصغر."""
    if "/1280px-" not in url:
        return ""
    return ", ".join("{} {}w".format(url.replace("/1280px-", "/{}px-".format(w)), w)
                     for w in (500, 960)) + ", {} 1280w".format(url)


def photo_figure(photo, alt, is_en=False, card=None):
    """صورة حرة الرخصة تحتها مصدرها. صور الصحف لا تُعرض (حقوقها لناشريها).
    card: كارت الموقع (رابط نسبي، 1200×675، عليه العنوان نفسه) — يُعرض حين
    لا صورة تخص الخبر، ويحل محل الصورة إن تعذّر تحميلها فلا تظهر صورة مكسورة."""
    if not photo or not photo.get("url"):
        if not card:
            return ""
        return ("<figure class='article-photo'><img src='{u}' alt='{a}' width='1200' "
                "height='675' loading='eager' fetchpriority='high' decoding='async'>"
                "</figure>").format(u=E(card), a=E(alt))
    size = ""
    if photo.get("width") and photo.get("height"):
        size = " width='{}' height='{}'".format(int(photo["width"]), int(photo["height"]))
    srcset = photo_srcset(photo["url"])
    if srcset:
        size += " srcset='{}' sizes='(max-width: 820px) 100vw, 820px'".format(E(srcset))
    if card:
        size += (" onerror=\"this.onerror=null;this.removeAttribute('srcset');"
                 "this.src='{}';var c=this.parentNode.querySelector('figcaption');"
                 "if(c)c.remove()\"").format(E(card))
    if photo.get("ai"):
        alt = ("AI image: " if is_en else "صورة مولّدة: ") + alt
    elif photo.get("stock"):
        alt = ("Illustrative photo: " if is_en else "صورة تعبيرية: ") + alt
    elif photo.get("wiki_title"):
        alt = photo["wiki_title"]
    return ("<figure class='article-photo'><img src='{u}' alt='{a}'{s} loading='eager' "
            "fetchpriority='high' decoding='async'>"
            "<figcaption>{c}</figcaption></figure>").format(
        u=E(photo["url"]), a=E(alt), s=size, c=photo_credit(photo, is_en))


def article_date(iso, is_en=False):
    """تاريخ ووقت مقروءان للقارئ بتوقيت بلده."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    tz = timezone(timedelta(hours=0 if is_en else 3))
    local = dt.astimezone(tz)
    if is_en:
        return local.strftime("%d %b %Y, %H:%M UTC")
    months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
              "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    return "{} {} {}، {}".format(local.day, months[local.month - 1], local.year,
                                 format_time(iso))


def facts_box(art, is_en=False):
    """«معلومات سريعة» — ما كتبه الكاتب من المصادر فقط، ولا شيء إن خلت."""
    rows = [(f.get("label", "").strip(), f.get("value", "").strip())
            for f in (art.get("facts") or []) if isinstance(f, dict)]
    rows = [(k, v) for k, v in rows if k and v][:6]
    if not rows:
        return ""
    title = "Quick facts" if is_en else "معلومات سريعة"
    items = "".join("<div class='fact'><dt>{}</dt><dd>{}</dd></div>".format(E(k), E(v))
                    for k, v in rows)
    return "<section class='facts' aria-label='{t}'><h2>{t}</h2><dl>{i}</dl></section>".format(
        t=title, i=items)


def build_trend(country, cfg, t, urls, hubs=None, news=None):
    """صفحة الخبر: العنوان، الإجابة في أول سطر، المعلومات السريعة، المتن،
    ثم المصادر. بلا صور صحف وبلا أسئلة مكررة من الملخص."""
    is_en = cfg.get("lang") == "en" or country == "world"
    cname = cfg.get("name_en", "Worldwide") if is_en else cfg["country_name"]
    slug = entities.slugify(t["title"])
    day = entities.day_of(cfg)
    art = t["article"]
    path = "{}/{}/{}/index.html".format(country, day, slug)
    canonical = "{}/{}/{}/{}/".format(BASE, country, day, slug)
    # خبر من مصدر واحد لا يُفهرس (شرط الحارس نفسه) — في كل النسخ
    is_indexed = indexed(country) and len(sources.good_sources(t.get("news", []))) >= 2

    card = BASE + "/cards/" + os.path.basename(t["card"]) if t.get("card") else BASE + "/og-default.jpg"
    # صورة المشاركة وDiscover: الصورة الحقيقية (1280 عرضًا) أولًا، ثم كارت الموقع
    photo = art.get("photo") or {}
    img = photo.get("url") or card
    published = t.get("published_at") or cfg["generated_at"]
    modified = art.get("written_at") or published

    # المتن فقرات؛ وأول فقرة تُحذف إن كانت تكرارًا للملخص
    summ = art.get("summary", "").strip()
    paras = [p.strip() for p in art["body"].split("\n") if p.strip()]
    if paras and summ:
        norm = lambda s: re.sub(r"[\s\.\،\:\-\_]+", "", s)
        if norm(paras[0]) == norm(summ) or norm(paras[0]).startswith(norm(summ)[:25]):
            paras = paras[1:] or paras
    body_html = "".join("<p>{}</p>".format(E(p)) for p in paras)
    tags = "".join("<span class='tag'>{}</span>".format(E(x)) for x in art.get("tags", []))
    cat_label = CAT_EN.get(t["category"], t["category"]) if is_en else t["category"]

    editor_url = "../../../../{}/".format(config.EDITOR_PATH)
    # «آخر تحديث» فقط لتحديث حقيقي، لا لدقيقة بين الرصد والكتابة
    try:
        gap = (datetime.fromisoformat(modified.replace("Z", "+00:00")) -
               datetime.fromisoformat(published.replace("Z", "+00:00"))).total_seconds()
    except Exception:
        gap = 0
    updated = gap > 1800
    if is_en:
        byline = ("<p class='byline'>By <a href='{u}'>{n}</a> · Published {p}"
                  "{m}</p>").format(
            u=editor_url, n=E(config.EDITOR_NAME_EN), p=E(article_date(published, True)),
            m=(" · Updated " + E(article_date(modified, True))) if updated else "")
        crumbs_home, crumbs_country = "Home", "{} trends".format(cname)
    else:
        byline = ("<p class='byline'>كتبه <a href='{u}'>{n}</a> · نُشر {p}"
                  "{m}</p>").format(
            u=editor_url, n=E(config.EDITOR_NAME), p=E(article_date(published)),
            m=(" · آخر تحديث " + E(article_date(modified))) if updated else "")
        crumbs_home, crumbs_country = "الرئيسية", "ترندات " + cname

    chips = ("<span class='chip'>{icon} {cat}</span>"
             "<span class='chip'>{flag} {cname}</span>"
             "<span class='chip'>🔍 {traffic}</span>").format(
        icon=t["icon"], cat=E(cat_label), flag=cfg["flag"], cname=E(cname),
        traffic=E(t["traffic"]) + (" searches" if is_en else " بحث"))

    hub_link = ""
    if hubs is not None and slug in hubs:
        hub_link = (" · <a href='../../../../e/{s}/'>{txt}</a>".format(
            s=slug, txt=("All coverage of this topic" if is_en else "كل تغطيتنا لـ«{}»".format(E(t["title"])))))
    meta_nav = ("<p class='meta'><a href='../'>{day_txt}</a> · <a href='../../'>{today}</a>{hub}</p>").format(
        day_txt=("← {} trends on {}".format(E(cname), day) if is_en
                 else "← ترندات {} يوم {}".format(E(cname), day)),
        today=("Today" if is_en else "اليوم"), hub=hub_link)

    promo = """
    <aside class="gold-promo-cta">
      <div class="gold-promo-content">
        <div class="gold-promo-text">
          <strong>{t}</strong>
          <p>{d}</p>
        </div>
        <a class="btn-gold-app" href="../../../../gold-app/">{b}</a>
      </div>
    </aside>""".format(
        t=("Goldex: live gold and currency prices" if is_en else "تطبيق Goldex لأسعار الذهب والعملات"),
        d=("Gold rates, making-charge calculator and price alerts on Android." if is_en
           else "أسعار الذهب والعملات، حاسبة المصنعية، وتنبيهات الأسعار على أندرويد."),
        b=("About the app" if is_en else "تعرّف على التطبيق"))

    body = f"""
    <nav class="breadcrumb"><a href="../../../../">{crumbs_home}</a> › <a href="../../">{E(crumbs_country)}</a> › <span>{E(t['title'])}</span></nav>
    <div class="when">{chips}</div>
    <h1>{E(art["headline"])}</h1>
    {byline}
    <p class="lead">{E(summ)}</p>
    {photo_figure(art.get("photo"), art["headline"], is_en,
                  card=get_card_thumb_url(t, root="../../../../") if t.get("card") else None)}
    {facts_box(art, is_en)}
    {data_table(t.get("data"))}
    {"" if is_en else evergreen.related_box(t["title"], country, "../../../../")}
    {"" if is_en else idphoto.related_box(t["title"], "../../../../")}
    <article class="story">{body_html}</article>
    <div class="tags">{tags}</div>
    {sources_list(t["news"], is_en=is_en)}
    {promo}
    {meta_nav}"""

    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "NewsArticle",
                "headline": art["headline"][:110],
                "description": summ,
                "image": ([photo["url"]] if photo.get("url") else []) + [card],
                "datePublished": published,
                "dateModified": modified,
                "inLanguage": "en" if is_en else "ar",
                "author": {"@type": "Person",
                           "name": config.EDITOR_NAME_EN if is_en else config.EDITOR_NAME,
                           "url": "{}/{}/".format(BASE, config.EDITOR_PATH)},
                "publisher": {"@type": "Organization",
                              "name": SITE_NAME_EN if is_en else SITE_NAME,
                              "url": BASE,
                              "logo": {"@type": "ImageObject", "url": BASE + "/logo.png"}},
                "mainEntityOfPage": canonical,
                "keywords": ", ".join(art.get("tags", [])),
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": crumbs_home, "item": BASE + "/"},
                    {"@type": "ListItem", "position": 2, "name": crumbs_country,
                     "item": "{}/{}/".format(BASE, country)},
                    {"@type": "ListItem", "position": 3, "name": art["headline"][:110]},
                ],
            },
        ],
    }

    if is_indexed:
        urls.append((canonical, modified, "0.8"))
        if news is not None:
            news.append({"loc": canonical, "published": published,
                         "title": art["headline"], "lang": "en" if is_en else "ar"})
    site_title = SITE_NAME_EN if is_en else SITE_NAME
    return page(path, art["headline"] + " | " + site_title,
                summ, body, canonical,
                nav=country_nav(country, 4, is_en=is_en), image=img,
                ogtype="article", jsonld=jsonld, depth=4, is_en=is_en,
                robots=ROBOTS_INDEX if is_indexed else ROBOTS_NOINDEX)


def keep_published(old, t):
    """ترند له مقال منشور يُحدَّث في لقطة يومه ولا يُستبدل بنسخة التشغيلة.

    التشغيلة الحالية قد لا ترفق مقاله، ومصادرها من Google Trends تتبدل خلال
    اليوم. الاستبدال الكامل كان يمحو المقال فيصير رابطه 404، أو ينزل مصادره
    تحت اثنين فيخرج من الفهرسة. فيبقى المقال، وتُضم المصادر القديمة للجديدة.
    """
    if not t.get("article"):
        for k, v in old.items():
            t.setdefault(k, v)          # المقال وصورته وكارته كما نُشرت
        t["article"] = old["article"]
    seen = {n.get("url") for n in t.get("news", [])}
    t["news"] = list(t.get("news", [])) + [
        n for n in old.get("news", [])
        if n.get("url") not in seen and not sources.is_spam(n)]


def archive_today(data):
    """يؤرشف حالة اليوم الحالية قبل البناء.

    تتم هنا لا في pipeline.py: المقالات والكروت تُضاف بعد الالتقاط،
    فأرشفتها مبكرًا تحفظ ترندات بلا محتوى. وهذه الخطوة تجري بعد
    اكتمال السلسلة، فتلتقط كل شيء.

    trends.json يُمحى كل 20 دقيقة؛ هذه اللقطة تجعل كل يوم دائمًا،
    فلا يصير رابط الأمس 404 اليوم — ورابط يختفي بعد يوم لا يُرتَّب.
    """
    days_dir = os.path.join(ROOT, "data", "days")
    os.makedirs(days_dir, exist_ok=True)

    for key, cfg in data.items():
        day = entities.day_of(cfg)
        path = os.path.join(days_dir, "{}-{}.json".format(key, day))

        # تشغيلات اليوم نفسه تُدمج: الجديد يُضاف والقديم يُحدَّث،
        # فلا يفقد اليوم ترندًا ظهر صباحًا وزال ظهرًا.
        merged = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for t in json.load(f).get("trends", []):
                    merged[t["title"]] = t
        for t in cfg["trends"]:
            old = merged.get(t["title"])
            if old and old.get("published_at"):
                t["published_at"] = old["published_at"]
            elif not t.get("published_at"):
                t["published_at"] = cfg.get("generated_at")
            if old and old.get("article"):
                keep_published(old, t)
            merged[t["title"]] = t

        snap = dict(cfg)
        lang = cfg.get("lang", "en" if key == "world" else "ar")
        snap["trends"] = dedup.dedup_trends(list(merged.values()), lang=lang)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)


def load_days():
    """كل اللقطات اليومية: {(بلد, تاريخ): بيانات}، الأحدث أولًا.

    الموقع يُبنى من هذه لا من trends.json وحده، وإلا اختفت صفحات
    الأمس اليوم. وهذا هو الفرق بين أرشيف وبين لوحة عرض.
    """
    days_dir = os.path.join(ROOT, "data", "days")
    out = {}
    if not os.path.isdir(days_dir):
        return out
    for name in sorted(os.listdir(days_dir), reverse=True):
        if not name.endswith(".json"):
            continue
        key, day = name[:-5].split("-", 1)
        with open(os.path.join(days_dir, name), encoding="utf-8") as f:
            snap = json.load(f)
        # اليوم من اسم الملف لا من generated_at: لقطة يوم القاهرة 24
        # قد تحمل وقت UTC من مساء 23.
        snap["day"] = day
        lang = snap.get("lang", "en" if key == "world" else "ar")
        snap["trends"] = dedup.dedup_trends(snap.get("trends", []), lang=lang)
        out[(key, day)] = snap
    return out


def country_nav(current, depth, is_en=False):
    root = "../" * depth if depth else "./"
    out = []
    if is_en:
        mark_world = " ●" if current == "world" else ""
        out.append(f"<a href='{root}world/'>🌐 Worldwide{mark_world}</a>")
        out.append(f"<a href='{root}' class='nav-lang-btn' title='الانتقال إلى النسخة العربية'>العربية</a>")
    else:
        # النسخة الإنجليزية زر لغة في آخر القائمة، لا بلد بين البلاد. ولينكها
        # من كل صفحة عربية يجعلها غير يتيمة، فيزحف لها جوجل ويفهرسها أسرع.
        for key, cfg in COUNTRIES.items():
            if key == "world":
                continue
            mark = " ●" if key == current else ""
            name = cfg.get("name_ar") or cfg.get("name_en") or key
            out.append(f"<a href='{root}{key}/'>{cfg['flag']} {E(name)}{mark}</a>")
        mark_jobs = " ●" if current == "jobs" else ""
        out.append(f"<a href='{root}jobs/' class='nav-jobs'>💼 وظائف وهجرة{mark_jobs}</a>")
        mark_gold = " ●" if current == "gold" else ""
        out.append(f"<a href='{root}gold-price/egypt/'>🪙 سعر الذهب{mark_gold}</a>")
        mark_pay = " ●" if current == "pay" else ""
        out.append(f"<a href='{root}saudi-payment-dates/'>📅 مواعيد الصرف{mark_pay}</a>")
        mark_photo = " ●" if current == "photo" else ""
        out.append(f"<a href='{root}{idphoto.SLUG}/'>📸 صور الجواز{mark_photo}</a>")
        if "world" in COUNTRIES:
            out.append(f"<a href='{root}world/' class='nav-lang-btn' lang='en' hreflang='en' "
                       f"title='English edition: world news'>🌐 English</a>")
    return "".join(out)


def build_day(country, day, cfg, urls, prev_day, next_day):
    """صفحة يوم واحد — العمق الذي يجعل للموقع أرشيفًا يُزحف إليه."""
    is_en = cfg.get("lang") == "en" or country == "world"
    cname = cfg.get("name_en", "Worldwide") if is_en else cfg["country_name"]
    pub = sorted([x for x in cfg["trends"] if x.get("article")],
                 key=lambda x: -x["traffic_num"])
    if not pub:
        return None

    items = []
    for i, x in enumerate(pub, 1):
        x_time = format_time(x.get("published_at") or cfg.get("generated_at"), is_en=is_en, country=country)
        x_href = "{}/".format(entities.slugify(x["title"]))
        items.append(render_trend_card(x, x_href, i, cname, cfg["flag"], x_time, root="../../", is_en=is_en))

    around = []
    all_days_text = "All Days" if is_en else "كل الأيام"
    if prev_day:
        around.append("<a href='../{}/'>← {}</a>".format(prev_day, prev_day))
    around.append("<a href='../archive/'>{}</a>".format(all_days_text))
    if next_day:
        around.append("<a href='../{}/'>{} →</a>".format(next_day, next_day))

    canonical = "{}/{}/{}/".format(BASE, country, day)
    heading = ("{flag} Trending in {name} — {day}" if is_en
               else "{flag} الأكثر بحثًا في {name} — {day}").format(
        flag=cfg["flag"], name=E(cname), day=day)
    meta_topics = ("{} stories" if is_en else "{} خبرًا").format(len(pub))
    body = f"""
    <h1>{heading}</h1>
    <p class="meta">{meta_topics}</p>
    <div class="trends-grid">{''.join(items)}</div>
    <p class="meta nav-days">{' · '.join(around)}</p>"""

    if indexed(country):
        urls.append((canonical, cfg["generated_at"], "0.6"))
    sname = SITE_NAME_EN if is_en else SITE_NAME
    page_title = ("Trending in {} on {} | {}" if is_en
                  else "الأكثر بحثًا في {} يوم {} | {}").format(cname, day, sname)
    page_desc = ("{} stories people searched for in {} on {}." if is_en
                 else "{} خبرًا بحث عنها الناس في {} يوم {}.").format(len(pub), cname, day)
    return page("{}/{}/index.html".format(country, day),
                page_title, page_desc, body, canonical,
                nav=country_nav(country, 2, is_en=is_en), depth=2, is_en=is_en,
                robots=ROBOTS_INDEX if indexed(country) else ROBOTS_NOINDEX)


def build_archive(country, cfg_days, urls):
    """فهرس كل الأيام — الصفحة التي تفتح للزاحف باب الأرشيف كله."""
    is_en = cfg_days[0][1].get("lang") == "en" or country == "world"
    cname = cfg_days[0][1].get("name_en", "Worldwide") if is_en else cfg_days[0][1]["country_name"]
    flag = cfg_days[0][1]["flag"]
    rows = []
    for day, cfg, n in cfg_days:
        if not n:
            continue
        sub_text = ("{} stories" if is_en else "{} خبرًا").format(n)
        rows.append(
            "<a class='item' href='../{d}/'><h3>{d}</h3>"
            "<p class='sub'>{sub}</p></a>".format(d=day, sub=sub_text))

    canonical = "{}/{}/archive/".format(BASE, country)
    heading = ("{flag} {name} Archive" if is_en else "{flag} أرشيف {name}").format(
        flag=flag, name=E(cname))
    lead = ("Every day we tracked, and what people searched for." if is_en
            else "كل يوم رصدناه، وما بحث عنه الناس فيه.")
    body = """
    <h1>{heading}</h1>
    <p class="lead">{lead}</p>
    <div class="list">{rows}</div>""".format(heading=heading, lead=lead, rows="".join(rows))

    if indexed(country):
        urls.append((canonical, datetime.now(timezone.utc).isoformat(), "0.5"))
    page_title = ("{} Archive | {}" if is_en else "أرشيف {} | {}").format(
        cname, SITE_NAME_EN if is_en else SITE_NAME)
    page_desc = ("Daily archive of what people searched for in {}." if is_en
                 else "أرشيف يومي لما بحث عنه الناس في {}.").format(cname)
    return page("{}/archive/index.html".format(country),
                page_title, page_desc, body, canonical,
                nav=country_nav(country, 2, is_en=is_en), depth=2, is_en=is_en,
                robots=ROBOTS_INDEX if indexed(country) else ROBOTS_NOINDEX)


def build_country(country, cfg, urls):
    is_en = cfg.get("lang") == "en" or country == "world"
    cname = cfg.get("name_en", "Worldwide") if is_en else cfg["country_name"]
    day = entities.day_of(cfg)
    clean_trends = dedup.dedup_trends(cfg["trends"], lang=cfg.get("lang", "en" if is_en else "ar"))
    pub = [t for t in clean_trends if t.get("article")]
    pub.sort(key=lambda x: -x["traffic_num"])

    cards = []
    spotlight_html = ""
    if pub:
        top_t = pub[0]
        top_time = format_time(top_t.get("published_at") or cfg.get("generated_at"), is_en=is_en, country=country)
        top_href = "{}/{}/".format(day, entities.slugify(top_t["title"]))
        spotlight_html = render_hero_spotlight(top_t, top_href, cname, cfg["flag"], top_time, root="../", is_en=is_en)
        for i, t in enumerate(pub[1:], 2):
            t_time = format_time(t.get("published_at") or cfg.get("generated_at"), is_en=is_en, country=country)
            t_href = "{}/{}/".format(day, entities.slugify(t["title"]))
            cards.append(render_trend_card(t, t_href, i, cname, cfg["flag"], t_time, root="../", is_en=is_en))

    names = [t["title"] for t in pub[:3]]
    canonical = "{}/{}/".format(BASE, country)
    if is_en:
        intro = "What people are searching for in {} on {}: {}.".format(
            cname, day, ", ".join(names)) if names else ""
        body = f"""
        <h1>{cfg["flag"]} Trending Today in {E(cname)}</h1>
        <p class="lead">{E(intro)}</p>
        <p class="meta">{day} · {len(pub)} stories · <a href="archive/">Archive</a></p>
        {spotlight_html}
        <div class="trends-grid">{''.join(cards)}</div>"""
        page_title = "Trending Today in {} | {}".format(cname, SITE_NAME_EN)
        page_desc = intro or "What people are searching for today in {}.".format(cname)
    else:
        intro = "أكثر ما بحث عنه الناس في {} يوم {}: {}.".format(
            cfg["country_name"], day, "، و".join(names)) if names else ""
        body = f"""
        <h1>{cfg["flag"]} الأكثر بحثًا اليوم في {E(cfg["country_name"])}</h1>
        <p class="lead">{E(intro)} كل خبر بمصادره.</p>
        <p class="meta">{day} · {len(pub)} خبرًا · <a href="archive/">أرشيف الأيام السابقة</a></p>
        {spotlight_html}
        <div class="trends-grid">{''.join(cards)}</div>"""
        page_title = "الأكثر بحثًا اليوم في {} | {}".format(cfg["country_name"], SITE_NAME)
        page_desc = intro or "ما يبحث عنه الناس اليوم في {}، بمصادره.".format(cfg["country_name"])

    if indexed(country):
        urls.append((canonical, cfg["generated_at"], "0.9"))
    return page("{}/index.html".format(country),
                page_title, page_desc, body, canonical,
                nav=country_nav(country, 1, is_en=is_en), depth=1, is_en=is_en,
                robots=ROBOTS_INDEX if indexed(country) else ROBOTS_NOINDEX)


# ── صفحات المواضيع ─────────────────────────────────────────────────
# كل موضوع تكرّر في الأخبار له صفحة تجمع تغطيته كلها. تحل محل صفحات
# الكيانات القديمة (عنوان وجدول من سطر واحد).
MIN_TOPIC_ITEMS = 2          # أقل عدد أخبار لتُبنى صفحة الموضوع
MIN_TOPIC_INDEXED = 3        # أقل عدد لتُفهرس في جوجل


def collect_topics(by_country):
    """كل موضوع ومقالاته المنشورة عبر الأيام، في النسخ العربية المفهرسة."""
    topics = {}
    for key, entries in by_country.items():
        if not has_hubs(key):
            continue
        for day, cfg in entries:
            for t in cfg["trends"]:
                art = t.get("article")
                if not art:
                    continue
                slug = entities.slugify(t["title"])
                tp = topics.setdefault(slug, {"name": t["title"], "items": []})
                tp["items"].append({
                    "country": key, "cname": cfg["country_name"], "flag": cfg["flag"],
                    "day": day, "headline": art["headline"], "summary": art.get("summary", ""),
                    "href": "{}/{}/{}/".format(key, day, slug),
                    "published": t.get("published_at") or cfg["generated_at"],
                    "tags": art.get("tags") or [],
                })
    for tp in topics.values():
        tp["items"].sort(key=lambda x: x["published"], reverse=True)
        # الموقع عربي: عنوان بحث إنجليزي («gulf cup») يُعرض بأول وسم عربي
        if not dedup.is_arabic(tp["name"]):
            tag = next((g for it in tp["items"] for g in it["tags"] if dedup.is_arabic(g)), None)
            if tag:
                tp["name"] = tag
    return topics


def build_topic(slug, tp, urls):
    items = tp["items"]
    latest = items[0]
    canonical = "{}/e/{}/".format(BASE, slug)
    rows = "".join(
        "<li><a href='../../{h}'><span class='t'>{hl}</span>"
        "<span class='d'>{flag} {c} · {day}</span></a></li>".format(
            h=it["href"], hl=E(it["headline"]), flag=it["flag"], c=E(it["cname"]), day=it["day"])
        for it in items)
    body = """
    <nav class="breadcrumb"><a href="../../">الرئيسية</a> › <span>{name}</span></nav>
    <h1>{name}: كل الأخبار</h1>
    <p class="lead">{lead}</p>
    <p class="meta">{n} خبرًا · آخر خبر {last}</p>
    <ul class="topic-list">{rows}</ul>""".format(
        name=E(tp["name"]), lead=E(latest["summary"]), n=len(items), last=latest["day"], rows=rows)
    jsonld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": tp["name"],
        "url": canonical,
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i, "url": BASE + "/" + it["href"]}
            for i, it in enumerate(items, 1)]},
    }
    is_indexed = len(items) >= MIN_TOPIC_INDEXED
    if is_indexed:
        urls.append((canonical, latest["published"], "0.5"))
    return page("e/{}/index.html".format(slug),
                "{} — كل الأخبار | {}".format(tp["name"], SITE_NAME),
                latest["summary"] or "كل أخبار {}".format(tp["name"]),
                body, canonical, nav=country_nav(None, 2), depth=2, jsonld=jsonld,
                robots=ROBOTS_INDEX if is_indexed else ROBOTS_NOINDEX)


STUBS = set()   # مسارات التحويلات المكتوبة في هذا البناء: ليست صفحات حية


def redirect_stub(path, target):
    """تحويل فوري لرابط لم يعد صفحة. جوجل تعامل meta refresh الفوري
    كتحويل دائم. يُستخدم بدل ملف _redirects لأن مطابقة الروابط العربية
    فيه غير مضمونة. لا يكتب فوق صفحة حقيقية أبدًا."""
    full = os.path.join(OUT, path)
    if os.path.exists(full):
        return False
    STUBS.add(os.path.normpath(full))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    t = E(target)
    with open(full, "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
                '<meta name="robots" content="noindex, follow">'
                '<link rel="canonical" href="{t}">'
                '<meta http-equiv="refresh" content="0; url={t}">'
                '<title>{s}</title></head><body><p><a href="{t}">{s}</a></p>'
                '</body></html>'.format(t=t, s=E(SITE_NAME)))
    return True


PUBLISHED = os.path.join(ROOT, "data", "published_urls.json")
DAY_RE = re.compile(r"20\d\d-\d\d-\d\d$")


def keep_published_urls(urls, built, hubs):
    """شبكة أمان: كل رابط ظهر في خريطة الموقع يومًا يبقى صفحة أو تحويلًا.

    حتى 3 أكتوبر 2026 كان 546 رابطًا عرفها جوجل (كانت في الخريطة) ترجع 404:
    مقالات حذفها الكاتب أو الدمج بعد نشرها، وأيام وصفحات مواضيع فرغت من
    المقالات. السجل data/published_urls.json يضم كل رابط دخل الخريطة، وكل
    رابط منه لم يعد صفحة يأخذ تحويلًا لأقرب صفحة حية: الخبر نفسه في يوم
    آخر، ثم صفحة موضوعه، ثم يومه، ثم نسخته. يعمل بعد بناء كل الصفحات
    والتحويلات الأخرى، فلا يكتب فوق صفحة أبدًا (انظر redirect_stub)."""
    known = set()
    if os.path.exists(PUBLISHED):
        with open(PUBLISHED, encoding="utf-8") as f:
            known = set(json.load(f))

    def live(path):
        """صفحة حقيقية — لا تحويل، فلا يشير تحويل إلى تحويل."""
        full = os.path.normpath(os.path.join(OUT, path, "index.html"))
        return os.path.exists(full) and full not in STUBS

    def taken(path):
        return os.path.exists(os.path.join(OUT, path, "index.html"))

    days_of = {}
    for key, day, slug in built:
        days_of.setdefault((key, slug), []).append(day)

    def nearest(key, slug, day):
        ds = days_of.get((key, slug))
        if not ds:
            return None
        ref = datetime.strptime(day, "%Y-%m-%d")
        return min(ds, key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d") - ref).days))

    n = 0
    for u in sorted(known):
        if not u.startswith(BASE + "/"):
            continue
        path = u[len(BASE):].strip("/")
        if not path or "." in path.rsplit("/", 1)[-1] or taken(path):
            continue
        p = path.split("/")
        target = None
        if len(p) == 3 and DAY_RE.match(p[1]):          # مقال
            key, day, slug = p
            near = nearest(key, slug, day)
            if near:
                target = "{}/{}/{}/{}/".format(BASE, key, near, slug)
            elif has_hubs(key) and slug in hubs:
                target = "{}/e/{}/".format(BASE, slug)
            elif live("{}/{}".format(key, day)):
                target = "{}/{}/{}/".format(BASE, key, day)
        elif len(p) == 2 and DAY_RE.match(p[1]):        # يوم فرغ من المقالات
            if live(p[0] + "/archive"):
                target = "{}/{}/archive/".format(BASE, p[0])
        elif len(p) == 2 and p[0] == "e":               # صفحة موضوع لم تعد صفحة
            hits = [(d, k) for (k, s), ds in days_of.items() if s == p[1] for d in ds]
            if hits:
                d, k = max(hits)
                target = "{}/{}/{}/{}/".format(BASE, k, d, p[1])
        if not target:
            target = "{}/{}/".format(BASE, p[0]) if live(p[0]) else BASE + "/"
        if redirect_stub(path + "/index.html", target):
            n += 1

    # السجل للنطاق الحقيقي فقط: بناء تجريبي على عنوان محلي لا يضيف روابطه
    host = BASE.split("//", 1)[-1].split("/", 1)[0]
    if host.startswith(("localhost", "127.")) or host.endswith((".pages.dev", ".workers.dev")):
        return n
    known.update(u for u, *_ in urls)
    with open(PUBLISHED, "w", encoding="utf-8") as f:
        json.dump(sorted(known), f, ensure_ascii=False, indent=0)
    return n


def news_time(t, cfg):
    """وقت آخر نشر حقيقي للخبر: كتابة مقاله أو ظهور الترند، أيهما أحدث.
    published_at وقت أول ظهور للترند في يومه، ومقال النتيجة قد يُكتب بعده
    بساعات («تونس ضد بوتسوانا» ظهر 00:01 ومقال النتيجة كُتب 05:01)."""
    art = t.get("article") or {}
    times = [x for x in (t.get("published_at"), art.get("written_at")) if x]
    return max(times) if times else (cfg.get("generated_at") or "")


def build_home(data, urls):
    # الخبر الأبرز: الأكثر بحثًا الآن في البلدين. والباقي «أحدث الأخبار» فعلًا:
    # من الأحدث نشرًا للأقدم، فيظهر الخبر الجديد أول ما يُنشر (لا حسب حجم البحث)
    pool = [(key, data[key], t) for key in ("eg", "sa") if key in data
            for t in data[key]["trends"] if t.get("article")]
    top = max(pool, key=lambda x: x[2]["traffic_num"], default=None)
    rest = sorted((x for x in pool if x is not top),
                  key=lambda x: news_time(x[2], x[1]), reverse=True)
    mixed = ([top] if top else []) + rest[:17]

    spotlight_html = ""
    news_cards = []
    if mixed:
        first_key, first_cfg, first_t = mixed[0]
        first_time = format_time(news_time(first_t, first_cfg), is_en=False, country=first_key)
        first_href = "{}/{}/{}/".format(first_key, entities.day_of(first_cfg), entities.slugify(first_t["title"]))
        spotlight_html = render_hero_spotlight(
            first_t, first_href, first_cfg["country_name"], first_cfg["flag"], first_time, root="./", is_en=False)
        for i, (key, cfg, t) in enumerate(mixed[1:], 2):
            t_time = format_time(news_time(t, cfg), is_en=False, country=key)
            t_href = "{}/{}/{}/".format(key, entities.day_of(cfg), entities.slugify(t["title"]))
            news_cards.append(render_trend_card(
                t, t_href, i, cfg["country_name"], cfg["flag"], t_time, root="./", is_en=False))

    body = f"""
    <div class="home-head">
      <h1>إيه اللي بيدور عليه الناس دلوقتي؟</h1>
      <p class="lead">أكثر ما يبحث عنه الناس في مصر والسعودية الآن، وكل خبر بمصادره.</p>
    </div>
    {spotlight_html}
    <div class="section-head">
      <h2>أحدث الأخبار</h2>
      <span class="meta">تتحدث كل ربع ساعة</span>
    </div>
    <div class="trends-grid">{"".join(news_cards)}</div>"""

    urls.append((BASE + "/", datetime.now(timezone.utc).isoformat(), "1.0"))
    return page("index.html", "{} — الأكثر بحثًا اليوم في مصر والسعودية".format(SITE_NAME),
                "أكثر ما يبحث عنه الناس الآن في مصر والسعودية، مع كل خبر ومصادره.",
                body, BASE + "/", nav=country_nav(None, 0), depth=0)


CONTACT = config.CONTACT_EMAIL
ED = config.EDITOR_NAME

# صفحات ثابتة — يطمئن إليها القارئ ومراجع AdSense: من يقف خلف الموقع،
# وكيف يعمل، وكيف يُتواصل معه.
PAGES = [
    ("about", "من نحن", "من يقف خلف الترندات وكيف يعمل.", f"""
    <h1>من نحن</h1>
    <p class="lead">الترندات موقع عربي مستقل يرصد ما يبحث عنه الناس في مصر والسعودية، ويكتب الخبر وراء كل موضوع بمصادره.</p>
    <article>
      <p>نبدأ من قوائم الأكثر بحثًا التي تنشرها Google لكل بلد، ونقرأ ما نشرته الصحف حول كل موضوع، ثم نكتب خبرًا عربيًا يجيب عما يبحث عنه القارئ، وننسب كل معلومة إلى مصدرها ونضع رابطه.</p>
      <p>يحرر الموقع <a href="../{config.EDITOR_PATH}/">{ED}</a>. نستخدم أدوات ذكاء اصطناعي في جمع المصادر وكتابة المسودة الأولى، ويراجع المحرر أهم الأخبار يوميًا. التفاصيل الكاملة في <a href="../editorial-policy/">سياسة التحرير</a>.</p>
      <p>وحين يكون الموضوع رقمًا يبحث عنه القارئ، مثل مواقيت الصلاة أو سعر صرف، نحضر الرقم من جهته الرسمية ونعرضه في جدول.</p>
      <h2>ما لا ننشره</h2>
      <p>لا ننشر تلقائيًا أي موضوع عن وفاة أو حادث أو جريمة أو قضية منظورة أو مرض، ولا موضوعًا ليس له مصدران صحفيان على الأقل، ولا نكتب عن فرد عادي أو قاصر.</p>
      <h2>تصحيح الأخطاء</h2>
      <p>إن وجدت خطأً فراسلنا على <strong>{CONTACT}</strong>، وسنصحّحه أو نزيل الصفحة.</p>
    </article>"""),

    ("privacy", "سياسة الخصوصية", "كيف نتعامل مع بياناتك.", f"""
    <h1>سياسة الخصوصية</h1>
    <p class="lead">لا نطلب منك تسجيل دخول، ولا نجمع اسمك أو بريدك.</p>
    <article>
      <h2>الإحصاءات</h2>
      <p>نستخدم إحصاءات مجمّعة عن الصفحات الأكثر قراءة (Cloudflare Web Analytics)، ولا تعرّف هذه الإحصاءات أي زائر بعينه.</p>
      <h2>الإشعارات</h2>
      <p>إن فعّلت إشعارات المتصفح، تحفظ خدمة OneSignal معرّفًا لجهازك لإرسال الإشعارات فقط. يمكنك إيقافها في أي وقت من إعدادات المتصفح.</p>
      <h2>ملفات تعريف الارتباط والإعلانات</h2>
      <p>قد يعرض الموقع إعلانات عبر شبكات خارجية منها Google AdSense، وتستخدم هذه الشبكات ملفات تعريف ارتباط لعرض إعلانات تناسب اهتماماتك بناءً على زياراتك لهذا الموقع ولمواقع أخرى.</p>
      <p>يمكنك تعطيل الإعلانات المخصصة من <a href="https://www.google.com/settings/ads" rel="nofollow noopener" target="_blank">إعدادات إعلانات Google</a>، أو منع ملفات تعريف الارتباط من إعدادات متصفحك.</p>
      <h2>أداة صور الجواز والتأشيرة</h2>
      <p>الصورة التي تختارها في <a href="../passport-photo/">أداة صور الجواز</a> تُعالَج داخل متصفحك ولا تُرفع إلى خوادمنا ولا نحتفظ بها. يحمّل المتصفح مكتبات المعالجة ونماذجها فقط من خدمات jsDelivr وGoogle وHugging Face، وهذه الخدمات ترى عنوان IP كأي طلب تحميل، ولا تصلها صورتك.</p>
      <h2>الروابط الخارجية</h2>
      <p>نضع روابط إلى الصحف التي نقلنا عنها، ولا نتحكم في سياسات تلك المواقع.</p>
      <h2>الأطفال</h2>
      <p>الموقع غير موجّه لمن هم دون 13 عامًا، ولا نجمع بيانات عنهم عن قصد.</p>
      <h2>التواصل</h2>
      <p>لأي سؤال عن الخصوصية: <strong>{CONTACT}</strong></p>
    </article>"""),

    ("contact", "اتصل بنا", "للتصحيح أو الإعلان أو الاستفسار.", f"""
    <h1>اتصل بنا</h1>
    <p class="lead">نقرأ كل رسالة، ونرد على بلاغات التصحيح أولًا.</p>
    <article>
      <p>راسلنا على: <strong>{CONTACT}</strong></p>
      <ul>
        <li>تصحيح معلومة أو نسبتها إلى مصدرها</li>
        <li>طلب إزالة صفحة أو الاعتراض على محتواها</li>
        <li>الإبلاغ عن إعلان وظيفة مشبوه</li>
        <li>الإعلان على الموقع</li>
      </ul>
      <p>بلاغات التصحيح والإزالة لها أولوية، ونتعامل معها خلال أيام قليلة.</p>
    </article>"""),

    (config.EDITOR_PATH, ED, "محرر موقع الترندات.", f"""
    <h1>{ED}</h1>
    <p class="lead">محرر موقع الترندات.</p>
    <article>
      <p>يتابع {ED} ما يبحث عنه الناس في مصر والسعودية يوميًا، ويشرف على الأخبار المنشورة في الموقع: اختيار الموضوعات، ومراجعة أهم الأخبار، وتصحيح الأخطاء التي يبلّغ عنها القراء.</p>
      <p>تُكتب المسودات الأولى بمساعدة أدوات ذكاء اصطناعي من المصادر الصحفية المذكورة في كل خبر، وفق <a href="../editorial-policy/">سياسة التحرير</a>.</p>
      <p>للتواصل مع المحرر: <strong>{CONTACT}</strong></p>
    </article>"""),

    ("editorial-policy", "سياسة التحرير", "كيف نختار الأخبار ونكتبها ونصححها.", f"""
    <h1>سياسة التحرير</h1>
    <p class="lead">كيف نختار ما نكتب عنه، وكيف نكتبه، وكيف نصحح أخطاءنا.</p>
    <article>
      <h2>اختيار الموضوعات</h2>
      <p>نبدأ من قوائم الأكثر بحثًا في Google لكل بلد. لا نكتب عن موضوع إلا إن كان حجم البحث عنه كبيرًا، وله مصدران صحفيان حقيقيان على الأقل.</p>
      <h2>الكتابة</h2>
      <ul>
        <li>نكتب الخبر نفسه في أول سطر: ماذا حدث، ومتى، وأين.</li>
        <li>كل معلومة منسوبة إلى مصدرها بالاسم، وروابط المصادر أسفل كل خبر.</li>
        <li>لا عناوين مبالغ فيها، ولا معلومات غير موجودة في المصادر.</li>
        <li>تُكتب المسودة الأولى بمساعدة أدوات ذكاء اصطناعي تقرأ نص المصادر، ثم تُفحص آليًا، ويراجع المحرر أهم الأخبار يوميًا.</li>
      </ul>
      <h2>ما لا ننشره</h2>
      <p>الوفيات والحوادث والجرائم والقضايا المنظورة والأمراض، والأفراد العاديون والقاصرون، والشائعات التي لا تؤكدها أو تنفيها جهة رسمية.</p>
      <h2>الصور</h2>
      <p>لا ننشر صور الصحف. صور الموقع كروت نصممها بأنفسنا.</p>
      <h2>التحديث والتصحيح</h2>
      <p>حين تتطور قصة نحدّث الخبر على الرابط نفسه ونذكر وقت آخر تحديث. وإن وجدت خطأً فراسلنا على <strong>{CONTACT}</strong>.</p>
      <h2>الوظائف والهجرة</h2>
      <p>أدلة الوظائف والهجرة مكتوبة من المواقع الرسمية للجهات، مع روابطها. لا ننشر وظيفة إلا بإعلان رسمي، ولا نتقاضى أي رسوم، ولا نتوسط في التوظيف. اقرأ <a href="../jobs/verification/">كيف نتحقق من الوظائف</a>.</p>
    </article>"""),

    ("terms", "شروط الاستخدام", "شروط استخدام موقع الترندات.", f"""
    <h1>شروط الاستخدام</h1>
    <article>
      <h2>المحتوى</h2>
      <p>ما ننشره للمعرفة العامة. نبذل جهدنا ليكون دقيقًا ومنسوبًا إلى مصادره، لكننا لا نضمن خلوه من الأخطاء، ولا يغني عن الرجوع إلى الجهات الرسمية في القرارات المهمة، مثل التقديم على وظيفة أو تأشيرة أو قرار مالي.</p>
      <h2>الروابط الخارجية</h2>
      <p>نضع روابط لمواقع أخرى للمصدر والمرجع، ولا نتحمل مسؤولية محتواها أو سياساتها.</p>
      <h2>الملكية</h2>
      <p>نصوص الموقع وكروته ملك للموقع. يمكنك الاقتباس مع ذكر المصدر ورابطه.</p>
      <h2>التعديل</h2>
      <p>قد نحدّث هذه الشروط، وتسري النسخة المنشورة هنا.</p>
      <p>للتواصل: <strong>{CONTACT}</strong></p>
    </article>"""),
]


def build_static(urls):
    for slug, title, desc, body in PAGES:
        canonical = "{}/{}/".format(BASE, slug)
        jsonld = None
        if slug == config.EDITOR_PATH:
            jsonld = {"@context": "https://schema.org", "@type": "ProfilePage",
                      "mainEntity": {"@type": "Person", "name": config.EDITOR_NAME,
                                     "jobTitle": "محرر", "worksFor": {"@type": "Organization",
                                                                    "name": SITE_NAME, "url": BASE}}}
        page("{}/index.html".format(slug), "{} | {}".format(title, SITE_NAME), desc,
             body, canonical, nav=country_nav(None, 1), depth=1, jsonld=jsonld)
        urls.append((canonical, datetime.now(timezone.utc).isoformat(), "0.3"))


FAQ = [
    ("ما هو موقع الترندات؟",
     "موقع عربي يرصد ما يبحث عنه الناس في مصر والسعودية، ويكتب الخبر وراء كل موضوع مع روابط مصادره."),
    ("من أين تأتي الموضوعات؟",
     "من قوائم الأكثر بحثًا التي تنشرها Google لكل بلد. ونكتب فقط عن الموضوعات التي حجم البحث عنها كبير ولها مصدران صحفيان على الأقل."),
    ("هل تستخدمون الذكاء الاصطناعي؟",
     "نعم في جمع المصادر وكتابة المسودة الأولى من نص الأخبار نفسها، ثم تُفحص المسودة آليًا، ويراجع المحرر أهم الأخبار يوميًا. التفاصيل في سياسة التحرير."),
    ("كيف أبلغ عن خطأ؟",
     "راسلنا على " + config.CONTACT_EMAIL + " مع رابط الصفحة، وسنصحح الخطأ أو نزيل الصفحة."),
    ("هل تنشرون إعلانات وظائف؟",
     "ننشر أدلة للتقديم على وظائف الجهات الرسمية وتأشيرات العمل، مع روابط مواقعها الرسمية. لا نتقاضى أي رسوم ولا نتوسط في التوظيف."),
    ("ما علاقة الموقع بتطبيق Goldex؟",
     "Goldex تطبيق لأسعار الذهب والعملات من نفس صاحب الموقع، ويعرض أخبار الاقتصاد والسياسة المنشورة هنا."),
]


def build_faq_page(urls):
    canonical = "{}/faq/".format(BASE)
    items = "".join("<div class='faq-item'><h2>{}</h2><p>{}</p></div>".format(E(q), E(a)) for q, a in FAQ)
    body = """
    <h1>الأسئلة الشائعة</h1>
    <p class="lead">إجابات مختصرة عن الموقع وطريقة عمله.</p>
    <div class="faq-list">{}</div>
    <p class="meta">التفاصيل الكاملة في <a href="../editorial-policy/">سياسة التحرير</a>.</p>""".format(items)
    page("faq/index.html", "الأسئلة الشائعة | " + SITE_NAME,
         "إجابات مختصرة عن موقع الترندات: مصادر الأخبار، واستخدام الذكاء الاصطناعي، والتصحيح.",
         body, canonical, nav=country_nav(None, 1), depth=1)
    urls.append((canonical, datetime.now(timezone.utc).isoformat(), "0.3"))


GOLDEX_PLAY = "https://play.google.com/store/apps/details?id=com.aurex.markets"


def build_gold_app_page(urls):
    """صفحة تطبيق Goldex. بلا تقييمات مكتوبة في البيانات المنظمة: جوجل لا
    تسمح بنقل تقييمات موقع آخر، والتقييم الحقيقي على صفحة المتجر."""
    canonical = "{}/gold-app/".format(BASE)
    schema = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Goldex - أسعار الذهب والعملات",
        "operatingSystem": "Android",
        "applicationCategory": "FinanceApplication",
        "installUrl": GOLDEX_PLAY,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }
    features = [
        ("🪙 أسعار الذهب", "عيار 24 و21 و18 والجنيه الذهب وسعر الأوقية في مصر والسعودية والدول العربية."),
        ("⚖️ حاسبة المصنعية", "احسب المصنعية والدمغة قبل الشراء، وقارن بين عروض المحلات."),
        ("💼 محفظة الذهب", "سجّل مشترياتك من الذهب والسبائك، وتابع قيمتها مع تغيّر السعر."),
        ("💵 أسعار العملات", "الدولار واليورو والريال والدرهم والدينار، مع التحويل بينها."),
        ("🔔 تنبيهات الأسعار", "حدد السعر الذي تنتظره، ويصلك إشعار عند وصول السوق إليه."),
    ]
    cards = "".join("<div class='goldex-feat-card'><h4>{}</h4><p>{}</p></div>".format(E(a), E(b))
                    for a, b in features)
    body = f"""
    <div class="goldex-container">
      <div class="goldex-hero-header">
        <img class="goldex-logo-img" src="../goldex-logo.png" alt="شعار تطبيق Goldex" width="96" height="96">
        <div>
          <h1 class="goldex-brand-title">تطبيق <span>Goldex</span></h1>
          <p class="lead" style="margin:0">أسعار الذهب والفضة والعملات، وحاسبة المصنعية، وتنبيهات الأسعار على هاتفك.</p>
        </div>
      </div>
      <div class="goldex-features-grid">{cards}</div>
      <div class="goldex-cta-banner">
        <p>التطبيق مجاني على Google Play لهواتف أندرويد، وتقييمات المستخدمين منشورة على صفحته في المتجر.</p>
        <a class="btn-play-store" href="{GOLDEX_PLAY}" target="_blank" rel="noopener">صفحة التطبيق على Google Play</a>
      </div>
    </div>"""
    page("gold-app/index.html",
         "تطبيق Goldex لأسعار الذهب والعملات | " + SITE_NAME,
         "Goldex تطبيق أندرويد مجاني لأسعار الذهب والعملات، مع حاسبة المصنعية ومحفظة الذهب وتنبيهات الأسعار.",
         body, canonical, nav=country_nav(None, 1), depth=1, jsonld=schema)
    urls.append((canonical, datetime.now(timezone.utc).isoformat(), "0.5"))


def build_en_redirect():
    """توجيه /en/ إلى النسخة الإنجليزية (/world/): تحويل 301 من Cloudflare
    عبر ملف _redirects، وهذه الصفحة احتياط لو لم يُقرأ الملف."""
    with open(os.path.join(OUT, "_redirects"), "w", encoding="utf-8") as f:
        f.write("/en /world/ 301\n/en/ /world/ 301\n")
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={BASE}/world/">
<link rel="canonical" href="{BASE}/world/">
<title>ALTRENDAT English</title>
</head>
<body><p><a href="{BASE}/world/">ALTRENDAT English</a></p></body>
</html>"""
    en_dir = os.path.join(OUT, "en")
    os.makedirs(en_dir, exist_ok=True)
    with open(os.path.join(en_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(doc)


def build_404():
    """صفحة الخطأ — يخدمها Cloudflare لأي رابط غير موجود."""
    body = """
    <h1>الصفحة غير موجودة</h1>
    <p class="lead">ربما تغيّر الرابط، أو لم يعد هذا الموضوع منشورًا.</p>
    <p class="meta"><a href="/">← الصفحة الرئيسة</a></p>"""
    page("404.html", "الصفحة غير موجودة | " + SITE_NAME, "", body,
         BASE + "/404.html", nav="", depth=0, robots=ROBOTS_NOINDEX)


def build_feed(pairs, english=False):
    """خلاصة RSS لأحدث 40 خبرًا من النسخ المفهرسة، عبر كل الأيام.
    العربية في /feed.xml، والإنجليزية (النسخة العالمية) في /world/feed.xml.
    pairs: [(بلد, بيانات يوم), ...]"""
    items = []
    for key, cfg in pairs:
        if not indexed(key) or (key == "world") != english:
            continue
        for t in cfg["trends"]:
            art = t.get("article")
            if art:
                items.append((t.get("published_at") or cfg["generated_at"], key, cfg, t, art))
    items.sort(key=lambda x: x[0], reverse=True)

    body = []
    for pub, key, cfg, t, art in items[:40]:
        link = "{}/{}/{}/{}/".format(BASE, key, entities.day_of(cfg), entities.slugify(t["title"]))
        img = ""
        photo = art.get("photo") or {}
        if photo.get("url"):
            img = '<enclosure url="{}" type="image/jpeg"/>'.format(E(photo["url"]))
        elif t.get("card"):
            img = '<enclosure url="{}/cards/{}" type="image/png"/>'.format(BASE, os.path.basename(t["card"]))
        cat = CAT_EN.get(t["category"], t["category"]) if english else t["category"]
        # تاريخ النشر بصيغة RSS: به يعرف القارئ الآلي الجديد من القديم
        try:
            when = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            pub_date = "<pubDate>{}</pubDate>".format(format_datetime(when))
        except Exception:
            pub_date = ""
        body.append(
            "<item><title>{t}</title><link>{l}</link><guid>{l}</guid>{p}"
            "<description>{d}</description><category>{c}</category>{img}</item>".format(
                t=E(art["headline"]), l=E(link), p=pub_date, d=E(art.get("summary", "")),
                c=E(cat), img=img))

    if english:
        title, home, desc, lang, path = (SITE_NAME_EN, BASE + "/world/",
                                         "What the world is searching for, explained with sources",
                                         "en", os.path.join(OUT, "world", "feed.xml"))
    else:
        title, home, desc, lang, path = (SITE_NAME, BASE + "/",
                                         "ما يبحث عنه الناس في مصر والسعودية",
                                         "ar", os.path.join(OUT, "feed.xml"))
    # rel="hub": مركز WebSub الذي يُخطَر عند كل تحديث (engine/indexnow.py)، وهو
    # طريق جوجل المعتمد لاكتشاف جديد الخلاصات بسرعة. rel="self": عنوان الخلاصة.
    self_url = home + "feed.xml"
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
           '<title>{s}</title><link>{h}</link>'
           '<description>{d}</description>'
           '<language>{lang}</language>'
           '<atom:link href="{self}" rel="self" type="application/rss+xml"/>'
           '<atom:link href="{hub}" rel="hub"/>'
           '{items}</channel></rss>').format(
        s=E(title), h=home, d=E(desc), lang=lang, self=self_url, hub=WEBSUB_HUB,
        items="".join(body))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return len(body)


def build_sitemaps(urls, news):
    """خريطة الموقع (الصفحات المفهرسة فقط)، وخريطة الأخبار لآخر 48 ساعة."""
    seen, rows = set(), []
    for loc, mod, pri in urls:
        if loc in seen:
            continue
        seen.add(loc)
        rows.append("  <url><loc>{}</loc><lastmod>{}</lastmod><priority>{}</priority></url>".format(
            E(loc), E((mod or "")[:10]), pri))
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                "\n".join(rows) + "\n</urlset>\n")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    fresh = []
    for n in news:
        try:
            when = datetime.fromisoformat(n["published"].replace("Z", "+00:00"))
        except Exception:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= cutoff:
            fresh.append((when, n))
    fresh.sort(key=lambda x: x[0], reverse=True)
    items = []
    for when, n in fresh[:1000]:
        items.append(
            "  <url><loc>{loc}</loc><news:news><news:publication><news:name>{name}</news:name>"
            "<news:language>{lang}</news:language></news:publication>"
            "<news:publication_date>{d}</news:publication_date><news:title>{t}</news:title>"
            "</news:news></url>".format(
                loc=E(n["loc"]), name=E(SITE_NAME), lang=n["lang"],
                d=when.isoformat(timespec="seconds"), t=E(n["title"])))
    with open(os.path.join(OUT, "sitemap-news.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n' +
                "\n".join(items) + "\n</urlset>\n")

    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\n"
                "Sitemap: {b}/sitemap.xml\nSitemap: {b}/sitemap-news.xml\n".format(b=BASE))
    return len(rows), len(items)


# بلد الخبر من كلماته، لا من النسخة التي رصدته (photos.story_country): بوت
# الإشعارات يوجّه الخبر المحلي لمشتركي بلده (حقل about).
story_country = photos.story_country


def gold_news_image(t, art, is_en):
    """صورة الخبر للتطبيق والإشعار: الصورة الحقيقية (مقاسان) مع حقوقها، وإلا الكارت.
    حقوق الصورة مكتوبة أيضًا في صفحة الخبر التي يفتحها الإشعار (رابطها sourceUrl)،
    وهذا ما تسمح به رخص المشاع الإبداعي حين لا يتسع المكان لسطر المصدر."""
    photo = art.get("photo") or {}
    url = photo.get("url")
    if not url:
        card = (BASE + "/cards/" + os.path.basename(t["card"])) if t.get("card") \
            else (BASE + "/og-default.jpg")
        return {"image": card, "thumb": card}
    thumb = url.replace("/1280px-", "/500px-") if "/1280px-" in url else url
    if photo.get("ai"):
        return {"image": url, "thumb": thumb, "imageCredit":
                "AI-generated image" if is_en else "صورة مولّدة بالذكاء الاصطناعي"}
    credit = "{} {} · {} · {}".format(
        "Photo:" if is_en else "تصوير:", photo.get("artist", ""), photo.get("license", ""),
        "Wikimedia Commons" if is_en else "ويكيميديا كومنز")
    if photo.get("stock"):
        credit = ("Illustrative photo · " if is_en else "صورة تعبيرية · ") + credit
    return {"image": url, "thumb": thumb, "imageCredit": credit,
            "imageCreditUrl": photo.get("file_page", "")}


def build_gold_news_api(days_dict):
    """يصدر خلاصة الأخبار السياسية والاقتصادية والمؤثرة على الذهب بصيغة JSON نظيفة لتطبيق الذهب مع أولوية قصوى للسياسة."""
    def is_ar_text(txt):
        return any("\u0600" <= c <= "\u06FF" for c in (txt or ""))

    gold_feed = []
    seen = set()
    items_to_check = []
    if all(isinstance(k, tuple) for k in days_dict.keys()):
        sorted_keys = sorted(days_dict.keys(), key=lambda x: x[1], reverse=True)
        for (key, day) in sorted_keys:
            items_to_check.append((key, day, days_dict[(key, day)]))
    else:
        for key, cfg in days_dict.items():
            day = entities.day_of(cfg)
            items_to_check.append((key, day, cfg))

    for key, day, cfg in items_to_check:
        cname = cfg.get("country_name", key)
        flag = cfg.get("flag", "")
        for t in cfg.get("trends", []):
            art = t.get("article")
            if not art:
                continue
            cat = t.get("category", "")
            if cat in ("رياضة", "فن ومشاهير", "طقس", "أبراج وفلك", "فضول عام"):
                continue
            title_text = (t.get("title", "") + " " + art.get("headline", "") + " " + art.get("body", "")).lower()
            
            is_politics = cat == "سياسة" or any(k in title_text for k in [
                "سياس", "حكوم", "برلمان", "مجلس الأمن", "انتخاب", "قمة", "عقوبات", "وزير", "رئيس",
                "دبلوماس", "مفاوض", "معاهدة", "هدنة", "حرب", "جيش", "قوات", "غارة", "استخبارات",
                "politics", "president", "election", "biden", "trump", "white house", "congress",
                "senate", "parliament", "summit", "sanctions", "ballot", "voter", "truce", "military"
            ])
            is_gold = any(k in title_text for k in ["ذهب", "عيار", "سبائك", "أوقية", "صاغة", "gold", "bullion", "karat"])
            is_silver = any(k in title_text for k in ["فضة", "silver"])
            is_econ = cat == "اقتصاد" or any(k in title_text for k in [
                "اقتصاد", "دولار", "جنيه", "ريال", "فائدة", "تضخم", "مركزي", "صندوق النقد", "بريكس",
                "سويس", "بحر أحمر", "نفط", "أوبك", "سندات", "بورصة", "أسهم", "رواتب", "معاش",
                "dollar", "fed", "inflation", "currency", "oil", "opec", "market", "economy", "central bank", "stocks"
            ])
            if not (is_politics or is_gold or is_silver or is_econ):
                continue

            slug = entities.slugify(t["title"])
            uid = f"{key}-{slug}"
            if uid in seen:
                continue
            seen.add(uid)

            pub_time = t.get("published_at") or cfg.get("generated_at") or datetime.now(timezone.utc).isoformat()
            
            # حساب الأولوية: السياسة رقم 1 دائماً (طلب صاحب التطبيق)، تليها أخبار الذهب، ثم الفضة، ثم الاقتصاد
            if is_politics:
                cat_key = "cat_politics"
                icon = "🏛️"
                impact = "breaking"
                prio = 3000000000
            elif is_gold:
                cat_key = "cat_gold"
                icon = "🥇"
                impact = "bullish" if any(w in title_text for w in ["ارتفاع", "صعود", "مكاسب", "surge", "rise", "gain"]) else "neutral"
                prio = 2000000000
            elif is_silver:
                cat_key = "cat_silver"
                icon = "🥈"
                impact = "neutral"
                prio = 1500000000
            else:
                cat_key = "cat_fed"
                icon = "📈"
                impact = "bearish" if any(w in title_text for w in ["هبوط", "تراجع", "انخفاض", "خسائر", "drop", "fall"]) else "neutral"
                prio = 1000000000

            try:
                ts = int(datetime.fromisoformat(pub_time.replace("Z", "+00:00")).timestamp())
            except Exception:
                ts = 0

            canonical = f"{BASE}/{key}/{day}/{slug}/"
            headline = art.get("headline") or t.get("title", "")
            is_ar = is_ar_text(t.get("title", "")) or is_ar_text(headline)
            is_en = not is_ar
            # صورة الخبر الحقيقية (حرة الرخصة) لا صور الصحف، وإلا كارت الموقع
            img = gold_news_image(t, art, is_en)
            img_url = img["image"]
            # بلد الخبر من كلماته (للإشعار المحلي)؛ النسخة الإنجليزية بلا بلد
            about = story_country(headline, art.get("summary", ""),
                                  " ".join(art.get("tags") or [])) if key in ("eg", "sa") else ""

            gold_feed.append({
                "id": f"{key}-{day}-{slug}",
                "title": headline,
                "detail": art.get("summary") or ((art.get("body", "")[:280] + "...") if art.get("body") else headline),
                "categoryKey": cat_key,
                "category": cat or ("سياسة" if is_politics else "اقتصاد"),
                "publishedAt": pub_time,
                "published_at": pub_time,
                "impact": impact,
                "icon": icon,
                "source": f"التريندات • {cname}" if not is_en else f"Altrendat • {cname}",
                "sourceUrl": canonical,
                "url": canonical,
                "image": img_url,
                "thumb": img["thumb"],
                "imageCredit": img.get("imageCredit", ""),
                "imageCreditUrl": img.get("imageCreditUrl", ""),
                "country": key,
                "about": about,
                "country_name": cname,
                "flag": flag,
                "lang": "en" if is_en else "ar",
                "traffic": t.get("traffic", ""),
                "sources": [n["source"] for n in t.get("news", []) if n.get("source")],
                "_prio": prio + ts
            })

    # يوم الإثنين: إدراج خبر استئناف تداولات سوق الذهب والبورصات العالمية بعد العطلة الأسبوعية
    now_utc = datetime.now(timezone.utc)
    if now_utc.weekday() == 0:
        day_str = now_utc.strftime("%Y-%m-%d")
        monday_ar = {
            "id": f"monday-gold-market-{day_str}-ar",
            "title": "استئناف تداولات سوق الذهب والبورصات العالمية مع افتتاح تعاملات الإثنين",
            "detail": "عادت البورصات العالمية وأسواق تداول الذهب والمعادن الثمينة للعمل صباح اليوم الإثنين بعد العطلة الأسبوعية، وسط ترقب المستثمرين لمؤشرات التضخم وحركة الدولار وأسعار الفائدة العالمية.",
            "categoryKey": "cat_gold",
            "category": "اقتصاد",
            "publishedAt": now_utc.isoformat(),
            "published_at": now_utc.isoformat(),
            "impact": "bullish",
            "icon": "🪙",
            "source": "التريندات • أسواق الذهب",
            "sourceUrl": f"{BASE}/gold-app/",
            "url": f"{BASE}/gold-app/",
            "image": f"{BASE}/og-default.jpg",
            "country": "world",
            "country_name": "العالم",
            "flag": "🌍",
            "lang": "ar",
            "traffic": "تداول عالمي",
            "sources": ["التريندات", "بورصات المعادن العالمية"],
            "_prio": 4000000000 + int(now_utc.timestamp())
        }
        monday_en = {
            "id": f"monday-gold-market-{day_str}-en",
            "title": "Global Gold & Commodity Markets Resume Trading as Monday Sessions Kick Off",
            "detail": "International bullion and commodity exchanges have reopened this Monday morning following the weekend pause, as traders closely monitor interest rate outlooks, currency movements, and central bank signals.",
            "categoryKey": "cat_gold",
            "category": "Finance",
            "publishedAt": now_utc.isoformat(),
            "published_at": now_utc.isoformat(),
            "impact": "bullish",
            "icon": "🪙",
            "source": "Altrendat • Gold Markets",
            "sourceUrl": f"{BASE}/gold-app/",
            "url": f"{BASE}/gold-app/",
            "image": f"{BASE}/og-default.jpg",
            "country": "world",
            "country_name": "Worldwide",
            "flag": "🌍",
            "lang": "en",
            "traffic": "Global Trading",
            "sources": ["Altrendat", "Global Bullion Exchanges"],
            "_prio": 4000000000 + int(now_utc.timestamp())
        }
        gold_feed.append(monday_ar)
        gold_feed.append(monday_en)

    # ترتيب نهائي: الأخبار السياسية أولاً، ثم الأحدث فالأحدث
    gold_feed.sort(key=lambda x: x["_prio"], reverse=True)
    for item in gold_feed:
        item.pop("_prio", None)

    # الاحتفاظ بـ 15 خبر فقط كما كان الأصل دون زيادة حجم الملف أو التأثير على الموقع
    gold_feed = gold_feed[:15]

    out_file = os.path.join(OUT, "gold-news.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(gold_feed),
            "items": gold_feed
        }, f, ensure_ascii=False, indent=2)
    return len(gold_feed)


def build_trends_feed(days_dict, hours=48, limit=60):
    """trends-feed.json: كل أخبار آخر hours ساعة من كل الفئات، لإشعارات Goldex فقط.

    gold-news.json يبقى سياسة واقتصاد وذهب (هو شاشة الأخبار في التطبيق). أما
    الإشعار فيُرسل الأقوى بحثًا أيًّا كانت فئته، رياضة أو فن (قرار صاحب التطبيق
    2026-10-01)، فيقرأ البوت الملفين ويختار. نفس شكل عناصر gold-news.json، فلا
    يتغير شيء في قراءة البوت، ومعها traffic للترتيب.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    items, seen = [], set()
    for (key, day), cfg in days_dict.items():
        cname = cfg.get("country_name", key)
        is_en = key == "world" or cfg.get("lang") == "en"
        for t in cfg.get("trends", []):
            art = t.get("article")
            if not art or not art.get("body"):
                continue
            pub = news_time(t, cfg)
            try:
                when = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                continue
            if when < cutoff:
                continue
            slug = entities.slugify(t["title"])
            if (key, slug) in seen:
                continue
            seen.add((key, slug))
            headline = art.get("headline") or t.get("title", "")
            img = gold_news_image(t, art, is_en)
            canonical = f"{BASE}/{key}/{day}/{slug}/"
            items.append({
                "id": f"{key}-{day}-{slug}",
                "title": headline,
                "detail": art.get("summary") or headline,
                "categoryKey": "cat_trend",
                "category": t.get("category", ""),
                "icon": t.get("icon", "🔥"),
                "publishedAt": pub,
                "source": f"Altrendat • {cname}" if is_en else f"التريندات • {cname}",
                "sourceUrl": canonical,
                "url": canonical,
                "image": img["image"],
                "thumb": img["thumb"],
                "country": key,
                "about": "" if is_en else story_country(headline, art.get("summary", ""),
                                                        " ".join(art.get("tags") or [])),
                "lang": "en" if is_en else "ar",
                "traffic": t.get("traffic", ""),
            })
    items.sort(key=lambda x: x["publishedAt"], reverse=True)
    items = items[:limit]
    with open(os.path.join(OUT, "trends-feed.json"), "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(),
                   "total": len(items), "items": items}, f, ensure_ascii=False, indent=2)
    return len(items)


COUNTRIES = {}


def load_pruned():
    """المقالات المحذوفة لضعفها (انظر prune.py) — لكل منها تحويل."""
    path = os.path.join(ROOT, "data", "pruned.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def main():
    global BASE, COUNTRIES
    if len(sys.argv) > 1:
        BASE = sys.argv[1].rstrip("/")

    with open(os.path.join(ROOT, "data", "trends.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(ROOT, "engine", "countries.json"), encoding="utf-8") as f:
        c_defs = json.load(f)
        rank = {k: i for i, k in enumerate(c_defs)}

    archive_today(data)

    # كل يوم مؤرشف يُبنى: صفحة الأمس تبقى على رابطها.
    enabled_keys = {k for k, cfg in c_defs.items() if cfg.get("enabled")}
    days = load_days()
    by_country = {}
    for (key, day), cfg in days.items():
        if key not in enabled_keys:
            continue
        by_country.setdefault(key, []).append((day, cfg))
    for entries in by_country.values():
        entries.sort(key=lambda x: x[0], reverse=True)

    # مقال لم تصله photos.py يأخذ صورة تعبيرية إن طابق موضوعها كلماته
    # (بلا اتصال بالشبكة)، وإلا يُعرض كارت الموقع مكانها — لا صورة غريبة.
    for key, entries in by_country.items():
        for _, cfg in entries:
            for t in cfg["trends"]:
                art = t.get("article")
                if art and not art.get("photo"):
                    art["photo"] = photos.stock_photo(t["title"], t.get("category", ""), key,
                                                      photos.photo_text(art))

    # الصفحة الرئيسة وصفحات البلاد تُبنى من أحدث يوم مؤرشف لكل بلد،
    # فلا يسقط بلد من الموقع بسبب تشغيلة فشل فيها جلبه.
    #
    # وأحدث يوم "بمحتوى" لا أحدث يوم بالتقويم: النسخة العالمية تُنشر
    # فيها سياسة واقتصاد فقط (WORLD_CATEGORIES)، فأول تشغيلات اليوم قد
    # تمر بصفر مقالات قبل أن يظهر خبر يطابق الشرط. لولا هذا السقوط إلى
    # آخر يوم فيه مقالات، كانت الرئيسة وتبويب Worldwide يعرضان "0
    # أخبار اليوم" لساعات كل صباح رغم وجود أخبار أمس الحقيقية.
    def _has_articles(cfg):
        return any(t.get("article") for t in cfg["trends"])

    latest = {}
    for k in sorted(by_country, key=lambda k: rank.get(k, len(rank))):
        entries = by_country[k]
        day_with_content = next((c for _, c in entries if _has_articles(c)), None)
        latest[k] = day_with_content if day_with_content else entries[0][1]
    COUNTRIES = {k: {
        "flag": v["flag"],
        "name_ar": c_defs.get(k, {}).get("name_ar", v["country_name"]),
        "name_en": c_defs.get(k, {}).get("name_en", v.get("name_en", v["country_name"])),
        "lang": c_defs.get(k, {}).get("lang", v.get("lang", "ar")),
    } for k, v in latest.items()}

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    keyfile = os.path.join(ROOT, "data", "indexnow_key.txt")
    if os.path.exists(keyfile):
        with open(keyfile, encoding="utf-8") as kf:
            k = kf.read().strip()
            if k:
                with open(os.path.join(OUT, k + ".txt"), "w", encoding="utf-8") as kout:
                    kout.write(k)

    urls, news = [], []
    topics = collect_topics(by_country)
    hubs = {s for s, tp in topics.items() if len(tp["items"]) >= MIN_TOPIC_ITEMS}
    n_trends = n_days = 0
    built = set()       # (نسخة، يوم، slug) لكل صفحة خبر بُنيت — لشبكة الأمان

    for key, entries in by_country.items():
        dates = [d for d, _ in entries]
        for i, (day, cfg) in enumerate(entries):
            prev_day = dates[i + 1] if i + 1 < len(dates) else None
            next_day = dates[i - 1] if i > 0 else None
            if build_day(key, day, cfg, urls, prev_day, next_day):
                n_days += 1
            for t in cfg["trends"]:
                if t.get("article"):
                    build_trend(key, cfg, t, urls, hubs=hubs if has_hubs(key) else None, news=news)
                    built.add((key, day, entities.slugify(t["title"])))
                    n_trends += 1
        build_archive(key, [(d, c, len([x for x in c["trends"] if x.get("article")]))
                            for d, c in entries], urls)

    for key, cfg in latest.items():
        build_country(key, cfg, urls)
    for slug in hubs:
        build_topic(slug, topics[slug], urls)

    build_home(latest, urls)
    build_static(urls)
    build_faq_page(urls)
    build_gold_app_page(urls)
    jobs_urls = jobs.build_jobs_site(BASE, OUT, lambda d: country_nav("jobs", d), page)
    urls.extend(jobs_urls)
    # صفحات دائمة (سعر الذهب ومواعيد الصرف): أسعار حيّة تُجلب هنا في كل بناء
    urls.extend(evergreen.build_evergreen_site(
        BASE, lambda d: country_nav("gold" if d == 2 else "pay", d), page))
    # أداة صور الجواز والتأشيرة: صفحات ثابتة + سكربت يعمل داخل المتصفح
    urls.extend(idphoto.build_idphoto_site(BASE, OUT, lambda d: country_nav("photo", d), page))
    all_days = [(k, c) for k, entries in by_country.items() for _, c in entries]
    n_feed = build_feed(all_days) + build_feed(all_days, english=True)
    n_gold = build_gold_news_api(days)
    n_notify = build_trends_feed(days)   # إشعارات Goldex: كل الفئات
    build_404()
    build_en_redirect()

    # الكروت والملفات الثابتة
    cards_src = os.path.join(ROOT, "output", "cards")
    if os.path.isdir(cards_src):
        shutil.copytree(cards_src, os.path.join(OUT, "cards"))
    # صور aiart.py: تُحفظ في output/art (مثل الكروت) لأن site/ يُمسح كل بناء
    art_src = os.path.join(ROOT, "output", "art")
    if os.path.isdir(art_src):
        shutil.copytree(art_src, os.path.join(OUT, "art"))
    static_src = os.path.join(ROOT, "static")
    if os.path.isdir(static_src):
        for fname in os.listdir(static_src):
            shutil.copy2(os.path.join(static_src, fname), os.path.join(OUT, fname))
    with open(os.path.join(OUT, "style.css"), "w", encoding="utf-8") as f:
        f.write(STYLE)

    # تحويلات الروابط التي لم تعد صفحات — بعد بناء كل الصفحات الحقيقية،
    # فالتحويل لا يكتب فوق صفحة أبدًا (انظر redirect_stub).
    n_stubs = 0
    for p in load_pruned():
        key, day, slug = p["country"], p["day"], p["slug"]
        if has_hubs(key) and slug in hubs:
            target = "{}/e/{}/".format(BASE, slug)
        elif os.path.exists(os.path.join(OUT, key, day, "index.html")):
            target = "{}/{}/{}/".format(BASE, key, day)
        elif os.path.exists(os.path.join(OUT, key, "index.html")):
            target = "{}/{}/".format(BASE, key)
        else:
            target = BASE + "/"
        if redirect_stub("{}/{}/{}/index.html".format(key, day, slug), target):
            n_stubs += 1

    # صفحات الكيانات القديمة التي لم تصر صفحات مواضيع: تتحول لأحدث خبر.
    store = entities.load()
    for ent in store.values():
        slug = ent["slug"]
        if slug in hubs or not any(a.get("publishable") for a in ent["appearances"]):
            continue
        tp = topics.get(slug)
        target = BASE + "/" + tp["items"][0]["href"] if tp else BASE + "/"
        if redirect_stub("e/{}/index.html".format(slug), target):
            n_stubs += 1

    # وأي رابط آخر نُشر يومًا ولم يعد صفحة (انظر keep_published_urls)
    n_stubs += keep_published_urls(urls, built, hubs)

    n_map, n_news = build_sitemaps(urls, news)

    print("✓ الموقع جاهز في site/")
    print("  " + str(len(latest)) + " بلد · " + str(n_days) + " صفحة يوم · " +
          str(n_trends) + " خبر · " + str(len(hubs)) + " صفحة موضوع · " +
          str(len(jobs.GUIDES)) + " دليل وظائف")
    print("  " + str(n_map) + " رابطًا في sitemap.xml · " + str(n_news) +
          " في sitemap-news.xml · " + str(n_feed) + " في feed.xml · " +
          str(n_gold) + " في gold-news.json · " + str(n_notify) + " في trends-feed.json")
    print("  " + str(n_stubs) + " تحويلًا لروابط لم تعد صفحات")
    print("  النطاق المستخدم: " + BASE)


if __name__ == "__main__":
    main()
