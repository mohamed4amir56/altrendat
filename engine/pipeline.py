# -*- coding: utf-8 -*-
"""
محرّك الترندات — طبقة البيانات.

يلتقط الترندات من Google Trends، ثم يثريها بما لا تعطيه Google:
نص الأخبار وصورها، مستخرجةً من وسوم og: في صفحات المصادر نفسها.
ثم يصنّفها ويحكم على صلاحيتها للنشر التلقائي.
"""
import concurrent.futures
import gzip
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HT = "{https://trends.google.com/trending/rss}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
TIMEOUT = 15
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==================================================
# 1. التصنيف — قواعد كلمات مفتاحية، مجانية وفورية
# ==================================================
CATEGORIES = [
    ("اقتصاد", "💰", "#f5c542", [
        "سعر", "أسعار", "دولار", "ذهب", "فضة", "بنك", "فائدة", "شهادات", "بورصة",
        "عملة", "جنيه", "ريال", "درهم", "دينار", "تموين", "دواجن", "لحوم", "سلع",
        "مخبز", "خبز", "وقود", "بنزين", "تضخم", "راتب", "معاش", "استثمار",
    ]),
    ("رياضة", "⚽", "#3ddc97", [
        "منتخب", "مباراة", "الأهلي", "الزمالك", "الهلال", "النصر", "الاتحاد",
        "دوري", "كأس", "لاعب", "هدف", "مدرب", "بطولة", "تصفيات", "ملعب",
        "محرز", "صلاح", "رونالدو", "ميسي", " vs ", "الترجي", "الرجاء",
    ]),
    ("تقنية", "💻", "#5aa9ff", [
        "gemini", "chatgpt", "شات جي بي تي", "ذكاء اصطناعي", "آيفون", "ايفون",
        "هاتف", "تطبيق", "جوجل", "google", "واتساب", "سامسونج", "أندرويد",
        "تحديث", "openai", "ماسنجر", "إنستغرام", "تيك توك",
    ]),
    ("فن ومشاهير", "🎬", "#c77dff", [
        "فيلم", "مسلسل", "حفل", "فنان", "فنانة", "ممثل", "ممثلة", "أغنية",
        "سينما", "مهرجان", "دراما", "مسرح", "كليب", "ألبوم", "برنامج",
    ]),
    ("ديني", "🕌", "#4dd0b1", [
        "صلاة", "أذان", "اذان", "رمضان", "حج", "عمرة", "دعاء", "سورة",
        "مسجد", "إفطار", "سحور", "زكاة", "عيد", "هجري",
    ]),
    ("تعليم", "🎓", "#ff9f68", [
        "امتحان", "امتحانات", "نتيجة", "ثانوية", "جامعة", "تنسيق", "مدرسة",
        "طلاب", "منحة", "منح", "دورة", "كلية", "دبلوم", "ترم",
    ]),
    ("طقس", "🌤️", "#7fd8ff", [
        "طقس", "أمطار", "حرارة", "عاصفة", "رياح", "الأرصاد",
    ]),
    ("أبراج وفلك", "🔮", "#b39ddb", [
        "برج", "أبراج", "فلكي", "حظك", "توقعات", "الأبراج",
    ]),
    ("فضول عام", "🐾", "#8fd694", [
        "سمكة", "حيوان", "طائر", "نبات", "ظاهرة", "اكتشاف", "غريب",
    ]),
]

# محظور من النشر التلقائي — خطر قانوني وأخلاقي حقيقي
BLOCKED_KEYWORDS = [
    "وفاة", "وفاته", "وفاتها", "مقتل", "قتل", "جريمة", "جثة", "انتحار",
    "حادث", "حريق", "غرق", "تشييع", "جنازة", "عزاء", "ضحايا", "قتيل",
    "محكمة", "حبس", "سجن", "اتهام", "متهم", "قضية", "نيابة",
    "تحرش", "اغتصاب", "مخدرات", "رشوة", "فضيحة", "طلاق", "خيانة",
    "مرض", "سرطان", "وباء", "فيروس", "مستشفى",
]


def _match(text):
    """يعيد أول فئة تطابق النص، أو None."""
    low = text.lower()
    for name, icon, color, keywords in CATEGORIES:
        for word in keywords:
            if word.lower() in low:
                return (name, icon, color, word.strip())
    return None


def classify(title, news_titles):
    """يعيد (الفئة، الأيقونة، اللون، سبب القرار، هل يُنشر تلقائيًا).

    ترتيب الفحص مقصود: عنوان الترند هو عبارة البحث نفسها، فهو وحده
    ما يحدد إن كان الموضوع شخصًا. لو صنّفنا من عناوين الأخبار أولًا،
    لمرّ اسم شخص لمجرد ورود كلمة "فنان" في خبر عنه — وهذه بالضبط
    الحالة التي يجب ألا تُنشر تلقائيًا.
    """
    haystack = (title + " " + " ".join(news_titles)).lower()

    # 1) الحظر أولًا، ويفحص كل شيء
    for word in BLOCKED_KEYWORDS:
        if word in haystack:
            return ("حوادث وقضايا", "⛔", "#ff6b6b",
                    "ورد لفظ حسّاس: " + word, False)

    # 2) تصنيف من عنوان الترند نفسه
    hit = _match(title)
    if hit:
        name, icon, color, word = hit
        return (name, icon, color, "العنوان يطابق: " + word, True)

    # 3) بلا تطابق في العنوان + عبارة عربية قصيرة = اسم شخص على الأرجح
    words = title.strip().split()
    if 1 <= len(words) <= 3 and re.search(r"[؀-ۿ]", title):
        return ("شخصية", "👤", "#ffd166",
                "اسم شخص على الأرجح — يحتاج مراجعة", False)

    # 4) وأخيرًا من عناوين الأخبار
    hit = _match(" ".join(news_titles))
    if hit:
        name, icon, color, word = hit
        return (name, icon, color, "الأخبار تطابق: " + word, True)

    return ("عام", "🌐", "#9aa4b2", "بلا تصنيف واضح", True)


# ==================================================
# 2. جلب الترندات الخام
# ==================================================
def _get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "ar,en;q=0.8",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw


def fetch_trends(geo):
    """يقرأ ترندات بلد واحد من Google Trends RSS."""
    raw = _get("https://trends.google.com/trending/rss?geo=" + geo)
    root = ET.fromstring(raw.decode("utf-8", errors="replace"))

    trends = []
    for item in root.findall(".//item"):
        def val(tag):
            el = item.find(HT + tag)
            return (el.text or "").strip() if el is not None and el.text else ""

        news = []
        for n in item.findall(HT + "news_item"):
            def nval(tag):
                el = n.find(HT + tag)
                return (el.text or "").strip() if el is not None and el.text else ""
            url = nval("news_item_url")
            if url:
                news.append({
                    "title": html.unescape(nval("news_item_title")),
                    "url": url,
                    "source": nval("news_item_source"),
                    "thumb": nval("news_item_picture"),
                })

        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        traffic = val("approx_traffic") or "0"
        trends.append({
            "title": html.unescape(title),
            "traffic": traffic,
            "traffic_num": int(re.sub(r"\D", "", traffic) or 0),
            "published": item.findtext("pubDate") or "",
            "image": val("picture"),
            "image_source": val("picture_source"),
            "news": news,
        })
    return trends


# ==================================================
# 3. الإثراء — استخراج ما لا تعطيه Google
# ==================================================
def _og_patterns(prop):
    """المواقع تكتب الوسم بترتيبين مختلفين — نطابق الاثنين."""
    return [
        re.compile(
            r'<meta[^>]+property=["\']og:' + prop +
            r'["\'][^>]*content=["\'](.*?)["\']', re.I | re.S),
        re.compile(
            r'<meta[^>]+content=["\'](.*?)["\'][^>]*property=["\']og:' +
            prop + r'["\']', re.I | re.S),
    ]


OG = {
    "og_title": _og_patterns("title"),
    "og_desc": _og_patterns("description"),
    "og_image": _og_patterns("image"),
}


def fetch_og(url):
    """يجلب صفحة الخبر ويستخرج og:description — النص الذي لا توفره Google."""
    out = {"og_title": "", "og_desc": "", "og_image": "", "ok": False}
    try:
        page = _get(url, timeout=12)[:400_000].decode("utf-8", errors="replace")
        for key, patterns in OG.items():
            for pat in patterns:
                m = pat.search(page)
                if m:
                    out[key] = html.unescape(m.group(1)).strip()
                    break
        out["ok"] = bool(out["og_desc"] or out["og_title"])
    except Exception as e:
        out["error"] = type(e).__name__
    return out


def enrich(trends, workers=12):
    """يثري كل الأخبار بالتوازي — 30 صفحة في ثوانٍ بدل دقائق."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = [(n, pool.submit(fetch_og, n["url"]))
                for t in trends for n in t["news"]]
        for news_item, future in jobs:
            try:
                news_item.update(future.result())
            except Exception:
                news_item["ok"] = False
    return trends


# ==================================================
# 4. التشغيل
# ==================================================
def build(country_key, cfg):
    print("  ↓ جلب ترندات " + cfg["name_ar"] + " ...")
    trends = fetch_trends(cfg["trends_geo"])
    print("  ✓ " + str(len(trends)) + " ترند")

    n_pages = sum(len(t["news"]) for t in trends)
    print("  ↓ إثراء " + str(n_pages) + " صفحة خبر بالتوازي ...")
    enrich(trends)
    ok = sum(1 for t in trends for n in t["news"] if n.get("ok"))
    print("  ✓ استُخرج النص من " + str(ok) + " صفحة")

    for t in trends:
        cat, icon, color, reason, publishable = classify(
            t["title"], [n["title"] for n in t["news"]])
        t.update(category=cat, icon=icon, color=color,
                 reason=reason, publishable=publishable)
        # صفحة بلا مصدرين على الأقل = صفحة رقيقة، لا تُنشر
        if publishable and len([n for n in t["news"] if n.get("ok")]) < 2:
            t["publishable"] = False
            t["reason"] = "مصادر غير كافية (أقل من خبرين بنص)"

    return {
        "country": country_key,
        "country_name": cfg["name_ar"],
        "flag": cfg["flag"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trends": trends,
    }


def main():
    cfg_path = os.path.join(ROOT, "engine", "countries.json")
    with open(cfg_path, encoding="utf-8") as f:
        countries = json.load(f)

    only = sys.argv[1] if len(sys.argv) > 1 else None
    results = {}
    for key, cfg in countries.items():
        if only and key != only:
            continue
        if not only and not cfg.get("enabled"):
            continue
        print("\n" + cfg["flag"] + "  " + cfg["name_ar"])
        try:
            results[key] = build(key, cfg)
        except Exception as e:
            print("  ✗ فشل: " + type(e).__name__ + ": " + str(e))

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "trends.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total = sum(len(r["trends"]) for r in results.values())
    pub = sum(1 for r in results.values()
              for t in r["trends"] if t["publishable"])
    print("\n" + "=" * 46)
    print("  الإجمالي: " + str(total) + " ترند من " + str(len(results)) + " بلد")
    print("  صالح للنشر التلقائي: " + str(pub))
    print("  يحتاج مراجعة بشرية: " + str(total - pub))
    print("  حُفظ في: data/trends.json")
    print("=" * 46)


if __name__ == "__main__":
    main()
