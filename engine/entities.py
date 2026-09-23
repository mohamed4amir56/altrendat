# -*- coding: utf-8 -*-
"""
ذاكرة المحرّك — صفحات الكيانات.

منافسك ينشر ترند اليوم ثم ينساه. هذا الملف يجعل الموقع يتذكّر:
كل ظهور لكل مصطلح، في أي بلد، وبأي حجم بحث، وبأي تاريخ.

بعد أشهر تصير لديك إجابات لا يملكها أحد:
"كم مرة تصدّر هذا العام؟"، "متى ظهر أول مرة؟"، "هل ترند في بلد آخر؟"
وهذه بيانات تتراكم مع الوقت ولا يمكن شراؤها أو اللحاق بها.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "entities.json")


def slugify(text):
    """يحوّل العنوان إلى معرّف صالح للرابط، مع إبقاء العربية كما هي."""
    s = text.strip().lower()
    s = re.sub(r"[^\w؀-ۿ\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")[:80] or "trend"


def day_of(d):
    """يوم البلد بتوقيته المحلي — المصدر الوحيد لليوم في كل الخطوات.

    الكاتب والكروت والذاكرة والموقع يجب أن تتفق على اليوم نفسه، وإلا
    كُتب المقال تحت يوم ونُشر تحت آخر. البيانات القديمة بلا حقل day
    تبقى على تاريخ UTC الذي بُنيت به، فلا تتغيّر روابطها.
    """
    return d.get("day") or d["generated_at"][:10]


def load():
    if os.path.exists(STORE):
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(store):
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def merge(store, data):
    """يدمج تشغيلة اليوم في الذاكرة. إعادة التشغيل لا تُكرّر الظهور."""
    new_entities = new_appearances = 0

    for country_key, d in data.items():
        day = day_of(d)

        for t in d["trends"]:
            slug = slugify(t["title"])
            entity = store.get(slug)

            if entity is None:
                entity = {
                    "slug": slug,
                    "name": t["title"],
                    "first_seen": day,
                    "appearances": [],
                }
                store[slug] = entity
                new_entities += 1

            # المفتاح: يوم + بلد. تشغيل المحرّك مرارًا في اليوم نفسه
            # يحدّث الظهور ولا ينشئ ظهورًا جديدًا.
            key = day + "|" + country_key
            existing = next(
                (a for a in entity["appearances"] if a["key"] == key), None)

            record = {
                "key": key,
                "date": day,
                "country": country_key,
                "country_name": d["country_name"],
                "traffic": t.get("traffic", ""),
                "traffic_num": t.get("traffic_num", 0),
                "category": t.get("category", ""),
                "publishable": t.get("publishable", False),
                "headlines": [n["title"] for n in t.get("news", [])][:3],
            }

            if existing:
                existing.update(record)
            else:
                entity["appearances"].append(record)
                new_appearances += 1

            # حقول محسوبة
            entity["name"] = t["title"]
            entity["last_seen"] = max(
                a["date"] for a in entity["appearances"])
            entity["first_seen"] = min(
                a["date"] for a in entity["appearances"])
            entity["total"] = len(entity["appearances"])
            entity["countries"] = sorted(
                {a["country"] for a in entity["appearances"]})
            entity["peak_traffic"] = max(
                a["traffic_num"] for a in entity["appearances"])
            entity["category"] = t.get("category", "")

    return new_entities, new_appearances


def main():
    path = os.path.join(ROOT, "data", "trends.json")
    if not os.path.exists(path):
        print("✗ لا يوجد data/trends.json — شغّل pipeline.py أولًا")
        return 1

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    store = load()
    before = len(store)
    new_e, new_a = merge(store, data)
    save(store)

    print("  كيانات جديدة: " + str(new_e))
    print("  ظهورات جديدة: " + str(new_a))
    print("  إجمالي الكيانات في الذاكرة: " + str(len(store)) +
          "  (كان " + str(before) + ")")

    repeats = [e for e in store.values() if e["total"] > 1]
    if repeats:
        print("\n  المتصدّرون تكرارًا:")
        for e in sorted(repeats, key=lambda x: -x["total"])[:5]:
            print("   • " + e["name"] + " — " + str(e["total"]) +
                  " ظهور في " + ", ".join(e["countries"]))
    else:
        print("\n  (لا تكرارات بعد — تظهر بعد أيام من التشغيل)")

    multi = [e for e in store.values() if len(e["countries"]) > 1]
    if multi:
        print("\n  ترند في أكثر من بلد:")
        for e in multi[:5]:
            print("   • " + e["name"] + " — " + ", ".join(e["countries"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
