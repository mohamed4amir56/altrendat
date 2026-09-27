# -*- coding: utf-8 -*-
"""
أتمتة إرسال إشعارات تطبيق الذهب (Goldex) عبر OneSignal.

الميزات:
1. جلب الأخبار الحية المحدثة من site/gold-news.json (المولدة من التريندات).
2. إعطاء الأولوية القصوى للأخبار السياسية (cat_politics)، تليها أخبار الذهب والعملات.
3. منع تكرار إرسال أي خبر سبق إرساله عبر data/onesignal_posted.json.
4. إرسال الإشعار برابط المقال الكامل على altrendat.com لفتح التفاصيل وزيادة المشاهدات.
5. دعم متعدد اللغات (عربي وإنجليزي) يتكيف مع لغة جهاز المستخدم تلقائياً.
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


def send_onesignal_notification(app_id, api_key, item, base_url):
    if not requests:
        print("[OneSignal] خطأ: مكتبة requests غير مثبتة.")
        return False

    cat_key = item.get("categoryKey", "cat_gold")
    title = item.get("title", "")
    detail = item.get("detail", "")
    url = item.get("sourceUrl") or item.get("url") or f"{base_url}/"
    image = item.get("image") or f"{base_url}/og-default.jpg"

    # تحديد العنوان والعناوين حسب التصنيف والأولوية
    is_politics = cat_key == "cat_politics"
    if is_politics:
        heading_ar = "🏛️ خبر سياسي عاجل"
        heading_en = "🏛️ Breaking Political News"
    elif cat_key == "cat_gold":
        heading_ar = "🥇 تنبيه أسواق الذهب"
        heading_en = "🥇 Gold Market Update"
    elif cat_key == "cat_silver":
        heading_ar = "🥈 حركة أسواق الفضة"
        heading_en = "🥈 Silver Market Alert"
    else:
        heading_ar = "📈 اقتصاد وعملات"
        heading_en = "📈 Market & Economy Alert"

    # المحتوى اللغوي المتكيف
    is_ar = is_ar_text(title)
    if is_ar:
        content_ar = title[:120]
        content_en = f"Breaking: {title[:100]}"
    else:
        content_en = title[:120]
        content_ar = f"عاجل: {title[:100]}"

    payload = {
        "app_id": app_id,
        "included_segments": ["Subscribed Users"],
        "headings": {
            "ar": heading_ar,
            "en": heading_en,
        },
        "contents": {
            "ar": content_ar,
            "en": content_en,
        },
        "data": {
            "url": url,
            "id": item.get("id", ""),
            "category": cat_key,
        },
        "chrome_web_icon": image,
        "big_picture": image,
        "android_accent_color": "FFD700" if not is_politics else "E53935",
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
            print(f"[OneSignal] ✓ تم إرسال الإشعار بنجاح! المستلمون: {recipients} جهاز.")
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

    posted = load_posted()

    # الأخبار في الخلاصة مرتبة بالفعل: السياسة أولاً ثم الأحدث
    # نبحث عن أول خبر ذي أولوية لم يُرسل بعد
    target_item = None
    for item in items:
        item_id = item.get("id")
        if not item_id:
            continue
        if item_id in posted:
            continue
        target_item = item
        break

    if not target_item:
        print("[OneSignal] جميع الأخبار تم إشعار المستخدمين بها مسبقاً. لا يوجد جديد للإرسال.")
        return

    print(f"[OneSignal] جاري إرسال إشعار للخبر ذو الأولوية: [{target_item.get('categoryKey')}] {target_item.get('title')[:60]}")
    success = send_onesignal_notification(app_id, api_key, target_item, base_url)
    if success:
        posted.add(target_item["id"])
        save_posted(posted)


if __name__ == "__main__":
    main()
