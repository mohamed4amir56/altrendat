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
- الجودة: نعرض نسخة بعرض 1280 (مقاس قياسي عند ويكيميديا، وفوق حد Google
  Discover وهو 1200). الصور التعبيرية أصلها 1280 فأكثر، وصورة الشخص نفسه
  تُقبل من 960.
- ما لا صورة له بالاسم يأخذ صورة تعبيرية من مجموعة منتقاة لفئته (STOCK):
  ملفات كومنز حرة عالية الدقة، بياناتها في data/stock_photos.json،
  ويُكتب تحتها «صورة تعبيرية». فلا يبقى مقال بلا صورة.

  python engine/photos.py            # يملأ صور المقالات التي لم تُجرَّب بعد
  python engine/photos.py --recheck  # يعيد التجربة لكل المقالات
  python engine/photos.py --stock    # يحدّث بيانات الصور التعبيرية من كومنز
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
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UA = "AltrendatBot/1.0 (https://altrendat.com; info@altrendat.com)"
# أسماء أعلام فقط. «مجلس الشيوخ» في السياسة قد تكون صفحته عن مجلس بلد آخر،
# فلا صور بالاسم لفئات المصطلحات العامة (تأخذ صورة تعبيرية بدلها).
PHOTO_CATEGORIES = {"شخصية", "رياضة", "فن ومشاهير", "دول وأماكن"}
FREE = re.compile(r"(cc[\s-]?by|cc0|public domain|^pd\b|gfdl)", re.I)
NOT_FREE = re.compile(r"(\bnc\b|\bnd\b|non-?commercial|no-?deriv|fair use)", re.I)
TAGS = re.compile(r"<[^>]+>")
WIDTH = 1280                       # عرض العرض، ومقاس قياسي لمصغّرات ويكيميديا
# صورة الشخص نفسه بعرض 960 أنفع من صورة تعبيرية، وتبقى حادة في عمود المقال
MIN_NAMED = 960
RASTER = re.compile(r"\.(jpe?g|png|webp)$", re.I)
STOCK_PATH = os.path.join(ROOT, "data", "stock_photos.json")

# صور تعبيرية لكل فئة: ملفات من ويكيميديا كومنز برخص حرة، كلها أعرض من
# 1600 بكسل. «فئة@بلد» تخص نسخة بعينها وتسبق الفئة العامة، والفئات غير
# المذكورة («عام»، «دول وأماكن»...) تأخذ صورة بلد النسخة (@eg، @sa، @world). غيّر القائمة ثم شغّل: python engine/photos.py --stock
STOCK = {
    "سياسة": ["United Nations General Assembly Hall (3).jpg",
              "United Nations General Assembly 2024.jpg",
              "Vecteezy stack-of-newspaper 1961329.jpg"],
    "اقتصاد": ["Gold bullion bars.jpg",
               "Frankfurt Stock Exchange (Ank Kumar) 03.jpg",
               "Container ship NYK Themis at the Port of Los Angeles.jpg"],
    "رياضة": ["Adidas soccer ball on a grass pitch (Unsplash).jpg",
              "The Peninsula Stadium at night - Salford City - Aug 24.jpg",
              "Cairo International Stadium 2019.jpg"],
    "رياضة@sa": ["Adidas soccer ball on a grass pitch (Unsplash).jpg",
                 "King Fahd International Stadium 2020s.jpg"],
    "طقس": ["Close-up of the rain drops on a car window. Car in a blurry background.jpg",
            "Lightning in Dallas 2015.jpg",
            "Cloud cumulonimbus at baltic sea(1).jpg"],
    "ديني": ["Masjid al-Haram 2022.jpg",
             "The Courtyard of Al-Azhar Mosque, Cairo, Egypt.jpg"],
    "تقنية": ["Black smartphone in hand (Unsplash).jpg",
              "Datacenter Server Racks (22370909788).jpg"],
    "تعليم": ["Hamamatsu Municipal Sakuma Library reading room ac (1).jpg"],
    "تعليم@sa": ["King Saud University Entrance Gate, Riyadh.jpg"],
    "تعليم@eg": ["Cairouni.jpg"],
    "فن ومشاهير": ["Beach-Please-2022-crowd-stage-lights-night-performance.jpg",
                   "A large crowd enjoys a music concert illuminated by colorful lights and a stunning stage display.jpg"],
    "أبراج وفلك": ["Beneath the Milky Way.jpg"],
    "حوادث وقضايا": ["Courtroom One Gavel - Flickr - Joe Gratz.jpg"],
    "شخصية": ["Vecteezy stack-of-newspaper 1961329.jpg"],
    "@eg": ["Cairo skyline, Nile River, Egypt.jpg",
            "Cairo skyline, Panoramic view, Egypt.jpg"],
    "@sa": ["Riyadh Skyline.jpg",
            "Riyadh Skyline showing the King Abdullah Financial District (KAFD) and the famous Kingdom Tower .jpg"],
    "@world": ["Shore of the East River with Headquarters of the United Nations, New York City, 20231005 1131 2226.jpg",
               "Vecteezy stack-of-newspaper 1961329.jpg"],
}


def _get_json(lang, params):
    base = COMMONS_API if lang == "commons" else API.format(lang=lang)
    url = base + "?" + urllib.parse.urlencode(params)
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


def _file_info(lang, name, min_width=WIDTH):
    """بيانات ملف: الرخصة والمصوّر ومصغّر بعرض WIDTH، أو None إن لم يصلح."""
    if not RASTER.search(name):
        return None                    # الشعارات والخرائط (svg) ليست صورًا
    meta = _get_json(lang, {
        "action": "query", "format": "json", "formatversion": "2",
        "titles": "File:" + name, "prop": "imageinfo",
        "iiprop": "extmetadata|url|size", "iiurlwidth": str(WIDTH),
        "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
    })
    info = ((meta.get("query", {}).get("pages") or [{}])[0].get("imageinfo") or [{}])[0]
    if (info.get("width") or 0) < min_width or not info.get("thumburl"):
        return None                    # أصغر من أن تكون صورة عالية الجودة
    em = info.get("extmetadata") or {}
    lic = _clean((em.get("LicenseShortName") or {}).get("value", ""))
    if not lic or not FREE.search(lic) or NOT_FREE.search(lic):
        return None
    artist = _clean((em.get("Artist") or {}).get("value", ""))
    if not artist or artist.lower().startswith(("see ", "unknown")):
        artist = "مصور غير مذكور"
    return {
        "url": info["thumburl"].split("?", 1)[0],
        "width": info.get("thumbwidth"), "height": info.get("thumbheight"),
        "artist": artist[:80],
        "license": lic,
        "license_url": (em.get("LicenseUrl") or {}).get("value", ""),
        "file_page": info.get("descriptionurl") or
        "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(name),
    }


def find_photo(title, category, langs=("ar", "en")):
    """صورة حرة الرخصة عالية الدقة لصفحة ويكيبيديا بعنوان الترند، أو None."""
    if category not in PHOTO_CATEGORIES or not title.strip():
        return None
    for lang in langs:
        try:
            data = _get_json(lang, {
                "action": "query", "format": "json", "formatversion": "2",
                "titles": title.strip(), "redirects": "1",
                "prop": "pageimages|pageprops", "piprop": "name",
                "pilicense": "free",
            })
            page = (data.get("query", {}).get("pages") or [{}])[0]
            props = page.get("pageprops") or {}
            if page.get("missing") or "disambiguation" in props:
                continue
            name = page.get("pageimage")
            if not name:
                continue
            if not matches_kind(props.get("wikibase_item"), category):
                return None      # الصفحة موجودة لكنها ليست من نوع الترند
            photo = _file_info(lang, name, MIN_NAMED)
            if not photo:
                continue
            photo.update({"wiki_title": page.get("title", title), "wiki_lang": lang})
            return photo
        except Exception:
            continue
    return None


_stock = None


def load_stock():
    global _stock
    if _stock is None:
        try:
            with open(STOCK_PATH, encoding="utf-8") as f:
                _stock = json.load(f)
        except Exception:
            _stock = {}
    return _stock


def stock_photo(title, category, country):
    """صورة تعبيرية من مجموعة الفئة (أو صورة البلد)، ثابتة لكل عنوان."""
    pool = load_stock()
    choices = (pool.get(category + "@" + country) or pool.get(category) or
               pool.get("@" + country) or pool.get("@world") or [])
    if not choices:
        return None
    seed = sum(ord(c) for c in title)          # ثابت بين التشغيلات، بخلاف hash()
    photo = dict(choices[seed % len(choices)])
    photo["stock"] = True
    return photo


def photo_for(title, category, country, langs=("ar", "en")):
    """صورة بالاسم إن وُجدت، وإلا صورة تعبيرية — فلكل مقال صورة."""
    return find_photo(title, category, langs) or stock_photo(title, category, country)


def refresh_stock():
    """يقرأ بيانات صور STOCK من كومنز ويحفظها في data/stock_photos.json."""
    out = {}
    for key, names in STOCK.items():
        out[key] = []
        for name in names:
            try:
                photo = _file_info("commons", name)
            except Exception as e:
                print("  ✗ " + name + ": " + str(e))
                photo = None
            if photo:
                out[key].append(photo)
            else:
                print("  ✗ لا تصلح: " + name)
            time.sleep(0.2)
        print("  " + key + ": " + str(len(out[key])) + " صورة")
    with open(STOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def backfill(recheck=False):
    """يجرّب مرة واحدة لكل مقال لم تُجرَّب صورته، في الأرشيف ومخزن المقالات.
    recheck: يعيد التجربة لكل المقالات (بعد تغيير قواعد المطابقة)."""
    days = os.path.join(ROOT, "data", "days")
    store_path = os.path.join(ROOT, "data", "articles.json")
    with open(store_path, encoding="utf-8") as f:
        store = json.load(f)
    named = tried = 0
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
            if not art or (art.get("photo") and not recheck):
                continue
            art["photo"] = photo_for(t["title"], t.get("category", ""), key, langs)
            tried += 1
            k = key + "|" + day + "|" + t["title"]
            if k in store and isinstance(store[k], dict) and store[k].get("body"):
                store[k]["photo"] = art["photo"]
            changed = True
            if art["photo"] and not art["photo"].get("stock"):
                named += 1
                print("  📷 " + t["title"] + " ← " + art["photo"]["license"])
            time.sleep(0.2)
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print("✓ جُرّب " + str(tried) + " مقالًا: " + str(named) +
          " بصورة بالاسم، والباقي بصورة تعبيرية")


if __name__ == "__main__":
    if "--stock" in sys.argv:
        refresh_stock()
    else:
        backfill(recheck="--recheck" in sys.argv)
