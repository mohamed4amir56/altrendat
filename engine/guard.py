# -*- coding: utf-8 -*-
"""
حارس السياسات — يفحص الموقع المبني قبل نشره، ويوقف النشر عند أي مخالفة.

يعمل في GitHub Actions بعد site.py. لو خرج بخطأ، لا تُحفظ التشغيلة ولا
يتغير الموقع الحي، ويبقى آخر موقع سليم منشورًا. الهدف أن لا تعود مخالفة
أُزيلت، أيًّا كانت الأداة التي أضافتها:

- علامة JobPosting على صفحة ليست وظيفة حقيقية بإعلان رسمي.
- تقييمات (aggregateRating) مكتوبة في البيانات المنظمة.
- FAQPage مولّد، أو نص يطلب من نماذج الذكاء الاصطناعي الاستشهاد بالموقع.
- روابط لمواقع بث مقرصن أو صفحات سبام.
- صور من مواقع أخرى (صور الصحف حقوقها لناشريها).
- خبر بعنوان مبالغ فيه، أو بلا كاتب، أو بأقل من مصدرين.
- صفحة في خريطة الموقع وهي noindex.

  python engine/guard.py          # يفحص site/
"""
import json
import os
import re
import sys
import urllib.parse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")

JSONLD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)"', re.I)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
HREF = re.compile(r"""href=['"](https?://[^'"]+)['"]""", re.I)
IMG = re.compile(r"""<img[^>]+src=['"](https?://[^'"]+)['"]""", re.I)
SOURCE_ITEMS = re.compile(r"<ul class='sources'>(.*?)</ul>", re.S)
SOURCE_TITLE = re.compile(r"<span class='t'>(.*?)</span>", re.S)
TAGS = re.compile(r"<[^>]+>")
BANNED_TEXT = ("should cite", "llm agents", "generative ai models", "ai knowledge graph")
IMG_ALLOWED = ("wikimedia.org", "altrendat.com")      # صور حرة الرخصة، بشرط سطر مصدرها


def _types(node, out):
    if isinstance(node, list):
        for x in node:
            _types(x, out)
    elif isinstance(node, dict):
        t = node.get("@type")
        if t:
            out.extend(t if isinstance(t, list) else [t])
        for k, v in node.items():
            if k == "aggregateRating":
                out.append("aggregateRating")
            if isinstance(v, (dict, list)):
                _types(v, out)
    return out


def check_page(rel, html_text, errors):
    if 'http-equiv="refresh"' in html_text:
        return None                       # تحويل، لا صفحة
    lower = html_text.lower()

    types, author = [], False
    for raw in JSONLD.findall(html_text):
        try:
            data = json.loads(raw)
        except Exception:
            errors.append((rel, "بيانات منظمة غير صالحة"))
            continue
        _types(data, types)
        author = author or '"author"' in raw
    if "JobPosting" in types and "data-job-verified" not in html_text:
        errors.append((rel, "JobPosting بلا إعلان رسمي موثق"))
    if "aggregateRating" in types:
        errors.append((rel, "تقييمات مكتوبة في البيانات المنظمة"))
    if "FAQPage" in types:
        errors.append((rel, "FAQPage مولّد"))
    for phrase in BANNED_TEXT:
        if phrase in lower:
            errors.append((rel, "نص موجّه لنماذج الذكاء الاصطناعي: " + phrase))

    for url in HREF.findall(html_text):
        host = urllib.parse.urlparse(url).netloc.lower()
        if any(d in host for d in sources.SPAM_DOMAINS):
            errors.append((rel, "رابط لموقع بث/سبام: " + host))
    for block in SOURCE_ITEMS.findall(html_text):
        for title in SOURCE_TITLE.findall(block):
            if sources.is_spam({"url": "", "title": TAGS.sub("", title)}):
                errors.append((rel, "مصدر سبام: " + TAGS.sub("", title)[:60]))
    for src in IMG.findall(html_text):
        host = urllib.parse.urlparse(src).netloc.lower()
        if not any(host.endswith(a) for a in IMG_ALLOWED):
            errors.append((rel, "صورة من موقع آخر: " + host))
        elif host.endswith("wikimedia.org") and "ويكيميديا كومنز" not in html_text and "Wikimedia Commons" not in html_text:
            errors.append((rel, "صورة ويكيميديا بلا سطر مصدرها (شرط الرخصة)"))

    if "NewsArticle" in types:
        m = H1.search(html_text)
        head = TAGS.sub("", m.group(1)) if m else ""
        why = sources.hype_reason(head)
        if why:
            errors.append((rel, "عنوان مبالغ فيه (" + why + "): " + head[:60]))
        if not author:
            errors.append((rel, "خبر بلا كاتب"))
        robots = ROBOTS.search(html_text)
        indexed = robots and "noindex" not in robots.group(1)
        n_src = sum(len(SOURCE_TITLE.findall(b)) for b in SOURCE_ITEMS.findall(html_text))
        if indexed and n_src < 2:
            errors.append((rel, "خبر مفهرس بأقل من مصدرين"))

    robots = ROBOTS.search(html_text)
    return robots.group(1) if robots else ""


def main():
    if not os.path.isdir(SITE):
        print("✗ لا يوجد site/ — شغّل engine/site.py أولًا")
        return 1
    errors, robots_of, pages = [], {}, 0
    for dirpath, _, files in os.walk(SITE):
        for name in files:
            if not name.endswith(".html"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, SITE).replace(os.sep, "/")
            with open(full, encoding="utf-8") as f:
                robots = check_page(rel, f.read(), errors)
            if robots is not None:
                pages += 1
                robots_of[rel] = robots

    # كل رابط في خريطة الموقع صفحة حقيقية قابلة للفهرسة
    sitemap = os.path.join(SITE, "sitemap.xml")
    if os.path.exists(sitemap):
        with open(sitemap, encoding="utf-8") as f:
            locs = re.findall(r"<loc>(.*?)</loc>", f.read())
        for loc in locs:
            path = urllib.parse.unquote(urllib.parse.urlparse(loc.replace("&amp;", "&")).path)
            rel = path.strip("/")
            rel = (rel + "/index.html") if rel else "index.html"
            if rel not in robots_of:
                errors.append((rel, "في خريطة الموقع وليس صفحة"))
            elif "noindex" in robots_of[rel]:
                errors.append((rel, "في خريطة الموقع وهو noindex"))

    print("  حارس السياسات: فُحصت " + str(pages) + " صفحة")
    if errors:
        print("  ✗ " + str(len(errors)) + " مخالفة — لن يُنشر الموقع:")
        for rel, why in errors[:40]:
            print("    • " + rel + " — " + why)
        return 1
    print("  ✓ لا مخالفات")
    return 0


if __name__ == "__main__":
    sys.exit(main())
