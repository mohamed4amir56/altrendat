# -*- coding: utf-8 -*-
"""
طبقة كشف التكرار والدمج الذكي للترندات (Deduplication Layer).

المشكلة:
Google Trends يورد استعلامات مختلفة لنفس الموضوع في نفس اليوم:
1. استعلامات الطقس العامة: "الطقس"، "weather"، "weather tomorrow"، "حالة الطقس".
2. المباريات بلغات مختلفة: "australia vs brazil"، "أستراليا ضد البرازيل"، "australie - brésil".
3. أخبار متطابقة بمصادر مشتركة: ترند "وقود" وترند "وزارة البترول" لنفس البيان.
4. مقالات بعناوين شديدة التشابه تصف نفس الحدث الإخباري.

هذا الملف يوفر:
- كشف التكرار قبل الكتابة (في pipeline.py) لتوفير استهلاك الذكاء الاصطناعي.
- كشف التكرار عند بناء وتحديث صفحات الموقع والأرشيف (في site.py).
"""
import re
import unicodedata

_AR_LETTERS = "ء-ي"

_NORM_TRANS = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي",
})
_TASHKEEL = re.compile(r"[ً-ٓـ]")

STOP_WORDS = {
    # عربي
    "في", "من", "على", "الى", "إلى", "عن", "مع", "هذا", "هذه", "تم", "كان",
    "اليوم", "امس", "أمس", "غدا", "ان", "أن", "لا", "ما", "هو", "هي", "التي",
    "الذي", "الذين", "قبل", "بعد", "خلال", "حول", "نحو", "كل", "جميع", "بين",
    "ضد", "نادي", "فريق", "منتخب", "مباراة", "بطولة", "كأس", "دوري", "رسميا",
    # English
    "in", "on", "at", "to", "for", "of", "and", "the", "a", "an", "vs", "v",
    "with", "after", "before", "today", "tomorrow", "yesterday", "fc", "club",
    "team", "match", "cup", "league", "standings", "official", "faces", "against"
}

WEATHER_GENERIC = {
    "weather", "forecast", "طقس", "الطقس", "ارصاد", "الأرصاد", "الارصاد",
    "درجات الحرارة", "درجه الحراره", "حالة الطقس", "حاله الطقس", "شبورة", "شبوره"
}

# تطبيع أسماء الفرق والدول الأكثر شيوعاً للمطابقة الثنائية
TEAM_MAP = {
    "australia": "australia", "australie": "australia", "استراليا": "australia", "أستراليا": "australia",
    "brazil": "brazil", "brasil": "brazil", "bresil": "brazil", "البرازيل": "brazil", "برازيل": "brazil",
    "tunisia": "tunisia", "تونس": "tunisia",
    "uganda": "uganda", "اوغندا": "uganda", "أوغندا": "uganda",
    "senegal": "senegal", "السنغال": "senegal",
    "mozambique": "mozambique", "موزمبيق": "mozambique",
    "barcelona": "barcelona", "برشلونة": "barcelona", "برشلونه": "barcelona",
    "paris": "paris", "باريس": "paris",
    "portugal": "portugal", "البرتغال": "portugal",
    "wales": "wales", "ويلز": "wales",
    "netherlands": "netherlands", "هولندا": "netherlands",
    "germany": "germany", "المانيا": "germany", "ألمانيا": "germany",
    "saudi": "saudi", "السعودية": "saudi", "السعوديه": "saudi",
    "kuwait": "kuwait", "الكويت": "kuwait",
    "ghana": "ghana", "غانا": "ghana",
    "cote divoire": "ivory_coast", "côte divoire": "ivory_coast", "ساحل العاج": "ivory_coast", "كوت ديفوار": "ivory_coast",
    "japan": "japan", "اليابان": "japan",
    "uruguay": "uruguay", "اوروغواي": "uruguay", "أوروغواي": "uruguay",
    "denmark": "denmark", "الدنمارك": "denmark",
    "norway": "norway", "النرويج": "norway",
}

MATCH_SPLIT = re.compile(r"\s+(?:vs\.?|v\.?|ضد|–|-)\s+", re.I)


def is_arabic(text):
    return any("\u0600" <= c <= "\u06ff" for c in text)


def norm_text(text):
    """تنظيف وتطبيع النص للمقارنة واستخراج الكلمات الدلالية المهمة."""
    if not text:
        return ""
    # إزالة التشكيل وتوحيد الحروف
    text = _TASHKEEL.sub("", text).translate(_NORM_TRANS).lower()
    # استبدال علامات الترقيم بمسافات
    text = re.sub(r"[^\w\s]", " ", text)
    return text


def content_words(text):
    """استخراج الكلمات غير الشائعة التي لا يقل طولها عن 3 أحرف."""
    norm = norm_text(text)
    words = [w for w in norm.split() if len(w) >= 3 and w not in STOP_WORDS]
    return set(words)


def headline_similarity(h1, h2):
    """حساب نسبة تداخل الكلمات بين عنوانين."""
    w1 = content_words(h1)
    w2 = content_words(h2)
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / min(len(w1), len(w2))


def extract_match_teams(title):
    """استخراج وتطبيع طرفي المباراة إذا كان الترند لمباراة."""
    parts = MATCH_SPLIT.split(title.strip())
    if len(parts) == 2:
        t1, t2 = parts[0].strip(), parts[1].strip()
        # تنظيف كل طرف
        c1 = " ".join([w for w in norm_text(t1).split() if w not in STOP_WORDS])
        c2 = " ".join([w for w in norm_text(t2).split() if w not in STOP_WORDS])
        
        # محاولة رسم الخريطة المعيارية
        m1 = TEAM_MAP.get(c1, c1)
        m2 = TEAM_MAP.get(c2, c2)
        # فحص إن كانت إحدى الكلمات موجودة في الخريطة
        for k, v in TEAM_MAP.items():
            if k in c1.split():
                m1 = v
            if k in c2.split():
                m2 = v
        if m1 and m2:
            return frozenset([m1, m2])
    return None


def is_generic_weather(trend):
    """هل الاستعلام استعلام طقس عام لبلد؟ (وليس إعصاراً أو كارثة باسم خاص)."""
    title_norm = norm_text(trend.get("title", ""))
    cat = trend.get("category", "")
    is_weather_cat = (cat == "طقس")
    
    words = set(title_norm.split())
    has_weather_word = any(w in WEATHER_GENERIC for w in words)
    
    # استثناء العواصف/الأعاصير ذات الأسماء الخاصة
    has_specific_name = any(w in words for w in ["helene", "milton", "دانيال", "شاهين"])
    
    return (is_weather_cat or has_weather_word) and not has_specific_name


def shared_news_urls(t1, t2):
    """فحص إن كان الترندان يشاركان نفس روابط الأخبار."""
    u1 = {n.get("url") for n in t1.get("news", []) if n.get("url")}
    u2 = {n.get("url") for n in t2.get("news", []) if n.get("url")}
    return len(u1 & u2) > 0


def are_duplicates(t1, t2):
    """
    الحكم على ما إذا كان الترندان يمثلان نفس الموضوع أو نفس الخبر.
    يعيد (True/False, سبب_التطابق).
    """
    # 1. طقس عام في نفس اليوم لنفس البلد
    if is_generic_weather(t1) and is_generic_weather(t2):
        return True, "طقس عام مكرر لنفس اليوم"

    # 2. طرفا مباراة متطابقان
    teams1 = extract_match_teams(t1.get("title", ""))
    teams2 = extract_match_teams(t2.get("title", ""))
    if teams1 and teams2 and teams1 == teams2:
        return True, "مباراة رياضية لنفس الفريقين"

    # 3. مشاركة نفس رابط الخبر الإخباري
    if shared_news_urls(t1, t2):
        return True, "روابط مصادر إخبارية مشتركة"

    # 4. تشابه عناوين المقالات إن كانت مكتوبة (أكثر من 45% تداخل كلمات)
    h1 = (t1.get("article") or {}).get("headline", "")
    h2 = (t2.get("article") or {}).get("headline", "")
    if h1 and h2:
        sim = headline_similarity(h1, h2)
        if sim >= 0.45:
            return True, "تشابه صياغة العنوان بنسبة {:.0f}%".format(sim * 100)

    # 5. تشابه مباشر في عنوان الترند الأصلي (مثل australia vs brazil و australia - brasil)
    title_sim = headline_similarity(t1.get("title", ""), t2.get("title", ""))
    if title_sim >= 0.70:
        return True, "تشابه استعلام البحث بنسبة {:.0f}%".format(title_sim * 100)

    return False, ""


def merge_two_trends(primary, secondary, lang="ar"):
    """
    دمج ترند ثانوي في ترند رئيسي:
    - جمع أو تعظيم حجم البحث
    - دمج المصادر الإخبارية دون تكرار الروابط
    - حفظ البيانات الحية إن وجدت
    """
    res = dict(primary)
    
    # دمج أحجام البحث
    p_traf = primary.get("traffic_num", 0)
    s_traf = secondary.get("traffic_num", 0)
    combined_traf = p_traf + s_traf
    res["traffic_num"] = combined_traf
    res["traffic"] = "+{}".format(combined_traf) if combined_traf >= 100 else primary.get("traffic", "")

    # دمج الأخبار
    existing_urls = {n.get("url") for n in res.get("news", []) if n.get("url")}
    merged_news = list(res.get("news", []))
    for n in secondary.get("news", []):
        u = n.get("url")
        if u and u not in existing_urls:
            merged_news.append(n)
            existing_urls.add(u)
    res["news"] = merged_news

    # دمج البيانات
    if not res.get("data") and secondary.get("data"):
        res["data"] = secondary["data"]

    # إن كان الثانوي يملك مقالاً والرئيسي لا يملك
    if not res.get("article") and secondary.get("article"):
        res["article"] = secondary["article"]

    return res


def prefer_trend(t1, t2, lang="ar"):
    """
    تحديد أي الترندين أولى بأن يكون الأساس:
    1. من يملك مقالاً مكتوباً بالفعل أولى.
    2. التوافق اللغوي (عربي للدول العربية، إنجليزي للدولي).
    3. أعلى حجم بحث (traffic_num).
    """
    has_art1 = bool(t1.get("article"))
    has_art2 = bool(t2.get("article"))
    if has_art1 and not has_art2:
        return t1, t2
    if has_art2 and not has_art1:
        return t2, t1

    # التوافق اللغوي
    ar1 = is_arabic(t1.get("title", ""))
    ar2 = is_arabic(t2.get("title", ""))
    if lang == "ar":
        if ar1 and not ar2:
            return t1, t2
        if ar2 and not ar1:
            return t2, t1
    elif lang == "en":
        if not ar1 and ar2:
            return t1, t2
        if not ar2 and ar1:
            return t2, t1

    # الأعلى ترافيك
    if t1.get("traffic_num", 0) >= t2.get("traffic_num", 0):
        return t1, t2
    return t2, t1


def dedup_trends(trends, lang="ar"):
    """
    تصفية ودمج قائمة ترندات بالكامل لمنع أي تكرار للموضوع الواحد.
    يعيد قائمة نظيفة مرتبة حسب حجم البحث.
    """
    if not trends:
        return []

    # ترتيب مبدئي بالأعلى بحثاً
    pool = sorted(trends, key=lambda x: -x.get("traffic_num", 0))
    kept = []

    for t in pool:
        matched_idx = None
        for i, existing in enumerate(kept):
            is_dup, reason = are_duplicates(t, existing)
            if is_dup:
                matched_idx = i
                break

        if matched_idx is None:
            kept.append(dict(t))
        else:
            primary, secondary = prefer_trend(kept[matched_idx], t, lang=lang)
            merged = merge_two_trends(primary, secondary, lang=lang)
            kept[matched_idx] = merged

    # إعادة الترتيب النهائي بعد الدمج وجمع أحجام البحث
    kept.sort(key=lambda x: -x.get("traffic_num", 0))
    return kept
