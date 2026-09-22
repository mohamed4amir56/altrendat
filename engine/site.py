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
h1{font-size:1.85rem;font-weight:800;line-height:1.45;margin-bottom:10px}
h2{font-size:1.25rem;font-weight:800;margin:28px 0 10px}
.meta{color:var(--mut);font-size:.8rem;margin-bottom:20px}
.hero{width:100%;border-radius:16px;border:1px solid var(--line);
  margin:16px 0 22px;display:block}
.lead{
  font-size:1.02rem;font-weight:600;color:var(--gold);
  border-inline-start:3px solid var(--gold);padding-inline-start:13px;
  margin-bottom:20px;
}
article p{margin-bottom:14px;text-align:justify}
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
table{width:100%;border-collapse:collapse;font-size:.88rem;margin:16px 0;
  display:block;overflow-x:auto;white-space:nowrap}
th{color:var(--mut);font-size:.76rem;font-weight:600;text-align:start;
  padding:7px 10px;border-bottom:1px solid var(--line)}
td{padding:7px 10px;border-bottom:1px solid rgba(255,255,255,.05);
  font-variant-numeric:tabular-nums}
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
    </div>
    <h1>{head}</h1>
    <p class="meta">الترند: {term}</p>
    {hero}
    <p class="lead">{summ}</p>
    {table}
    <article>{paras}</article>
    <div class="tags">{tags}</div>
    {sources}
    <p class="meta"><a href="../../">← كل ترندات {cname}</a> ·
       <a href="../../../e/{slug}/">أرشيف "{term}"</a></p>""".format(
        icon=t["icon"], cat=E(t["category"]), traffic=E(t["traffic"]),
        flag=cfg["flag"], cname=E(cfg["country_name"]), day=day,
        head=E(art["headline"]), term=E(t["title"]),
        hero=("<img class='hero' src='{}cards/{}' alt='{}' "
              "width='1200' height='675' loading='eager'>".format(
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
