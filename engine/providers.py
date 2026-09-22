# -*- coding: utf-8 -*-
"""
مزوّدو البيانات — للترندات التي لا يكفيها السرد.

الترندات نوعان:

  خبر   : "ماكرون في نيويورك"  → القارئ يريد القصة، والسرد يكفي.
  بيانات: "موعد اذان المغرب"   → القارئ يريد رقمًا، والسرد بلا قيمة.

فشل حقيقي كشف هذا: كُتب مقال كامل عن مواقيت الصلاة لم يذكر موعد
المغرب ولا مرة، لأن المواقيت موجودة في جداول HTML داخل صفحات الصحف
ولا تظهر في وسم og:description الذي نقرأه. فخرج نص يتحدث عن الجداول
ومن أعدّها، ولا يعطي القارئ ما جاء من أجله.

الحل ليس تحسين الصياغة، بل إحضار البيانات من مصدرها.
"""
import gzip
import json
import re
import sys
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# مدن كل بلد التي تُعرض مواقيتها
CITIES = {
    "eg": [("القاهرة", "Cairo"), ("الإسكندرية", "Alexandria"),
           ("الجيزة", "Giza"), ("أسوان", "Aswan"),
           ("الأقصر", "Luxor"), ("الغردقة", "Hurghada"),
           ("شرم الشيخ", "Sharm El Sheikh"), ("بورسعيد", "Port Said")],
    "sa": [("الرياض", "Riyadh"), ("جدة", "Jeddah"), ("مكة", "Mecca"),
           ("المدينة", "Medina"), ("الدمام", "Dammam"), ("أبها", "Abha")],
    "ae": [("دبي", "Dubai"), ("أبوظبي", "Abu Dhabi"), ("الشارقة", "Sharjah")],
    "ma": [("الرباط", "Rabat"), ("الدار البيضاء", "Casablanca"),
           ("مراكش", "Marrakesh"), ("طنجة", "Tangier")],
    "dz": [("الجزائر", "Algiers"), ("وهران", "Oran")],
    "kw": [("الكويت", "Kuwait City")],
}

COUNTRY_EN = {"eg": "Egypt", "sa": "Saudi Arabia", "ae": "United Arab Emirates",
              "ma": "Morocco", "dz": "Algeria", "kw": "Kuwait"}

# طريقة الحساب المعتمدة رسميًا في كل بلد — لا رقم عشوائي:
# 5 = الهيئة العامة للمساحة المصرية، وهي الجهة التي تنشر عنها الصحف
# المصرية مواقيتها. 4 = جامعة أم القرى (السعودية والخليج).
METHOD = {"eg": 5, "sa": 4, "ae": 16, "ma": 21, "dz": 19, "kw": 9}

PRAYERS = [("الفجر", "Fajr"), ("الشروق", "Sunrise"), ("الظهر", "Dhuhr"),
           ("العصر", "Asr"), ("المغرب", "Maghrib"), ("العشاء", "Isha")]


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json",
        "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8", errors="replace"))


def prayer_times(country_key):
    """مواقيت الصلاة اليوم لمدن البلد، من AlAdhan."""
    cities = CITIES.get(country_key)
    if not cities:
        return None

    country = COUNTRY_EN.get(country_key, "")
    method = METHOD.get(country_key, 5)
    rows, hijri, gregorian, source = [], "", "", ""

    for ar_name, en_name in cities:
        try:
            url = ("https://api.aladhan.com/v1/timingsByCity"
                   "?city=" + urllib.parse.quote(en_name) +
                   "&country=" + urllib.parse.quote(country) +
                   "&method=" + str(method))
            d = _get_json(url)["data"]
        except Exception:
            continue

        timings = d["timings"]
        rows.append({
            "city": ar_name,
            "times": {ar: re.sub(r"\s*\(.*\)", "", timings[en]).strip()
                      for ar, en in PRAYERS},
        })
        if not hijri:
            hijri = d["date"]["hijri"]["date"]
            gregorian = d["date"]["readable"]
            source = d["meta"]["method"]["name"]

    if not rows:
        return None

    return {
        "kind": "prayer_times",
        "title": "مواقيت الصلاة اليوم",
        "columns": [ar for ar, _ in PRAYERS],
        "rows": rows,
        "hijri": hijri,
        "gregorian": gregorian,
        "source": source,
        "source_url": "https://aladhan.com",
    }


# -- عملات ومعادن ----------------------------------------------------

CURRENCY = {"eg": ("EGP", "جنيه"), "sa": ("SAR", "ريال"),
            "ae": ("AED", "درهم"), "ma": ("MAD", "درهم"),
            "dz": ("DZD", "دينار"), "kw": ("KWD", "دينار")}

# أونصة تروي بالجرام — الثابت الذي تُحسب عليه أسعار الذهب كلها
OUNCE_G = 31.1034768


def _fx(code):
    d = _get_json("https://open.er-api.com/v6/latest/USD")
    rate = d["rates"].get(code)
    if not rate:
        raise ValueError("no rate for " + code)
    return rate, d.get("time_last_update_utc", "")[:16]


def gold_prices(country_key):
    """سعر الذهب بالعملة المحلية لكل عيار، محسوبًا من السعر العالمي."""
    cur = CURRENCY.get(country_key)
    if not cur:
        return None
    code, name = cur

    spot = _get_json("https://api.gold-api.com/price/XAU")["price"]
    rate, updated = _fx(code)
    per_gram_24 = spot / OUNCE_G * rate

    rows = []
    for karat in (24, 22, 21, 18, 14):
        rows.append({
            "city": "عيار " + str(karat),
            "times": {
                "سعر الجرام": "{:,.0f} {}".format(
                    per_gram_24 * karat / 24, name),
            },
        })

    return {
        "kind": "gold",
        "title": "سعر الذهب اليوم",
        "columns": ["سعر الجرام"],
        "rows": rows,
        "gregorian": updated,
        "hijri": "",
        "source": "السعر العالمي ({:,.0f}$ للأونصة) محوّلًا بسعر الصرف "
                  "الرسمي — والسعر المحلي في محلات الذهب يزيد عليه "
                  "المصنعية والعلاوة المحلية".format(spot),
        "source_url": "https://api.gold-api.com",
    }


def currency_rates(country_key):
    """أسعار العملات الرئيسة مقابل العملة المحلية."""
    cur = CURRENCY.get(country_key)
    if not cur:
        return None
    code, name = cur

    d = _get_json("https://open.er-api.com/v6/latest/USD")
    rates = d["rates"]
    local = rates.get(code)
    if not local:
        return None

    majors = [("الدولار الأمريكي", "USD"), ("اليورو", "EUR"),
              ("الجنيه الإسترليني", "GBP"), ("الريال السعودي", "SAR"),
              ("الدرهم الإماراتي", "AED"), ("الدينار الكويتي", "KWD")]

    rows = []
    for ar, c in majors:
        if c == code or c not in rates:
            continue
        # كم وحدة محلية تساوي وحدة واحدة من هذه العملة
        rows.append({
            "city": ar,
            "times": {"السعر": "{:,.2f} {}".format(local / rates[c], name)},
        })

    return {
        "kind": "currency",
        "title": "أسعار العملات اليوم",
        "columns": ["السعر"],
        "rows": rows,
        "gregorian": d.get("time_last_update_utc", "")[:16],
        "hijri": "",
        "source": "أسعار الصرف الرسمية — وسعر السوق قد يختلف",
        "source_url": "https://www.exchangerate-api.com",
    }


# أي ترند يستدعي أي مزوّد. المطابقة على عنوان الترند وحده.
MATCHERS = [
    (["اذان", "أذان", "مواقيت", "الصلاة", "صلاة", "الفجر", "المغرب",
      "العشاء", "الظهر", "العصر", "امساكية", "إمساكية"], prayer_times),
    (["ذهب", "الذهب", "عيار", "جرام الذهب", "سبيكة"], gold_prices),
    (["دولار", "الدولار", "يورو", "اليورو", "سعر الصرف", "العملات",
      "الاسترليني", "الإسترليني"], currency_rates),
]


def for_trend(title, country_key, normalize):
    """يعيد بيانات جاهزة لهذا الترند، أو None إن لم يكن ترند بيانات."""
    norm = normalize(title)
    for keywords, fn in MATCHERS:
        if any(normalize(k) in norm for k in keywords):
            try:
                return fn(country_key)
            except Exception as e:
                print("    ⚠ تعذّر جلب البيانات: " + type(e).__name__)
                return None
    return None


def is_data_trend(title, normalize):
    """هل هذا ترند بيانات (يحتاج أرقامًا لا سردًا)؟"""
    norm = normalize(title)
    return any(any(normalize(k) in norm for k in kws) for kws, _ in MATCHERS)


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    d = prayer_times("eg")
    print(d["title"], "—", d["gregorian"], "|", d["hijri"])
    print("المصدر:", d["source"])
    print()
    print("المدينة".ljust(14) + "".join(c.ljust(9) for c in d["columns"]))
    for r in d["rows"]:
        print(r["city"].ljust(14) +
              "".join(r["times"][c].ljust(9) for c in d["columns"]))
