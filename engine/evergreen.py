# -*- coding: utf-8 -*-
"""
صفحات دائمة — إجابتها رقم أو تاريخ، لا مقال.

مقال الترند يعيش يومًا. أما «سعر الذهب اليوم في مصر» و«موعد حساب المواطن»
فيُبحث عنهما كل يوم بلا انقطاع، والقارئ يريد الرقم نفسه لا سردًا حوله.
هذه الصفحات تُبنى من بيانات حقيقية (لا نص من نموذج لغوي)، فلا تكلف رصيد
API، وتتحدّث مع كل بناء للموقع:

  /gold-price/egypt/      سعر الذهب في مصر  (كل عيار + الجنيه الذهب + الأوقية)
  /gold-price/saudi/      سعر الذهب في السعودية
  /saudi-payment-dates/   مواعيد صرف الرواتب والدعم في السعودية

الأسعار تُحفظ في data/evergreen.json (آخر نقطة + إغلاق كل يوم)، فتعرض
الصفحة التغيّر عن الأمس ومنحنى آخر 30 يومًا، وإن تعذّر الجلب تبقى آخر
نقطة معروفة بوقتها بدل صفحة فارغة.
"""
import html
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import providers  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "evergreen.json")
E = html.escape

FETCH_EVERY = timedelta(minutes=10)   # بناء محلي متكرر لا يستهلك المزوّدين
KEEP_DAYS = 400

WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
          "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def _tz(name, hours):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=hours))   # ويندوز بلا tzdata


TZ = {"eg": _tz("Africa/Cairo", 3), "sa": _tz("Asia/Riyadh", 3)}


def ar_date(d):
    return "{} {} {} {}".format(WEEKDAYS[d.weekday()], d.day, MONTHS[d.month - 1], d.year)


def ar_time(dt):
    h = dt.hour % 12 or 12
    return "{}:{:02d} {}".format(h, dt.minute, "م" if dt.hour >= 12 else "ص")


# -- البيانات ----------------------------------------------------------

def load():
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"latest": None, "daily": {}}


def save(store):
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=1, sort_keys=True)


def fetch_point():
    spot = providers._get_json("https://api.gold-api.com/price/XAU")
    fx = providers._get_json("https://open.er-api.com/v6/latest/USD")
    price = float(spot["price"])
    egp, sar = float(fx["rates"]["EGP"]), float(fx["rates"]["SAR"])
    # قيم شاذة من مزوّد معطوب لا تُنشر على صفحة يثق فيها الناس
    if not (500 < price < 20000 and 5 < egp < 500 and 3 < sar < 4.5):
        raise ValueError("قيم خارج المعقول: {} {} {}".format(price, egp, sar))
    return {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "spot": round(price, 2), "EGP": round(egp, 4), "SAR": round(sar, 4)}


def update(store):
    """يجلب نقطة جديدة إن مرّ وقت كافٍ، ويسجّلها إغلاقًا لليوم. يعيد True إن جلب."""
    last = store.get("latest")
    if last:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(last["t"])
        if age < FETCH_EVERY:
            return False
    try:
        p = fetch_point()
    except Exception as e:
        print("  ⚠ تعذّر جلب سعر الذهب (" + type(e).__name__ + ") — تبقى آخر نقطة")
        return False
    store["latest"] = p
    day = datetime.now(TZ["eg"]).date().isoformat()
    store.setdefault("daily", {})[day] = p
    for d in sorted(store["daily"])[:-KEEP_DAYS]:
        del store["daily"][d]
    save(store)
    return True


def gram(p, code, karat=24):
    return p["spot"] / providers.OUNCE_G * p[code] * karat / 24


# -- مكوّنات مشتركة -----------------------------------------------------

EXTRA_CSS = """
<style>
.eg-hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.eg-tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.eg-tile .k{color:var(--mut);font-size:.8rem}
.eg-tile .v{font-size:1.45rem;font-weight:800;color:var(--gold);font-variant-numeric:tabular-nums}
.eg-tile .c{font-size:.8rem;font-weight:700}
.up{color:#3ecf8e}.down{color:#ff6b6b}.flat{color:var(--mut)}
.eg-note{background:rgba(90,169,255,.07);border:1px solid rgba(90,169,255,.25);
  border-radius:12px;padding:12px 15px;font-size:.88rem;margin:16px 0;color:#dfe6f0}
.eg-calc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:18px 0}
.eg-calc label{display:block;font-size:.82rem;color:var(--mut);margin-bottom:4px}
.eg-calc .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
.eg-calc input,.eg-calc select{width:100%;background:var(--bg2);color:var(--txt);
  border:1px solid var(--line);border-radius:10px;padding:9px 11px;font:inherit}
.eg-calc output{display:block;margin-top:12px;font-size:1.2rem;font-weight:800;color:var(--gold)}
.eg-chart{width:100%;height:auto;margin:10px 0 4px}
.eg-links{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}
.eg-links a{text-decoration:none;border:1px solid var(--line);border-radius:99px;
  padding:6px 14px;font-size:.85rem;color:var(--txt)}
.eg-links a:hover{border-color:var(--gold);color:var(--gold)}
.eg-next{background:linear-gradient(135deg,rgba(245,197,66,.12),rgba(90,169,255,.08));
  border:1px solid rgba(245,197,66,.3);border-radius:16px;padding:16px 18px;margin:12px 0}
.eg-next h3{font-size:1.05rem;margin-bottom:4px}
.eg-next .d{font-size:1.25rem;font-weight:800;color:var(--gold)}
.eg-next .left{font-size:.85rem;color:var(--mut)}
.eg-page h2{margin:26px 0 8px;font-size:1.2rem}
.eg-page p{margin-bottom:10px}
</style>"""


def links_row(root, current):
    items = [("gold-price/egypt/", "🇪🇬 سعر الذهب في مصر"),
             ("gold-price/saudi/", "🇸🇦 سعر الذهب في السعودية"),
             ("saudi-payment-dates/", "📅 مواعيد الصرف في السعودية"),
             ("gold-app/", "📱 تطبيق Goldex")]
    return "<nav class='eg-links'>" + "".join(
        "<a href='{}{}'>{}</a>".format(root, p, E(t)) for p, t in items if p != current) + "</nav>"


def change_html(now, before):
    if not before:
        return "<span class='c flat'>—</span>"
    diff = now - before
    pct = diff / before * 100 if before else 0
    if abs(pct) < 0.05:
        return "<span class='c flat'>ثابت عن أمس</span>"
    cls, arrow = ("up", "▲") if diff > 0 else ("down", "▼")
    return "<span class='c {}'>{} {:,.0f} ({:+.1f}%) عن أمس</span>".format(cls, arrow, abs(diff), pct)


def chart_svg(series, label):
    """منحنى بسيط لآخر 30 يومًا. أقل من 3 أيام = لا منحنى (لا معنى لخطين)."""
    if len(series) < 3:
        return ""
    vals = [v for _, v in series]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    w, h, pad = 600, 160, 12
    pts = []
    for i, v in enumerate(vals):
        x = pad + i * (w - 2 * pad) / (len(vals) - 1)
        y = pad + (1 - (v - lo) / span) * (h - 2 * pad)
        pts.append("{:.1f},{:.1f}".format(x, y))
    first, last = series[0][0], series[-1][0]
    return ("<svg class='eg-chart' viewBox='0 0 {w} {h}' role='img' aria-label='{lab}'>"
            "<polyline fill='none' stroke='#f5c542' stroke-width='2.5' points='{pts}'/>"
            "</svg><p class='src'>{lab}: من {a} إلى {b} · أعلى {hi:,.0f} · أدنى {lo:,.0f}</p>").format(
        w=w, h=h, pts=" ".join(pts), lab=E(label), a=first, b=last, hi=hi, lo=lo)


# -- صفحات الذهب --------------------------------------------------------

GOLD = {
    "eg": {
        "slug": "gold-price/egypt/", "name": "مصر", "flag": "🇪🇬", "code": "EGP",
        "cur": "جنيه", "karats": (24, 21, 18, 14), "main": 21,
        "extra": [("الجنيه الذهب (8 جرام عيار 21)", 8, 21)],
        "about": [
            ("عيار 21 هو الأكثر تداولًا في مصر",
             "أغلب المشغولات في محلات الصاغة المصرية عيار 21، لذلك يُذكر سعره أولًا. "
             "عيار 18 شائع في المشغولات الخفيفة، وعيار 24 للسبائك."),
            ("الجنيه الذهب",
             "الجنيه الذهب وزنه 8 جرامات من عيار 21، ويُشترى للادخار لأن مصنعيته أقل من المشغولات."),
        ],
    },
    "sa": {
        "slug": "gold-price/saudi/", "name": "السعودية", "flag": "🇸🇦", "code": "SAR",
        "cur": "ريال", "karats": (24, 22, 21, 18), "main": 24,
        "extra": [("سبيكة 10 جرام عيار 24", 10, 24), ("سبيكة 100 جرام عيار 24", 100, 24)],
        "about": [
            ("الأعيرة في السوق السعودي",
             "عيار 24 للسبائك، وعيار 22 و21 للمشغولات الخليجية، وعيار 18 للمجوهرات المرصّعة."),
            ("الريال مربوط بالدولار",
             "سعر الريال ثابت تقريبًا عند 3.75 للدولار، فسعر الذهب في السعودية يتحرك مع السعر العالمي وحده."),
        ],
    },
}


def build_gold(key, store, base, nav, page_func):
    g = GOLD[key]
    p = store.get("latest")
    if not p:
        return None
    code, cur = g["code"], g["cur"]
    when = datetime.fromisoformat(p["t"]).astimezone(TZ[key])
    today = when.date().isoformat()
    days = sorted(d for d in store.get("daily", {}) if d < today)
    prev = store["daily"][days[-1]] if days else None

    main_now = gram(p, code, g["main"])
    main_prev = gram(prev, code, g["main"]) if prev else None
    ounce = p["spot"] * p[code]

    tiles = ("<div class='eg-tile'><div class='k'>جرام عيار {m}</div><div class='v'>{v:,.0f} {c}</div>{ch}</div>"
             "<div class='eg-tile'><div class='k'>جرام عيار 24</div><div class='v'>{v24:,.0f} {c}</div></div>"
             "<div class='eg-tile'><div class='k'>الأوقية</div><div class='v'>{oz:,.0f} {c}</div>"
             "<span class='c flat'>{spot:,.0f}$ عالميًا</span></div>").format(
        m=g["main"], v=main_now, c=cur, ch=change_html(main_now, main_prev),
        v24=gram(p, code, 24), oz=ounce, spot=p["spot"])

    rows = []
    for k in g["karats"]:
        now_k = gram(p, code, k)
        prev_k = gram(prev, code, k) if prev else None
        ch = "—" if not prev_k else "{:+,.0f}".format(now_k - prev_k)
        rows.append("<tr><td>عيار {}</td><td>{:,.0f} {}</td><td>{}</td></tr>".format(k, now_k, cur, ch))
    for label, grams, k in g["extra"]:
        rows.append("<tr><td>{}</td><td>{:,.0f} {}</td><td>—</td></tr>".format(
            E(label), gram(p, code, k) * grams, cur))
    table = ("<table><thead><tr><th>العيار</th><th>السعر</th><th>التغيّر عن أمس</th></tr></thead>"
             "<tbody>{}</tbody></table>").format("".join(rows))

    series = [(d, gram(store["daily"][d], code, g["main"]))
              for d in sorted(store.get("daily", {}))[-30:]]
    chart = chart_svg(series, "سعر جرام عيار {} آخر 30 يومًا".format(g["main"]))

    prices = {str(k): round(gram(p, code, k), 2) for k in (24, 22, 21, 18, 14)}
    options = "".join("<option value='{k}'{s}>عيار {k}</option>".format(
        k=k, s=" selected" if k == g["main"] else "") for k in g["karats"])
    calc = f"""
    <section class="eg-calc" id="calc">
      <h2 style="margin-top:0">احسب ثمن قطعة ذهب</h2>
      <div class="row">
        <div><label for="gk">العيار</label><select id="gk">{options}</select></div>
        <div><label for="gw">الوزن بالجرام</label><input id="gw" type="number" min="0" step="0.1" value="10" inputmode="decimal"></div>
        <div><label for="gm">المصنعية للجرام ({cur})</label><input id="gm" type="number" min="0" step="1" value="0" inputmode="decimal"></div>
      </div>
      <output id="gout"></output>
    </section>
    <script>
    (function(){{
      var P={json.dumps(prices)},c="{cur}";
      function f(n){{return Math.round(n).toLocaleString("en-US")}}
      function run(){{
        var k=document.getElementById("gk").value,w=+document.getElementById("gw").value||0,
            m=+document.getElementById("gm").value||0,gold=P[k]*w,tot=gold+m*w;
        document.getElementById("gout").textContent="الإجمالي: "+f(tot)+" "+c+
          (m?" (ذهب "+f(gold)+" + مصنعية "+f(m*w)+")":"");
      }}
      ["gk","gw","gm"].forEach(function(id){{document.getElementById(id).addEventListener("input",run)}});
      run();
    }})();
    </script>"""

    about = "".join("<h2>{}</h2><p>{}</p>".format(E(h), E(t)) for h, t in g["about"])
    title_main = "سعر الذهب اليوم في {} — عيار {} الآن".format(g["name"], g["main"])
    body = f"""{EXTRA_CSS}
    <div class="eg-page">
    <nav class="breadcrumb"><a href="../../">الرئيسية</a> › <span>سعر الذهب في {E(g['name'])}</span></nav>
    <h1>{g['flag']} سعر الذهب اليوم في {E(g['name'])}</h1>
    <p class="lead">جرام عيار {g['main']} بـ {main_now:,.0f} {cur} — آخر تحديث {E(ar_date(when))} الساعة {E(ar_time(when))} بتوقيت {E(g['name'])}.</p>
    <div class="eg-hero">{tiles}</div>
    <h2>أسعار الذهب بكل عيار</h2>
    {table}
    <p class="src">السعر العالمي للأوقية ({p['spot']:,.0f}$) محوّلًا بسعر صرف الدولار ({p[code]:,.2f} {cur}). تتحدّث الصفحة تلقائيًا عدة مرات في الساعة.</p>
    <div class="eg-note">هذا سعر الذهب الخام. في محلات الصاغة تُضاف <strong>المصنعية</strong> (وتختلف من محل ومن قطعة لأخرى)، وقد يزيد السعر المحلي أو ينقص قليلًا عن المحسوب هنا حسب العرض والطلب. استخدم الحاسبة تحت لتعرف الإجمالي قبل الشراء.</div>
    {chart}
    {calc}
    {about}
    <h2>كيف نحسب السعر؟</h2>
    <p>جرام عيار 24 = سعر الأوقية بالدولار ÷ 31.1 جرام × سعر الدولار بالعملة المحلية. وباقي الأعيرة بنسبة الذهب فيها: عيار 21 = 21 ÷ 24 من سعر عيار 24، وعيار 18 = 18 ÷ 24، وهكذا.</p>
    <p class="src">المصادر: السعر العالمي من gold-api.com، وسعر الصرف من ExchangeRate-API. الأرقام للمعلومة وليست عرض بيع أو شراء أو نصيحة استثمارية.</p>
    {links_row("../../", g["slug"])}
    </div>"""

    canonical = base + "/" + g["slug"]
    jsonld = {
        "@context": "https://schema.org", "@type": "WebPage", "name": title_main,
        "url": canonical, "inLanguage": "ar", "dateModified": p["t"],
        "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "الرئيسية", "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": "سعر الذهب في " + g["name"], "item": canonical}]},
    }
    desc = ("سعر الذهب اليوم في {n}: عيار {m} بـ {v:,.0f} {c}، مع كل الأعيرة{x} وسعر الأوقية، "
            "والتغيّر عن أمس، وحاسبة للمصنعية. تتحدّث تلقائيًا.").format(
        n=g["name"], m=g["main"], v=main_now, c=cur,
        x=" والجنيه الذهب" if key == "eg" else " والسبائك")
    page_func(g["slug"] + "index.html", title_main, desc, body, canonical,
              nav=nav, depth=2, jsonld=jsonld)
    return (canonical, p["t"], "0.8")


# -- مواعيد الصرف في السعودية -------------------------------------------

# القاعدة الرسمية لكل برنامج: يوم ثابت من الشهر الميلادي، وإن وافق
# الجمعة يُقدَّم للخميس، وإن وافق السبت يُؤخَّر للأحد. تحقّقنا من
# القاعدة 2026-09-30 من إعلانات الجهات كما نقلتها عكاظ وعاجل وسبق.
PROGRAMS = [
    {"id": "citizen", "name": "حساب المواطن", "day": 10,
     "who": "دعم شهري للأسر السعودية المستحقة", "url": "https://www.ca.gov.sa",
     "note": "تظهر نتيجة الأهلية قبل الإيداع بأيام في حساب المستفيد على المنصة."},
    {"id": "salary", "name": "رواتب موظفي الدولة", "day": 27,
     "who": "الموظفون المدنيون والعسكريون (وزارة المالية)", "url": "https://www.mof.gov.sa",
     "note": "القطاع الخاص يصرف بموعد كل شركة، والتاريخ هنا لرواتب الدولة."},
    {"id": "social", "name": "الضمان الاجتماعي المطور", "day": 1,
     "who": "مستفيدو الضمان (وزارة الموارد البشرية)", "url": "https://www.hrsd.gov.sa",
     "note": "تُعلن نتيجة الأهلية قرب يوم 27 من الشهر السابق."},
    {"id": "pension", "name": "المعاشات التقاعدية", "day": 1,
     "who": "متقاعدو التقاعد المدني والعسكري والتأمينات", "url": "https://www.gosi.gov.sa",
     "note": "موحّد في أول كل شهر ميلادي منذ مايو 2024."},
]


def pay_date(year, month, day):
    d = date(year, month, day)
    if d.weekday() == 4:          # الجمعة → الخميس
        return d - timedelta(days=1), "قُدّم من الجمعة"
    if d.weekday() == 5:          # السبت → الأحد
        return d + timedelta(days=1), "أُخّر من السبت"
    return d, ""


def upcoming(prog, today, n):
    out, y, m = [], today.year, today.month
    # الشهر السابق أيضًا: يوم 1 قد يُصرف في آخر أيام الشهر قبله
    m -= 1
    if m == 0:
        y, m = y - 1, 12
    while len(out) < n:
        d, why = pay_date(y, m, prog["day"])
        if d >= today:
            out.append((d, why, MONTHS[m - 1] + " " + str(y)))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def left_text(days):
    if days == 0:
        return "اليوم"
    if days == 1:
        return "غدًا"
    if days == 2:
        return "بعد يومين"
    return "بعد {} {}".format(days, "أيام" if days <= 10 else "يومًا")


def build_payments(base, nav, page_func):
    now = datetime.now(TZ["sa"])
    today = now.date()
    cards, sections = [], []
    for pr in PROGRAMS:
        nxt = upcoming(pr, today, 12)
        d, why, label = nxt[0]
        cards.append(
            "<div class='eg-next' data-pay='{iso}'><h3>{n}</h3>"
            "<div class='d'>{dt}</div><div class='left'>دفعة {lab} · <span class='cd'>{left}</span>{w}</div></div>".format(
                iso=d.isoformat(), n=E(pr["name"]), dt=E(ar_date(d)), lab=E(label),
                left=left_text((d - today).days), w=(" · " + why) if why else ""))
        rows = "".join("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            E(lab), E(ar_date(x)), E(w or "—")) for x, w, lab in nxt)
        sections.append(
            "<h2 id='{id}'>موعد صرف {n}</h2><p>{who}. يُصرف يوم <strong>{day}</strong> من كل شهر ميلادي. {note}</p>"
            "<table><thead><tr><th>الدفعة</th><th>يوم الصرف</th><th>ملاحظة</th></tr></thead><tbody>{rows}</tbody></table>"
            "<p class='src'>الجهة الرسمية: <a href='{url}' rel='noopener' target='_blank'>{host}</a></p>".format(
                id=pr["id"], n=E(pr["name"]), who=E(pr["who"]), day=pr["day"], note=E(pr["note"]),
                rows=rows, url=pr["url"], host=pr["url"].split("//")[1]))

    body = f"""{EXTRA_CSS}
    <div class="eg-page">
    <nav class="breadcrumb"><a href="../">الرئيسية</a> › <span>مواعيد الصرف في السعودية</span></nav>
    <h1>🇸🇦 مواعيد صرف الرواتب والدعم في السعودية</h1>
    <p class="lead">أقرب موعد لكل برنامج، محسوبًا بقاعدته الرسمية — اليوم {E(ar_date(today))}.</p>
    {"".join(cards)}
    <div class="eg-note">القاعدة في كل البرامج: إن وافق يوم الصرف <strong>الجمعة</strong> يُقدَّم إلى الخميس، وإن وافق <strong>السبت</strong> يُؤخَّر إلى الأحد. في الأعياد والإجازات الرسمية قد تعلن الجهة موعدًا مختلفًا، والإعلان الرسمي هو المرجع.</div>
    {"".join(sections)}
    <p class="src">الجداول محسوبة من القاعدة المعلنة لكل جهة وتتحدّث تلقائيًا كل يوم. للاستفسار عن استحقاقك تواصل مع الجهة نفسها.</p>
    {links_row("../", "saudi-payment-dates/")}
    </div>
    <script>
    (function(){{
      var t=new Date(new Date().toLocaleString("en-US",{{timeZone:"Asia/Riyadh"}}));t.setHours(0,0,0,0);
      document.querySelectorAll("[data-pay]").forEach(function(el){{
        var d=new Date(el.getAttribute("data-pay")+"T00:00:00"),n=Math.round((d-t)/864e5),s;
        if(n<0)return;
        s=n==0?"اليوم":n==1?"غدًا":n==2?"بعد يومين":"بعد "+n+(n<=10?" أيام":" يومًا");
        el.querySelector(".cd").textContent=s;
      }});
    }})();
    </script>"""

    canonical = base + "/saudi-payment-dates/"
    title = "مواعيد صرف حساب المواطن والرواتب والضمان والتقاعد في السعودية"
    first = min((upcoming(pr, today, 1)[0][0], pr["name"]) for pr in PROGRAMS)
    desc = ("أقرب مواعيد الصرف في السعودية: حساب المواطن يوم 10، والرواتب يوم 27، والضمان المطور "
            "والمعاشات يوم 1 من كل شهر، مع جدول 12 شهرًا وقاعدة الجمعة والسبت. الأقرب: {} {}.").format(
        first[1], ar_date(first[0]))
    jsonld = {
        "@context": "https://schema.org", "@type": "WebPage", "name": title,
        "url": canonical, "inLanguage": "ar",
        "dateModified": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "الرئيسية", "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": "مواعيد الصرف في السعودية", "item": canonical}]},
    }
    page_func("saudi-payment-dates/index.html", title, desc, body, canonical,
              nav=nav, depth=1, jsonld=jsonld)
    return (canonical, now.astimezone(timezone.utc).isoformat(), "0.8")


# -- ربط مقالات الترند بالصفحات الدائمة -----------------------------------

RELATED = [
    (("ذهب", "الذهب", "عيار", "سبيكة", "سبائك"), {"eg": "gold-price/egypt/", "sa": "gold-price/saudi/"},
     "سعر الذهب الآن بكل عيار، مع حاسبة المصنعية"),
    (("حساب المواطن", "الضمان", "رواتب", "الرواتب", "راتب", "المعاش", "معاشات", "التقاعد", "صرف"),
     {"sa": "saudi-payment-dates/"}, "كل مواعيد الصرف القادمة في السعودية بجدول واحد"),
]


def related_box(title, country, root):
    for words, targets, text in RELATED:
        if country in targets and any(w in title for w in words):
            return ("<aside class='eg-note' style='margin:18px 0'>📌 <a href='{}{}' style='color:var(--gold)'>{}</a></aside>"
                    .format(root, targets[country], E(text)))
    return ""


def build_evergreen_site(base, nav_func, page_func):
    """يحدّث الأسعار ثم يبني الصفحات الثلاث، ويعيد روابطها لخريطة الموقع."""
    store = load()
    if update(store):
        print("  ✓ سعر الذهب: {:,.2f}$ للأوقية".format(store["latest"]["spot"]))
    urls = []
    for key in ("eg", "sa"):
        u = build_gold(key, store, base, nav_func(2), page_func)
        if u:
            urls.append(u)
    urls.append(build_payments(base, nav_func(1), page_func))
    return urls


if __name__ == "__main__":
    s = load()
    update(s)
    print(json.dumps(s.get("latest"), ensure_ascii=False))
    today = datetime.now(TZ["sa"]).date()
    for pr in PROGRAMS:
        print(pr["name"], [(str(d), w) for d, w, _ in upcoming(pr, today, 4)])
