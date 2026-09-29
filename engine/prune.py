# -*- coding: utf-8 -*-
"""
تنظيف الأرشيف — حذف المقالات الضعيفة والمصطنعة بدل دفع ثمن إعادة كتابتها
(قرار صاحب الموقع، 28 سبتمبر 2026).

  python engine/prune.py --dry-run    # يعرض ما سيُحذف فقط
  python engine/prune.py              # يحذف
  python engine/prune.py --cards      # ويعيد رسم كروت المقالات الباقية

ما يُحذف:
1. «ترندات» مصطنعة: كل مصادرها صفحات رئيسية لمواقع، فلا هي من Google
   Trends ولا أخبارها مقالات. تُحذف من الأرشيف والذاكرة كليًا.
2. مقالات النسخة العالمية خارج السياسة والاقتصاد.
3. مقالات لها أقل من مصدرين حقيقيين بعد حذف مواقع البث والسبام.
4. مقالات متنها أقل من 120 كلمة.
5. مقالات عنوانها مبالغ فيه (sources.hype_reason).

المقال المحذوف يُنزع من يومه ومن articles.json و trends.json، ويُسجَّل
رابطه في data/pruned.json، فيبني له site.py تحويلًا لصفحة الموضوع أو
اليوم. الترند نفسه يبقى في الأرشيف (سجل ما بحث عنه الناس).
التشغيل مرة ثانية آمن: لا يحذف إلا ما بقي فيه سبب.
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import entities  # noqa: E402
import sources  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DAYS = os.path.join(DATA, "days")
PRUNED = os.path.join(DATA, "pruned.json")
MIN_OLD_BODY = 120


def _load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def _save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def is_synthetic(t):
    """ترند بلا مصدر حقيقي واحد: كل روابطه صفحات رئيسية."""
    ok = [n for n in t.get("news", []) if n.get("ok")]
    return bool(t.get("article")) and all(sources.is_homepage(n.get("url", "")) for n in ok)


def weak_reason(key, t):
    """سبب حذف المقال، أو None إن كان سليمًا."""
    art = t.get("article") or {}
    if (key == "world" and config.WORLD_CATEGORIES
            and t.get("category") not in config.WORLD_CATEGORIES):
        return "النسخة العالمية خارج السياسة والاقتصاد"
    if len(sources.good_sources(t.get("news", []))) < 2:
        return "أقل من مصدرين حقيقيين"
    if sources.word_count(art.get("body", "")) < MIN_OLD_BODY:
        return "متن أقل من {} كلمة".format(MIN_OLD_BODY)
    hype = sources.hype_reason(art.get("headline", ""))
    if hype:
        return "عنوان مبالغ فيه: " + hype
    return None


def main():
    dry = "--dry-run" in sys.argv
    now = datetime.now(timezone.utc).isoformat()
    articles = _load(os.path.join(DATA, "articles.json"), {})
    trends_now = _load(os.path.join(DATA, "trends.json"), {})
    store = entities.load()
    pruned = _load(PRUNED, [])
    known = {(p["country"], p["day"], p["slug"]) for p in pruned}

    reasons, kept, removed_titles = Counter(), 0, []
    synthetic_slugs = set()

    for name in sorted(os.listdir(DAYS)):
        if not name.endswith(".json"):
            continue
        key, day = name[:-5].split("-", 1)
        path = os.path.join(DAYS, name)
        snap = _load(path, {})
        out = []
        changed = False
        for t in snap.get("trends", []):
            slug = entities.slugify(t["title"])
            # مواقع البث والسبام تُحذف من مصادر كل ترند، مقالًا كان أو لا
            before = len(t.get("news", []))
            t["news"] = [n for n in t.get("news", []) if not sources.is_spam(n)]
            changed |= len(t["news"]) != before

            if is_synthetic(t):
                reason = "مصطنع: كل مصادره صفحات رئيسية"
                synthetic_slugs.add(slug)
                changed = True
            elif t.get("article"):
                reason = weak_reason(key, t)
            else:
                out.append(t)
                continue

            if not reason:
                kept += 1
                out.append(t)
                continue

            reasons[reason.split(":")[0]] += 1
            removed_titles.append((key, day, reason, (t.get("article") or {}).get("headline", t["title"])))
            articles.pop(key + "|" + day + "|" + t["title"], None)
            if (key, day, slug) not in known:
                pruned.append({"country": key, "day": day, "slug": slug,
                               "title": t["title"], "reason": reason, "at": now})
                known.add((key, day, slug))
            changed = True
            if slug in synthetic_slugs:
                continue                      # المصطنع يُحذف من الأرشيف كليًا
            t.pop("article", None)
            t["pruned"] = reason
            out.append(t)

        if changed and not dry:
            snap["trends"] = out
            _save(path, snap)

    # trends.json: نفس الحذف لترندات اليوم، وإلا أعادها archive_today
    for key, d in trends_now.items():
        day = entities.day_of(d)
        for t in d.get("trends", []):
            slug = entities.slugify(t["title"])
            if (key, day, slug) in known and t.get("article"):
                t.pop("article", None)
                t["pruned"] = True

    for slug in synthetic_slugs:
        store.pop(slug, None)

    total = sum(reasons.values())
    print("سيُحذف" if dry else "حُذف", total, "مقالًا · بقي", kept)
    for r, n in reasons.most_common():
        print("  ", n, "×", r)
    print("\nأمثلة:")
    for key, day, reason, head in removed_titles[:12]:
        print("  [{}] {} {} — {}".format(key, day, head[:70], reason[:40]))

    if dry:
        print("\n(تجربة — لم يُحفظ شيء)")
        return 0

    _save(os.path.join(DATA, "articles.json"), articles)
    _save(os.path.join(DATA, "trends.json"), trends_now)
    entities.save(store)
    _save(PRUNED, pruned)
    print("\n✓ حُفظ: data/days · articles.json · trends.json · entities.json · pruned.json")

    if "--cards" in sys.argv:
        redraw_cards()
    return 0


def redraw_cards():
    """يعيد رسم كروت كل المقالات الباقية — كروت 25 سبتمبر وما بعدها رُسمت
    بحروف مقطّعة على خادم GitHub (انظر arabic.py)."""
    import cards
    snaps = []
    for name in sorted(os.listdir(DAYS)):
        if name.endswith(".json"):
            key, day = name[:-5].split("-", 1)
            snaps.append((key, day, _load(os.path.join(DAYS, name), {})))
    # وترندات اليوم في trends.json: مقالاتها قد لا تكون وصلت لملف اليوم بعد
    for key, snap in _load(os.path.join(DATA, "trends.json"), {}).items():
        snaps.append((key, entities.day_of(snap), snap))

    done = set()
    for key, day, snap in snaps:
        is_en = snap.get("lang") == "en" or key == "world"
        cname = snap.get("name_en", "Worldwide") if is_en else snap.get("country_name", "")
        for t in snap.get("trends", []):
            if not t.get("article"):
                continue
            fname = "{}-{}-{}.png".format(key, day, entities.slugify(t["title"]))
            if fname in done:
                continue
            done.add(fname)
            cards.make_card(t, cname, os.path.join(ROOT, "output", "cards", fname), is_en=is_en)
    print("✓ أعيد رسم", len(done), "كارت")


if __name__ == "__main__":
    sys.exit(main())
