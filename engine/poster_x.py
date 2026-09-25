# -*- coding: utf-8 -*-
"""
أتمتة النشر على X (تويتر) — إطلاق التغريدات فور التقاط الترند المحلي والعالمي.

الميزات:
1. صياغة تغريدات باللغة العربية للترندات المحلية (مصر/السعودية) بهاشتاجات عربية نشطة (#عاجل #مصر #الترندات).
2. صياغة تغريدات باللغة الإنجليزية للترندات العالمية (Worldwide) بهاشتاجات عالمية فيروسية
   (#BreakingNews #WorldNews #Trending #ALTRENDAT #US).
3. التوزيع المتوازن: تغريدة عربية + تغريدة عالمية في كل دورة تشغيل.
4. منع تكرار نشر أي ترند تم التغريد به مسبقاً.
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "x_posted.json")
MAX_PER_RUN = 2  # حد أقصى للتغريدات في كل تشغيلة لتجنب تجاوز الحصة المجانية


def load_posted():
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_posted(posted):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(posted)), f, ensure_ascii=False, indent=1)


def get_global_hashtags(trend):
    """توليد هاشتاجات عالمية قوية ومستهدفة للترندات العالمية."""
    cat = trend.get("category", "")
    cat_tags = {
        "Sports": ["#BreakingNews", "#Sports", "#Trending"],
        "Entertainment": ["#Breaking", "#Entertainment", "#Hollywood"],
        "Finance": ["#BreakingNews", "#Markets", "#Stocks", "#Economy"],
        "Places": ["#WorldNews", "#Breaking", "#News"],
        "Weather": ["#WeatherAlert", "#BreakingNews"],
    }
    tags_pool = cat_tags.get(cat, ["#BreakingNews", "#WorldNews", "#TrendingNow"])

    # تحويل عنوان الترند إلى هاشتاج CamelCase (مثلاً Cubs vs Red Sox -> #RedSox)
    raw_title = trend.get("title", "")
    words = re.findall(r"[A-Za-z0-9]+", raw_title)
    if words:
        clean_camel = "".join(w.capitalize() for w in words[:3])
        if 2 <= len(clean_camel) <= 22:
            tags_pool.append(f"#{clean_camel}")

    # وسوم المقال
    tags = trend.get("article", {}).get("tags", [])
    for t in tags[:2]:
        clean_words = re.findall(r"[A-Za-z0-9]+", t)
        if clean_words:
            t_camel = "".join(w.capitalize() for w in clean_words[:2])
            if 2 <= len(t_camel) <= 18:
                tags_pool.append(f"#{t_camel}")

    tags_pool.append("#ALTRENDAT")

    # إزالة التكرار مع الحفاظ على الترتيب
    seen = set()
    final_tags = []
    for tag in tags_pool:
        k = tag.lower()
        if k not in seen:
            seen.add(k)
            final_tags.append(tag)
    return final_tags[:5]


def get_arabic_hashtags(trend, country_key):
    """توليد هاشتاجات عربية نشطة للأخبار المحلية."""
    country_name = "#مصر" if country_key == "eg" else "#السعودية"
    tags_pool = ["#عاجل", country_name, "#الترندات", "#ترند_اليوم"]

    # هاشتاج عنوان الترند
    title_clean = re.sub(r"[^\w\s]", "", trend.get("title", "")).strip().replace(" ", "_")
    if 2 <= len(title_clean) <= 24:
        tags_pool.append(f"#{title_clean}")

    # وسوم المقال
    tags = trend.get("article", {}).get("tags", [])
    for t in tags[:2]:
        t_clean = re.sub(r"[^\w\s]", "", t).strip().replace(" ", "_")
        if 2 <= len(t_clean) <= 20:
            tags_pool.append(f"#{t_clean}")

    seen = set()
    final_tags = []
    for tag in tags_pool:
        if tag not in seen:
            seen.add(tag)
            final_tags.append(tag)
    return final_tags[:5]


def build_tweet_text(trend, country_key, day, base):
    """صياغة نص التغريدة ليكون جذاباً، مختصراً، ومصحوباً بأقوى الهاشتاجات."""
    art = trend.get("article", {})
    headline = art.get("headline") or trend.get("title")

    # استيراد entities لدقة الـ slug
    try:
        sys.path.insert(0, os.path.join(ROOT, "engine"))
        import entities
        slug = entities.slugify(trend["title"])
    except Exception:
        from urllib.parse import quote
        slug = quote(trend.get("title", "").replace(" ", "-"))

    url = f"{base}/{country_key}/{day}/{slug}/"
    is_en = country_key == "world"

    if is_en:
        hashtags = get_global_hashtags(trend)
        hash_str = " ".join(hashtags)
        text = (
            f"🔥 Trending Now: {headline}\n\n"
            f"Read full story & verified sources 👇\n"
            f"{url}\n\n"
            f"{hash_str}"
        )
    else:
        hashtags = get_arabic_hashtags(trend, country_key)
        hash_str = " ".join(hashtags)
        text = (
            f"🔴 ترند الآن | {headline}\n\n"
            f"التفاصيل والمصادر الرسمية كاملة 👇\n"
            f"{url}\n\n"
            f"{hash_str}"
        )

    # التحقق من سعة الحروف القصوى في X (280 حرف)
    if len(text) > 275:
        available = 275 - len(url) - len(hash_str) - 35
        short_head = headline[:max(20, available)].rsplit(" ", 1)[0] + "…"
        if is_en:
            text = f"🔥 Trending: {short_head}\n\nFull story 👇\n{url}\n\n{hash_str}"
        else:
            text = f"🔴 ترند الآن: {short_head}\n\nالتفاصيل 👇\n{url}\n\n{hash_str}"

    return text


def post_to_x(text, api_key, api_secret, access_token, access_secret):
    """إرسال التغريدة عبر X API v2 الرسمي."""
    try:
        from requests_oauthlib import OAuth1Session
    except ImportError:
        print("  ⚠️ مكتبة requests_oauthlib غير مثبتة — تخطي النشر على X.")
        return False

    client = OAuth1Session(
        api_key,
        client_secret=api_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_secret,
    )

    url = "https://api.twitter.com/2/tweets"
    payload = {"text": text}
    res = client.post(url, json=payload, timeout=20)

    if res.status_code in (200, 201):
        data = res.json()
        tweet_id = data.get("data", {}).get("id")
        print(f"  ✓ نُشرت التغريدة بنجاح! ID: {tweet_id}")
        return True
    else:
        print(f"  ✗ فشل النشر على X (كود {res.status_code}): {res.text}")
        return False


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "https://altrendat.com").rstrip("/")

    api_key = os.environ.get("X_API_KEY", "").strip()
    api_secret = os.environ.get("X_API_SECRET", "").strip()
    access_token = os.environ.get("X_ACCESS_TOKEN", "").strip()
    access_secret = os.environ.get("X_ACCESS_SECRET", "").strip()

    if not all([api_key, api_secret, access_token, access_secret]):
        print("ℹ️ مفاتيح X API غير مكتملة في البيئة — تخطي النشر التلقائي حتى إضافتها.")
        return 0

    trends_file = os.path.join(ROOT, "data", "trends.json")
    if not os.path.exists(trends_file):
        print("  لا يوجد ملف trends.json")
        return 0

    with open(trends_file, encoding="utf-8") as f:
        data = json.load(f)

    posted = load_posted()
    to_post = []

    # جمع الترندات الجديدة الجاهزة للنشر
    for country_key, cfg in data.items():
        day = cfg.get("day") or cfg.get("generated_at", "")[:10]
        for t in cfg.get("trends", []):
            if not t.get("publishable") or not t.get("article"):
                continue
            key = f"{country_key}|{day}|{t['title']}"
            if key not in posted:
                to_post.append((key, country_key, day, t))

    if not to_post:
        print("  لا توجد ترندات جديدة غير منشورة على X.")
        return 0

    # تنويع النشر: اختيار ترند عربي وترند عالمي لضمان تغطية كل الأقسام
    arabic_candidates = [item for item in to_post if item[1] in ("eg", "sa")]
    world_candidates = [item for item in to_post if item[1] == "world"]

    selected = []
    if arabic_candidates:
        arabic_candidates.sort(key=lambda item: -item[3].get("traffic_num", 0))
        selected.append(arabic_candidates[0])
    if world_candidates:
        world_candidates.sort(key=lambda item: -item[3].get("traffic_num", 0))
        selected.append(world_candidates[0])

    if len(selected) < MAX_PER_RUN:
        remaining = [item for item in to_post if item not in selected]
        remaining.sort(key=lambda item: -item[3].get("traffic_num", 0))
        selected.extend(remaining[:MAX_PER_RUN - len(selected)])

    print(f"🚀 بدء النشر التلقائي على X لـ {len(selected)} ترند (عربي + عالمي)...")
    for key, ckey, day, t in selected:
        tweet = build_tweet_text(t, ckey, day, base)
        print(f"\nنص التغريدة المقترحة [{ckey.upper()}]:\n---\n{tweet}\n---")
        ok = post_to_x(tweet, api_key, api_secret, access_token, access_secret)
        if ok:
            posted.add(key)

    save_posted(posted)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
