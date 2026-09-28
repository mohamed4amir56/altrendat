# -*- coding: utf-8 -*-
"""
جودة المصادر والعناوين — قواعد يشترك فيها المحرّك والكاتب والموقع والحارس.

1. مصادر مرفوضة: مواقع البث المقرصن وصفحات السبام التي تظهر أحيانًا
   ضمن أخبار Google Trends. الربط بها مخالف لسياسة حقوق النشر في AdSense.
2. مصادر لا تُحسب: الصفحة الرئيسية لموقع ما ليست خبرًا.
3. عناوين مبالغ فيها: صياغة «X.. ماذا يخبئ؟» وكلمات الإثارة.
4. نص المقال كاملًا: الكاتب يقرأ الخبر نفسه لا الملخص الذي فوقه.
"""
import gzip
import html
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# ── 1. مواقع البث والسبام ─────────────────────────────────────────
SPAM_DOMAINS = (
    "yalla-shoot", "yallashoot", "yalla-live", "yallalive", "kora-live",
    "koora-live", "kooralive", "livekoora", "kora-star", "korastar",
    "crackstreams", "streameast", "methstreams", "buffstreams", "totalsportek",
    "sportsurge", "hesgoal", "footybite", "vipbox", "vipleague", "rojadirecta",
    "livetv.sx", "sportsbay", "cricfy", "streamsgate", "soccerstreams",
    "redditsoccerstreams", "nbabite", "nflbite", "mlbbite", "scorebat",
    "weakstreams", "720pstream", "sportshd", "freestreams", "bilasport",
)

SPAM_TITLE = [re.compile(p, re.I) for p in (
    r"\[\[\[", r"@!!", r"a-s-s-i-s-t-i-r", r"\bassistir\b", r"\bao\s*vivo\b",
    r"\ben\s+vivo\s+(gratis|online)\b",
    r"\blive\s+free\b", r"\bfree\s+(live\s+)?stream", r"\blive\s*stream(ing)?\s+(free|online|hd|reddit)\b",
    r"\bwatch\s+.{0,80}\b(free|online)\b", r"\breddit\s*streams?\b",
    r"بث\s*مباشر\s*(مجان|بدون\s*تقطيع|hd\b)", r"مشاهدة\s*.{0,40}بث\s*مباشر\s*(الآن|مجان)",
)]


def _host(url):
    try:
        return urllib.parse.urlparse(url or "").netloc.lower()
    except Exception:
        return ""


def is_spam(item):
    """مصدر بث مقرصن أو سبام — لا يُعرض ولا يُحسب."""
    host = _host(item.get("url", ""))
    if any(d in host for d in SPAM_DOMAINS):
        return True
    title = (item.get("title") or "") + " " + (item.get("og_title") or "")
    if any(p.search(title) for p in SPAM_TITLE):
        return True
    # رموز متراكمة في العنوان علامة سبام شبه مؤكدة
    return len(re.findall(r"[\[\]\^@|]", title)) >= 4


def is_homepage(url):
    """رابط الصفحة الرئيسية لموقع ما ليس خبرًا يُستشهد به."""
    try:
        path = urllib.parse.urlparse(url or "").path
    except Exception:
        return True
    return bool(re.fullmatch(r"/?((ar|en)/?)?(index\.(html?|php|aspx))?/?", path or "/"))


def good_sources(news):
    """المصادر الصالحة للعرض والحساب: بنص، ليست سبامًا، وليست صفحة رئيسية."""
    return [n for n in news
            if n.get("ok") and not is_spam(n) and not is_homepage(n.get("url", ""))]


# ── 3. العناوين المبالغ فيها ─────────────────────────────────────
# صياغة الخطّاف التي فرضها البرومبت القديم: «جملة.. ماذا/كيف/هل ...؟»
HOOK_RE = re.compile(r"\.\.\s*(ماذا|كيف|هل|لماذا|ما|من|متى|أين|ما الذي)\s.*[؟?]\s*$")

# كل كلمة بحدودها: «ناري» داخل «سيناريو» ليست إثارة. يُسمح بسابقة
# (و، ف، ب، ل، ك، ال) وباللواحق الشائعة.
_AR = "؀-ۿ"
_HYPE_WORDS = (
    "خيالي", "خيالية", "جنوني", "جنونية", "ناري", "نارية", "صادم", "صادمة",
    "صدمة", "مفاجأة", "مفاجآت", "مفاجاة", "لن تصدق", "يخطف الأنظار",
    "خطف الأنظار", "تخطف الأنظار", "ليلة الحسم", "يشعل", "تشعل", "أشعل",
    "يثير عاصفة", "ضجة كبرى", "بالفيديو", "شاهد", "سيناريو جنوني",
    "قنبلة الموسم", "يفجر", "يفجّر",
)
HYPE_AR = re.compile(
    "(?<![" + _AR + "])(?:[وفبلك]?ال|[وفبلك])?(" +
    "|".join(re.escape(w) for w in _HYPE_WORDS) +
    ")(?:ة|ات|ين|ون|ه|ها)?(?![" + _AR + "])"
    "|تحطيم\\s+\\S*أرقام")
HYPE_EN = re.compile(
    r"\b(shocking|stunning|unbelievable|you won'?t believe|jaw-?dropping|"
    r"mind-?blowing|insane|explosive|epic)\b", re.I)


def hype_reason(headline):
    """سبب رفض العنوان، أو None إن كان العنوان سليمًا."""
    h = (headline or "").strip()
    if HOOK_RE.search(h):
        return "صياغة خطّاف «.. ماذا/كيف؟»"
    m = HYPE_AR.search(h) or HYPE_EN.search(h)
    if m:
        return "كلمة إثارة: " + m.group(0)
    return None


def word_count(text):
    return len(re.findall(r"\w+", text or "", re.UNICODE))


# ── 4. نص المقال كاملًا ───────────────────────────────────────────
_DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|nav|header|footer|aside|form|figure|svg|iframe)\b.*?</\1\s*>",
    re.I | re.S)
_COMMENTS = re.compile(r"<!--.*?-->", re.S)
_ARTICLE = re.compile(r"<article\b[^>]*>(.*?)</article\s*>", re.I | re.S)
_PARA = re.compile(r"<p\b[^>]*>(.*?)</p\s*>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_BOILER = re.compile(
    r"(اقرأ أيض|اقرأ ايض|تابعونا|تابعوا|اشترك|للاشتراك|جميع الحقوق|حقوق النشر|"
    r"شارك الخبر|نشرة|ملفات تعريف الارتباط|cookie|subscribe|newsletter|"
    r"read more|advertisement|all rights reserved|follow us|sign up)", re.I)


def _charset(headers, head):
    ct = headers.get("Content-Type", "") if headers else ""
    m = re.search(r"charset=([\w-]+)", ct, re.I) or re.search(
        rb"<meta[^>]+charset=[\"']?([\w-]+)", head, re.I)
    if not m:
        return "utf-8"
    cs = m.group(1)
    return cs.decode("ascii", "ignore") if isinstance(cs, bytes) else cs


_JSONLD = re.compile(
    r"<script[^>]+application/ld\+json[^>]*>(.*?)</script\s*>", re.I | re.S)


def _trim(text, max_chars):
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind("."), cut.rfind("۔"), cut.rfind("؟"), cut.rfind("!"))
    return cut[:end + 1] if end > max_chars * 0.6 else cut


def _jsonld_body(page):
    """articleBody من بيانات NewsArticle المنظمة — أنظف نص متاح إن وُجد."""
    import json
    for raw in _JSONLD.findall(page):
        try:
            data = json.loads(raw.strip())
        except Exception:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                body = node.get("articleBody")
                if isinstance(body, str) and len(body) > 200:
                    text = html.unescape(_TAGS.sub(" ", body))
                    return re.sub(r"[ \t]+", " ", text).strip()
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return ""


def _paragraphs(scope, max_chars):
    out, seen, total = [], set(), 0
    for raw in _PARA.findall(scope):
        text = html.unescape(_TAGS.sub(" ", raw))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 50 or _BOILER.search(text) or text in seen:
            continue
        seen.add(text)
        out.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return _trim("\n".join(out), max_chars)


def extract_text(page, max_chars=2400):
    """نص الخبر من صفحته — تقريب بسيط بلا مكتبات، يكفي صفحات الأخبار.

    الترتيب: articleBody من البيانات المنظمة، ثم فقرات وسم <article>،
    ثم فقرات الصفحة كلها (بعض المواقع تضع <article> على بطاقة جانبية).
    """
    body = _jsonld_body(page)
    if len(body) >= 200:
        return _trim(body, max_chars)
    page = _DROP_BLOCKS.sub(" ", _COMMENTS.sub(" ", page))
    blocks = _ARTICLE.findall(page)
    scopes = ([max(blocks, key=len)] if blocks else []) + [page]
    text = ""
    for scope in scopes:
        text = _paragraphs(scope, max_chars)
        if len(text) >= 200:
            return text
    return text


def fetch_text(url, max_chars=2400, timeout=10):
    """يجلب صفحة الخبر ويعيد نصه، أو نصًا فارغًا عند أي فشل."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept-Language": "ar,en;q=0.8",
            "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(600_000)
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            cs = _charset(r.headers, raw[:4000])
        try:
            page = raw.decode(cs, errors="replace")
        except LookupError:
            page = raw.decode("utf-8", errors="replace")
        return extract_text(page, max_chars=max_chars)
    except Exception:
        return ""
