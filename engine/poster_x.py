# -*- coding: utf-8 -*-
"""
أتمتة النشر على X (تويتر) — إطلاق التغريدات فور التقاط الترند.

لماذا X؟
1. خوارزميات جوجل تمتلك وصولاً لحظياً (Firehose) لتغريدات X، مما يجعل
   Googlebot يلتقط رابط المقال ويفهرسه أسرع بمرات من الروابط التقليدية.
2. جلب زوار لحظيين يبحثون عن الترند في نفس دقيقة اشتعاله.

المتطلبات:
  - مكتبة: requests requests-oauthlib
  - المتغيرات في GitHub Secrets:
      X_API_KEY
      X_API_SECRET
      X_ACCESS_TOKEN
      X_ACCESS_SECRET
"""
import json
import os
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


def build_tweet_text(trend, country_key, day, base):
    """صياغة نص التغريدة ليكون جذاباً، مختصراً، ومصحوباً بالهاشتاجات."""
    art = trend.get("article", {})
    headline = art.get("headline") or trend.get("title")
    slug = trend.get("title").replace(" ", "-")
    # محاولة استخراج slug من الكيان لو وُجد
    from urllib.parse import quote
    slug_encoded = quote(trend.get("title").replace(" ", "-"))

    # استيراد entities لو أمكن لدقة الـ slug
    try:
        sys.path.insert(0, os.path.join(ROOT, "engine"))
        import entities
        slug = entities.slugify(trend["title"])
    except Exception:
        slug = slug_encoded

    url = f"{base}/{country_key}/{day}/{slug}/"

    # وسم البلد
    flags = {"eg": "🇪🇬 #مصر", "sa": "🇸🇦 #السعودية", "world": "🌐 #World"}
    country_tag = flags.get(country_key, "#الترندات")

    # وسم الكلمات المفتاحية
    tags = art.get("tags", [])
    hashtags = [f"#{t.replace(' ', '_')}" for t in tags[:2] if len(t) <= 18]
    hash_str = " ".join(hashtags)

    is_en = country_key == "world"
    if is_en:
        text = f"🔥 Trending Now: {headline}\n\nRead full story & verified sources 👇\n{url}\n\n{country_tag} #Trends {hash_str}"
    else:
        text = f"🔴 ترند الآن | {headline}\n\nالتفاصيل والمصادر الرسمية كاملة 👇\n{url}\n\n{country_tag} #الترندات {hash_str}"

    # التأكد من عدم تجاوز حد الـ 280 حرف
    if len(text) > 275:
        available = 275 - len(url) - len(country_tag) - len(hash_str) - 30
        short_head = headline[:available].rsplit(" ", 1)[0] + "…"
        if is_en:
            text = f"🔥 Trending: {short_head}\n\nFull story 👇\n{url}\n\n{country_tag} {hash_str}"
        else:
            text = f"🔴 ترند الآن: {short_head}\n\nالتفاصيل 👇\n{url}\n\n{country_tag} {hash_str}"

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

    # اختيار الأحدث والأعلى بحثاً
    to_post.sort(key=lambda item: -item[3].get("traffic_num", 0))
    selected = to_post[:MAX_PER_RUN]

    print(f"🚀 بدء النشر التلقائي على X لـ {len(selected)} ترند...")
    for key, ckey, day, t in selected:
        tweet = build_tweet_text(t, ckey, day, base)
        print(f"\nنص التغريدة المقترحة:\n---\n{tweet}\n---")
        ok = post_to_x(tweet, api_key, api_secret, access_token, access_secret)
        if ok:
            posted.add(key)

    save_posted(posted)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
