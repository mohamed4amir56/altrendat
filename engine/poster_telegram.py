# -*- coding: utf-8 -*-
"""
أتمتة النشر على تليجرام (Telegram) — إرسال الكروت والمقالات لحظياً مجاناً 100%.

الميزات:
1. مجاني للأبد بدون أي قيود أو اشتراكات شهرية أو رسوم للروابط.
2. إرسال كارت الترند المصمم تلقائياً كصورة مع شرح جذاب ورابط مباشر للمقال.
3. التوزيع المتوازن: ترند محلي عربي (مصر/السعودية) + ترند عالمي (Worldwide) في كل دورة تشغيل.
4. منع تكرار نشر أي ترند تم إرساله مسبقاً عبر حفظ السجل في data/telegram_posted.json.
"""
import html
import json
import os
import re
import sys

try:
    import requests
except ImportError:
    requests = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "telegram_posted.json")
MAX_PER_RUN = 2  # ترند عربي + ترند عالمي في كل تشغيلة


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

    raw_title = trend.get("title", "")
    words = re.findall(r"[A-Za-z0-9]+", raw_title)
    if words:
        clean_camel = "".join(w.capitalize() for w in words[:3])
        if 2 <= len(clean_camel) <= 22:
            tags_pool.append(f"#{clean_camel}")

    tags = trend.get("article", {}).get("tags", [])
    for t in tags[:2]:
        clean_words = re.findall(r"[A-Za-z0-9]+", t)
        if clean_words:
            t_camel = "".join(w.capitalize() for w in clean_words[:2])
            if 2 <= len(t_camel) <= 18:
                tags_pool.append(f"#{t_camel}")

    tags_pool.append("#ALTRENDAT")

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

    title_clean = re.sub(r"[^\w\s]", "", trend.get("title", "")).strip().replace(" ", "_")
    if 2 <= len(title_clean) <= 24:
        tags_pool.append(f"#{title_clean}")

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


def build_telegram_caption(trend, country_key, day, base):
    """صياغة نص الرسالة بتنسيق HTML جذاب لجمهور تليجرام."""
    art = trend.get("article", {})
    headline = html.escape(art.get("headline") or trend.get("title", ""))

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

    # استخراج ملخص موجز من المقال
    summary = art.get("summary") or art.get("lead") or ""
    if not summary and art.get("body"):
        # أول فقرة
        paragraphs = art["body"].split("\n\n")
        summary = paragraphs[0] if paragraphs else ""
    summary_clean = html.escape(summary[:220].rsplit(" ", 1)[0] + "…") if len(summary) > 220 else html.escape(summary)

    if is_en:
        hashtags = " ".join(get_global_hashtags(trend))
        caption = (
            f"🌍 <b>Trending Worldwide | {headline}</b>\n\n"
            f"{summary_clean}\n\n"
            f"🔗 <b>Full story & verified facts:</b>\n"
            f"👉 <a href=\"{url}\">{url}</a>\n\n"
            f"{hashtags}"
        )
    else:
        country_badge = "🇪🇬 مصر" if country_key == "eg" else "🇸🇦 السعودية"
        hashtags = " ".join(get_arabic_hashtags(trend, country_key))
        caption = (
            f"🔴 <b>ترند عاجل في {country_badge} | {headline}</b>\n\n"
            f"{summary_clean}\n\n"
            f"🔗 <b>التفاصيل والمصادر الرسمية كاملة:</b>\n"
            f"👉 <a href=\"{url}\">{url}</a>\n\n"
            f"{hashtags}"
        )

    # الحد الأقصى لشرح الصورة في تليجرام هو 1024 حرف
    if len(caption) > 1000:
        caption = caption[:990].rsplit(" ", 1)[0] + f"…\n\n👉 <a href=\"{url}\">{url}</a>"

    return caption


def find_card_path(trend):
    """البحث عن صورة الكارت المولدة على القرص."""
    card_rel = trend.get("card")
    if not card_rel:
        return None

    # مسار في output أو site
    candidates = [
        os.path.join(ROOT, "output", card_rel),
        os.path.join(ROOT, "site", card_rel),
        os.path.join(ROOT, card_rel),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            return p
    return None


def send_to_telegram(token, chat_id, caption, card_path=None, fallback_image_url=None):
    """إرسال المنشور إلى قناة أو مجموعة تليجرام عبر Bot API الرسمي مجاناً."""
    if not requests:
        print("  ⚠️ مكتبة requests غير مثبتة — تخطي الإرسال.")
        return False

    base_api = f"https://api.telegram.org/bot{token}"

    # محاولة 1: إرسال صورة الكارت المحلية مع الشرح
    if card_path and os.path.exists(card_path):
        try:
            with open(card_path, "rb") as f:
                res = requests.post(
                    f"{base_api}/sendPhoto",
                    data={
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                    },
                    files={"photo": f},
                    timeout=25,
                )
            if res.status_code == 200:
                print("  ✓ تم نشر الكارت والشرح بنجاح على تليجرام!")
                return True
            else:
                print(f"  ⚠️ تعذر إرسال الصورة المحلية ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"  ⚠️ خطأ أثناء رفع الصورة المحلية: {e}")

    # محاولة 2: إرسال صورة عبر رابط خارجي إذا وجد
    if fallback_image_url and fallback_image_url.startswith("http"):
        try:
            res = requests.post(
                f"{base_api}/sendPhoto",
                data={
                    "chat_id": chat_id,
                    "photo": fallback_image_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                timeout=20,
            )
            if res.status_code == 200:
                print("  ✓ تم نشر الصورة والرابط بنجاح على تليجرام!")
                return True
        except Exception as e:
            print(f"  ⚠️ خطأ في إرسال رابط الصورة: {e}")

    # محاولة 3: إرسال الرسالة كنص مع رابط المعاينة
    try:
        res = requests.post(
            f"{base_api}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        if res.status_code == 200:
            print("  ✓ تم إرسال الرسالة النصية بنجاح على تليجرام!")
            return True
        else:
            print(f"  ✗ فشل الإرسال إلى تليجرام (كود {res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"  ✗ خطأ في الاتصال بـ Telegram API: {e}")
        return False


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "https://altrendat.com").rstrip("/")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        print("ℹ️ لم يتم تحديد TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID في البيئة — تخطي النشر التلقائي حتى إضافتهما.")
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
        print("  لا توجد ترندات جديدة غير منشورة على تليجرام.")
        return 0

    # التوزيع: ترند عربي + ترند عالمي
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

    print(f"🚀 بدء النشر التلقائي على تليجرام لـ {len(selected)} ترند (عربي + عالمي)...")
    for key, ckey, day, t in selected:
        caption = build_telegram_caption(t, ckey, day, base)
        card_path = find_card_path(t)
        fallback_img = t.get("image")

        print(f"\nإرسال الترند [{ckey.upper()}]: {t.get('title')}")
        ok = send_to_telegram(token, chat_id, caption, card_path, fallback_img)
        if ok:
            posted.add(key)

    save_posted(posted)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
