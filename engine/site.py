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
from itertools import zip_longest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entities  # noqa: E402
import dedup  # noqa: E402
import jobs  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site")
E = html.escape

SITE_NAME = "الترندات"
SITE_NAME_EN = "ALTRENDAT"


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
<!-- بلا هذا الوسم لا تدخل الصفحة Google Discover إطلاقًا -->
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="alternate" type="application/rss+xml" title="{site}" href="{root}feed.xml">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="site">
  <a class="brand" href="{root}">{site}</a>
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
  max-width:860px;margin:0 auto;padding:20px 18px;
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
.brand{
  font-size:1.5rem;font-weight:800;text-decoration:none;
  background:linear-gradient(95deg,var(--gold),#ff9f68);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
nav{display:flex;gap:10px;flex-wrap:wrap}
nav a{
  font-size:.84rem;text-decoration:none;color:var(--mut);
  border:1px solid var(--line);border-radius:99px;padding:4px 13px;
}
nav a:hover{color:var(--txt);border-color:var(--acc)}
main{max-width:860px;margin:0 auto;padding:8px 18px 30px}
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
.btn-tg{
  background:#229ed9;color:#fff!important;font-weight:700;font-size:.88rem;
  padding:9px 20px;border-radius:99px;text-decoration:none;
  display:inline-flex;align-items:center;gap:6px;transition:.2s;white-space:nowrap;
}
.btn-tg:hover{background:#1c88bd;transform:translateY(-1px)}
.floating-cta{
  position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:999;
  background:rgba(17,22,34,.95);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid var(--line);box-shadow:0 8px 24px rgba(0,0,0,.5);
  border-radius:99px;padding:6px 14px;display:flex;align-items:center;gap:10px;max-width:92%;
}
.floating-cta span{font-size:.8rem;font-weight:600;color:var(--txt);white-space:nowrap}
@media(max-width:560px){
  h1{font-size:1.45rem}
  .channel-cta{flex-direction:column;align-items:stretch;text-align:center}
  .btn-tg{justify-content:center}
}
/* --- قسم الوظائف (Jobs Section) --- */
.nav-jobs{
  background:linear-gradient(135deg,rgba(245,197,66,.18),rgba(255,159,104,.15));
  border-color:rgba(245,197,66,.5)!important;color:var(--gold)!important;
  font-weight:700;
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

.job-filters-wrap{margin:22px 0 16px}
.job-filters-group{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.filter-label{font-size:.84rem;color:var(--mut);font-weight:600}
.filter-btn{
  background:var(--card);border:1px solid var(--line);color:var(--txt);
  padding:6px 14px;border-radius:99px;font-family:inherit;font-size:.84rem;cursor:pointer;
  transition:.2s;
}
.filter-btn:hover{border-color:var(--acc);color:#fff}
.filter-btn.active{background:var(--acc);border-color:var(--acc);color:#0a0d14;font-weight:700}

.jobs-list{display:grid;gap:16px;margin:24px 0}
.job-card{
  background:linear-gradient(165deg,var(--card),var(--bg2));
  border:1px solid var(--line);border-radius:16px;padding:20px 22px;transition:.2s;
}
.job-card:hover{border-color:rgba(90,169,255,.5);transform:translateY(-2px)}
.job-header{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
.job-badge{
  font-size:.76rem;font-weight:700;padding:3px 10px;border-radius:99px;
  background:rgba(255,255,255,.06);color:var(--c,var(--gold));border:1px solid rgba(255,255,255,.1);
}
.job-country{font-size:.82rem;color:var(--mut)}
.job-title{font-size:1.25rem;font-weight:800;line-height:1.45;margin-bottom:12px}
.job-title a{text-decoration:none;color:var(--txt)}
.job-title a:hover{color:var(--acc)}
.job-meta{display:flex;flex-wrap:wrap;gap:10px 16px;margin-bottom:12px;font-size:.84rem;color:var(--mut)}
.job-meta-item{display:inline-flex;align-items:center;gap:4px}
.job-summary{font-size:.95rem;color:#c8d1e0;line-height:1.75;margin-bottom:16px}
.job-footer{display:flex;justify-content:flex-end}
.btn-job-details{
  font-size:.86rem;font-weight:700;color:var(--gold);text-decoration:none;
  padding:6px 14px;border-radius:99px;border:1px solid rgba(245,197,66,.3);transition:.2s;
}
.btn-job-details:hover{background:rgba(245,197,66,.12);border-color:var(--gold)}

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
"""


CAT_EN = {
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


def page(path, title, desc, body, canonical, nav="", image=None,
         ogtype="website", jsonld=None, depth=0, is_en=False):
    root = "../" * depth if depth else "./"
    ogimage = ('<meta property="og:image" content="{}">'.format(E(image))
               if image else "")
    ld = ('<script type="application/ld+json">{}</script>'.format(
        json.dumps(jsonld, ensure_ascii=False)) if jsonld else "")

    lang = "en" if is_en else "ar"
    direction = "ltr" if is_en else "rtl"
    locale = "en_US" if is_en else "ar_AR"
    site_brand = SITE_NAME_EN if is_en else SITE_NAME

    if is_en:
        flinks = ('<a href="{r}about/">About Us</a>'
                  '<a href="{r}privacy/">Privacy Policy</a>'
                  '<a href="{r}contact/">Contact</a>').format(r=root)
        fdesc = "{site} — Tracking daily trending search topics worldwide.".format(site=E(site_brand))
        ffine = "News stories are attributed and linked to their original publishers."
    else:
        flinks = ('<a href="{r}about/">من نحن</a>'
                  '<a href="{r}privacy/">سياسة الخصوصية</a>'
                  '<a href="{r}contact/">اتصل بنا</a>').format(r=root)
        fdesc = "{site} — يرصد الأكثر بحثًا يوميًا في العالم العربي والعالم.".format(site=E(site_brand))
        ffine = "الأخبار منسوبة إلى مصادرها وروابطها، والأرقام إلى جهاتها."

    if is_en:
        floating_bar = """<div class="floating-cta">
  <span>📢 Follow Trending News:</span>
  <a class="btn-tg" href="https://t.me/altrendat_news" target="_blank" rel="noopener">Telegram</a>
</div>"""
    else:
        floating_bar = """<div class="floating-cta">
  <span>📢 تابع الترندات أولاً بأول:</span>
  <a class="btn-tg" href="https://t.me/altrendat_news" target="_blank" rel="noopener">تليجرام</a>
</div>"""

    out = SHELL.format(
        lang=lang, dir=direction, locale=locale,
        title=E(title), desc=E(desc[:300]), canonical=E(canonical),
        site=E(site_brand), ogimage=ogimage, ogtype=ogtype, jsonld=ld,
        nav=nav, body=body, root=root, flinks=flinks, fdesc=fdesc, ffine=ffine,
        floating_bar=floating_bar,
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
    for n in news:
        if not n.get("ok"):
            continue
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


def pick_trend_photo(t):
    """يختار صورة صحفية صالحة للترند إن كان يحتاج صورة.

    المقالات التي لا تحتاج صورة:
    - الترندات التي موضوعها الأساسي جدول بيانات رسمي (مثل مواقيت الصلاة)
    """
    if t.get("data"):
        return None

    for n in t.get("news", []):
        img = (n.get("og_image") or "").strip()
        if img and img.startswith(("http://", "https://")) and not any(bad in img for bad in ("<", ">", "\n", "\r")):
            if any(x in img.lower() for x in ("favicon", "logo_square", "avatar", "placeholder")):
                continue
            return {
                "url": img,
                "source": n.get("source") or "مصدر إخباري",
            }

    g_img = (t.get("image") or "").strip()
    if g_img and g_img.startswith(("http://", "https://")):
        return {
            "url": g_img,
            "source": t.get("image_source") or "تغطية إخبارية",
        }

    return None


def build_trend(country, cfg, t, urls):
    is_en = cfg.get("lang") == "en" or country == "world"
    cname = cfg.get("name_en", "Worldwide") if is_en else cfg["country_name"]
    slug = entities.slugify(t["title"])
    day = entities.day_of(cfg)
    art = t["article"]
    path = "{}/{}/{}/index.html".format(country, day, slug)
    canonical = "{}/{}/{}/{}/".format(BASE, country, day, slug)

    img = None
    if t.get("card"):
        img = BASE + "/cards/" + os.path.basename(t["card"])

    photo = pick_trend_photo(t)
    photo_html = ""
    if photo:
        cap = ("News coverage photo · Source: " + photo["source"] if is_en
               else "صورة من التغطية الإخبارية · المصدر: " + photo["source"])
        photo_html = (
            '<figure class="article-photo">'
            '<img src="{u}" alt="{alt}" loading="eager" decoding="async">'
            '<figcaption>{cap}</figcaption>'
            '</figure>'.format(u=E(photo["url"]), alt=E(art["headline"]), cap=E(cap))
        )

    jsonld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": art["headline"],
        "description": art.get("summary", ""),
        "datePublished": cfg["generated_at"],
        "dateModified": cfg["generated_at"],
        "inLanguage": "en" if is_en else "ar",
        "publisher": {"@type": "Organization", "name": SITE_NAME_EN if is_en else SITE_NAME},
        "mainEntityOfPage": canonical,
    }
    img_list = []
    if photo:
        img_list.append(photo["url"])
    if img:
        img_list.append(img)
    if img_list:
        jsonld["image"] = img_list

    paras = "".join("<p>{}</p>".format(E(p.strip()))
                    for p in art["body"].split("\n") if p.strip())
    tags = "".join("<span class='tag'>{}</span>".format(E(x))
                   for x in art.get("tags", []))

    cat_label = CAT_EN.get(t["category"], t["category"]) if is_en else t["category"]
    n_sources = len([n for n in t["news"] if n.get("ok")])

    t_time = format_time(t.get("published_at") or cfg.get("generated_at"), is_en=is_en, country=country)
    time_chip = f'<span class="chip">🕒 {E(t_time)}</span>' if t_time else ""

    if is_en:
        chips = """
        <span class="chip">{icon} {cat}</span>
        <span class="chip">🔍 {traffic} searches</span>
        <span class="chip">{flag} {cname}</span>
        <span class="chip">📅 {day}</span>
        {time_chip}
        <span class="chip">📎 {nsrc} sources</span>""".format(
            icon=t["icon"], cat=E(cat_label), traffic=E(t["traffic"]),
            flag=cfg["flag"], cname=E(cname), day=day, time_chip=time_chip, nsrc=n_sources)
        meta_nav = """<p class="meta"><a href="../">← {cname} trends on {day}</a> ·
           <a href="../../">Today</a> ·
           <a href="../../../../e/{slug}/">Topic history</a></p>""".format(
            cname=E(cname), day=day, slug=slug)
        src_html = sources_list(t["news"], is_en=True)
    else:
        chips = """
        <span class="chip">{icon} {cat}</span>
        <span class="chip">🔍 {traffic}</span>
        <span class="chip">{flag} {cname}</span>
        <span class="chip">📅 {day}</span>
        {time_chip}
        <span class="chip">📎 {nsrc} مصادر</span>""".format(
            icon=t["icon"], cat=E(t["category"]), traffic=E(t["traffic"]),
            flag=cfg["flag"], cname=E(cfg["country_name"]), day=day, time_chip=time_chip, nsrc=n_sources)
        meta_nav = """<p class="meta"><a href="../">← ترندات {cname} يوم {day}</a> ·
           <a href="../../">اليوم</a> ·
           <a href="../../../../e/{slug}/">كل ظهور لـ"{term}"</a></p>""".format(
            cname=E(cfg["country_name"]), day=day, term=E(t["title"]), slug=slug)
        src_html = sources_list(t["news"], is_en=False)

    hero_top = ""
    if not photo and t.get("card"):
        hero_top = ("<figure class='article-photo'>"
                    "<img class='hero' src='{}cards/{}' alt='{}' "
                    "width='1200' height='675' loading='eager'>"
                    "</figure>".format(
                        "../../../../", os.path.basename(t["card"]), E(t["title"])))

    if is_en:
        cta = """
        <div class="channel-cta">
          <div class="channel-cta-text">
            <h4>📢 Follow ALTRENDAT on Telegram</h4>
            <p>Get real-time updates and breaking news directly on your phone.</p>
          </div>
          <div class="channel-cta-btns">
            <a class="btn-tg" href="https://t.me/altrendat_news" target="_blank" rel="noopener">👉 Join Channel</a>
          </div>
        </div>"""
    else:
        cta = """
        <div class="channel-cta">
          <div class="channel-cta-text">
            <h4>📢 انضم لقناة الترندات على تليجرام</h4>
            <p>تابع أهم وأحدث الأخبار العاجلة وترندات الساعة لحظة بلحظة مع الصور والتفاصيل الكاملة مجاناً.</p>
          </div>
          <div class="channel-cta-btns">
            <a class="btn-tg" href="https://t.me/altrendat_news" target="_blank" rel="noopener">👉 انضم للقناة الآن</a>
          </div>
        </div>"""

    body = """
    <div class="when">{chips}</div>
    <h1>{head}</h1>
    <p class="lead">{summ}</p>
    {table}
    {photo}
    {hero_top}
    <article>{paras}</article>
    <div class="tags">{tags}</div>
    {cta}
    {sources}
    {meta_nav}""".format(
        chips=chips, head=E(art["headline"]), summ=E(art.get("summary", "")),
        table=data_table(t.get("data")), photo=photo_html, hero_top=hero_top,
        paras=paras, tags=tags, cta=cta, sources=src_html, meta_nav=meta_nav)

    urls.append((canonical, cfg["generated_at"], "0.8"))
    site_title = SITE_NAME_EN if is_en else SITE_NAME
    return page(path, art["headline"] + " | " + site_title,
                art.get("summary", ""), body, canonical,
                nav=country_nav(country, 4, is_en=is_en), image=img,
                ogtype="article", jsonld=jsonld, depth=4, is_en=is_en)


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
    jobs_label = "💼 Jobs" if is_en else "💼 وظائف اليوم"
    mark = " ●" if current == "jobs" else ""
    out.append("<a href='{r}jobs/' class='nav-jobs'>{l}{m}</a>".format(
        r=root, l=jobs_label, m=mark))
    for key, cfg in COUNTRIES.items():
        mark = " ●" if key == current else ""
        name = cfg.get("name_en") if is_en else cfg.get("name_ar")
        out.append("<a href='{r}{k}/'>{f} {n}{m}</a>".format(
            r=root, k=key, f=cfg["flag"], n=E(name or key), m=mark))
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
        cat_label = CAT_EN.get(x["category"], x["category"]) if is_en else x["category"]
        traffic_label = "🔍 " + x["traffic"] + (" searches" if is_en else "")
        x_time = format_time(x.get("published_at") or cfg.get("generated_at"), is_en=is_en, country=country)
        time_part = " · 🕒 " + x_time if x_time else ""
        items.append(
            "<a class='item' href='{s}/'>"
            "<h3><span class='rank'>{i}</span>{h}</h3>"
            "<p class='sub'>{ic} {cat} · {tr}{tm}</p></a>".format(
                s=entities.slugify(x["title"]), i=i,
                h=E(x["article"]["headline"]), ic=x["icon"],
                cat=E(cat_label), tr=E(traffic_label), tm=E(time_part)))

    around = []
    all_days_text = "All Days" if is_en else "كل الأيام"
    if prev_day:
        around.append("<a href='../{}/'>← {}</a>".format(prev_day, prev_day))
    around.append("<a href='../archive/'>{}</a>".format(all_days_text))
    if next_day:
        around.append("<a href='../{}/'>{} →</a>".format(next_day, next_day))

    canonical = "{}/{}/{}/".format(BASE, country, day)
    heading = ("{flag} Trending Searches in {name} — {day}" if is_en
               else "{flag} الأكثر بحثًا في {name} — {day}").format(
        flag=cfg["flag"], name=E(cname), day=day)
    meta_topics = ("{} topics" if is_en else "{} موضوعًا").format(len(pub))
    body = """
    <h1>{heading}</h1>
    <p class="meta">{meta}</p>
    <div class="list">{items}</div>
    <p class="meta nav-days">{around}</p>""".format(
        heading=heading, meta=meta_topics,
        items="".join(items), around=" · ".join(around))

    urls.append((canonical, cfg["generated_at"], "0.7"))
    sname = SITE_NAME_EN if is_en else SITE_NAME
    page_title = ("Trending Searches in {} on {} | {}" if is_en
                  else "الأكثر بحثًا في {} يوم {} | {}").format(cname, day, sname)
    page_desc = ("Top {} topics trending in {} on {}." if is_en
                 else "أهم {} موضوعًا تصدّرت البحث في {} يوم {}.").format(len(pub), cname, day)
    return page("{}/{}/index.html".format(country, day),
                page_title, page_desc,
                body, canonical, nav=country_nav(country, 2, is_en=is_en), depth=2, is_en=is_en)


def build_archive(country, cfg_days, urls):
    """فهرس كل الأيام — الصفحة التي تفتح للزاحف باب الأرشيف كله."""
    is_en = cfg_days[0][1].get("lang") == "en" or country == "world"
    cname = cfg_days[0][1].get("name_en", "Worldwide") if is_en else cfg_days[0][1]["country_name"]
    flag = cfg_days[0][1]["flag"]
    rows = []
    for day, cfg, n in cfg_days:
        sub_text = ("{} topics" if is_en else "{} موضوعًا").format(n)
        rows.append(
            "<a class='item' href='../{d}/'><h3>{d}</h3>"
            "<p class='sub'>{sub}</p></a>".format(d=day, sub=sub_text))

    canonical = "{}/{}/archive/".format(BASE, country)
    heading = ("{flag} {name} Archive" if is_en else "{flag} أرشيف {name}").format(
        flag=flag, name=E(cname))
    lead = ("Every day tracked, and what was trending." if is_en
            else "كل يوم رصدناه، وما تصدّر البحث فيه.")
    body = """
    <h1>{heading}</h1>
    <p class="lead">{lead}</p>
    <div class="list">{rows}</div>""".format(
        heading=heading, lead=lead, rows="".join(rows))

    urls.append((canonical, datetime.now(timezone.utc).isoformat(), "0.6"))
    page_title = ("{} Archive | {}" if is_en else "أرشيف {} | {}").format(
        cname, SITE_NAME_EN if is_en else SITE_NAME)
    page_desc = ("Daily archive of trending topics in {}." if is_en
                 else "أرشيف يومي لما تصدّر البحث في {}.").format(cname)
    return page("{}/archive/index.html".format(country),
                page_title, page_desc,
                body, canonical, nav=country_nav(country, 2, is_en=is_en), depth=2, is_en=is_en)


def build_country(country, cfg, urls):
    is_en = cfg.get("lang") == "en" or country == "world"
    cname = cfg.get("name_en", "Worldwide") if is_en else cfg["country_name"]
    day = entities.day_of(cfg)
    clean_trends = dedup.dedup_trends(cfg["trends"], lang=cfg.get("lang", "en" if is_en else "ar"))
    pub = [t for t in clean_trends if t.get("article")]
    pub.sort(key=lambda x: -x["traffic_num"])

    items = []
    for i, t in enumerate(pub, 1):
        slug = entities.slugify(t["title"])
        cat_label = CAT_EN.get(t["category"], t["category"]) if is_en else t["category"]
        traffic_label = "🔍 " + t["traffic"] + (" searches" if is_en else "")
        t_time = format_time(t.get("published_at") or cfg.get("generated_at"), is_en=is_en, country=country)
        time_part = " · 🕒 " + t_time if t_time else ""
        items.append(
            "<a class='item' href='{d}/{s}/'>"
            "<h3><span class='rank'>{i}</span>{h}</h3>"
            "<p class='sub'>{ic} {cat} · {tr}{tm}</p></a>".format(
                d=day, s=slug, i=i, h=E(t["article"]["headline"]),
                ic=t["icon"], cat=E(cat_label), tr=E(traffic_label), tm=E(time_part)))

    names = [t["title"] for t in pub[:3]]
    canonical = "{}/{}/".format(BASE, country)

    if is_en:
        intro_text = "Most searched topics in {} on {}: {}.".format(
            cname, day, ", ".join(names)) if names else ""
        lead_html = "<p class='lead'>{} Explained with verified sources.</p>".format(E(intro_text)) if intro_text else ""
        body = """
        <h1>{flag} Trending Searches Today in {name}</h1>
        {lead}
        <p class="meta">{day} · {n} topics ·
           <a href="archive/">Previous Days Archive</a></p>
        <div class="list">{items}</div>""".format(
            flag=cfg["flag"], name=E(cname), lead=lead_html, day=day,
            n=len(pub), items="".join(items))
        page_title = "Trending Searches Today in {} | {}".format(cname, SITE_NAME_EN)
        page_desc = intro_text or "Trending search topics today in {}, explained with sources.".format(cname)
    else:
        intro = "أكثر ما بحث عنه الناس في {} يوم {}: {}.".format(
            cfg["country_name"], day, "، و".join(names)) if names else ""
        body = """
        <h1>{flag} الأكثر بحثًا اليوم في {name}</h1>
        {intro}
        <p class="meta">{day} · {n} موضوعًا ·
           <a href="archive/">أرشيف الأيام السابقة</a></p>
        <div class="list">{items}</div>""".format(
            flag=cfg["flag"], name=E(cfg["country_name"]), day=day,
            intro="<p class='lead'>{} نشرح كل موضوع بمصادره.</p>".format(E(intro))
                  if intro else "",
            n=len(pub), items="".join(items))
        page_title = "الأكثر بحثًا اليوم في {} | {}".format(cfg["country_name"], SITE_NAME)
        page_desc = intro or "أهم ما يبحث عنه الناس اليوم في {}، مشروحًا بمصادره.".format(cfg["country_name"])

    urls.append((canonical, cfg["generated_at"], "0.9"))
    return page("{}/index.html".format(country),
                page_title, page_desc,
                body, canonical, nav=country_nav(country, 1, is_en=is_en), depth=1, is_en=is_en)


def build_entity(ent, urls):
    slug = ent["slug"]
    apps = sorted(ent["appearances"], key=lambda a: a["date"], reverse=True)

    rows = "".join(
        "<tr><td>{d}</td><td>{c}</td><td>{t}</td><td>{k}</td></tr>".format(
            d=E(a["date"]), c=E(a["country_name"]),
            t=E(a.get("traffic", "")), k=E(a.get("category", "")))
        for a in apps)

    canonical = "{}/e/{}/".format(BASE, slug)
    body = """
    <h1>{name}</h1>
    <p class="meta">ظهر {n} مرة · من {first} إلى {last} ·
       {countries}</p>
    <p class="lead">أرشيف ظهور "{name}" ضمن الأكثر بحثًا.</p>
    <h2>سجل الظهور</h2>
    <table><thead><tr><th>التاريخ</th><th>البلد</th>
      <th>حجم البحث</th><th>الفئة</th></tr></thead>
      <tbody>{rows}</tbody></table>""".format(
        name=E(ent["name"]), n=ent.get("total", 1),
        first=E(ent.get("first_seen", "")), last=E(ent.get("last_seen", "")),
        countries=E(" · ".join(ent.get("countries", []))), rows=rows)

    urls.append((canonical, ent.get("last_seen", ""), "0.5"))
    return page("e/{}/index.html".format(slug),
                "{} — أرشيف الترند | {}".format(ent["name"], SITE_NAME),
                "كل مرة تصدّر فيها \"{}\" نتائج البحث، بالتاريخ والبلد.".format(
                    ent["name"]),
                body, canonical, nav=country_nav(None, 2), depth=2)


def build_home(data, urls):
    cards = []
    for key, cfg in data.items():
        pub = [t for t in cfg["trends"] if t.get("article")]
        top = max(pub, key=lambda x: x["traffic_num"], default=None)
        cards.append(
            "<a class='item' href='{k}/'><h3>{f} {n}</h3>"
            "<p class='sub'>{c} موضوعًا اليوم{t}</p></a>".format(
                k=key, f=cfg["flag"], n=E(cfg["country_name"]),
                c=len(pub),
                t=" · أبرزها: " + E(top["title"]) if top else ""))

    # أبرز الأخبار مباشرة من الرئيسة.
    #
    # كانت الرئيسة تربط بالبلدان وحدها، فالخبر على بعد نقرتين منها.
    # والرئيسة أقوى صفحة عند Google وأول ما يُزحف إليه، فرابط مباشر منها
    # يوصل الزاحف إلى الخبر في زيارته الأولى — وهو ما يُفهرس ويُبحث عنه.
    # بالتناوب بين البلدان: أرقام بحث مصر أكبر، فالترتيب بالرقم وحده
    # يُخفي السعودية كلها.
    per = []
    for key, cfg in data.items():
        pub = sorted([t for t in cfg["trends"] if t.get("article")],
                     key=lambda x: -x["traffic_num"])
        per.append([(key, cfg, t) for t in pub])
    mixed = [x for row in zip_longest(*per) for x in row if x][:12]

    news = []
    for i, (key, cfg, t) in enumerate(mixed, 1):
        t_time = format_time(t.get("published_at") or cfg.get("generated_at"), is_en=False, country=key)
        time_part = " · 🕒 " + t_time if t_time else ""
        news.append(
            "<a class='item' href='{k}/{d}/{s}/'>"
            "<h3><span class='rank'>{i}</span>{h}</h3>"
            "<p class='sub'>{f} {n} · {ic} {cat} · 🔍 {tr}{tm}</p></a>".format(
                k=key, d=entities.day_of(cfg), s=entities.slugify(t["title"]),
                i=i, h=E(t["article"]["headline"]), f=cfg["flag"],
                n=E(cfg["country_name"]), ic=t["icon"],
                cat=E(t["category"]), tr=E(t["traffic"]), tm=E(time_part)))

    jobs_banner = """
    <div class="channel-cta" style="background:linear-gradient(135deg,rgba(61,220,151,.12),rgba(90,169,255,.08));border-color:rgba(61,220,151,.35);margin:18px 0 24px;">
      <div class="channel-cta-text">
        <h4 style="color:#3ddc97;">💼 دليل وظائف اليوم وعقود العمل الرسمية 2026</h4>
        <p>وظائف حكومية ومسابقات رسمية، عقود عمل بالخارج (ألمانيا، كندا، إيطاليا)، وظائف الخليج، والعمل عن بعد بالدولار مع روابط التقديم المباشرة.</p>
      </div>
      <div class="channel-cta-btns">
        <a class="btn-tg" style="background:#3ddc97;color:#0a0d14!important;font-weight:800;" href="./jobs/">استعرض جميع الوظائف ⬅️</a>
      </div>
    </div>"""

    body = """
    <h1>ما الذي يبحث عنه العرب اليوم؟</h1>
    <p class="lead">الترند قبل أن يبرد… ما يشغل الملايين الآن ⚡</p>
    {jobs_banner}
    <div class="list">{cards}</div>
    {news}""".format(
        jobs_banner=jobs_banner,
        cards="".join(cards),
        news=("<h2>أبرز أخبار اليوم</h2><div class='list'>" +
              "".join(news) + "</div>") if news else "")

    urls.append((BASE + "/", datetime.now(timezone.utc).isoformat(), "1.0"))
    return page("index.html", "{} — الأكثر بحثًا اليوم في العالم العربي".format(
        SITE_NAME), "رصد يومي لأكثر ما يبحث عنه الناس في كل بلد عربي.",
        body, BASE + "/", nav=country_nav(None, 0), depth=0)


# بريد يُستبدل ببريد الموقع بعد حجز النطاق
CONTACT = "info@altrendat.com"

# صفحات ثابتة — شرط أساسي لقبول AdSense.
# موقع بلا "من نحن" و"سياسة خصوصية" و"اتصل بنا" يُرفض غالبًا مهما
# كان محتواه، لأن المراجع لا يجد من يقف خلفه ولا كيف يُتواصل معه.
PAGES = [
    ("about", "من نحن", "من يقف خلف الترندات وكيف يعمل.", """
    <h1>من نحن</h1>
    <p class="lead">الترندات موقع عربي مستقل يرصد يوميًا أكثر ما
       يبحث عنه الناس في كل بلد، ويشرح لماذا.</p>
    <article>
      <p>نبدأ من قوائم الأكثر بحثًا التي تنشرها Google لكل بلد، ثم
         نقرأ ما نشرته الصحف حول كل موضوع، ونكتب منه خبرًا عربيًا
         موجزًا ينسب كل معلومة إلى مصدرها بالاسم ويضع رابطه.</p>
      <p>وحين يكون الموضوع رقمًا يبحث عنه القارئ — مواقيت الصلاة أو
         سعر صرف أو سعر ذهب — نحضر الرقم من جهته الرسمية وننشره في
         جدول، لأن الحديث عن الرقم لا يغني عن الرقم نفسه.</p>
      <h2>ما لا ننشره</h2>
      <p>لا ننشر تلقائيًا أي موضوع يتعلق بوفاة أو حادث أو جريمة أو
         قبض أو قضية منظورة أو مرض، ولا موضوعًا لم نجد له مصدرين
         موثوقين على الأقل. هذه الموضوعات تُحال إلى مراجعة بشرية قبل
         أي نشر.</p>
      <h2>الشخصيات</h2>
      <p>نكتب عن الشخصيات العامة — الفنان واللاعب والمدرب والمسؤول —
         في نشاطهم العام فقط: أعمالهم ومبارياتهم وتصريحاتهم المنشورة،
         وننسب كل قول إلى قائله. ولا نكتب عن فرد عادي، ولا عن أي
         شخص تدور الأخبار حوله حول اتهام أو شائعة أو مرض أو وفاة أو
         حياة خاصة أو عائلية، ولا عن قاصر.</p>
      <h2>تصحيح الأخطاء</h2>
      <p>إن وجدت خطأً في معلومة أو نسبة إلى مصدر، راسلنا وسنصحّحه أو
         نزيل الصفحة. نتعامل مع كل بلاغ جديًا.</p>
    </article>"""),

    ("privacy", "سياسة الخصوصية", "كيف نتعامل مع بياناتك.", """
    <h1>سياسة الخصوصية</h1>
    <p class="lead">لا نطلب منك تسجيل دخول ولا نجمع بياناتك الشخصية
       بأنفسنا.</p>
    <article>
      <h2>ما نجمعه</h2>
      <p>لا يطلب الموقع تسجيلًا ولا اسمًا ولا بريدًا، ولا ننشئ
         حسابات للزوار. وما يصلنا هو إحصاءات مجمّعة عن الصفحات
         الأكثر قراءة، بلا ما يعرّف شخصًا بعينه.</p>
      <h2>ملفات تعريف الارتباط والإعلانات</h2>
      <p>قد يعرض الموقع إعلانات عبر شبكات إعلانية خارجية، منها
         Google AdSense. وتستخدم هذه الشبكات ملفات تعريف ارتباط
         لعرض إعلانات تناسب اهتماماتك بناءً على زياراتك لهذا الموقع
         ولمواقع أخرى.</p>
      <p>يمكنك تعطيل الإعلانات المخصصة من إعدادات إعلانات Google على
         <a href="https://www.google.com/settings/ads"
            rel="nofollow noopener" target="_blank">google.com/settings/ads</a>،
         كما يمكنك حذف ملفات تعريف الارتباط أو منعها من إعدادات
         متصفحك في أي وقت.</p>
      <h2>الروابط الخارجية</h2>
      <p>نضع روابط إلى مواقع الصحف التي نقلنا عنها. ولا نتحكم في
         سياسات تلك المواقع ولا نتحمل مسؤولية محتواها، ونشجعك على
         قراءة سياسة الخصوصية في كل موقع تزوره.</p>
      <h2>الأطفال</h2>
      <p>الموقع غير موجّه لمن هم دون 13 عامًا، ولا نجمع بيانات عنهم
         عن قصد.</p>
      <h2>التعديلات</h2>
      <p>قد نحدّث هذه السياسة، وسيظهر أي تعديل على هذه الصفحة.</p>
    </article>"""),

    ("contact", "اتصل بنا", "للتصحيح أو الإعلان أو الاستفسار.", """
    <h1>اتصل بنا</h1>
    <p class="lead">نقرأ كل رسالة، ونرد على بلاغات التصحيح أولًا.</p>
    <article>
      <p>للتواصل في أي من الأمور التالية:</p>
      <ul>
        <li>تصحيح معلومة أو نسبتها إلى مصدرها</li>
        <li>طلب إزالة صفحة أو الاعتراض على محتواها</li>
        <li>الإعلان على الموقع</li>
        <li>أي استفسار آخر</li>
      </ul>
      <p>راسلنا على: <strong>{contact}</strong></p>
      <p>بلاغات التصحيح والإزالة لها أولوية، ونتعامل معها خلال أيام
         قليلة.</p>
    </article>"""),
]


def build_static(urls):
    """الصفحات الثابتة التي يشترطها AdSense ويطمئن إليها القارئ."""
    for slug, title, desc, body in PAGES:
        canonical = "{}/{}/".format(BASE, slug)
        page("{}/index.html".format(slug),
             "{} | {}".format(title, SITE_NAME), desc,
             body.replace("{contact}", E(CONTACT)),
             canonical, nav=country_nav(None, 1), depth=1)
        urls.append((canonical, datetime.now(timezone.utc).isoformat(), "0.3"))


def build_404():
    """صفحة الخطأ — يخدمها Cloudflare لأي رابط غير موجود."""
    body = """
    <h1>الصفحة غير موجودة</h1>
    <p class="lead">ربما تغيّر الرابط، أو لم يعد هذا الموضوع منشورًا.</p>
    <p class="meta"><a href="/">← الصفحة الرئيسة</a></p>"""
    page("404.html", "الصفحة غير موجودة | " + SITE_NAME, "", body,
         BASE + "/404.html", nav="", depth=0)
    path_404 = os.path.join(OUT, "404.html")
    if os.path.exists(path_404):
        with open(path_404, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace('content="index, follow', 'content="noindex, follow')
        with open(path_404, "w", encoding="utf-8") as f:
            f.write(content)


def build_feed(data):
    """خلاصة RSS — تقرأها المجمّعات وقارئات الأخبار، وتسرّع اكتشاف
    الجديد. تُبقي أحدث 40 موضوعًا فقط."""
    items = []
    for key, cfg in data.items():
        for t in cfg["trends"]:
            art = t.get("article")
            if not art:
                continue
            items.append((t["traffic_num"], key, cfg, t, art))
    items.sort(key=lambda x: -x[0])

    body = []
    for _, key, cfg, t, art in items[:40]:
        link = "{}/{}/{}/{}/".format(BASE, key, entities.day_of(cfg),
                                     entities.slugify(t["title"]))
        img = ""
        if t.get("card"):
            img = ('<enclosure url="{}/cards/{}" type="image/png"/>'
                   .format(BASE, os.path.basename(t["card"])))
        body.append(
            "<item><title>{t}</title><link>{l}</link><guid>{l}</guid>"
            "<description>{d}</description>"
            "<category>{c}</category>{img}</item>".format(
                t=E(art["headline"]), l=E(link),
                d=E(art.get("summary", "")), c=E(t["category"]), img=img))

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0"><channel>'
           '<title>{s}</title><link>{b}/</link>'
           '<description>الأكثر بحثًا اليوم — Trending searches today</description>'
           '<language>ar</language>{items}</channel></rss>').format(
        s=E(SITE_NAME), b=BASE, items="".join(body))

    with open(os.path.join(OUT, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    return len(body)


COUNTRIES = {}


def main():
    global BASE, COUNTRIES
    if len(sys.argv) > 1:
        BASE = sys.argv[1].rstrip("/")

    with open(os.path.join(ROOT, "data", "trends.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(ROOT, "engine", "countries.json"),
              encoding="utf-8") as f:
        c_defs = json.load(f)
        rank = {k: i for i, k in enumerate(c_defs)}

    archive_today(data)

    # كل يوم مؤرشف يُبنى، لا يوم واحد. صفحة الأمس تبقى على رابطها،
    # وهذا شرط الفهرسة: رابط يختفي بعد يوم لا يُرتَّب أبدًا.
    enabled_keys = {k for k, cfg in c_defs.items() if cfg.get("enabled")}
    days = load_days()
    by_country = {}
    for (key, day), cfg in days.items():
        if key not in enabled_keys:
            continue
        by_country.setdefault(key, []).append((day, cfg))
    for entries in by_country.values():
        entries.sort(key=lambda x: x[0], reverse=True)

    # صفحة البلد والرئيسة والقائمة تُبنى من أحدث يوم مؤرشف لكل بلد،
    # لا من trends.json. حين فشل جلب مصر مرة خرجت من trends.json،
    # فاختفت من القائمة وصار /eg/ خطأ 404 رغم أن أرشيفها كامل. الأرشيف
    # لا يُمحى، فالبناء منه لا يُسقط بلدًا بسبب تشغيلة واحدة.
    latest = {k: by_country[k][0][1]
              for k in sorted(by_country, key=lambda k: rank.get(k, len(rank)))}
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

    urls = []
    n_trends = n_days = 0

    for key, entries in by_country.items():
        dates = [d for d, _ in entries]

        for i, (day, cfg) in enumerate(entries):
            prev_day = dates[i + 1] if i + 1 < len(dates) else None
            next_day = dates[i - 1] if i > 0 else None
            if build_day(key, day, cfg, urls, prev_day, next_day):
                n_days += 1
            for t in cfg["trends"]:
                if t.get("article"):
                    build_trend(key, cfg, t, urls)
                    n_trends += 1

        build_archive(key, [(d, c, len([x for x in c["trends"]
                                        if x.get("article")]))
                            for d, c in entries], urls)

    # صفحة البلد تعرض اليوم الأحدث
    for key, cfg in latest.items():
        build_country(key, cfg, urls)

    build_home(latest, urls)
    build_static(urls)
    jobs_urls = jobs.build_jobs_site(BASE, OUT, lambda d: country_nav("jobs", d))
    urls.extend(jobs_urls)
    n_feed = build_feed(latest)
    build_404()

    # صفحات الكيانات — الأصل الذي يتراكم.
    #
    # وبوابة الأمان تسري هنا أيضًا: كيان لم يُجَز أي ظهور له لا صفحة
    # له. بدون هذا الشرط أنشأ المولّد صفحة عامة اسمها "القبض على ملحن"
    # بعد أن منعت البوابة مقالها — أي أن المنع أوقف المقال وحده وترك
    # الصفحة. المنع يجب أن يسري على الموقع كله لا على خطوة الكتابة.
    store = entities.load()
    skipped = 0
    for ent in store.values():
        if not any(a.get("publishable") for a in ent["appearances"]):
            skipped += 1
            continue
        build_entity(ent, urls)

    # الكروت تُنسخ مرة واحدة بجانب الصفحات
    cards_src = os.path.join(ROOT, "output", "cards")
    if os.path.isdir(cards_src):
        shutil.copytree(cards_src, os.path.join(OUT, "cards"))

    with open(os.path.join(OUT, "style.css"), "w", encoding="utf-8") as f:
        f.write(STYLE)

    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for loc, mod, pri in urls:
            f.write("  <url><loc>{}</loc><lastmod>{}</lastmod>"
                    "<priority>{}</priority></url>\n".format(
                        E(loc), E(mod[:10]), pri))
        f.write("</urlset>\n")

    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: " +
                BASE + "/sitemap.xml\n")

    print("✓ الموقع جاهز في site/")
    print("  " + str(len(latest)) + " بلد · " + str(n_days) + " صفحة يوم · " +
          str(n_trends) + " صفحة ترند · " +
          str(len(store) - skipped) + " صفحة كيان · " +
          str(len(jobs_urls) - 1) + " وظيفة شاغرة (/jobs/)")
    print("  " + str(skipped) + " كيانًا حجبته بوابة الأمان")
    print("  " + str(len(urls)) + " رابطًا في sitemap.xml · " +
          str(n_feed) + " في feed.xml")
    print("  النطاق المستخدم: " + BASE)


if __name__ == "__main__":
    main()
