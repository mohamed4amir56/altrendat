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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dedup  # noqa: E402
# المعرّف مأخوذ من client.models.list() لا من التخمين.
# نستخدم نموذج Claude Haiku 4.5: أسرع نموذج وأقلها تكلفة (~95% توفير).
MODEL = "claude-haiku-4-5-20251001"

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
SYSTEM = """أنت محرر صحفي استقصائي ومحترف في الصحافة الرقمية السريعة والذكية. مهمتك كتابة الخبر وصياغة عناوينه بأسلوب Hook مشوق يشد القارئ ويشعل فضوله من أول نظرة، اعتمادًا على المصادر المرفقة وحدها وبلا كذب أو تضليل.

القواعد:
- العنوان هو خُطّاف القراءة الأهم (Headline Hook): صغ عنوانًا مشوقًا من 8 إلى 14 كلمة يثير الفضول بذكاء ويدفع القارئ للنقر والقراءة فورًا. ركّز على المفاجأة، أو التحول الدرامي في الأحداث، أو كواليس ما حدث، أو الأثر المباشر على القارئ والأسواق (مثل: "مفاجأة في قرار المركزي.. ماذا يعني تثبيت الفائدة لأسعار الذهب غداً؟" أو "بهدف خيالي.. كيف خطف مرموش أنظار العالم الليلة؟"). تجنب العناوين الباردة الميتة التي تشبه البيانات الحكومية الروتينية.
- الافتتاحية الساخنة (Hook Lead): ابدأ بالذروة والمفاجأة مباشرة: ماذا حدث فجأة، وما هو التطور الصادم أو القرار الحاسم، وماذا يعني للمتابعين.
- اكتب بعربية فصيحة سلسة وذكية يفهمها القارئ العادي، 150 إلى 250 كلمة مقسمة إلى فقرات مركزة.
- لا تكتب عن البحث ولا عن الترند ولا عن الخوارزميات. القارئ جاء ليعرف القصة والحدث، لا ليقرأ تقريرًا عن عادات الإنترنت. عبارات مثل "يرجع ارتفاع البحث" و"يتصدر الترند" و"أثار اهتمام الجمهور" ممنوعة منعًا باتًا في المقال وفي العنوان.
- كل جملة يجب أن تضيف معلومة وحقيقة أو تُحذف؛ تجنب الجمل الإنشائية الفارغة.
- انسب كل معلومة إلى مصدرها بالاسم داخل النص.
- لا تذكر رقمًا أو تاريخًا أو اقتباسًا غير موجود في المصادر.
- إن كان الموضوع عن شخص، صِف ما أوردته المصادر حول نشاطه العام وتصريحاته، ولا تنسب إليه اتهامًا أو تخوض في حياته الخاصة.
- إن أُرفقت بيانات أو أرقام، اذكرها فورًا لأنها جوهر ما يبحث عنه القارئ.
- في حقل tags ضع من 3 إلى 6 كلمات مفتاحية عربية دقيقة."""

SYSTEM_EN = """You are a world-class digital investigative editor and master of high-engagement news storytelling. Your mission is to craft irresistible Hook Headlines and fact-rich, thrilling news stories based SOLELY on the provided sources, completely free of fluff or falsehoods.

Core Directives:
- Headline Hook (The Click Magnet): Craft a compelling, curiosity-igniting headline of 8 to 14 words in Title Case. Center it on the unexpected twist, the high stakes, breaking controversy, or dramatic outcome (e.g. "Shocking Verdict: Man City Found Guilty of 114 Financial Breaches as Historic Sanctions Loom" or "Stunning Last-Minute Strike: How Modern Stars Redrew the Nations League Race"). Never produce dry, bureaucratic press release titles.
- Hot Hook Lead: Open with the dramatic peak and climax in the very first sentence. Tell the reader what shocking event just unfolded, who made the decisive move, and what it triggers.
- Rich & Fact-Packed Body: Write in authoritative, vibrant, and precise English (180 to 280 words) organized into short, punchy paragraphs. Pack every sentence with concrete facts, verified statistics, dates, names of key players, and quotes from sources. Empty filler phrases are strictly banned.
- Absolutely Zero Meta-Talk: Never mention search engines, Google Trends, search spikes, algorithms, or "searches surged". The reader wants the real story, not internet traffic reports.
- Source Attribution: Explicitly attribute every key claim to its named source (e.g., "according to Reuters", "The Athletic reported").
- Public Figure Standards: Focus strictly on public actions, official statements, and career milestones. Do not speculate on private personal lives.
- Search Intent Tags: Provide 3 to 6 high-intent English keywords in the tags field."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string",
                     "description": "عنوان صحفي مشوق ومحفز للنقر (Hook Headline) من 8-14 كلمة يثير الفضول بذكاء، بلا ذكر ترند أو بحث"},
        "summary": {"type": "string", "description": "افتتاحية ساخنة وسريعة تلخص المفاجأة أو الحدث الأساسي في جملة واحدة"},
        "body":     {"type": "string", "description": "الخبر كاملًا 150-250 كلمة مركزة ومقسمة لفقرات"},
        "tags":     {"type": "array", "items": {"type": "string"},
                     "description": "من 3 إلى 6 كلمات مفتاحية عربية للبحث"},
    },
    "required": ["headline", "summary", "body", "tags"],
    "additionalProperties": False,
}

SCHEMA_EN = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": "Magnetic, curiosity-piquing hook headline (8-14 words, Title Case, no search meta-talk, zero false clickbait)",
        },
        "summary": {
            "type": "string",
            "description": "Urgent, gripping hook lead summarizing the climax or central breakthrough in one punchy sentence",
        },
        "body": {
            "type": "string",
            "description": "Full informative story (180-280 words) packed with verified facts, divided into crisp paragraphs, citing sources by name",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3 to 6 high-intent English search keywords or entity names",
        },
    },
    "required": ["headline", "summary", "body", "tags"],
    "additionalProperties": False,
}

SCHEMA_PERSON = {
    "type": "object",
    "properties": dict(SCHEMA["properties"], decline={
        "type": "boolean",
        "description": "true إن امتنعت عن الكتابة؛ عندها اترك بقية الحقول فارغة"}),
    "required": SCHEMA["required"] + ["decline"],
    "additionalProperties": False,
}

SCHEMA_PERSON_EN = {
    "type": "object",
    "properties": dict(SCHEMA_EN["properties"], decline={
        "type": "boolean",
        "description": "Set to true if declining to write about a private non-public individual or sensitive legal/personal issue; leave other fields empty"}),
    "required": SCHEMA_EN["required"] + ["decline"],
    "additionalProperties": False,
}

PERSON_RULES = """
هذا الاسم قد يكون شخصًا وقد لا يكون. إن كان موضوعًا أو مكانًا أو حدثًا
فاكتب عنه كالمعتاد.
إن كان شخصًا فاكتب فقط إن كان شخصية عامة معروفة (فنان، لاعب، مدرب، مسؤول،
إعلامي) والمصادر عن نشاطه العام: عمله، مبارياته، أعماله، تصريحاته المنشورة.
أعد decline=true وبقية الحقول فارغة إن كان الشخص فردًا عاديًا، أو تدور
المصادر حول اتهام أو قضية أو وفاة أو مرض أو حياة خاصة أو عائلية، أو كان
قاصرًا، أو لم تضف المصادر معلومة جديدة عنه.
لا تنسب إليه رأيًا أو فعلًا لم تذكره المصادر، وانسب كل قول لقائله بالاسم.
"""

PERSON_RULES_EN = """
This trending query might be a person.
- If it is a known public figure (athlete, artist, filmmaker, CEO, public official) and the news covers their public career, works, games, or official statements, write the explanation.
- Return decline=true and leave other fields empty if the person is a private non-public individual, or if the sources focus on violent crime, court prosecution, death, tragic accident, sexual assault, personal scandal, or private medical details.
"""


def build_prompt_en(trend, country_name):
    sources = []
    for i, n in enumerate(trend["news"], 1):
        if not n.get("ok"):
            continue
        sources.append(
            "Source {i} — {src}\nTitle: {t}\nSummary: {d}\nURL: {u}".format(
                i=i, src=n.get("source") or "Unknown", t=n["title"],
                d=n.get("og_desc") or n.get("og_title") or "(no description)",
                u=n["url"]))

    block = ""
    if trend.get("person"):
        block = PERSON_RULES_EN + "\n"

    return (
        "Trending Search Query: {title}\n"
        "Region: {country}\n"
        "Search Traffic: {traffic}\n"
        "Category: {cat}\n\n"
        "{block}"
        "News Sources:\n\n{sources}"
    ).format(title=trend["title"], country=country_name,
             traffic=trend["traffic"], cat=trend["category"],
             block=block, sources="\n\n".join(sources))


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

    # البيانات المؤكدة تسبق المصادر: هي جواب القارئ، والخبر سياق حولها.
    block = ""
    data = trend.get("data")
    if data:
        lines = [
            "",
            "=== بيانات مؤكدة من جهتها الرسمية ===",
            data["title"] + " — " + data.get("gregorian", "") +
            " / " + data.get("hijri", ""),
            "الجهة: " + data.get("source", ""),
            "",
            " | ".join(["المدينة"] + data["columns"]),
        ]
        for r in data["rows"]:
            lines.append(" | ".join(
                [r["city"]] + [r["times"][c] for c in data["columns"]]))
        lines += [
            "",
            "هذه الأرقام مؤكدة ومتاحة لك. اذكر أهمها في العنوان وفي أول "
            "جملتين، ولا تقل إن المواعيد غير متوفرة.",
            "",
        ]
        block = "\n".join(lines)

    # موضوع محلي (انظر LOCAL_CATEGORIES في pipeline): مصادره اختيرت لأنها
    # عن هذا البلد، والمقال يبقى عنه ولا يستطرد إلى غيره.
    if trend.get("local_only"):
        block = ("\nهذا موضوع محلي: اكتب عن " + country_name +
                 " وحدها، ولا تنقل أخبار بلد آخر.\n") + block

    if trend.get("person"):
        block = PERSON_RULES + block

    return (
        "المصطلح الأكثر بحثًا: {title}\n"
        "البلد: {country}\n"
        "حجم البحث التقريبي: {traffic}\n"
        "الفئة: {cat}\n"
        "{block}\n"
        "المصادر الصحفية:\n\n{sources}"
    ).format(title=trend["title"], country=country_name,
             traffic=trend["traffic"], cat=trend["category"],
             block=block, sources="\n\n".join(sources))


def write_one(client, trend, country_name, is_en=False):
    """يكتب شرح ترند واحد. يعيد dict، أو {"declined": True} إن امتنع
    الكاتب عن شخص غير مناسب، أو None عند الفشل."""
    person = bool(trend.get("person"))
    sys_prompt = SYSTEM_EN if is_en else SYSTEM
    if is_en:
        active_schema = SCHEMA_PERSON_EN if person else SCHEMA_EN
        user_prompt = build_prompt_en(trend, country_name)
    else:
        active_schema = SCHEMA_PERSON if person else SCHEMA
        user_prompt = build_prompt(trend, country_name)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=[{
            "type": "text",
            "text": sys_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={
            "format": {"type": "json_schema",
                       "schema": active_schema},
        },
        messages=[{"role": "user", "content": user_prompt}],
    )

    if response.stop_reason == "refusal":
        cat = getattr(response.stop_details, "category", None)
        print("    ⛔ رفض النموذج الكتابة (" + str(cat) + ") — يُحال للمراجعة")
        return None

    for block in response.content:
        if block.type == "text":
            article = json.loads(block.text)
            if person:
                # جسم فارغ بلا امتناع صريح يُعامل امتناعًا أيضًا: الأسلم
                # ألا تُنشر صفحة فارغة عن شخص.
                if article.pop("decline", False) or not article.get("body"):
                    return {"declined": True}
            return article
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
    written = skipped = failed = cached = declined = 0
    attempts = 0
    streak = 0          # فشل متتالٍ

    for key, d in data.items():
        is_en = d.get("lang") == "en" or key == "world"
        cname = d.get("name_en", "Worldwide") if is_en else d["country_name"]
        print("\n" + d["flag"] + "  " + (cname if is_en else d["country_name"]))
        # نفس قاعدة entities.day_of: اليوم بتوقيت البلد
        day = d.get("day") or d["generated_at"][:10]
        lang = d.get("lang", "en" if is_en else "ar")
        d["trends"] = dedup.dedup_trends(d.get("trends", []), lang=lang)

        for t in d["trends"]:
            # الحد يحسب المحاولات لا النجاحات: لو حسب النجاحات وحدها،
            # لواصل خطأ منهجي استهلاك الطلبات حتى آخر ترند.
            if limit is not None and attempts >= limit:
                break
            # قاطع دورة: ثلاثة إخفاقات متتالية تعني خطأً في الإعداد
            # لا مشكلة في ترند بعينه — توقّف بدل مهاجمة الخدمة.
            if streak >= 3:
                print("  ⏹ توقّف: ثلاثة إخفاقات متتالية — راجع الإعداد")
                break
            k = article_key(t, key, day)

            # القاعدة الحاسمة: لا يُكتب إلا ما أجازته طبقة الأمان
            if not t["publishable"]:
                # وإن كان مكتوبًا قبل أن يتشدّد الفلتر، يُحذف الآن.
                # بوابة الأمان يجب أن تُبطل ما أجازته سابقًا بالخطأ،
                # وإلا بقي مقال عن شخص مخزَّنًا بعد منع النشر عنه.
                if store.pop(k, None) is not None:
                    save_articles(store)
                    print("  🗑 حُذف مقال قديم: " + t["title"])
                print("  ⛔ تخطّي: " + t["title"] + " — " + t["reason"])
                skipped += 1
                continue
            # مقال كُتب قبل أن يُربط مزوّد بيانات بهذا الترند لا يحمل
            # أرقامه، فيبقى يدور حول الموضوع بلا أن يعطيه. إضافة مزوّد
            # تُبطل المخزون، وإلا ظلّت الصفحة القديمة تُعرض بلا أرقام.
            # الشرط ضيّق عمدًا: يُعاد فقط ما صارت له بيانات ولم تكن له.
            # المقارنة المتماثلة (`!=`) أعادت كتابة كل شيء أول مرة، لأن
            # المقالات القديمة لا تحمل الحقل أصلًا فيعود None ويخالف
            # False. وفقدان البيانات لا يستدعي إنفاقًا: النص المكتوب
            # يبقى صحيحًا ومنسوبًا لوقته.
            has_data = bool(t.get("data"))
            stale = k in store and has_data and not store[k].get("_had_data")
            if stale:
                print("  ♻ إعادة كتابة (تغيّرت البيانات): " + t["title"])

            # وبالقاعدة الضيقة نفسها: مقال كُتب من مصادر عن بلد آخر، ثم
            # استُبدلت بها أخبار البلد (localize في pipeline)، يُعاد — وإلا
            # عُرض نص عن طقس الإمارات فوق مصادر مصرية.
            localized = bool(t.get("localized"))
            if (k in store and localized and not stale
                    and not store[k].get("_localized")):
                stale = True
                print("  ♻ إعادة كتابة (مصادر محلية): " + t["title"])

            if k in store and not force and not stale:
                if store[k].get("declined"):
                    continue          # امتنع الكاتب عنه سابقًا؛ لا مال يُنفق ثانية
                t["article"] = store[k]
                cached += 1
                continue

            attempts += 1
            try:
                article = write_one(client, t, cname, is_en=is_en)
                if article and article.get("declined"):
                    store[k] = {"declined": True}
                    save_articles(store)
                    declined += 1
                    streak = 0
                    print("  ⤫ امتنع الكاتب (شخص غير مناسب للنشر): " + t["title"])
                elif article:
                    n_tags = len(article.get("tags") or [])
                    if n_tags < 3:
                        print("  ⚠ " + str(n_tags) + " كلمة مفتاحية فقط")
                    article["_had_data"] = has_data
                    article["_localized"] = localized
                    t["article"] = article
                    store[k] = article
                    save_articles(store)   # حفظ فوري: انقطاع لا يضيّع ما دُفع ثمنه
                    written += 1
                    streak = 0
                    print("  ✓ " + article["headline"])
                else:
                    failed += 1
                    streak += 1
            except Exception as e:
                failed += 1
                streak += 1
                print("  ✗ " + t["title"] + ": " + type(e).__name__ + ": " + str(e))

    save_articles(store)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 46)
    print("  كُتب الآن: " + str(written) + "   مكتوب سابقًا: " + str(cached))
    print("  تُخطّي (أمان): " + str(skipped) + "   امتنع الكاتب: " +
          str(declined) + "   فشل: " + str(failed))
    print("=" * 46)
    return 0


if __name__ == "__main__":
    sys.exit(main())
