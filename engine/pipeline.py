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
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import providers  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HT = "{https://trends.google.com/trending/rss}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
TIMEOUT = 15
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# # ==================================================
# 1. التصنيف — قواعد كلمات مفتاحية، مجانية وفورية
# ==================================================
CATEGORIES = [
    ("طقس", "🌤️", "#7fd8ff", [
        "طقس", "أمطار", "حرارة", "عاصفة", "رياح", "الأرصاد",
        "weather", "forecast", "storm", "hurricane", "tornado", "snow",
        "blizzard", "heatwave", "flood", "flooding", "nor'easter", "wind", "winds",
    ]),
    ("اقتصاد", "💰", "#f5c542", [
        "سعر", "أسعار", "دولار", "ذهب", "فضة", "بنك", "فائدة", "شهادات", "بورصة",
        "عملة", "جنيه", "ريال", "درهم", "دينار", "تموين", "دواجن", "لحوم", "سلع",
        "مخبز", "خبز", "وقود", "بنزين", "تضخم", "راتب", "معاش", "استثمار",
        "stock", "stocks", "price", "prices", "inflation", "fed rate", "interest rate",
        "crypto", "bitcoin", "dollar", "gold price", "market", "economy", "bank", "dow",
        "nasdaq", "s&p", "earnings", "revenue", "tariff", "tariffs",
    ]),
    ("رياضة", "⚽", "#3ddc97", [
        "منتخب", "مباراة", "الأهلي", "الزمالك", "الهلال", "النصر", "الاتحاد",
        "دوري", "كأس", "لاعب", "هدف", "مدرب", "بطولة", "تصفيات", "ملعب",
        "محرز", "صلاح", "رونالدو", "ميسي", " vs ", "الترجي", "الرجاء",
        "نادي", "النادي", "فريق", "الإسماعيلي", "بيراميدز", "سموحة",
        "المقاولون", "إنبي", "الزوراء", "الشرطة", "الوحدة", "السد",
        "vs", "nba", "nfl", "mlb", "nhl", "premier league", "champions league",
        "cup", "match", "game", "score", "scores", "fc", "club", "coach", "player",
        "tournament", "lakers", "celtics", "warriors", "chiefs", "ufc", "wwe",
        "football", "basketball", "baseball", "soccer", "tennis", "phillies", "magic number",
    ]),
    ("تقنية", "💻", "#5aa9ff", [
        "gemini", "chatgpt", "شات جي بي تي", "ذكاء اصطناعي", "آيفون", "ايفون",
        "هاتف", "تطبيق", "جوجل", "google", "واتساب", "سامسونج", "أندرويد",
        "تحديث", "openai", "ماسنجر", "إنستغرام", "تيك توك",
        "ai", "apple", "iphone", "ios", "microsoft", "nvidia", "meta",
        "android", "samsung", "app", "update", "software", "tech", "gadget",
        "cyber", "deepseek", "anthropic", "claude",
    ]),
    ("فن ومشاهير", "🎬", "#c77dff", [
        "فيلم", "مسلسل", "حفل", "فنان", "فنانة", "ممثل", "ممثلة", "أغنية",
        "سينما", "مهرجان", "دراما", "مسرح", "كليب", "ألبوم", "برنامج",
        "movie", "film", "trailer", "actor", "actress", "singer", "album",
        "song", "concert", "series", "season", "episode", "grammy", "oscar",
        "emmy", "billboard", "hollywood", "celebrity", "star", "box office",
        "lingerie", "model", "fashion", "dating", "boyfriend", "girlfriend", "romance",
    ]),
    ("ديني", "🕌", "#4dd0b1", [
        "صلاة", "أذان", "اذان", "رمضان", "حج", "عمرة", "دعاء", "سورة",
        "مسجد", "إفطار", "سحور", "زكاة", "عيد", "هجري",
        "prayer", "easter", "christmas", "ramadan", "eid", "church", "mosque",
    ]),
    ("تعليم", "🎓", "#ff9f68", [
        "امتحان", "امتحانات", "نتيجة", "ثانوية", "جامعة", "تنسيق", "مدرسة",
        "طلاب", "منحة", "منح", "دورة", "كلية", "دبلوم", "ترم",
        "university", "college", "school", "exam", "admissions", "scholarship", "ranking",
    ]),
    ("أبراج وفلك", "🔮", "#b39ddb", [
        "برج", "أبراج", "فلكي", "حظك", "توقعات", "الأبراج",
        "horoscope", "zodiac", "astrology",
    ]),
    ("فضول عام", "🐾", "#8fd694", [
        "سمكة", "حيوان", "طائر", "نبات", "ظاهرة", "اكتشاف", "غريب",
        "animal", "species", "space", "nasa", "discovery", "eclipse", "comet", "planet",
    ]),
    ("دول وأماكن", "🗺️", "#79c0ff", [
        "مصر", "السعودية", "الإمارات", "المغرب", "الجزائر", "تونس",
        "ليبيا", "السودان", "الأردن", "لبنان", "سوريا", "العراق",
        "الكويت", "قطر", "البحرين", "عُمان", "اليمن", "فلسطين",
        "فرنسا", "أمريكا", "بريطانيا", "ألمانيا", "تركيا", "إيران",
        "الصين", "روسيا", "إسبانيا", "إيطاليا", "اليابان", "الهند",
        "القاهرة", "الرياض", "جدة", "دبي", "الإسكندرية", "مكة",
        "usa", "california", "texas", "florida", "new york", "china",
        "russia", "japan", "france", "germany", "canada", "mexico",
    ]),
]

LOCAL_CATEGORIES = {
    "طقس": ["طقس {country}", "الطقس غدا {country}", "الأرصاد {country}"],
}

# محظور من النشر التلقائي — خطر قانوني وأخلاقي وحماية لحساب AdSense
BLOCKED_KEYWORDS = [
    "وفاة", "وفاته", "وفاتها", "مقتل", "قتل", "جريمة", "جثة", "انتحار",
    "حادث", "حريق", "غرق", "تشييع", "جنازة", "عزاء", "ضحايا", "قتيل",
    "محكمة", "حبس", "سجن", "اتهام", "متهم", "قضية", "نيابة",
    "تحرش", "اغتصاب", "مخدرات", "رشوة", "فضيحة", "طلاق", "خيانة",
    "مرض", "سرطان", "وباء", "فيروس", "مستشفى", "حوادث",
    "قبض", "اعتقال", "توقيف", "احتجاز",
    # English sensitive terms
    "death", "dies", "died", "dead", "murder", "murdered", "killed", "killing",
    "suicide", "crime", "body", "fatal", "crash", "accident", "shooting", "shot",
    "drowning", "funeral", "victims", "court", "trial", "arrest", "arrested",
    "custody", "jail", "prison", "lawsuit", "sued", "rape", "assault", "sexual",
    "drugs", "overdose", "scandal", "cancer", "epidemic",
]

# إضافي للأشخاص وحدهم
PERSON_BLOCKED = [
    "شائعة", "شائعات", "مزاعم", "ادعاءات", "تسريب", "تسريبات", "مسرب",
    "rumor", "rumors", "allegation", "allegations", "leak", "leaks", "leaked",
]


_AR = "ء-ي"
_CACHE = {}

_NORM = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي",
})
_TASHKEEL = re.compile(r"[ً-ٓـ]")


def normalize(text):
    """يوحّد صور الحروف العربية ويزيل التشكيل، للمقارنة فقط."""
    return _TASHKEEL.sub("", text).translate(_NORM).lower()


def _has_arabic(text):
    return bool(re.search(r"[؀-ۿ]", text))


def _word_re(word):
    """يبني نمطًا يطابق الكلمة بدقة بالعربية والإنجليزية."""
    if word not in _CACHE:
        clean = word.strip()
        if _has_arabic(clean):
            _CACHE[word] = re.compile(
                re.escape(normalize(clean)) + "(?![" + _AR + "])", re.I)
        else:
            _CACHE[word] = re.compile(
                r"(?<!['’\w])" + re.escape(clean.lower()) + r"(?!['’\w])", re.I)
    return _CACHE[word]


_BLOCK_CACHE = {}


def _blocked_re(word):
    """نمط الكلمة الحسّاسة: يمنع التطابقات الكاذبة بالعربية والإنجليزية."""
    if word not in _BLOCK_CACHE:
        clean = word.strip()
        if _has_arabic(clean):
            _BLOCK_CACHE[word] = re.compile(
                "(?<![" + _AR + "])[وفبلكس]{0,2}(?:ال)?[يتن]?" +
                re.escape(normalize(clean)) +
                "(?:ها|هم|هن|ات|ان|ين|ون|وا|نا|ه|ي|ا|ت|ك)?(?![" + _AR + "])")
        else:
            _BLOCK_CACHE[word] = re.compile(
                r"(?<!['’\w])" + re.escape(clean.lower()) + r"(?!['’\w])", re.I)
    return _BLOCK_CACHE[word]


def blocked_hit(text, words=None):
    """أول لفظ حسّاس في النص، أو None."""
    norm = normalize(text)
    for word in (words or BLOCKED_KEYWORDS):
        if _blocked_re(word).search(norm):
            return word
    return None


def _match(text):
    """يعيد أول فئة تطابق النص، أو None."""
    norm = normalize(text)
    for name, icon, color, keywords in CATEGORIES:
        for word in keywords:
            if _word_re(word).search(norm):
                return (name, icon, color, word.strip())
    return None


def classify(title, news_titles):
    """يعيد (الفئة، الأيقونة، اللون، سبب القرار، هل يُنشر تلقائيًا)."""
    # 1) الحظر أولًا، ويفحص كل شيء
    word = blocked_hit(title + " " + " ".join(news_titles))
    if word:
        return ("حوادث وقضايا", "⛔", "#ff6b6b",
                "ورد لفظ حسّاس: " + word, False)

    # 2) تصنيف من عنوان الترند نفسه
    hit = _match(title)
    if hit:
        name, icon, color, word = hit
        return (name, icon, color, "العنوان يطابق: " + word, True)

    # 3) بلا تطابق في العنوان + عبارة قصيرة = اسم شخص على الأرجح
    words = title.strip().split()
    if 1 <= len(words) <= 3:
        if _has_arabic(title) or all(w[0].isupper() for w in words if w.isalpha()):
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
                    val = html.unescape(m.group(1)).strip()
                    if key == "og_image":
                        # استبعاد الروابط غير الصالحة أو التي تحوي وسوماً متسربة
                        if not val.startswith(("http://", "https://")) or any(c in val for c in ("<", ">", "\n", "\r")):
                            continue
                    out[key] = val
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


def title_matched(title):
    """هل عرفنا موضوع الترند من عنوانه وحده؟"""
    return _match(title) is not None


def _sources_mention(trend, min_len=3):
    """هل تذكر المصادر موضوع الترند فعلًا؟

    تحذير: هذا فحص لفظي، والصحافة تعيد الصياغة. ترند "موعد اذان
    المغرب" رُفض بهذا الفحص رغم أن مصادره الثلاثة عن "مواقيت الصلاة"
    — نفس الموضوع بألفاظ أخرى. لذلك لا يُستدعى إلا حين يكون الموضوع
    مجهولًا لنا أصلًا (انظر شرط الاستدعاء في build).
    """
    haystack = " ".join(
        normalize(n.get("title", "") + " " + n.get("og_desc", "") + " " +
                  n.get("og_title", ""))
        for n in trend["news"] if n.get("ok"))
    if not haystack.strip():
        return False

    words = [w for w in re.split(r"\W+", trend["title"], flags=re.UNICODE)
             if len(w) >= min_len]
    if not words:                      # عنوان قصير جدًا للحكم عليه
        return True
    return any(normalize(w) in haystack for w in words)


def mentions_place(text, cfg):
    """هل يذكر النص البلد أو إحدى مدنه؟ (places في countries.json)"""
    norm = normalize(text)
    return any(_word_re(p).search(norm)
               for p in cfg.get("places") or [cfg["name_ar"]])


_ALL_COUNTRIES = None


def _all_countries():
    global _ALL_COUNTRIES
    if _ALL_COUNTRIES is None:
        with open(os.path.join(ROOT, "engine", "countries.json"),
                  encoding="utf-8") as f:
            _ALL_COUNTRIES = json.load(f)
    return _ALL_COUNTRIES


def only_here(text, cfg):
    """يذكر هذا البلد ولا يذكر بلدًا آخر من countries.json.

    ذِكر البلد وحده لا يكفي: خبر عنوانه "أخبار مصر : طقس السعودية.. أمطار
    في جازان وعسير" يذكر مصر في اسم القسم، وهو عن السعودية.
    """
    return mentions_place(text, cfg) and not any(
        mentions_place(text, other) for other in _all_countries().values()
        if other.get("code") != cfg.get("code"))


def about_here(news_item, cfg):
    """هل الخبر عن هذا البلد؟ يُحكم بموضوعه لا بموقع ناشره: "صدى البلد"
    المصري يكتب عن طقس السعودية، وخبره عن السعودية لا عن مصر."""
    return only_here(" ".join([
        news_item.get("title", ""), news_item.get("og_title", ""),
        news_item.get("og_desc", "")]), cfg)


def fetch_local_news(query, cfg, max_age_hours=48):
    """أخبار البلد نفسه من Bing News، الأحدث أولًا.

    لا Google News: روابطه مشفّرة خلف news.google.com ولا تفتح صفحة
    الخبر، فلا نستخرج منها og: ولا نجد نصًا نكتب منه. Bing يضع رابط
    المقال الحقيقي في معامل url=. والوسوم الإضافية (المصدر والصورة)
    في نطاق أسماء عنوانه هو رابط البحث نفسه، فتُقرأ باسمها المحلي.
    """
    url = ("https://www.bing.com/news/search?format=rss&setlang=ar&cc=" +
           cfg["code"] + "&q=" + urllib.parse.quote(query))
    root = ET.fromstring(_get(url).decode("utf-8", errors="replace"))

    now = datetime.now(timezone.utc)
    items = []
    for item in root.findall(".//item"):
        link = html.unescape(item.findtext("link") or "")
        real = urllib.parse.parse_qs(
            urllib.parse.urlparse(link).query).get("url", [""])[0]
        if not real.startswith("http"):
            continue
        extra = {c.tag.rsplit("}", 1)[-1]: (c.text or "").strip() for c in item}
        try:
            when = parsedate_to_datetime(item.findtext("pubDate") or "")
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if now - when > timedelta(hours=max_age_hours):
                continue                      # طقس الأسبوع الماضي لا يجيب أحدًا
        except (TypeError, ValueError):
            when = None
        items.append({
            "title": html.unescape(item.findtext("title") or "").strip(),
            "url": real,
            "source": extra.get("Source", ""),
            "thumb": extra.get("Image", ""),
            "_desc": html.unescape(item.findtext("description") or ""),
            "_when": when,
        })

    items.sort(key=lambda n: n["_when"] or now - timedelta(days=365), reverse=True)
    return items


def localize(trend, cfg):
    """يستبدل بمصادر عن بلد آخر أخبارَ البلد نفسه، أو يوقف الترند."""
    queries = [q.format(country=cfg["name_ar"])
               for q in LOCAL_CATEGORIES[trend["category"]]]
    print("  ↻ \"" + trend["title"] + "\" مصادره عن بلد آخر — بحث: " +
          " / ".join(queries))
    found, seen = [], set()
    for query in queries:
        try:
            for n in fetch_local_news(query, cfg):
                if n["url"] not in seen:
                    seen.add(n["url"])
                    found.append(n)
        except Exception as e:
            print("    ✗ " + query + ": " + type(e).__name__)
    found.sort(key=lambda n: n["_when"] or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)

    local = [n for n in found
             if only_here(n["title"] + " " + n["_desc"], cfg)][:3]
    for n in local:
        n.pop("_desc", None)
        n.pop("_when", None)
    enrich([{"news": local}])
    # يُعاد الحكم بعد قراءة الصفحة: og:description أطول من ملخص Bing
    # وقد يكشف أن الخبر عن بلد آخر.
    ok = [n for n in local if n.get("ok") and about_here(n, cfg)]

    if len(ok) < 2:
        trend["publishable"] = False
        trend["reason"] = "موضوع محلي ومصادره عن بلد آخر، ولا أخبار محلية كافية"
        print("    ✗ لا أخبار محلية كافية — لن يُنشر")
        return

    trend["news"] = ok
    trend["localized"] = True           # writer يعيد مقالًا كُتب قبل الاستبدال
    # صورة الترند من Google كانت لخبر البلد الآخر؛ تُستبدل بصورة محلية.
    pic = next((n for n in ok if n.get("og_image")), None)
    trend["image"] = pic["og_image"] if pic else ""
    trend["image_source"] = pic.get("source", "") if pic else ""
    trend["reason"] += " · مصادر محلية بدل مصادر عن بلد آخر"
    print("    ✓ " + " · ".join(n["source"] or "?" for n in ok))


# ==================================================
# 4. التشغيل
# ==================================================
def local_now(cfg):
    """الوقت بتوقيت البلد لا بتوقيت الخادم.

    اليوم في الروابط كان يُؤخذ من UTC، فخبر كُتب في القاهرة ليلة 23
    سبتمبر خرج برابط 2026-09-22 ونصّه يقول "23 سبتمبر". القارئ يعيش
    بتوقيت بلده، واليوم يجب أن يبدأ عنده لا في لندن.
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(cfg["tz"]))
    except Exception:
        # ويندوز بلا حزمة tzdata لا يعرف أسماء المناطق — إزاحة ثابتة
        # تكفي للتجربة المحلية، وخادم Linux يملك القاعدة كاملة.
        return datetime.now(timezone(timedelta(hours=cfg.get("utc_offset", 3))))


def fetch_with_retry(geo, tries=3):
    """Google ترفض أحيانًا طلبًا واحدًا من خوادم GitHub؛ المحاولة الثانية
    بعد ثوانٍ تنجح غالبًا. والقائمة الفارغة فشل أيضًا لا "لا ترندات"."""
    err = None
    for i in range(tries):
        try:
            trends = fetch_trends(geo)
            if trends:
                return trends
            err = ValueError("قائمة فارغة")
        except Exception as e:
            err = e
        if i < tries - 1:
            print("  ⟳ محاولة " + str(i + 2) + " بعد خطأ: " + type(err).__name__)
            time.sleep(5 * (i + 1))
    raise err


def person_ok(trend):
    """هل يُكتب عن هذا الاسم؟ (نعم/لا، السبب)

    كان كل اسم شخص يُحجب، وهو ما حجب نحو ثلث الترندات: رئيس دولة، مدرب
    فريق، فنان. والاسم وحده ليس الخطر؛ الخطر أن يكون الموضوع اتهامًا أو
    وفاة أو مرضًا أو حياة خاصة، أو فردًا عاديًا لا يعرفه أحد. لذلك تُقبل
    الشخصية حين تجتمع ثلاثة شروط:
      1) مصدران على الأقل بنص،
      2) الاسم يرد في مصدرين على الأقل — كاملًا أو بلقبه الأخير، لأن
         الصحف تكتب "السيسي" لا "عبد الفتاح السيسي"،
      3) لا لفظ حسّاس في نص أي مصدر — لا في العناوين وحدها كما في
         الفحص العام، بل في الملخصات أيضًا لأن الاتهام يُذكر فيها.
    ثم يحكم الكاتب نفسه في writer.py، فيمتنع إن كان الشخص فردًا عاديًا.

    ملاحظة: الفحص يلتقط أيضًا ما ليس شخصًا ("طائرة"، "اذكار الصباح")
    لأن أي عبارة عربية قصيرة بلا فئة تُعدّ اسمًا. وهذا لا يضرّ: هذه
    مواضيع سليمة تمرّ بالشروط نفسها.
    """
    ok = [n for n in trend["news"] if n.get("ok")]
    if len(ok) < 2:
        return False, "شخصية بأقل من مصدرين"

    texts = [n.get("title", "") + " " + n.get("og_title", "") + " " +
             n.get("og_desc", "") for n in ok]
    joined = " ".join(texts)
    hit = blocked_hit(joined) or blocked_hit(joined, PERSON_BLOCKED)
    if hit:
        return False, "شخصية ورد في مصادرها لفظ حسّاس: " + hit

    name = normalize(trend["title"].strip())
    parts = name.split()
    surname = parts[-1] if len(parts) > 1 and len(parts[-1]) >= 4 else None

    def mentions_name(text):
        text = normalize(text)
        if name in text:
            return True
        if not surname:
            return False
        if _has_arabic(surname):
            return bool(re.search(
                "(?<![" + _AR + "])(?:ال)?" + re.escape(surname) +
                "(?![" + _AR + "])", text))
        return bool(re.search(r"\b" + re.escape(surname) + r"\b", text, re.I))

    mentions = sum(1 for x in texts if mentions_name(x))
    if mentions < 2:
        return False, "شخصية لا يرد اسمها في مصدرين"
    return True, ("شخصية: " + str(mentions) + " مصادر تذكر الاسم "
                  "بلا ألفاظ حسّاسة")


def build(country_key, cfg):
    print("  ↓ جلب ترندات " + cfg["name_ar"] + " ...")
    trends = fetch_with_retry(cfg["trends_geo"])
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

        # اسم شخص: يُقبل بشروط بدل الحجب المطلق (انظر person_ok).
        if cat == "شخصية" and not publishable:
            allowed, why = person_ok(t)
            t["reason"] = why
            if allowed:
                t["publishable"] = True
                t["person"] = True     # writer يطبّق قواعد الأشخاص ويحق له الامتناع

        # موضوع محلي بطبعه: مصادره يجب أن تتحدث عن هذا البلد (لا يسري على القسم العالمي).
        if country_key != "world" and t["publishable"] and t["category"] in LOCAL_CATEGORIES:
            t["local_only"] = True
            if not any(about_here(n, cfg) for n in t["news"] if n.get("ok")):
                localize(t, cfg)

        # صفحة بلا مصدرين على الأقل = صفحة رقيقة، لا تُنشر
        if t["publishable"] and len([n for n in t["news"] if n.get("ok")]) < 2:
            t["publishable"] = False
            t["reason"] = "مصادر غير كافية (أقل من خبرين بنص)"

        # ترند بيانات: أحضر الأرقام من مصدرها بدل انتظارها من نص خبر.
        if t["publishable"]:
            data = providers.for_trend(t["title"], country_key, normalize)
            if data:
                t["data"] = data
                t["reason"] += " · بيانات حيّة مرفقة"
            elif providers.is_data_trend(t["title"], normalize):
                # ترند يحتاج أرقامًا ولا مزوّد له: السرد وحده يخرج
                # مقالًا يدور حول الموضوع بلا أن يعطي القارئ ما يريد.
                t["publishable"] = False
                t["reason"] = "ترند بيانات بلا مزوّد — لا يُكتب سردًا"

        # ولا تُنشر إن كانت المصادر لا تتحدث عن الموضوع أصلًا.
        # حدث فعلًا: كُتب مقال عن اسم لم تذكره أي من مصادره، فخرج
        # النص يقول "المصادر المتاحة لا تذكر الاسم" — صفحة بلا قيمة
        # دُفع ثمنها. هذا الفحص يوقفها قبل الإنفاق لا بعده.
        #
        # ويُطبَّق فقط على ما لم نعرف موضوعه من عنوانه: فحين يطابق
        # العنوان فئةً نعرف عمّ يتحدث، ولا حاجة لتطابق لفظي مع مصادر
        # تعيد الصياغة بطبعها.
        if (t["publishable"] and not title_matched(t["title"])
                and not _sources_mention(t)):
            t["publishable"] = False
            t["reason"] = "المصادر لا تذكر الموضوع — تحتاج مراجعة"

    return {
        "country": country_key,
        "country_name": cfg["name_ar"],
        "name_en": cfg.get("name_en", "Worldwide"),
        "lang": cfg.get("lang", "ar"),
        "flag": cfg["flag"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "day": local_now(cfg).strftime("%Y-%m-%d"),
        "trends": trends,
    }


def main():
    cfg_path = os.path.join(ROOT, "engine", "countries.json")
    with open(cfg_path, encoding="utf-8") as f:
        countries = json.load(f)

    out_path = os.path.join(ROOT, "data", "trends.json")
    prev = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = {}

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
            # فشل الجلب لا يمحو البلد. حدث فعلًا: رفضت Google طلب مصر
            # مرة واحدة، فخرجت مصر من trends.json، فاختفت صفحتها من
            # الموقع وصار /eg/ خطأ 404. آخر نسخة ناجحة أصدق من لا شيء.
            if key in prev:
                results[key] = prev[key]
                results[key]["stale"] = True
                print("  ↺ أُبقيت آخر نسخة ناجحة: " +
                      prev[key]["generated_at"][:16] + " UTC")

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # اللقطة اليومية لا تُحفظ هنا: المقالات والكروت تُضاف بعد هذه
    # الخطوة، فحفظها الآن يؤرشف ترندات بلا محتوى. الأرشفة تتم في
    # site.py بعد اكتمال السلسلة — انظر archive_today هناك.

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
