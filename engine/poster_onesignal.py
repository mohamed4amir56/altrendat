# -*- coding: utf-8 -*-
"""
أتمتة إرسال إشعارات تطبيق الذهب (Goldex) عبر OneSignal.

الميزات:
1. جلب الأخبار الحية المحدثة من site/gold-news.json (المولدة من التريندات).
2. إعطاء الأولوية القصوى للأخبار السياسية (cat_politics)، تليها أخبار الذهب والعملات.
3. استهداف لغوي دقيق (عربي / إنجليزي):
   - المستخدم العربي تصله إشعارات الأخبار العربية من altrendat.com.
   - المستخدم الإنجليزي تصله إشعارات الأخبار الإنجليزية من altrendat.com/world.
4. منع تكرار إرسال أي خبر سبق إرساله عبر data/onesignal_posted.json.
5. تمرير رابط المقال والمصدر والأيقونة ليفتح التطبيق المقال من الموقع فوراً.
"""
import json
import os
import sys

try:
    import requests
except ImportError:
    requests = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "onesignal_posted.json")
DEFAULT_APP_ID = "a624b9fa-0c01-46de-a5c2-99e05d1a5bb5"


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
    # الاحتفاظ بآخر 300 خبر لمنع تضخم الملف
    posted_list = sorted(list(posted))[-300:]
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(posted_list, f, ensure_ascii=False, indent=1)


def is_ar_text(txt):
    return any("\u0600" <= c <= "\u06FF" for c in (txt or ""))


def send_onesignal_notification(app_id, api_key, item, base_url, lang="ar"):
    if not requests:
        print("[OneSignal] خطأ: مكتبة requests غير مثبتة.")
        return False

    cat_key = item.get("categoryKey", "cat_gold")
    title = item.get("title", "")
    url = item.get("sourceUrl") or item.get("url") or f"{base_url}/"
    image = item.get("image") or f"{base_url}/og-default.jpg"
    icon = item.get("icon") or ("🏛️" if cat_key == "cat_politics" else "🥇")
    source = item.get("source", "التريندات")

    is_politics = cat_key == "cat_politics"
    if lang == "ar":
        if is_politics:
            heading = "🏛️ خبر سياسي عاجل"
        elif cat_key == "cat_gold":
            heading = "🥇 أسواق الذهب والمعادن"
        elif cat_key == "cat_silver":
            heading = "🥈 أسواق الفضة"
        else:
            heading = "📈 اقتصاد وعملات"
        content = title[:130]

        # استهداف المستخدمين الناطقين بالعربية أو من اختار العربية في التطبيق
        filters = [
            {"field": "tag", "key": "news_lang", "relation": "=", "value": "ar"},
            {"operator": "OR"},
            {"field": "language", "relation": "=", "value": "ar"},
        ]
    else:
        if is_politics:
            heading = "🏛️ Breaking Political News"
        elif cat_key == "cat_gold":
            heading = "🥇 Gold & Metal Markets"
        elif cat_key == "cat_silver":
            heading = "🥈 Silver Market Alert"
        else:
            heading = "📈 Economy & Currency Alert"
        content = title[:130]

        # استهداف المستخدمين باللغة الإنجليزية
        filters = [
            {"field": "tag", "key": "news_lang", "relation": "=", "value": "en"},
            {"operator": "OR"},
            {"field": "language", "relation": "=", "value": "en"},
        ]

    payload = {
        "app_id": app_id,
        "filters": filters,
        "headings": {
            "en": heading,
            "ar": heading,
        },
        "contents": {
            "en": content,
            "ar": content,
        },
        "data": {
            "url": url,
            "id": item.get("id", ""),
            "category": cat_key,
            "source": source,
            "icon": icon,
        },
        "chrome_web_icon": image,
        "big_picture": image,
        "android_accent_color": "E53935" if is_politics else "FFD700",
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {api_key}",
    }

    try:
        resp = requests.post(
            "https://onesignal.com/api/v1/notifications",
            headers=headers,
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            res_data = resp.json()
            recipients = res_data.get("recipients", 0)
            print(f"[OneSignal] ✓ تم إرسال إشعار ({lang}) بنجاح! المستلمون: {recipients} جهاز.")
            print(f"            الخبر: [{cat_key}] {title[:60]}")
            return True
        else:
            print(f"[OneSignal] ✗ فشل الإرسال (رمز {resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"[OneSignal] ✗ استثناء أثناء الاتصال: {e}")
        return False


def main():
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "https://altrendat.com").rstrip("/")
    app_id = os.getenv("ONESIGNAL_APP_ID", DEFAULT_APP_ID).strip()
    api_key = os.getenv("ONESIGNAL_REST_API_KEY", "").strip()

    if not api_key:
        print("[OneSignal] ℹ تخطي: لم يتم تعيين مفتاح ONESIGNAL_REST_API_KEY في Secrets.")
        print("            لإرسال إشعارات لحظية لهواتف المستخدمين، أضف ONESIGNAL_REST_API_KEY إلى مستودع GitHub.")
        return

    feed_file = os.path.join(ROOT, "site", "gold-news.json")
    if not os.path.exists(feed_file):
        print(f"[OneSignal] خطأ: الملف {feed_file} غير موجود.")
        return

    try:
        with open(feed_file, encoding="utf-8") as f:
            feed_data = json.load(f)
    except Exception as e:
        print(f"[OneSignal] خطأ في قراءة {feed_file}: {e}")
        return

    items = feed_data.get("items", [])
    if not items:
        print("[OneSignal] لا توجد أخبار في الخلاصة.")
        return

    # فرز الأخبار حسب اللغة
    ar_items = [it for it in items if it.get("lang") == "ar" or is_ar_text(it.get("title", ""))]
    en_items = [it for it in items if it.get("lang") == "en" and not is_ar_text(it.get("title", ""))]

    posted = load_posted()

    # 1. إرسال أحدث خبر عربي ذو أولوية للمستخدمين بالعربية
    target_ar = next((it for it in ar_items if it.get("id") and it["id"] not in posted), None)
    if target_ar:
        print(f"[OneSignal] إرسال إشعار بالعربية: [{target_ar.get('categoryKey')}] {target_ar.get('title')[:60]}")
        if send_onesignal_notification(app_id, api_key, target_ar, base_url, lang="ar"):
            posted.add(target_ar["id"])

    # 2. إرسال أحدث خبر إنجليزي ذو أولوية للمستخدمين بالإنجليزية
    target_en = next((it for it in en_items if it.get("id") and it["id"] not in posted), None)
    if target_en:
        print(f"[OneSignal] Sending English notification: [{target_en.get('categoryKey')}] {target_en.get('title')[:60]}")
        if send_onesignal_notification(app_id, api_key, target_en, base_url, lang="en"):
            posted.add(target_en["id"])

    save_posted(posted)


if __name__ == "__main__":
    main()
