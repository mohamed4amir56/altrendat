# -*- coding: utf-8 -*-
"""
Google Indexing API — إشعار Googlebot لحظيًا بالصفحات والمقالات الجديدة.

لماذا هذه الخطوة حاسمة للترندات؟
- الفهرسة الطبيعية عبر Sitemap و Google Search Console تستغرق من عدة أيام إلى أسابيع.
- الترند يعيش ساعات فقط ويموت؛ إن لم يُفهرس فوراً تضيع كل زياراته.
- Google Indexing API ترسل إشعارًا مباشرًا إلى خوارزميات الفهرسة،
  فيبدأ زاحف Googlebot بزيارة الصفحة وفهرستها خلال دقائق معدودة.

الحصة المجانية لـ Google:
- 200 طلب فهرسة يومياً لكل مشروع، وهو كافٍ جداً لتغطية كافة ترندات اليوم.
- السكربت يحتفظ بما أُرسل في data/google_indexed.json حتى لا يكرر إرسال الرابط.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
STATE = os.path.join(ROOT, "data", "google_indexed.json")
LOCAL_KEY = os.path.join(ROOT, "data", "service_account.json")

SCOPES = ["https://www.googleapis.com/auth/indexing"]
ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
BATCH_LIMIT = 50  # حد الإرسال في التشغيلة الواحدة لتوزيع حصة الـ 200 على مدار اليوم


def get_credentials():
    """الحصول على بيانات اعتماد Service Account من البيئة أو ملف محلي."""
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError:
        print("  ⚠ مكتبة google-auth غير مثبتة. شغّل: pip install google-auth")
        return None

    creds = None
    env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json and env_json.strip():
        try:
            info = json.loads(env_json)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES)
        except Exception as e:
            print("  ✗ خطأ في قراءة GOOGLE_SERVICE_ACCOUNT_JSON: " + str(e))
            return None
    elif os.path.exists(LOCAL_KEY):
        try:
            creds = service_account.Credentials.from_service_account_file(
                LOCAL_KEY, scopes=SCOPES)
        except Exception as e:
            print("  ✗ خطأ في قراءة ملف المفتاح data/service_account.json: " + str(e))
            return None

    if creds:
        try:
            creds.refresh(Request())
            return creds
        except Exception as e:
            print("  ✗ تعذّر تجديد مفتاح الوصول لـ Google API: " + str(e))
            return None
    return None


def urls_from_sitemap():
    path = os.path.join(SITE, "sitemap.xml")
    if not os.path.exists(path):
        return []
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    try:
        root = ET.parse(path).getroot()
        return [el.text.strip() for el in root.iter(ns + "loc") if el.text]
    except Exception:
        return []


def load_sent():
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_sent(sent):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(sorted(sent), f, ensure_ascii=False, indent=1)


def notify_google(url, token):
    """إرسال إشعار URL_UPDATED لعنوان محدد."""
    payload = {
        "url": url,
        "type": "URL_UPDATED"
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "Bearer " + token
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    base = (sys.argv[1] if len(sys.argv) > 1
            else os.environ.get("SITE_BASE", "https://altrendat.com")).rstrip("/")

    # لا تُرسل للنطاقات التجريبية أو المحلية
    host = base.split("//", 1)[-1].split("/", 1)[0]
    TEMP = (".pages.dev", ".workers.dev", ".vercel.app", ".netlify.app")
    if host.endswith(TEMP) or host.startswith("localhost"):
        print("  ⏸ نطاق تجريبي (" + host + ") — لا يُرسل لـ Google Indexing API.")
        return 0

    creds = get_credentials()
    if not creds:
        print("  ℹ تخطي Google Indexing API: لم يتم ضبط Service Account بعد.")
        print("    (ضع المفتاح في GitHub Secrets باسم GOOGLE_SERVICE_ACCOUNT_JSON لتفعيله)")
        return 0

    all_urls = urls_from_sitemap()
    if not all_urls:
        print("  ✗ لم يتم العثور على روابط في sitemap.xml")
        return 0

    # تصفية الروابط الجديدة التابعة للنطاق
    all_urls = [u for u in all_urls if u.startswith(base)]
    sent = load_sent()
    new_urls = [u for u in all_urls if u not in sent]

    # أولوية الإرسال لمقالات الأخبار اليومية (الروابط ذات العمق)
    def priority(u):
        # المقالات تحوي تاريخ وتصنيف: أولوية عليا (1)، ثم صفحات الأيام (2)، ثم الباقي (3)
        parts = u.strip("/").split("/")
        if len(parts) >= 4:
            return 1
        elif len(parts) == 3:
            return 2
        return 3

    new_urls.sort(key=priority)
    to_send = new_urls[:BATCH_LIMIT]

    print("  إجمالي الخريطة: " + str(len(all_urls)) + " · مرسل سابقاً: " + str(len(sent)) + " · بانتظار الإرسال: " + str(len(to_send)))
    if not to_send:
        print("  لا توجد روابط جديدة لإرسالها لـ Google ✓")
        return 0

    success_count = 0
    token = creds.token
    for u in to_send:
        try:
            res = notify_google(u, token)
            notif = res.get("urlNotificationMetadata", {})
            pub_time = notif.get("latestUpdate", {}).get("notifyTime", "OK")
            print("  ✓ Google Indexed: " + u + " (" + pub_time[:19] + ")")
            sent.add(u)
            success_count += 1
            time.sleep(0.5)  # مراعاة قيود معدل الطلبات Rate Limit
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print("  ✗ خطأ " + str(e.code) + " عند إرسال " + u + ": " + err_body[:120])
            if e.code == 429:
                print("  ⏹ استنفدت الحصة اليومية لـ Google (Quota Exceeded)")
                break
        except Exception as e:
            print("  ✗ تعذر إرسال " + u + ": " + type(e).__name__ + ": " + str(e))

    if success_count > 0:
        save_sent(sent)
        print("  ✓ تم إخطار Google بنجاح بـ " + str(success_count) + " رابط جديد.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
