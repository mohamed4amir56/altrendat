# -*- coding: utf-8 -*-
"""
طبقة الكتابة — تحوّل المصادر المُثراة إلى شرح عربي أصلي.

هذه هي الخطوة التي تفصل الموقع عن مواقع النسخ: كل منافس يأخذ نفس
ملف RSS المجاني، والفرق هو ما يُكتب منه.

التشغيل يتطلب مفتاحًا:   setx ANTHROPIC_API_KEY "sk-ant-..."
والمكتبة:                pip install anthropic
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = "claude-opus-5"

# مخزن الشروح — منفصل عمدًا عن trends.json.
#
# السبب: pipeline.py يعيد بناء trends.json من الصفر في كل تشغيلة، فلو
# خُزّن الشرح داخله لضاع كل 20 دقيقة، ولأُعيدت كتابة كل الترندات من
# جديد: 72 تشغيلة يوميًا × 10 ترندات = 720 نداءً بدل 10. أي 72 ضعف
# الفاتورة. المفتاح هنا (عنوان + يوم) يبقى ثابتًا عبر التشغيلات.
ARTICLES = os.path.join(ROOT, "data", "articles.json")


def load_articles():
    if os.path.exists(ARTICLES):
        with open(ARTICLES, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_articles(store):
    os.makedirs(os.path.dirname(ARTICLES), exist_ok=True)
    with open(ARTICLES, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def article_key(trend, country_key, day):
    return country_key + "|" + day + "|" + trend["title"]

# تعليمات ثابتة عبر كل الطلبات — لذلك تُخزَّن مؤقتًا (prompt caching)
# فيُقرأ ما يقارب عُشر تكلفة الإدخال في كل نداء بعد الأول.
SYSTEM = """أنت محرر عربي في موقع أخبار ترندات. مهمتك أن تشرح للقارئ
لماذا أصبح مصطلح ما الأكثر بحثًا اليوم، اعتمادًا على المصادر المرفقة وحدها.

القواعد:
- اكتب بعربية فصيحة بسيطة يفهمها القارئ العادي، 150 إلى 250 كلمة.
- ابدأ بالإجابة المباشرة عن سؤال: لماذا يبحث الناس عن هذا الآن؟
- انسب كل معلومة إلى مصدرها بالاسم داخل النص.
- لا تذكر رقمًا أو تاريخًا أو اقتباسًا غير موجود في المصادر.
- إن كان الموضوع عن شخص، صِف ما أوردته المصادر فقط، ولا تنسب إليه
  اتهامًا أو فعلًا ولا تقيّمه، ولا تتحدث عن حياته الخاصة.
- إن تعارضت المصادر، قل ذلك صراحةً بدل الترجيح بينها.
- لا تنسخ جملة كما هي من المصادر؛ أعد الصياغة بالكامل.
- لا تخاطب القارئ بعبارات تسويقية ولا تستخدم عناوين مثيرة كاذبة."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "عنوان الصفحة، 6-12 كلمة، صادق بلا مبالغة"},
        "summary": {"type": "string", "description": "جملة واحدة تلخّص سبب الترند"},
        "body":     {"type": "string", "description": "الشرح الكامل 150-250 كلمة"},
        # الوصف وحده لا يُلزم: أول تشغيلة حقيقية أعادت كلمة واحدة فقط.
        # minItems هي ما يفرض العدد فعلًا.
        "tags":     {"type": "array", "items": {"type": "string"},
                     "minItems": 3, "maxItems": 6,
                     "description": "من 3 إلى 6 كلمات مفتاحية عربية للبحث"},
    },
    "required": ["headline", "summary", "body", "tags"],
    "additionalProperties": False,
}


def build_prompt(trend, country_name):
    sources = []
    for i, n in enumerate(trend["news"], 1):
        if not n.get("ok"):
            continue
        sources.append(
            "المصدر {i} — {src}\nالعنوان: {t}\nالملخص: {d}\nالرابط: {u}".format(
                i=i, src=n.get("source") or "غير معروف", t=n["title"],
                d=n.get("og_desc") or n.get("og_title") or "(بلا ملخص)",
                u=n["url"]))

    return (
        "المصطلح الأكثر بحثًا: {title}\n"
        "البلد: {country}\n"
        "حجم البحث التقريبي: {traffic}\n"
        "الفئة: {cat}\n\n"
        "المصادر المتاحة:\n\n{sources}"
    ).format(title=trend["title"], country=country_name,
             traffic=trend["traffic"], cat=trend["category"],
             sources="\n\n".join(sources))


def write_one(client, trend, country_name):
    """يكتب شرح ترند واحد. يعيد dict أو None عند الفشل."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=[{
            "type": "text",
            "text": SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[{"role": "user", "content": build_prompt(trend, country_name)}],
    )

    if response.stop_reason == "refusal":
        cat = getattr(response.stop_details, "category", None)
        print("    ⛔ رفض النموذج الكتابة (" + str(cat) + ") — يُحال للمراجعة")
        return None

    for block in response.content:
        if block.type == "text":
            return json.loads(block.text)
    return None


def main():
    try:
        import anthropic
    except ImportError:
        print("✗ المكتبة غير مثبّتة.  شغّل:  pip install anthropic")
        return 1

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("✗ لا يوجد مفتاح.  شغّل:  setx ANTHROPIC_API_KEY \"sk-ant-...\"")
        print("  ثم أعد فتح نافذة الأوامر.")
        return 1

    path = os.path.join(ROOT, "data", "trends.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # حدّ اختياري للتجربة:  python engine/writer.py --limit 1
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        print("⚠ وضع التجربة: " + str(limit) + " ترند فقط")

    # لا تُعد كتابة ما كُتب — إعادة التشغيل لا تُضاعف الفاتورة
    force = "--force" in sys.argv

    client = anthropic.Anthropic()
    store = load_articles()
    written = skipped = failed = cached = 0

    for key, d in data.items():
        print("\n" + d["flag"] + "  " + d["country_name"])
        day = d["generated_at"][:10]

        for t in d["trends"]:
            if limit is not None and written >= limit:
                break
            # القاعدة الحاسمة: لا يُكتب إلا ما أجازته طبقة الأمان
            if not t["publishable"]:
                print("  ⛔ تخطّي: " + t["title"] + " — " + t["reason"])
                skipped += 1
                continue

            k = article_key(t, key, day)
            if k in store and not force:
                t["article"] = store[k]
                cached += 1
                continue

            try:
                article = write_one(client, t, d["country_name"])
                if article:
                    t["article"] = article
                    store[k] = article
                    save_articles(store)   # حفظ فوري: انقطاع لا يضيّع ما دُفع ثمنه
                    written += 1
                    print("  ✓ " + article["headline"])
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print("  ✗ " + t["title"] + ": " + type(e).__name__ + ": " + str(e))

    save_articles(store)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 46)
    print("  كُتب الآن: " + str(written) + "   مكتوب سابقًا: " + str(cached))
    print("  تُخطّي (أمان): " + str(skipped) + "   فشل: " + str(failed))
    print("=" * 46)
    return 0


if __name__ == "__main__":
    sys.exit(main())
