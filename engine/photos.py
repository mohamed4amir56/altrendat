# -*- coding: utf-8 -*-
"""
صور مرخصة من ويكيبيديا وويكيميديا كومنز — البديل القانوني لصور الصحف.

صور الصحف حقوقها لناشريها، وعلامتها المائية (اليوم السابع، CNN...) علامة
حقوقهم، وإزالتها مخالفة للقانون. لذلك:
- نبحث عن صفحة ويكيبيديا بعنوان الترند نفسه (مع التحويلات)، بالعربية ثم
  بالإنجليزية. بلا بحث تقريبي: عنوان مطابق أو لا صورة، فلا تظهر صورة
  شخص آخر.
- نأخذ الصورة الرئيسية للصفحة فقط إن كانت برخصة حرة (pilicense=free)،
  ونستبعد صفحات التوضيح.
- نقرأ اسم المصوّر والرخصة من بيانات الملف، ويُكتبان تحت الصورة (شرط
  الرخصة). الحارس (guard.py) يرفض أي صورة من كومنز بلا هذا السطر.
- فئات بلا صور مفيدة (طقس، أسعار، مواقيت، أبراج، تعليم) بلا صورة.

  python engine/photos.py            # يملأ صور المقالات التي لم تُجرَّب بعد
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://{lang}.wikipedia.org/w/api.php"
UA = "AltrendatBot/1.0 (https://altrendat.com; info@altrendat.com)"
# أسماء أعلام فقط. «مجلس الشيوخ» في السياسة قد تكون صفحته عن مجلس بلد آخر،
# فلا صور لفئات المصطلحات العامة.
PHOTO_CATEGORIES = {"شخصية", "رياضة", "فن ومشاهير", "دول وأماكن"}
FREE = re.compile(r"(cc[\s-]?by|cc0|public domain|^pd\b|gfdl)", re.I)
NOT_FREE = re.compile(r"(\bnc\b|\bnd\b|non-?commercial|no-?deriv|fair use)", re.I)
TAGS = re.compile(r"<[^>]+>")


def _get_json(lang, params):
    url = API.format(lang=lang) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _clean(value):
    text = html.unescape(TAGS.sub(" ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _claims(qid, prop):
    """قيم خاصية من ويكي بيانات، مثل P31 (نوع الكيان)."""
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "wbgetclaims", "entity": qid, "property": prop, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for c in (data.get("claims") or {}).get(prop, []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        out.append(v.get("id") if isinstance(v, dict) and "id" in v else v)
    return out


def matches_kind(qid, category):
    """هل الصفحة من نوع الترند؟ الفئة «شخصية» تشمل عبارات قصيرة ليست
    أشخاصًا: «مجلس الوزراء» طابقت صورة لحكومة أمريكا 1981. لذلك:
    الأشخاص يجب أن يكونوا بشرًا (Q5)، والأماكن لها إحداثيات (P625)."""
    if not qid:
        return False
    if category in ("شخصية", "فن ومشاهير"):
        return "Q5" in _claims(qid, "P31")
    if category == "دول وأماكن":
        return bool(_claims(qid, "P625"))
    return True          # الرياضة: فرق وبطولات ولاعبون بأسمائهم


def find_photo(title, category, langs=("ar", "en")):
    """صورة حرة الرخصة لصفحة ويكيبيديا بعنوان الترند، أو None."""
    if category not in PHOTO_CATEGORIES or not title.strip():
        return None
    for lang in langs:
        try:
            data = _get_json(lang, {
                "action": "query", "format": "json", "formatversion": "2",
                "titles": title.strip(), "redirects": "1",
                "prop": "pageimages|pageprops", "piprop": "thumbnail|name",
                "pithumbsize": "1200", "pilicense": "free",
            })
            page = (data.get("query", {}).get("pages") or [{}])[0]
            props = page.get("pageprops") or {}
            if page.get("missing") or "disambiguation" in props:
                continue
            thumb, name = page.get("thumbnail"), page.get("pageimage")
            if not thumb or not name:
                continue
            if not matches_kind(props.get("wikibase_item"), category):
                return None      # الصفحة موجودة لكنها ليست من نوع الترند
            meta = _get_json(lang, {
                "action": "query", "format": "json", "formatversion": "2",
                "titles": "File:" + name, "prop": "imageinfo", "iiprop": "extmetadata|url",
                "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
            })
            info = ((meta.get("query", {}).get("pages") or [{}])[0].get("imageinfo") or [{}])[0]
            em = info.get("extmetadata") or {}
            lic = _clean((em.get("LicenseShortName") or {}).get("value", ""))
            if not lic or not FREE.search(lic) or NOT_FREE.search(lic):
                continue
            artist = _clean((em.get("Artist") or {}).get("value", ""))
            if not artist or artist.lower().startswith(("see ", "unknown")):
                artist = "مصور غير مذكور"
            return {
                "url": thumb["source"].split("?", 1)[0],
                "width": thumb.get("width"), "height": thumb.get("height"),
                "artist": artist[:80],
                "license": lic,
                "license_url": (em.get("LicenseUrl") or {}).get("value", ""),
                "file_page": info.get("descriptionurl") or
                "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(name),
                "wiki_title": page.get("title", title),
                "wiki_lang": lang,
            }
        except Exception:
            continue
    return None


def backfill(recheck=False):
    """يجرّب مرة واحدة لكل مقال لم تُجرَّب صورته، في الأرشيف ومخزن المقالات.
    recheck: يعيد التجربة لكل المقالات (بعد تغيير قواعد المطابقة)."""
    days = os.path.join(ROOT, "data", "days")
    store_path = os.path.join(ROOT, "data", "articles.json")
    with open(store_path, encoding="utf-8") as f:
        store = json.load(f)
    found = tried = 0
    for name in sorted(os.listdir(days)):
        if not name.endswith(".json"):
            continue
        key, day = name[:-5].split("-", 1)
        path = os.path.join(days, name)
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
        langs = ("en",) if key == "world" else ("ar", "en")
        changed = False
        for t in snap.get("trends", []):
            art = t.get("article")
            if not art or ("photo" in art and not recheck):
                continue
            art["photo"] = find_photo(t["title"], t.get("category", ""), langs)
            tried += 1
            found += bool(art["photo"])
            k = key + "|" + day + "|" + t["title"]
            if k in store and isinstance(store[k], dict) and store[k].get("body"):
                store[k]["photo"] = art["photo"]
            changed = True
            if art["photo"]:
                print("  📷 " + t["title"] + " ← " + art["photo"]["license"])
            time.sleep(0.2)
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print("✓ جُرّب " + str(tried) + " مقالًا، ووُجدت صورة حرة لـ " + str(found))


if __name__ == "__main__":
    backfill(recheck="--recheck" in sys.argv)
