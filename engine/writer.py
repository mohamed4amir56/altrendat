# -*- coding: utf-8 -*-
"""
طبقة الكتابة — تحوّل المصادر إلى خبر عربي أصلي.

القارئ وصل لأنه بحث عن موضوع، ويريد الخبر نفسه: ماذا حدث ومتى وأين،
والرقم أو الميعاد إن وُجد. لذلك:
- الكاتب يقرأ نص الخبر من صفحته (sources.fetch_text)، لا الملخص القصير
  الذي فوقه. نقص المعلومات كان يدفعه لملء الفراغ بكلام إثارة.
- العنوان خبري دقيق. صياغة «X.. ماذا يخبئ؟» وكلمات الإثارة مرفوضة، والرد
  الذي يخالفها يُعاد مرة واحدة ثم يُترك.
- «المعلومات السريعة» (facts) تُملأ فقط بما في المصادر.

التشغيل يتطلب مفتاحًا:   setx ANTHROPIC_API_KEY "sk-ant-..."
والمكتبة:                pip install anthropic
"""
import concurrent.futures
import json
import os
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dedup  # noqa: E402
import sources  # noqa: E402
import config  # noqa: E402
import photos  # noqa: E402

# Claude Haiku 4.5 — الأسرع والأقل تكلفة (قرار صاحب الموقع).
MODEL = "claude-haiku-4-5-20251001"

# رقم إصدار الكاتب. المقالات القديمة بلا هذا الرقم كُتبت بالبرومبت القديم.
WRITER_VERSION = 2

# مخزن المقالات — منفصل عمدًا عن trends.json.
#
# pipeline.py يعيد بناء trends.json من الصفر في كل تشغيلة، فلو خُزّن
# المقال داخله لضاع مع كل تشغيلة ولأُعيدت كتابة كل الترندات. المفتاح هنا
# (بلد + يوم + عنوان) يبقى ثابتًا عبر التشغيلات.
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


# تعليمات ثابتة عبر كل الطلبات — تُخزَّن مؤقتًا (prompt caching).
SYSTEM = """أنت محرر أخبار في موقع «الترندات». القارئ وصل لأنه بحث عن موضوع بعينه، ويريد أن يعرف الخبر نفسه بسرعة ودقة.

اكتب من المصادر المرفقة وحدها. أي معلومة غير موجودة فيها ممنوعة: رقم أو تاريخ أو ميعاد أو نتيجة أو اقتباس أو وصف لحدث.

العنوان (headline):
- جملة خبرية دقيقة من 7 إلى 14 كلمة تقول أهم ما حدث، وكل ما فيها موجود في المصادر.
- ممنوع العنوان المعلّق بسؤال بعد نقطتين، وممنوعة كلمات الإثارة والمبالغة.
- لا تذكر أن الموضوع رائج أو أن الناس يبحثون عنه.

الملخص (summary):
- جملة واحدة تجيب عما يبحث عنه القارئ: من، وماذا حدث، ومتى أو أين. إن كان في المصادر رقم أو ميعاد أو نتيجة فضعه في هذه الجملة.

المتن (body):
- من 180 إلى 350 كلمة، في 3 إلى 5 فقرات قصيرة يفصل بينها سطر فارغ.
- ابدأ بتفاصيل جديدة ولا تكرر جملة الملخص.
- انسب كل معلومة إلى مصدرها بالاسم.
- إن اختلفت المصادر في معلومة فاذكر الاختلاف.
- لا تكتب عن البحث أو الترند أو اهتمام الجمهور، ولا عبارات إنشائية فارغة.

المعلومات السريعة (facts):
- من 0 إلى 6 أسطر بصيغة «عنوان: قيمة» للمعلومات العملية الموجودة في المصادر فقط، مثل: الموعد، القناة الناقلة، النتيجة، السعر، المكان، الجهة الرسمية.
- إن لم تكن في المصادر معلومات عملية فاتركها فارغة.

الوسوم (tags): من 3 إلى 6 كلمات مفتاحية عربية دقيقة.

إن كان الموضوع عن شخص فصف نشاطه العام كما أوردته المصادر، ولا تنسب إليه اتهامًا ولا تخض في حياته الخاصة.
اكتب بعربية فصحى بسيطة."""

SYSTEM_EN = """You are a news editor at ALTRENDAT. The reader arrived because they searched for a specific topic and wants the actual news, fast and accurate.

Write only from the attached sources. Anything not in them is forbidden: numbers, dates, times, results, quotes, or descriptions of events.

headline:
- An accurate, factual sentence of 7 to 14 words stating what happened; everything in it must appear in the sources.
- No question-style teaser headlines, no hype or sensational words.
- Never mention that the topic is trending or being searched.

summary: one sentence that answers what the reader is looking for (who, what happened, when or where), including any number, time or result from the sources.

body: 180 to 350 words in 3 to 5 short paragraphs separated by blank lines. Start with new details and never repeat the summary. Attribute every claim to its named source. If sources disagree, say so. No filler and no talk about search interest.

facts: 0 to 6 practical "label: value" items found in the sources (date, time, TV channel, score, price, place, official body). Leave empty if none.

tags: 3 to 6 precise English keywords.

For people, describe public activity as reported; no accusations, no private life."""

FACT = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "description": "اسم المعلومة، مثل: الموعد"},
        "value": {"type": "string", "description": "القيمة كما وردت في المصادر"},
    },
    "required": ["label", "value"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "عنوان خبري دقيق من 7 إلى 14 كلمة"},
        "summary": {"type": "string", "description": "جملة واحدة تجيب عما يبحث عنه القارئ"},
        "body": {"type": "string", "description": "المتن 180-350 كلمة في فقرات يفصلها سطر فارغ"},
        "facts": {"type": "array", "items": FACT,
                  "description": "0-6 معلومات عملية من المصادر فقط"},
        "tags": {"type": "array", "items": {"type": "string"},
                 "description": "من 3 إلى 6 كلمات مفتاحية"},
    },
    "required": ["headline", "summary", "body", "facts", "tags"],
    "additionalProperties": False,
}


def _with_decline(schema, desc):
    return {
        "type": "object",
        "properties": dict(schema["properties"], decline={"type": "boolean", "description": desc}),
        "required": schema["required"] + ["decline"],
        "additionalProperties": False,
    }


SCHEMA_PERSON = _with_decline(SCHEMA, "true إن امتنعت عن الكتابة؛ عندها اترك بقية الحقول فارغة")
SCHEMA_PERSON_EN = _with_decline(
    SCHEMA, "true if declining (private individual or sensitive legal/personal topic); leave other fields empty")

PERSON_RULES = """
هذا الاسم قد يكون شخصًا وقد لا يكون. إن كان موضوعًا أو مكانًا أو حدثًا فاكتب عنه كالمعتاد.
إن كان شخصًا فاكتب فقط إن كان شخصية عامة معروفة (فنان، لاعب، مدرب، مسؤول، إعلامي) والمصادر عن نشاطه العام.
أعد decline=true وبقية الحقول فارغة إن كان الشخص فردًا عاديًا، أو تدور المصادر حول اتهام أو قضية أو وفاة أو مرض أو حياة خاصة أو عائلية، أو كان قاصرًا، أو لم تضف المصادر معلومة جديدة عنه.
"""

PERSON_RULES_EN = """
This query might be a person. Write only about a known public figure and their public work or statements.
Return decline=true with other fields empty for a private individual, or if the sources focus on crime, court cases, death, accidents, sexual assault, scandal or private medical details.
"""

# ألفاظ الحديث عن البحث نفسه — القارئ جاء للخبر لا لتقرير عن الإنترنت.
META_WORDS = ("ترند", "تريند", "الأكثر بحث", "محركات البحث", "عمليات البحث",
              "trending", "search volume", "google trends")


def problems(article):
    """أسباب رفض المقال، أو قائمة فارغة إن كان سليمًا."""
    out = []
    why = sources.hype_reason(article.get("headline", ""))
    if why:
        out.append("العنوان مرفوض: " + why)
    if sources.word_count(article.get("headline", "")) > 18:
        out.append("العنوان أطول من 18 كلمة")
    n = sources.word_count(article.get("body", ""))
    if n < config.MIN_BODY_WORDS:
        out.append("المتن {} كلمة فقط، والمطلوب {} على الأقل".format(n, config.MIN_BODY_WORDS))
    head = (article.get("headline", "") + " " + article.get("summary", "")).lower()
    if any(w in head for w in META_WORDS):
        out.append("العنوان أو الملخص يتحدث عن البحث أو الترند")
    return out


def fetch_texts(items):
    """نص كل مصدر من صفحته، بالتوازي ومع مهلة. يُضاف في الحقل text."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(sources.fetch_text, n["url"]): n for n in items}
        done, _ = concurrent.futures.wait(futures, timeout=25)
        for fut in done:
            try:
                futures[fut]["text"] = fut.result(timeout=1)
            except Exception:
                futures[fut]["text"] = ""


def _sources_block(items, is_en):
    parts = []
    for i, n in enumerate(items, 1):
        desc = n.get("og_desc") or n.get("og_title") or ""
        text = (n.get("text") or "").strip()
        if is_en:
            parts.append("Source {} — {}\nTitle: {}\nSummary: {}\nArticle text:\n{}\nURL: {}".format(
                i, n.get("source") or "Unknown", n["title"], desc or "(none)",
                text or "(could not be read — rely on the title and summary)", n["url"]))
        else:
            parts.append("المصدر {} — {}\nالعنوان: {}\nالملخص: {}\nنص الخبر:\n{}\nالرابط: {}".format(
                i, n.get("source") or "غير معروف", n["title"], desc or "(بلا ملخص)",
                text or "(تعذّرت قراءة الصفحة — اعتمد على العنوان والملخص)", n["url"]))
    return "\n\n".join(parts)


def build_prompt(trend, country_name, items, is_en=False):
    block = ""
    if is_en:
        if trend.get("person"):
            block = PERSON_RULES_EN + "\n"
        return ("Search query: {title}\nRegion: {country}\nCategory: {cat}\n\n{block}"
                "News sources:\n\n{src}").format(
            title=trend["title"], country=country_name, cat=trend["category"],
            block=block, src=_sources_block(items, True))

    # البيانات المؤكدة تسبق المصادر: هي جواب القارئ، والخبر سياق حولها.
    data = trend.get("data")
    if data:
        lines = ["", "=== بيانات مؤكدة من جهتها الرسمية ===",
                 data["title"] + " — " + data.get("gregorian", "") + " / " + data.get("hijri", ""),
                 "الجهة: " + data.get("source", ""), "",
                 " | ".join(["المدينة"] + data["columns"])]
        for r in data["rows"]:
            lines.append(" | ".join([r["city"]] + [r["times"][c] for c in data["columns"]]))
        lines += ["", "هذه الأرقام مؤكدة. اذكر أهمها في العنوان وفي الملخص وفي المعلومات السريعة.", ""]
        block = "\n".join(lines)
    # موضوع محلي: مصادره عن هذا البلد، والمقال يبقى عنه ولا يستطرد إلى غيره.
    if trend.get("local_only"):
        block = "\nهذا موضوع محلي: اكتب عن " + country_name + " وحدها.\n" + block
    if trend.get("person"):
        block = PERSON_RULES + block

    return ("ما بحث عنه القارئ: {title}\nالبلد: {country}\nالفئة: {cat}\n{block}\n"
            "المصادر الصحفية:\n\n{src}").format(
        title=trend["title"], country=country_name, cat=trend["category"],
        block=block, src=_sources_block(items, False))


def _call(client, sys_prompt, schema, messages):
    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=[{"type": "text", "text": sys_prompt, "cache_control": {"type": "ephemeral"}}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=messages,
    )
    if response.stop_reason == "refusal":
        return None, None
    if response.stop_reason == "max_tokens":
        return None, None
    for block in response.content:
        if block.type == "text":
            return json.loads(block.text), block.text
    return None, None


def write_one(client, trend, country_name, is_en=False, country_key="world"):
    """يكتب مقال ترند واحد. يعيد dict، أو {"declined": True}، أو
    {"rejected": سبب} إن خالف الرد القواعد مرتين، أو None عند الفشل."""
    person = bool(trend.get("person"))
    sys_prompt = SYSTEM_EN if is_en else SYSTEM
    if is_en:
        schema = SCHEMA_PERSON_EN if person else SCHEMA
    else:
        schema = SCHEMA_PERSON if person else SCHEMA

    items = sources.good_sources(trend.get("news", []))[:4]
    fetch_texts(items)
    prompt = build_prompt(trend, country_name, items, is_en=is_en)
    # النص الكامل للكتابة فقط: لو بقي في الترند لانتقل إلى trends.json
    # وأرشيف الأيام وتضخّم المستودع مع كل تشغيلة.
    for n in items:
        n.pop("text", None)
    messages = [{"role": "user", "content": prompt}]

    article, raw = _call(client, sys_prompt, schema, messages)
    if article is None:
        return None
    if person and (article.pop("decline", False) or not article.get("body")):
        return {"declined": True}
    article.pop("decline", None)

    issues = problems(article)
    if issues:
        # محاولة ثانية واحدة مع سبب الرفض
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "الرد مرفوض للأسباب التالية:\n- " + "\n- ".join(issues) +
             "\nأعد كتابة الرد كاملًا مع الالتزام بالقواعد، ومن المصادر نفسها فقط."},
        ]
        article, raw = _call(client, sys_prompt, schema, messages)
        if article is None:
            return None
        article.pop("decline", None)
        issues = problems(article)
        if issues:
            return {"rejected": "؛ ".join(issues)}

    article["_v"] = WRITER_VERSION
    article["written_at"] = datetime.now(timezone.utc).isoformat()
    # صورة حرة الرخصة عالية الدقة: من ويكيبيديا بالاسم (أشخاص وفرق وأماكن)،
    # وإلا صورة تعبيرية لفئته من كومنز. لا صور صحف.
    try:
        article["photo"] = photos.photo_for(
            trend["title"], trend.get("category", ""), country_key,
            ("en",) if is_en else ("ar", "en"))
    except Exception:
        article["photo"] = photos.stock_photo(
            trend["title"], trend.get("category", ""), country_key)
    return article


def main():
    try:
        import anthropic
    except ImportError:
        print("✗ المكتبة غير مثبّتة.  شغّل:  pip install anthropic")
        return 1

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("✗ لا يوجد مفتاح.  شغّل:  setx ANTHROPIC_API_KEY \"sk-ant-...\"")
        return 1

    path = os.path.join(ROOT, "data", "trends.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # حد اختياري للتجربة:  python engine/writer.py --limit 1
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        print("⚠ وضع التجربة: " + str(limit) + " ترند فقط")
    force = "--force" in sys.argv

    client = anthropic.Anthropic()
    store = load_articles()
    written = skipped = failed = cached = declined = rejected = 0
    attempts = 0
    streak = 0          # فشل متتالٍ = خطأ في الإعداد لا في ترند بعينه

    for key, d in data.items():
        is_en = d.get("lang") == "en" or key == "world"
        cname = d.get("name_en", "Worldwide") if is_en else d["country_name"]
        print("\n" + d["flag"] + "  " + cname)
        day = d.get("day") or d["generated_at"][:10]
        lang = d.get("lang", "en" if is_en else "ar")
        d["trends"] = dedup.dedup_trends(d.get("trends", []), lang=lang)

        for t in d["trends"]:
            if limit is not None and attempts >= limit:
                break
            if streak >= 3:
                print("  ⏹ توقّف: ثلاثة إخفاقات متتالية — راجع الإعداد")
                break
            k = article_key(t, key, day)

            # لا يُكتب إلا ما أجازته طبقة الأمان. وما كُتب قبل أن يتشدّد
            # الفلتر يُحذف الآن، فالمنع يسري على ما سبق أيضًا.
            if not t["publishable"]:
                if store.pop(k, None) is not None:
                    save_articles(store)
                    print("  🗑 حُذف مقال قديم: " + t["title"])
                skipped += 1
                continue

            # مقال كُتب قبل أن يُربط مزوّد بيانات أو قبل استبدال مصادره
            # بأخبار البلد نفسه يُعاد، وإلا بقي بلا أرقامه أو عن بلد آخر.
            has_data = bool(t.get("data"))
            localized = bool(t.get("localized"))
            stale = k in store and (
                (has_data and not store[k].get("_had_data")) or
                (localized and not store[k].get("_localized")))
            if stale:
                print("  ♻ إعادة كتابة (تغيّرت البيانات أو المصادر): " + t["title"])

            if k in store and not force and not stale:
                if store[k].get("declined") or store[k].get("rejected"):
                    continue          # حُسم أمره سابقًا؛ لا مال يُنفق ثانية
                if not store[k].get("photo"):
                    store[k]["photo"] = photos.stock_photo(
                        t["title"], t.get("category", ""), key)
                t["article"] = store[k]
                cached += 1
                continue

            attempts += 1
            try:
                article = write_one(client, t, cname, is_en=is_en, country_key=key)
                if article and article.get("declined"):
                    store[k] = {"declined": True}
                    declined += 1
                    streak = 0
                    print("  ⤫ امتنع الكاتب (شخص غير مناسب للنشر): " + t["title"])
                elif article and article.get("rejected"):
                    store[k] = {"rejected": article["rejected"]}
                    rejected += 1
                    streak = 0
                    print("  ✗ رُفض بعد محاولتين (" + article["rejected"] + "): " + t["title"])
                elif article:
                    article["_had_data"] = has_data
                    article["_localized"] = localized
                    t["article"] = article
                    store[k] = article
                    written += 1
                    streak = 0
                    print("  ✓ " + article["headline"])
                else:
                    failed += 1
                    streak += 1
                save_articles(store)   # حفظ فوري: انقطاع لا يضيّع ما دُفع ثمنه
            except Exception as e:
                failed += 1
                streak += 1
                print("  ✗ " + t["title"] + ": " + type(e).__name__ + ": " + str(e))

    save_articles(store)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 46)
    print("  كُتب الآن: " + str(written) + "   مكتوب سابقًا: " + str(cached))
    print("  تُخطّي (أمان): " + str(skipped) + "   امتنع الكاتب: " + str(declined) +
          "   رُفض: " + str(rejected) + "   فشل: " + str(failed))
    print("=" * 46)
    return 0


if __name__ == "__main__":
    sys.exit(main())
