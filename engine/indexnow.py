# -*- coding: utf-8 -*-
"""
IndexNow — إخطار محركات البحث فور نشر صفحة.

الزحف الطبيعي لموقع جديد يستغرق أسابيع، وترند اليوم يموت خلال
ساعات. IndexNow يقلب المعادلة: بدل انتظار المحرّك ليكتشف الصفحة،
نخبره بها لحظة نشرها فتُفهرس خلال دقائق.

بروتوكول واحد يصل إلى Bing و Yandex و Seznam و Naver دفعةً واحدة.
Google لا تدعمه، فتبقى خريطة الموقع و Search Console طريقها.

يرسل الجديد فقط: يحتفظ بما أُرسل في data/indexnow_sent.json، فلا
يُعيد إرسال صفحة مرتين ولا يُرهق الخدمة كل 20 دقيقة.

  python engine/indexnow.py https://altrendat.com
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
STATE = os.path.join(ROOT, "data", "indexnow_sent.json")
KEYFILE = os.path.join(ROOT, "data", "indexnow_key.txt")

# كل محرك بعنوانه: العنوان المشترك api.indexnow.org يرفض الطلب كله إن رفضه
# محرك واحد (Bing ظل يرد 403 من 23 سبتمبر فلم يصل شيء لأحد). والمحركات
# المشاركة تتبادل الروابط المقبولة فيما بينها.
ENDPOINTS = [
    ("Bing", "https://www.bing.com/indexnow"),
    ("Yandex", "https://yandex.com/indexnow"),
    ("Naver", "https://searchadvisor.naver.com/indexnow"),
    ("Seznam", "https://search.seznam.cz/indexnow"),
    ("Yep", "https://indexnow.yep.com/indexnow"),
]
BATCH = 10000   # الحد الأقصى لكل طلب

# WebSub (PubSubHubbub): إخطار مركز جوجل العام بأن خلاصتي الموقع تحدّثتا. هو
# الطريق الذي تذكره جوجل نفسها لاكتشاف جديد خلاصات RSS بسرعة (جوجل لا تدعم
# IndexNow، و Indexing API عندها لصفحات الوظائف والبث فقط). الخلاصتان تعلنان
# عن المركز بوسم rel="hub" (site.py).
WEBSUB_HUB = "https://pubsubhubbub.appspot.com/"
FEEDS = ("/feed.xml", "/world/feed.xml")
UA = "AltrendatBot/1.0 (+https://altrendat.com)"


def get_key():
    """مفتاح ثابت للموقع — يُولَّد مرة ويُحفظ، ويُنشر كملف نصي."""
    if os.path.exists(KEYFILE):
        with open(KEYFILE, encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key
    key = uuid.uuid4().hex
    os.makedirs(os.path.dirname(KEYFILE), exist_ok=True)
    with open(KEYFILE, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def publish_key(key):
    """المحرّك يتحقق من ملكيتك للموقع بقراءة هذا الملف من جذره."""
    path = os.path.join(SITE, key + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key + ".txt"


def urls_from_sitemap():
    path = os.path.join(SITE, "sitemap.xml")
    if not os.path.exists(path):
        return []
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    root = ET.parse(path).getroot()
    return [el.text.strip() for el in root.iter(ns + "loc") if el.text]


def load_sent():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_sent(sent):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(sorted(sent), f, ensure_ascii=False, indent=1)


def submit(endpoint, base, key, urls):
    """يرسل الروابط لمحرك واحد ويعيد كود الرد (200/202 = قُبل)."""
    host = base.split("//", 1)[-1].split("/", 1)[0]
    payload = {
        "host": host,
        "key": key,
        "keyLocation": base.rstrip("/") + "/" + key + ".txt",
        "urlList": urls[:BATCH],
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": UA},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def live_urls(base):
    """روابط خريطة الموقع المنشورة فعلًا الآن. هذه الخطوة تعمل قبل حفظ
    التشغيلة ونشرها، فصفحات هذه التشغيلة ليست على الموقع بعد؛ إخطار المحرك
    بها الآن يجعله يزور صفحة غير موجودة. تُرسل في التشغيلة التالية."""
    req = urllib.request.Request(base + "/sitemap.xml", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        root = ET.fromstring(r.read())
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    return {el.text.strip() for el in root.iter(ns + "loc") if el.text}


def ping_websub(base):
    """يخطر مركز WebSub بتحديث الخلاصتين (الرد 204 = استلم)."""
    data = urllib.parse.urlencode(
        [("hub.mode", "publish")] + [("hub.url", base + f) for f in FEEDS]).encode("utf-8")
    req = urllib.request.Request(
        WEBSUB_HUB, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    base = (sys.argv[1] if len(sys.argv) > 1
            else "https://altrendat.pages.dev").rstrip("/")

    key = get_key()
    name = publish_key(key)

    all_urls = urls_from_sitemap()
    if not all_urls:
        print("✗ لا توجد خريطة موقع — شغّل engine/site.py أولًا")
        return 1

    # الصفحات المبنية على نطاق مختلف عن المطلوب لا تُرسل
    all_urls = [u for u in all_urls if u.startswith(base)]
    sent = load_sent()
    new = [u for u in all_urls if u not in sent]

    # الروابط المحذوفة لضعفها (prune.py): نخبر المحركات بها مرة واحدة،
    # فتعيد زيارتها وتجد التحويل بدل أن تبقى في نتائجها.
    pruned_path = os.path.join(ROOT, "data", "pruned.json")
    if os.path.exists(pruned_path):
        with open(pruned_path, encoding="utf-8") as f:
            gone = ["{}/{}/{}/{}/".format(base, p["country"], p["day"], p["slug"])
                    for p in json.load(f)]
        new += [u for u in gone if u not in sent and u not in new]

    print("  ملف التحقق: site/" + name)
    print("  في الخريطة: " + str(len(all_urls)) + " · جديد: " + str(len(new)))

    # لا تُفهرس عنوانًا مؤقتًا.
    #
    # لو فُهرس altrendat.pages.dev ثم انتقل الموقع إلى نطاقه، لصار
    # للمحتوى نسختان في نتائج البحث، وتشتّتت قوة الموقع بين عنوانين.
    # الأنظف أن يبدأ الفهرسة على عنوانه النهائي مرة واحدة.
    host = base.split("//", 1)[-1].split("/", 1)[0]
    TEMP = (".pages.dev", ".workers.dev", ".vercel.app", ".netlify.app")
    if host.endswith(TEMP) or host.startswith("localhost"):
        print("  ⏸ عنوان مؤقت (" + host + ") — لا يُرسل للفهرسة.")
        print("     اضبط SITE_BASE على نطاقك بعد حجزه.")
        return 0

    if "--dry-run" in sys.argv:
        for u in new[:5]:
            print("   → " + u)
        print("  (تجربة — لم يُرسل شيء)")
        return 0

    if not new:
        print("  لا جديد يُرسل ✓")
        return 0

    # الفهرسة تحسين لا شرط — لا تُسقط التشغيلة بسببها
    try:
        live = live_urls(base)
    except Exception as e:
        print("  ⚠ تعذّرت قراءة الخريطة المنشورة: " + type(e).__name__ + " — يؤجَّل للتشغيلة التالية")
        return 0
    in_map = set(all_urls)
    # المنشور الآن فقط؛ والروابط المحذوفة (تحويلات قديمة) ليست في الخريطة أصلًا
    ready = [u for u in new if u in live or u not in in_map]
    waiting = len(new) - len(ready)
    if waiting:
        print("  " + str(waiting) + " رابطًا لم يُنشر بعد — يُرسل في التشغيلة التالية")
    if not ready:
        return 0

    accepted = []
    for engine, endpoint in ENDPOINTS:
        try:
            status = submit(endpoint, base, key, ready)
        except Exception as e:
            status = type(e).__name__
        ok = status in (200, 202)
        print("  {} {}: {}".format("✓" if ok else "✗", engine, status))
        if ok:
            accepted.append(engine)
    if accepted:
        sent.update(ready)
        save_sent(sent)
        print("  أُرسل " + str(len(ready)) + " رابطًا إلى: " + "، ".join(accepted))
    else:
        print("  ⚠ لم يقبل أي محرك الإرسال — يُعاد في التشغيلة التالية")

    try:
        print("  WebSub (خلاصتا الموقع ← مركز جوجل): " + str(ping_websub(base)))
    except Exception as e:
        print("  ⚠ WebSub: " + type(e).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
