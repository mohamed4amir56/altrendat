# -*- coding: utf-8 -*-
"""
Google Indexing API — إخطار جوجل بصفحات الموقع الجديدة.

قرار صاحب الموقع (2 أكتوبر 2026): يعود الإرسال لصفحات المقالات كما كان قبل
28 سبتمبر، لكن لنصفها فقط: الأعلى بحثًا من مقالات كل يوم في كل نسخة (SHARE).
من 28 سبتمبر اقتصر على صفحات الوظائف الموثقة (ولا توجد)، فلم يُرسل لجوجل
شيء، وتزامن ذلك مع هبوط الظهور في Search Console.

للعلم: جوجل تخصص هذه الواجهة رسميًا لصفحات JobPosting والبث المباشر
(BroadcastEvent)؛ إخطارها بصفحات أخرى قد يُتجاهل، وقد يوقف الوصول للواجهة.
صاحب الموقع يعلم ذلك واختار الإرسال. والطريق الرسمي يعمل معه: الخرائط
و WebSub (engine/indexnow.py). لا تُضاف بيانات JobPosting لصفحة ليست وظيفة.

- يُرسل ما هو منشور فعلًا الآن فقط (من الخريطة المنشورة): هذه الخطوة تعمل
  قبل حفظ التشغيلة ونشرها، وإخطار جوجل بصفحة لم تُنشر يجعلها تزور 404.
- المقالات الأحدث أولًا، وفي اليوم الواحد الأعلى بحثًا أولًا: الحصة 200 رابط
  في اليوم، فالخبر الجديد الذي عليه بحث قبل غيره.
"""
import json
import math
import os
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

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


def urls_from_sitemap(base):
    """روابط خريطة الموقع المنشورة فعلًا الآن (لا المبنية في هذه التشغيلة ولم
    تُنشر بعد)، وهي الصفحات المفهرسة فقط."""
    req = urllib.request.Request(base + "/sitemap.xml",
                                 headers={"User-Agent": "AltrendatBot/1.0 (+https://altrendat.com)"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print("  ⚠ تعذّرت قراءة الخريطة المنشورة: " + type(e).__name__)
        return []
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    return [el.text.strip() for el in root.iter(ns + "loc") if el.text]


FRESH_DAYS = 2    # مقالات آخر يومين فقط: الحصة للخبر الجديد، والقديم تجده جوجل من الخريطة


def article_day(url, base):
    """يوم المقال من رابطه (/النسخة/YYYY-MM-DD/العنوان/)، أو "" لغير المقالات."""
    parts = url[len(base):].strip("/").split("/")
    if len(parts) == 3 and len(parts[1]) == 10 and parts[1][:2] == "20":
        return parts[1]
    return ""


SHARE = 0.5       # نصف مقالات كل يوم في كل نسخة: الأعلى بحثًا (قرار صاحب الموقع)


def traffic_of(base, cutoff):
    """حجم بحث كل مقال حديث من أرشيف الأيام: {الرابط: traffic_num}."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import entities
    out = {}
    days_dir = os.path.join(ROOT, "data", "days")
    for name in os.listdir(days_dir):
        if not name.endswith(".json"):
            continue
        key, _, day = name[:-5].partition("-")
        if not day or day < cutoff:
            continue
        try:
            with open(os.path.join(days_dir, name), encoding="utf-8") as f:
                snap = json.load(f)
        except Exception:
            continue
        for t in snap.get("trends", []):
            if t.get("article"):
                url = "{}/{}/{}/{}/".format(base, key, day, entities.slugify(t["title"]))
                out[url] = t.get("traffic_num", 0) or 0
    return out


def strongest_half(all_urls, sent, base, cutoff):
    """المقالات التي تُرسل: نصف مقالات كل يوم في كل نسخة، الأعلى بحثًا. الخبر
    الذي عليه بحث كثير هو ما تفيده سرعة الفهرسة؛ والباقي تجده جوجل من الخريطة
    والخلاصة. ما أُرسل سابقًا يُحسب من النصف، فلا يتجاوزه اليوم مهما كبر."""
    traffic = traffic_of(base, cutoff)
    groups = {}
    for u in all_urls:
        day = article_day(u, base)
        if day and day >= cutoff:
            edition = u[len(base):].strip("/").split("/")[0]
            groups.setdefault((day, edition), []).append(u)
    picked = []
    for (day, edition), urls in groups.items():
        allowed = math.ceil(len(urls) * SHARE)               # نصف العدد مقرّبًا للأعلى
        left = allowed - sum(u in sent for u in urls)
        fresh = sorted((u for u in urls if u not in sent),
                       key=lambda u: -traffic.get(u, 0))
        picked += [(day, traffic.get(u, 0), u) for u in fresh[:max(left, 0)]]
    picked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [u for _, _, u in picked]


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

    all_urls = urls_from_sitemap(base)
    if not all_urls:
        print("  ℹ لا روابط في الخريطة المنشورة — لا شيء يُرسل لـ Indexing API.")
        return 0

    creds = get_credentials()
    if not creds:
        print("  ℹ تخطي Google Indexing API: لم يتم ضبط Service Account بعد.")
        return 0

    # تصفية الروابط الجديدة التابعة للنطاق
    all_urls = [u for u in all_urls if u.startswith(base)]
    sent = load_sent()

    # نصف مقالات آخر يومين (الأعلى بحثًا) والصفحات الثابتة فقط (انظر FRESH_DAYS و SHARE)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=FRESH_DAYS)).strftime("%Y-%m-%d")
    static = [u for u in all_urls if not article_day(u, base) and u not in sent]
    picked = strongest_half(all_urls, sent, base, cutoff)
    # الأحدث يومًا أولًا، وفي اليوم الواحد الأعلى بحثًا أولًا، ثم الصفحات الثابتة
    new_urls = picked + sorted(static)
    to_send = new_urls[:BATCH_LIMIT]

    print("  إجمالي الخريطة: " + str(len(all_urls)) + " · مرسل سابقاً: " + str(len(sent))
          + " · بانتظار الإرسال: " + str(len(new_urls)) + " (في هذه التشغيلة: " + str(len(to_send)) + ")")
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
