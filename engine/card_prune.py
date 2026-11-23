"""ينشر الكروت المستخدمة فقط، لأن Cloudflare Workers المجاني حده 20,000 ملف.

الأصل يبقى كاملًا في output/cards، وهذا يحذف من site/cards فقط ما لا تشير
إليه أي صفحة أو خلاصة. كروت اليوم وأمس تبقى دائمًا، لأن منشورات X وتليجرام
الجديدة قد تشير إليها.
"""
import datetime
import html
import os
import re
import urllib.parse

REF = re.compile(r"cards/([^\"'<>\s?#]+?\.png)", re.I)
DATED = re.compile(r"^[a-z]+-(\d{4}-\d{2}-\d{2})-", re.I)
TEXT_EXT = (".html", ".json", ".xml", ".js", ".txt", ".css")
SKIP_DIRS = ("cards", "art")


def in_use(out):
    used = set()
    for root, dirs, files in os.walk(out):
        if root == out:
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.lower().endswith(TEXT_EXT):
                continue
            with open(os.path.join(root, name), encoding="utf-8", errors="ignore") as f:
                text = f.read()
            for match in REF.findall(text):
                used.add(urllib.parse.unquote(html.unescape(match)))
    return used


def recent_days(today=None):
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    return {str(today), str(today - datetime.timedelta(days=1))}


def keep(name, used, days):
    if name in used:
        return True
    dated = DATED.match(name)
    return bool(dated and dated.group(1) in days)


def prune(out):
    folder = os.path.join(out, "cards")
    if not os.path.isdir(folder):
        return 0, 0
    used, days = in_use(out), recent_days()
    kept = removed = 0
    for name in os.listdir(folder):
        if keep(name, used, days):
            kept += 1
        else:
            os.remove(os.path.join(folder, name))
            removed += 1
    return kept, removed
