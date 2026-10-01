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
import urllib.error
import urllib.request
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
WRITER_VERSION = 4                # 4: عناوين حيّة بأفعال وأمثلة؛ 3: خطّاف حقيقي في العنوان وأول فقرة

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


# قياس الاستهلاك الفعلي: كل نداء لـ Claude يُحسب هنا ثم يُجمع في data/usage.json
# حسب اليوم، فنعرف التكلفة بالرقم لا بالتقدير. الأسعار لكل مليون توكن (Haiku 4.5).
USAGE_FILE = os.path.join(ROOT, "data", "usage.json")
PRICE_IN, PRICE_OUT = 1.0, 5.0
RUN_USAGE = {"calls": 0, "input": 0, "output": 0, "cut": 0, "refused": 0,
             "g_calls": 0, "g_input": 0, "g_output": 0, "g_errors": 0}
G_PRICE_IN, G_PRICE_OUT = 0.25, 1.50          # Gemini 3.1 Flash-Lite (المدفوع؛ المجاني بلا تكلفة)
GEMINI_MODEL = "gemini-3.1-flash-lite"
LAST_GEMINI_ERROR = [""]

# مقال فشل (قُطع رده أو رُفض) يُعاد في كل تشغيلة ويُدفع ثمنه كل مرة؛
# بعد هذا العدد من الإخفاقات في اليوم نتركه.
FAILURES_FILE = os.path.join(ROOT, "data", "write_failures.json")
MAX_FAILURES = 2


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def save_usage():
    if not (RUN_USAGE["calls"] or RUN_USAGE["g_calls"] or RUN_USAGE["g_errors"]):
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log = _load_json(USAGE_FILE)
    d = log.setdefault(today, {})
    for k in ("calls", "input", "output", "cut", "refused", "written",
              "g_calls", "g_input", "g_output", "g_errors"):
        d[k] = d.get(k, 0) + RUN_USAGE.get(k, 0)
    # usd = ما كان سيُدفع لو كان Gemini مدفوعًا + ما دُفع فعلًا لـ Claude
    d["usd"] = round(d["input"] * PRICE_IN / 1e6 + d["output"] * PRICE_OUT / 1e6, 3)
    d["gemini_usd_if_paid"] = round(d["g_input"] * G_PRICE_IN / 1e6 + d["g_output"] * G_PRICE_OUT / 1e6, 4)
    if LAST_GEMINI_ERROR[0]:
        d["last_gemini_error"] = LAST_GEMINI_ERROR[0]
    for old in sorted(log)[:-14]:                      # أسبوعان فقط
        del log[old]
    _save_json(USAGE_FILE, log)


# تعليمات ثابتة عبر كل الطلبات — تُخزَّن مؤقتًا (prompt caching).
SYSTEM = """أنت محرر أخبار في موقع «الترندات». القارئ وصل لأنه بحث عن موضوع بعينه، ويريد الخبر نفسه بسرعة ودقة، مكتوبًا بطريقة تشدّه حتى آخر سطر.

اكتب من المصادر المرفقة وحدها. أي معلومة غير موجودة فيها ممنوعة: رقم أو تاريخ أو ميعاد أو نتيجة أو اقتباس أو وصف لحدث.

الخطّاف (hook) مطلوب، بشرط واحد: يشدّ القارئ بمعلومة حقيقية، لا بإخفائها. القارئ يأخذ الخبر من العنوان والملخص، والخطّاف هو ما يجعله يكمل القراءة.
والخطّاف لا يضيف وصفًا ولا مكانًا ولا صفة ليست في المصادر: «منطقة عامة» لا تصير «الشارع»، و«قرار» لا يصير «قرارًا تاريخيًا».

العنوان (headline): أهم سطر في الموقع. هو ما يجعل القارئ يضغط، فاكتبه كعنوان صحيفة رياضية أو مجلة حيّة، لا كتقرير رسمي.
- من 7 إلى 13 كلمة، وكل ما فيه موجود في المصادر.
- ابحث في المصادر عن التفصيلة الأكثر حيوية وابنِ العنوان عليها: رقم لافت، هدف في الدقيقة الأخيرة، فارق كبير، أول مرة منذ سنوات، مفارقة (من كذا إلى كذا)، أثر مباشر على جيب القارئ أو يومه.
- أفعال حيّة محددة: يكتسح، يخطف، يحسم، ينفرد، يقلب، يعبر، يطيح، يقفز، يهوي، يكسر. لا أفعال باهتة: يشهد، يتم، يأتي، يحقق.
- مفردات الصحافة الرياضية مسموحة حين تصدق: «خماسية» لخمسة أهداف، «رباعية»، «ثلاثية»، «هدف قاتل» لهدف في آخر الدقائق، «ريمونتادا» لعودة من تأخر، «بشق الأنفس» لفوز بفارق هدف بعد معاناة.
- صيغة «عبارة قصيرة: الخبر» مسموحة إذا كانت العبارة نفسها معلومة لا تخفي شيئًا، مثل: «خماسية في جوبا: مصر تكتسح جنوب السودان وتحصد أول فوز في التصفيات».
- الأرقام بالأرقام (5-0، 88، 20%).
- أمثلة:
  باهت: «منتخب مصر يحقق انتصاره الأول في التصفيات بخمسة أهداف على جنوب السودان»
  حيّ: «خماسية في جوبا: مصر تكتسح جنوب السودان وتحصد أول فوز في التصفيات»
  باهت: «فرنسا تهزم بلجيكا بهدف وحيد وتتصدر المجموعة»
  حيّ: «هدف في الدقيقة 88 يمنح فرنسا صدارة دوري الأمم على حساب بلجيكا»
  باهت: «ارتفاع سعر الذهب في مصر اليوم»
  حيّ: «الذهب يقفز 45 جنيهًا في يوم واحد وعيار 21 يلامس 5200»
- ممنوع: العنوان المعلّق بسؤال أو بنقطتين يخفي الخبر («.. ماذا حدث؟»)، وكلمات الإثارة الفارغة (صادم، مفاجأة، ناري، لن تصدق، يشعل، يفجر...)، وأي صفة أو تضخيم ليس في المصادر. الحيوية تأتي من الوقائع، لا من الصفات.
- لا تذكر أن الموضوع رائج أو أن الناس يبحثون عنه.

الملخص (summary):
- جملة واحدة تجيب فورًا عما يبحث عنه القارئ: من، وماذا حدث، ومتى أو أين، ومعها أهم رقم أو ميعاد أو نتيجة في المصادر.

المتن (body): من 150 إلى 320 كلمة، ولا تنقص عن 150 مهما قلّت المصادر (وسّع الشرح والسياق من المصادر نفسها بلا إضافة وقائع)، في 3 إلى 5 فقرات قصيرة يفصل بينها سطر فارغ، بهذا الترتيب:
1. فقرة الخطّاف (جملة أو جملتان): افتح بأكثر تفصيلة لافتة وملموسة في المصادر لم يذكرها الملخص: اقتباس قوي، أو رقم مع ما يقارَن به، أو مشهد، أو مفارقة. لا تكرر الملخص.
2. لماذا يهم: فقرة قصيرة عما يعنيه الخبر للقارئ أو لمن يتأثر به، كما تورده المصادر أو كما يلزم مباشرة من وقائعها، بلا تخمين.
3. التفاصيل: الوقائع، مع نسبة كل معلومة إلى مصدرها بالاسم. إن اختلفت المصادر فاذكر الاختلاف.
4. الخطوة التالية، إن وُجدت في المصادر: موعد، أو قرار منتظر، أو ما سيحدث بعد ذلك.
- للمواضيع الخدمية (مواقيت، طقس، أسعار، نتائج، مواعيد): الخطّاف هو المعلومة العملية نفسها في أول سطر، بلا تمهيد.
- الأسلوب: جمل قصيرة متنوعة الطول، وأفعال محددة، وكل جملة تضيف معلومة. ممنوع الحشو والعبارات المستهلكة مثل: «في إطار»، «وفي هذا السياق»، «تجدر الإشارة»، «الجدير بالذكر»، «ومن جهة أخرى»، «يأتي ذلك في وقت».
- لا تكتب عن البحث أو الترند أو اهتمام الجمهور.

المعلومات السريعة (facts):
- من 0 إلى 6 أسطر بصيغة «عنوان: قيمة» للمعلومات العملية الموجودة في المصادر فقط، مثل: الموعد، القناة الناقلة، النتيجة، السعر، المكان، الجهة الرسمية.
- إن لم تكن في المصادر معلومات عملية فاتركها فارغة.

الوسوم (tags): من 3 إلى 6 كلمات مفتاحية عربية دقيقة.

إن كان الموضوع عن شخص فصف نشاطه العام كما أوردته المصادر، ولا تنسب إليه اتهامًا ولا تخض في حياته الخاصة.
اكتب بعربية فصحى بسيطة وحيوية، قريبة من القارئ."""

SYSTEM_EN = """You are a news editor at ALTRENDAT. The reader searched for a specific topic and wants the actual news: fast, accurate, and written so they keep reading to the last line.

Write only from the attached sources. Anything not in them is forbidden: numbers, dates, times, results, quotes, or descriptions of events.

Always write in English, even when a source is in Spanish or another language.

Hooks are required, with one rule: hook the reader with a real fact, never by withholding it. The reader gets the news from the headline and summary; the hook is what makes them read on.
A hook never adds a description, place or adjective that is not in the sources: "a public area" does not become "the streets", and "a decision" does not become "a historic decision".

headline: the most important line on the site; it is what makes the reader click. Write it like a lively sports page or magazine, not an official report.
- 7 to 13 words; everything in it must appear in the sources.
- Find the most vivid concrete detail in the sources and build on it: a striking number, a last-minute goal, a big margin, a first in years, a contrast (from X to Y), a direct hit to the reader's wallet or day.
- Vivid, specific verbs: routs, snatches, clinches, topples, surges, plunges, storms, breaks. Never weak ones: sees, is set to, comes amid, achieves.
- Sports vocabulary is fine when true: "late winner" for a goal in the final minutes, "comeback" when a team came from behind, "rout" for a win by 3+ goals.
- A short factual lead-in before a colon is fine if it hides nothing: "Five-star Egypt: Pharaohs rout South Sudan for first qualifying win".
- Numbers as digits (5-0, 88th minute, 20%).
- Examples:
  flat: "France defeats Belgium by one goal and tops the group"
  lively: "88th-minute winner sends France top of Nations League group over Belgium"
- Forbidden: question or colon teasers that hide the news, empty hype words (shocking, stunning, you won't believe...), and any adjective or claim that is not in the sources. The energy comes from the facts, not from adjectives.
- Never mention that the topic is trending or being searched.

summary: one sentence that immediately answers who, what happened, and when or where, with the key number, time or result from the sources.

body: 180 to 350 words in 3 to 5 short paragraphs separated by blank lines, in this order:
1. Hook paragraph (one or two sentences): open with the most striking concrete detail in the sources that the summary did not use: a strong quote, a number set against its comparison, a scene, or a contrast. Never repeat the summary.
2. Why it matters: a short paragraph on what the news means for readers or for those affected, as the sources report it or as follows directly from their facts. No speculation.
3. Details: the facts, each attributed to its named source. If sources disagree, say so.
4. What's next, if the sources say: a date, an expected decision, the next step.
- For service topics (times, weather, prices, scores, schedules), the hook is the practical answer itself in the first line, with no wind-up.
- Style: short sentences of varied length, concrete verbs, and every sentence adds information. No filler or clichés ("in a stunning turn of events", "it is worth noting", "in the wake of", "only time will tell").
- No talk about search interest.

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
        "headline": {"type": "string",
                     "description": "عنوان حيّ من 7 إلى 13 كلمة مبني على أكثر تفصيلة حيوية في الخبر، بفعل قوي"},
        "summary": {"type": "string", "description": "جملة واحدة تجيب فورًا عما يبحث عنه القارئ"},
        "body": {"type": "string",
                 "description": "150-320 كلمة (لا أقل من 150): فقرة خطّاف، ثم لماذا يهم، ثم التفاصيل، ثم الخطوة التالية"},
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


def _call_gemini(sys_prompt, schema, messages):
    """نداء Gemini عبر REST. يعيد (dict، النص) أو (None، None) إن قُطع/حُجب.
    يرفع استثناء عند أي خطأ آخر فيرجع _call إلى Claude."""
    contents = [{"role": "model" if m["role"] == "assistant" else "user",
                 "parts": [{"text": m["content"]}]} for m in messages]
    cats = ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")
    body = {
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json",
                             "responseJsonSchema": schema, "maxOutputTokens": 6000},
        # أخبار الحروب والجرائم تُحجب بالإعدادات الافتراضية؛ نخفّف إلى الحد الأعلى فقط.
        "safetySettings": [{"category": c, "threshold": "BLOCK_ONLY_HIGH"} for c in cats],
    }
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(GEMINI_MODEL),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError("Gemini HTTP {}: {}".format(e.code, e.read().decode("utf-8", "replace")[:300]))
    u = data.get("usageMetadata", {})
    RUN_USAGE["g_calls"] += 1
    RUN_USAGE["g_input"] += u.get("promptTokenCount", 0)
    RUN_USAGE["g_output"] += u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
    cands = data.get("candidates") or []
    if not cands:                                      # حُجب الطلب كله
        RUN_USAGE["refused"] += 1
        return None, None
    c = cands[0]
    if c.get("finishReason") == "MAX_TOKENS":
        RUN_USAGE["cut"] += 1
        return None, None
    if c.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"):
        RUN_USAGE["refused"] += 1
        return None, None
    text = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []))
    return json.loads(text), text


LAST_PROVIDER = [""]       # من كتب آخر رد ناجح: يُوسم به المقال
GEMINI_OFF = [False]       # بعد رفض حصة/رصيد لا نعيد المحاولة في بقية التشغيلة


def _call(client, sys_prompt, schema, messages):
    if (os.environ.get("GEMINI_API_KEY") and not GEMINI_OFF[0]
            and os.environ.get("WRITER_PROVIDER", "gemini") == "gemini"):
        try:
            out = _call_gemini(sys_prompt, schema, messages)
            LAST_PROVIDER[0] = "gemini"
            return out
        except Exception as e:                         # حصة، شبكة، JSON مكسور: Claude يكمل
            RUN_USAGE["g_errors"] += 1
            LAST_GEMINI_ERROR[0] = (type(e).__name__ + ": " + str(e))[:300]
            if any(c in LAST_GEMINI_ERROR[0] for c in ("HTTP 402", "HTTP 429", "HTTP 401", "HTTP 403")):
                GEMINI_OFF[0] = True
            print("  ⚠ Gemini فشل، التحويل إلى Claude: " + LAST_GEMINI_ERROR[0][:160])
    LAST_PROVIDER[0] = "claude"
    return _call_claude(client, sys_prompt, schema, messages)


def _call_claude(client, sys_prompt, schema, messages):
    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=[{"type": "text", "text": sys_prompt, "cache_control": {"type": "ephemeral"}}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=messages,
    )
    u = response.usage
    RUN_USAGE["calls"] += 1
    RUN_USAGE["input"] += (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0) \
        + (getattr(u, "cache_read_input_tokens", 0) or 0)
    RUN_USAGE["output"] += u.output_tokens or 0
    if response.stop_reason == "refusal":
        RUN_USAGE["refused"] += 1
        return None, None
    if response.stop_reason == "max_tokens":
        RUN_USAGE["cut"] += 1
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

    items = sources.good_sources(trend.get("news", []))[:3]
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
    article["_by"] = LAST_PROVIDER[0]       # gemini أو claude، للمراجعة والمقارنة
    article["written_at"] = datetime.now(timezone.utc).isoformat()
    # صورة حرة الرخصة تخص الخبر: صاحبه أو أحد أعلامه من ويكيبيديا، أو صورة
    # تعبيرية تطابق موضوعه، وإلا لا شيء (فيُعرض كارت الموقع). لا صور صحف.
    try:
        photos.mark(article, photos.photo_for(
            trend["title"], trend.get("category", ""), country_key,
            ("en",) if is_en else ("ar", "en"), article))
    except Exception:
        # تعذّر الاتصال: صورة تعبيرية إن طابقت، وتكمل photos.py الباقي لاحقًا
        article["photo"] = photos.stock_photo(
            trend["title"], trend.get("category", ""), country_key,
            photos.photo_text(article))
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
    failures = _load_json(FAILURES_FILE)
    failures = {k: v for k, v in failures.items() if v.get("day") == datetime.now(timezone.utc).strftime("%Y-%m-%d")}
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

        # النسخة الإنجليزية: حد يومي (config.WORLD_DAILY_MAX) والأكبر بحثًا أولًا،
        # فالحد يروح لأهم الترندات لا لأول ما وصل.
        order = d["trends"]
        world_left = None
        if key == "world":
            order = sorted(d["trends"], key=lambda x: -x.get("traffic_num", 0))
            done_today = sum(1 for sk, a in store.items()
                             if sk.startswith("world|" + day + "|") and isinstance(a, dict)
                             and a.get("body"))
            world_left = max(0, config.WORLD_DAILY_MAX - done_today)
            print("  الحد اليومي: كُتب {} من {}".format(done_today, config.WORLD_DAILY_MAX))

        for t in order:
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
                t["article"] = store[k]
                cached += 1
                continue

            if world_left is not None and world_left <= 0 and not stale:
                skipped += 1          # الحد اليومي للإنجليزي اكتمل؛ يُرصد ولا يُكتب
                continue

            if failures.get(k, {}).get("n", 0) >= MAX_FAILURES and not force:
                skipped += 1          # فشل مرتين اليوم؛ لا ندفع ثمنه ثالثة
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
                    RUN_USAGE["written"] = RUN_USAGE.get("written", 0) + 1
                    failures.pop(k, None)
                    streak = 0
                    if world_left is not None and not stale:
                        world_left -= 1
                    print("  ✓ " + article["headline"])
                else:
                    failed += 1
                    streak += 1
                    f = failures.setdefault(k, {"n": 0})
                    f["n"] += 1
                    f["day"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                save_articles(store)   # حفظ فوري: انقطاع لا يضيّع ما دُفع ثمنه
            except Exception as e:
                failed += 1
                streak += 1
                print("  ✗ " + t["title"] + ": " + type(e).__name__ + ": " + str(e))

    save_articles(store)
    _save_json(FAILURES_FILE, failures)
    save_usage()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 46)
    print("  استهلاك التشغيلة: {calls} نداء، {input} دخل، {output} خرج، "
          "قُطع {cut}، رُفض {refused}".format(**RUN_USAGE))
    print("  Gemini: {g_calls} نداء، {g_input} دخل، {g_output} خرج، أخطاء {g_errors}".format(**RUN_USAGE))
    print("  كُتب الآن: " + str(written) + "   مكتوب سابقًا: " + str(cached))
    print("  تُخطّي (أمان): " + str(skipped) + "   امتنع الكاتب: " + str(declined) +
          "   رُفض: " + str(rejected) + "   فشل: " + str(failed))
    print("=" * 46)
    return 0


if __name__ == "__main__":
    sys.exit(main())
