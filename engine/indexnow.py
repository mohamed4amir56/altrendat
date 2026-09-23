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
import urllib.request
import uuid
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
STATE = os.path.join(ROOT, "data", "indexnow_sent.json")
KEYFILE = os.path.join(ROOT, "data", "indexnow_key.txt")

ENDPOINT = "https://api.indexnow.org/IndexNow"
BATCH = 10000   # الحد الأقصى لكل طلب


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


def submit(base, key, urls):
    host = base.split("//", 1)[-1].split("/", 1)[0]
    payload = {
        "host": host,
        "key": key,
        "keyLocation": base.rstrip("/") + "/" + key + ".txt",
        "urlList": urls[:BATCH],
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status


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

    print("  ملف التحقق: site/" + name)
    print("  في الخريطة: " + str(len(all_urls)) + " · جديد: " + str(len(new)))

    # لا تُفهرس عنوانًا مؤقتًا.
    #
    # لو فُهرس altrendat.pages.dev ثم انتقل الموقع إلى نطاقه، لصار
    # للمحتوى نسختان في نتائج البحث، وتشتّتت قوة الموقع بين عنوانين.
    # الأنظف أن يبدأ الفهرسة على عنوانه النهائي مرة واحدة.
    host = base.split("//", 1)[-1].split("/", 1)[0]
    if host.endswith(".pages.dev") or host.startswith("localhost"):
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

    try:
        status = submit(base, key, new)
        print("  أُرسل " + str(len(new)) + " رابطًا — الرد: " + str(status))
        if status in (200, 202):
            sent.update(new)
            save_sent(sent)
    except Exception as e:
        # الفهرسة تحسين لا شرط — لا تُسقط التشغيلة بسببها
        print("  ⚠ تعذّر الإرسال: " + type(e).__name__ + ": " + str(e))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
