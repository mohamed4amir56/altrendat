# -*- coding: utf-8 -*-
"""
طبقة العرض — تحوّل data/trends.json إلى صفحة عربية RTL.

هذه معاينة لوحة التحكم: تُظهر ما التقطه المحرّك وما قرّره بشأن كل ترند.
صفحات الموقع النهائية ستُبنى من نفس الـ JSON في Next.js.
"""
import html
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = html.escape


def card(t, idx):
    news = [n for n in t["news"] if n.get("ok")]
    badge = ("<span class='ok'>✓ جاهز للنشر</span>" if t["publishable"]
             else "<span class='hold'>⛔ يحتاج مراجعة</span>")

    items = []
    for n in news:
        desc = (n.get("og_desc") or n.get("og_title") or "").strip()
        if len(desc) > 190:
            desc = desc[:190].rsplit(" ", 1)[0] + "…"
        items.append(
            "<li><a href='{u}' target='_blank' rel='noopener'>"
            "<span class='src'>{s}</span>"
            "<span class='ntitle'>{t}</span>"
            "<span class='ndesc'>{d}</span></a></li>".format(
                u=E(n["url"]), s=E(n.get("source") or "مصدر"),
                t=E(n["title"]), d=E(desc) or "—"))

    thumb = ""
    if t.get("image"):
        thumb = ("<div class='thumb' style='background-image:url({})'></div>"
                 .format(E(t["image"])))

    return """
    <article class="card{dim}" style="--accent:{color}">
      <div class="rank">{rank}</div>
      {thumb}
      <div class="body">
        <div class="top">
          <span class="cat">{icon} {cat}</span>
          <span class="traffic">🔍 {traffic}</span>
          {badge}
        </div>
        <h2>{title}</h2>
        <p class="why">{reason}</p>
        <div class="sources-label">{n} مصادر أُثريت بالنص الكامل</div>
        <ul class="sources">{items}</ul>
      </div>
    </article>""".format(
        dim="" if t["publishable"] else " dim",
        color=t["color"], rank=idx, thumb=thumb,
        icon=t["icon"], cat=E(t["category"]),
        traffic=E(t["traffic"]), badge=badge,
        title=E(t["title"]), reason=E(t["reason"]),
        n=len(news), items="".join(items))


def render(data):
    blocks, stats = [], []
    for key, d in data.items():
        trends = sorted(d["trends"], key=lambda x: -x["traffic_num"])
        pub = sum(1 for t in trends if t["publishable"])
        enriched = sum(1 for t in trends for n in t["news"] if n.get("ok"))
        total_news = sum(len(t["news"]) for t in trends)
        stats.append((d["flag"], d["country_name"], len(trends), pub,
                      enriched, total_news))

        cats = {}
        for t in trends:
            cats.setdefault((t["category"], t["icon"], t["color"]), 0)
            cats[(t["category"], t["icon"], t["color"])] += 1
        chips = "".join(
            "<span class='chip' style='--c:{c}'>{i} {n} <b>{v}</b></span>"
            .format(c=col, i=ic, n=E(nm), v=v)
            for (nm, ic, col), v in sorted(cats.items(), key=lambda x: -x[1]))

        blocks.append("""
        <section class="country">
          <header class="chead">
            <h1><span class="flag">{flag}</span> الأكثر بحثًا اليوم في {name}</h1>
            <div class="chips">{chips}</div>
          </header>
          <div class="grid">{cards}</div>
        </section>""".format(
            flag=d["flag"], name=E(d["country_name"]), chips=chips,
            cards="".join(card(t, i + 1) for i, t in enumerate(trends))))

    srows = "".join(
        """<div class="stat">
             <div class="snum">{v}</div><div class="slabel">{l}</div>
           </div>""".format(v=v, l=l)
        for v, l in [
            (sum(s[2] for s in stats), "ترند ملتقط"),
            (sum(s[3] for s in stats), "جاهز للنشر آليًا"),
            (sum(s[2] - s[3] for s in stats), "موقوف للمراجعة"),
            (sum(s[4] for s in stats), "صفحة خبر أُثريت"),
        ])

    now = datetime.now().strftime("%Y-%m-%d · %H:%M")
    return TEMPLATE.format(stats=srows, blocks="".join(blocks), now=now)


TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="max-image-preview:large">
<title>الترندات — لوحة المحرّك</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0a0d14; --bg2:#111622; --card:#151b29; --line:#222b3d;
    --txt:#e8ecf4; --mut:#8b96ab; --gold:#f5c542;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:
      radial-gradient(900px 500px at 85% -10%, #1b2440 0%, transparent 60%),
      radial-gradient(700px 400px at 10% 0%, #2a2033 0%, transparent 55%),
      var(--bg);
    color:var(--txt); font-family:Cairo,system-ui,sans-serif;
    padding:28px 16px 60px; line-height:1.7; min-height:100vh;
  }}
  .wrap {{ max-width:1180px; margin:0 auto; }}

  .hero {{ text-align:center; margin-bottom:26px; }}
  .logo {{
    font-size:2.5rem; font-weight:800; letter-spacing:-1px;
    background:linear-gradient(95deg,var(--gold),#ff9f68 55%,#c77dff);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }}
  .tag {{ color:var(--mut); font-size:.95rem; }}
  .live {{
    display:inline-flex; align-items:center; gap:7px; margin-top:10px;
    background:rgba(61,220,151,.1); border:1px solid rgba(61,220,151,.3);
    color:#3ddc97; padding:5px 14px; border-radius:99px; font-size:.82rem;
  }}
  .dot {{ width:7px; height:7px; border-radius:50%; background:#3ddc97;
         animation:pulse 1.8s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.25}} }}

  .stats {{
    display:grid; grid-template-columns:repeat(4,1fr); gap:12px;
    margin:26px 0 36px;
  }}
  .stat {{
    background:linear-gradient(160deg,var(--card),var(--bg2));
    border:1px solid var(--line); border-radius:16px;
    padding:18px 10px; text-align:center;
  }}
  .snum {{ font-size:2rem; font-weight:800; color:var(--gold); line-height:1.2; }}
  .slabel {{ font-size:.78rem; color:var(--mut); }}

  .chead {{ margin:34px 0 18px; }}
  .chead h1 {{ font-size:1.5rem; font-weight:800; }}
  .flag {{ font-size:1.6rem; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
  .chip {{
    background:color-mix(in srgb, var(--c) 14%, transparent);
    border:1px solid color-mix(in srgb, var(--c) 40%, transparent);
    color:var(--c); padding:4px 12px; border-radius:99px; font-size:.8rem;
  }}
  .chip b {{ color:var(--txt); }}

  .grid {{ display:grid; gap:16px; }}
  @media (min-width:860px) {{ .grid {{ grid-template-columns:1fr 1fr; }} }}

  .card {{
    position:relative; display:flex; gap:0; overflow:hidden;
    background:linear-gradient(165deg,var(--card),var(--bg2));
    border:1px solid var(--line); border-radius:18px;
    transition:transform .22s ease, border-color .22s ease, box-shadow .22s;
  }}
  .card::before {{
    content:""; position:absolute; inset-inline-start:0; top:0; bottom:0;
    width:4px; background:var(--accent);
  }}
  .card:hover {{
    transform:translateY(-4px); border-color:color-mix(in srgb,var(--accent) 55%,transparent);
    box-shadow:0 14px 36px -14px color-mix(in srgb,var(--accent) 45%,transparent);
  }}
  .card.dim {{ opacity:.62; }}
  .card.dim:hover {{ opacity:1; }}

  .rank {{
    position:absolute; top:12px; inset-inline-end:14px;
    font-size:2.4rem; font-weight:800; color:var(--accent);
    opacity:.16; line-height:1;
  }}
  .thumb {{
    flex:0 0 96px; background-size:cover; background-position:center;
    border-inline-end:1px solid var(--line);
  }}
  .body {{ padding:16px 18px; flex:1; min-width:0; }}
  .top {{ display:flex; flex-wrap:wrap; gap:7px; align-items:center;
          margin-bottom:9px; }}
  .cat {{
    background:color-mix(in srgb,var(--accent) 15%,transparent);
    color:var(--accent); padding:3px 11px; border-radius:99px;
    font-size:.76rem; font-weight:600;
  }}
  .traffic {{ color:var(--mut); font-size:.76rem; }}
  .ok, .hold {{ font-size:.72rem; padding:3px 9px; border-radius:99px; }}
  .ok {{ background:rgba(61,220,151,.12); color:#3ddc97; }}
  .hold {{ background:rgba(255,107,107,.12); color:#ff8787; }}

  .body h2 {{ font-size:1.22rem; font-weight:800; margin-bottom:4px;
              padding-inline-end:42px; }}
  .why {{ color:var(--mut); font-size:.78rem; margin-bottom:12px; }}
  .sources-label {{
    font-size:.72rem; color:var(--gold); border-top:1px dashed var(--line);
    padding-top:10px; margin-bottom:8px;
  }}
  .sources {{ list-style:none; display:grid; gap:8px; }}
  .sources a {{
    display:block; text-decoration:none; color:inherit;
    background:rgba(255,255,255,.028); border:1px solid transparent;
    border-radius:11px; padding:9px 11px; transition:.18s;
  }}
  .sources a:hover {{
    background:rgba(255,255,255,.06);
    border-color:color-mix(in srgb,var(--accent) 35%,transparent);
  }}
  .src {{
    display:inline-block; font-size:.68rem; color:var(--accent);
    margin-bottom:3px; font-weight:600;
  }}
  .ntitle {{ display:block; font-size:.84rem; font-weight:600; }}
  .ndesc {{ display:block; font-size:.76rem; color:var(--mut); margin-top:3px; }}

  footer {{ text-align:center; color:var(--mut); font-size:.78rem;
            margin-top:44px; border-top:1px solid var(--line); padding-top:18px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="logo">الترندات</div>
    <div class="tag">محرّك الرصد — بيانات حيّة من Google Trends مُثراة بنصوص المصادر</div>
    <div class="live"><span class="dot"></span> آخر تشغيل: {now}</div>
  </div>

  <div class="stats">{stats}</div>
  {blocks}

  <footer>
    كل بطاقة أدناه بُنيت آليًا: التقاط ← استخراج og: من صفحات الأخبار ←
    تصنيف ← حكم على صلاحية النشر.<br>
    الخطوة التالية: كتابة الشرح العربي بنموذج Claude، وتوليد كارت 1200×675.
  </footer>
</div>
</body>
</html>"""


def main():
    with open(os.path.join(ROOT, "data", "trends.json"), encoding="utf-8") as f:
        data = json.load(f)
    out = os.path.join(ROOT, "output", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    print("✓ الصفحة جاهزة: " + out)


if __name__ == "__main__":
    main()
