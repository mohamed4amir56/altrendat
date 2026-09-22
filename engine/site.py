# -*- coding: utf-8 -*-
"""
مولّد الموقع — يحوّل data/ إلى صفحات HTML ثابتة جاهزة للنشر.

لا Next.js ولا Node ولا خطوة بناء: المحرّك يملك المحتوى كاملًا، وما
يلزم هو صفحات بروابط دائمة ووسوم SEO صحيحة. صفحة ثابتة أسرع من أي
إطار على شبكات الموبايل، وتُنشر مجانًا على Cloudflare Pages أو
GitHub Pages، وتُفتح محليًا بلا خادم.

  python engine/site.py [https://altrendat.com]

البنية الناتجة:
  site/index.html              الصفحة الرئيسة
  site/eg/index.html           الأكثر بحثًا اليوم في مصر
  site/eg/t/<slug>/index.html  صفحة لكل ترند
  site/e/<slug>/index.html     صفحة لكل كيان (الذاكرة التراكمية)
  site/sitemap.xml
"""
import html
import json
import os
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entities  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site")
E = html.escape

SITE_NAME = "الترندات"
# يُستبدل بالنطاق الحقيقي فور حجزه — يمرَّر كوسيط للسكربت
BASE = "https://altrendat.com"

SHELL = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
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
<meta property="og:locale" content="ar_AR">
{ogimage}
<meta name="twitter:card" content="summary_large_image">
{jsonld}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap" rel="stylesheet">
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
    <a href="{root}about/">من نحن</a>
    <a href="{root}privacy/">سياسة الخصوصية</a>
    <a href="{root}contact/">اتصل بنا</a>
  </nav>
  <p>{site} — يرصد الأكثر بحثًا يوميًا في العالم العربي.</p>
  <p class="fine">الأخبار منسوبة إلى مصادرها وروابطها، والأرقام إلى جهاتها.</p>
</footer>
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
@media(max-width:560px){h1{font-size:1.45rem}}
"""


def page(path, title, desc, body, canonical, nav="", image=None,
         ogtype="website", jsonld=None, depth=0):
    root = "../" * depth if depth else "./"
    ogimage = ('<meta property="og:image" content="{}">'.format(E(image))
               if image else "")
    ld = ('<script type="application/ld+json">{}</script>'.format(
        json.dumps(jsonld, ensure_ascii=False)) if jsonld else "")

    out = SHELL.format(
        title=E(title), desc=E(desc[:300]), canonical=E(canonical),
        site=E(SITE_NAME), ogimage=ogimage, ogtype=ogtype, jsonld=ld,
        nav=nav, body=body, root=root)

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


def sources_list(news):
    items = []
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
                u=E(n["url"]), s=E(n.get("source") or "مصدر"),
                t=E(n["title"]), d=E(desc)))
    if not items:
        return ""
    return "<h2>المصادر</h2><ul class='sources'>" + "".join(items) + "</ul>"


def build_trend(country, cfg, t, urls):
    slug = entities.slugify(t["title"])
    day = cfg["generated_at"][:10]
    art = t["article"]
    path = "{}/t/{}/index.html".format(country, slug)
    canonical = "{}/{}/t/{}/".format(BASE, country, slug)

    img = None
    if t.get("card"):
        img = BASE + "/cards/" + os.path.basename(t["card"])

    jsonld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": art["headline"],
        "description": art.get("summary", ""),
        "datePublished": cfg["generated_at"],
        "dateModified": cfg["generated_at"],
        "inLanguage": "ar",
        "publisher": {"@type": "Organization", "name": SITE_NAME},
        "mainEntityOfPage": canonical,
    }
    if img:
        jsonld["image"] = [img]

    paras = "".join("<p>{}</p>".format(E(p.strip()))
                    for p in art["body"].split("\n") if p.strip())
    tags = "".join("<span class='tag'>{}</span>".format(E(x))
                   for x in art.get("tags", []))

    body = """
    <div class="when">
      <span class="chip">{icon} {cat}</span>
      <span class="chip">🔍 {traffic}</span>
      <span class="chip">{flag} {cname}</span>
      <span class="chip">{day}</span>
      <span class="chip">📎 {nsrc} مصادر</span>
    </div>
    <h1>{head}</h1>
    <p class="lead">{summ}</p>
    {table}
    <article>{paras}</article>
    <div class="tags">{tags}</div>
    {sources}
    {hero}
    <p class="meta"><a href="../../">← كل ترندات {cname}</a> ·
       <a href="../../../e/{slug}/">أرشيف "{term}"</a></p>""".format(
        icon=t["icon"], cat=E(t["category"]), traffic=E(t["traffic"]),
        flag=cfg["flag"], cname=E(cfg["country_name"]), day=day,
        head=E(art["headline"]), term=E(t["title"]),
        nsrc=len([n for n in t["news"] if n.get("ok")]),
        # الصورة نزلت إلى أسفل الصفحة. مكانها بين العنوان والإجابة كان
        # يدفع الجواب خارج الشاشة بصورة تكرّر ما بحث عنه الزائر أصلًا.
        # وتبقى og:image لمعاينة المشاركة، وهذا دورها الحقيقي.
        hero=("<img class='hero' src='{}cards/{}' alt='{}' "
              "width='1200' height='675' loading='lazy'>".format(
                  "../../../", os.path.basename(t["card"]), E(t["title"]))
              if t.get("card") else ""),
        summ=E(art.get("summary", "")), table=data_table(t.get("data")),
        paras=paras, tags=tags, sources=sources_list(t["news"]),
        slug=slug)

    urls.append((canonical, cfg["generated_at"], "0.8"))
    return page(path, art["headline"] + " | " + SITE_NAME,
                art.get("summary", ""), body, canonical,
                nav=country_nav(country, 3), image=img,
                ogtype="article", jsonld=jsonld, depth=3)


def country_nav(current, depth):
    root = "../" * depth if depth else "./"
    out = []
    for key, cfg in COUNTRIES.items():
        mark = " ●" if key == current else ""
        out.append("<a href='{r}{k}/'>{f} {n}{m}</a>".format(
            r=root, k=key, f=cfg["flag"], n=E(cfg["name_ar"]), m=mark))
    return "".join(out)


def build_country(country, cfg, urls):
    day = cfg["generated_at"][:10]
    pub = [t for t in cfg["trends"] if t.get("article")]
    pub.sort(key=lambda x: -x["traffic_num"])

    items = []
    for i, t in enumerate(pub, 1):
        slug = entities.slugify(t["title"])
        items.append(
            "<a class='item' href='t/{s}/'>"
            "<h3><span class='rank'>{i}</span>{h}</h3>"
            "<p class='sub'>{ic} {cat} · 🔍 {tr}</p></a>".format(
                s=slug, i=i, h=E(t["article"]["headline"]),
                ic=t["icon"], cat=E(t["category"]), tr=E(t["traffic"])))

    canonical = "{}/{}/".format(BASE, country)
    body = """
    <h1>{flag} الأكثر بحثًا اليوم في {name}</h1>
    <p class="meta">{day} · {n} موضوعًا</p>
    <div class="list">{items}</div>""".format(
        flag=cfg["flag"], name=E(cfg["country_name"]), day=day,
        n=len(pub), items="".join(items))

    urls.append((canonical, cfg["generated_at"], "0.9"))
    return page("{}/index.html".format(country),
                "الأكثر بحثًا اليوم في {} | {}".format(
                    cfg["country_name"], SITE_NAME),
                "أهم ما يبحث عنه الناس اليوم في {}، مشروحًا بمصادره.".format(
                    cfg["country_name"]),
                body, canonical, nav=country_nav(country, 1), depth=1)


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

    body = """
    <h1>ما الذي يبحث عنه العرب اليوم؟</h1>
    <p class="lead">نرصد الأكثر بحثًا في كل بلد، ونشرح لماذا —
       بمصادره وأرقامه.</p>
    <div class="list">{cards}</div>""".format(cards="".join(cards))

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
         قضية منظورة، ولا موضوعًا محوره شخص بعينه، ولا موضوعًا لم
         نجد له مصدرين موثوقين على الأقل. هذه الموضوعات تُحال إلى
         مراجعة بشرية قبل أي نشر.</p>
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


COUNTRIES = {}


def main():
    global BASE, COUNTRIES
    if len(sys.argv) > 1:
        BASE = sys.argv[1].rstrip("/")

    with open(os.path.join(ROOT, "data", "trends.json"), encoding="utf-8") as f:
        data = json.load(f)
    COUNTRIES = {k: {"flag": v["flag"], "name_ar": v["country_name"]}
                 for k, v in data.items()}

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    urls = []
    n_trends = 0
    for key, cfg in data.items():
        build_country(key, cfg, urls)
        for t in cfg["trends"]:
            if t.get("article"):
                build_trend(key, cfg, t, urls)
                n_trends += 1
    build_home(data, urls)
    build_static(urls)

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
    print("  " + str(len(data)) + " بلد · " + str(n_trends) + " صفحة ترند · " +
          str(len(store) - skipped) + " صفحة كيان")
    print("  " + str(skipped) + " كيانًا حجبته بوابة الأمان")
    print("  " + str(len(urls)) + " رابطًا في sitemap.xml")
    print("  النطاق المستخدم: " + BASE)


if __name__ == "__main__":
    main()
