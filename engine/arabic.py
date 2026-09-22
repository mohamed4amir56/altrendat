# -*- coding: utf-8 -*-
"""
تشكيل النص العربي للرسم على الصور — بلا أي مكتبة خارجية.

المشكلة: مكتبة Pillow ترسم الحروف كما تردها، حرفًا حرفًا ومن اليسار.
فتخرج "سعر" هكذا: "ر ع س" بحروف منفصلة. السبب أن العربية تصل حروفها
وتغيّر شكل الحرف حسب موضعه في الكلمة، وهذا ما لا تفعله Pillow وحدها.

الحل هنا يقوم بما تفعله مكتبة arabic-reshaper:
1. يستبدل كل حرف بشكله الصحيح من كتلة Arabic Presentation Forms-B
   (يونيكود يعرّف لكل حرف عربي أشكاله: منفصل، أول، وسط، آخر).
2. يدمج "لا" وأخواتها في حرف واحد كما تُكتب فعلًا.
3. يعكس ترتيب العرض ليظهر من اليمين، مع إبقاء الأرقام والكلمات
   الإنجليزية بترتيبها الصحيح.
"""
import re

# (الحرف، أول رمز في كتلة الأشكال، عدد الأشكال)
# ترتيب الأشكال في اليونيكود: منفصل، آخر، [أول، وسط]
_SPEC = [
    ("ء", 0xFE80, 1), ("آ", 0xFE81, 2), ("أ", 0xFE83, 2), ("ؤ", 0xFE85, 2),
    ("إ", 0xFE87, 2), ("ئ", 0xFE89, 4), ("ا", 0xFE8D, 2), ("ب", 0xFE8F, 4),
    ("ة", 0xFE93, 2), ("ت", 0xFE95, 4), ("ث", 0xFE99, 4), ("ج", 0xFE9D, 4),
    ("ح", 0xFEA1, 4), ("خ", 0xFEA5, 4), ("د", 0xFEA9, 2), ("ذ", 0xFEAB, 2),
    ("ر", 0xFEAD, 2), ("ز", 0xFEAF, 2), ("س", 0xFEB1, 4), ("ش", 0xFEB5, 4),
    ("ص", 0xFEB9, 4), ("ض", 0xFEBD, 4), ("ط", 0xFEC1, 4), ("ظ", 0xFEC5, 4),
    ("ع", 0xFEC9, 4), ("غ", 0xFECD, 4), ("ف", 0xFED1, 4), ("ق", 0xFED5, 4),
    ("ك", 0xFED9, 4), ("ل", 0xFEDD, 4), ("م", 0xFEE1, 4), ("ن", 0xFEE5, 4),
    ("ه", 0xFEE9, 4), ("و", 0xFEED, 2), ("ى", 0xFEEF, 2), ("ي", 0xFEF1, 4),
]

ISO, FIN, INI, MED = 0, 1, 2, 3

FORMS = {}
for ch, base, n in _SPEC:
    if n == 1:
        FORMS[ch] = (chr(base), chr(base), chr(base), chr(base))
    elif n == 2:
        # حرف لا يتصل بما بعده: شكلاه فقط منفصل وآخر
        FORMS[ch] = (chr(base), chr(base + 1), chr(base), chr(base + 1))
    else:
        FORMS[ch] = (chr(base), chr(base + 1), chr(base + 2), chr(base + 3))

# الحروف التي تتصل بما بعدها (أربعة أشكال)
CONNECTS_FORWARD = {ch for ch, _, n in _SPEC if n == 4}

# تراكيب لام + ألف تُكتب حرفًا واحدًا
LAM_ALEF = {
    "آ": (0xFEF5, 0xFEF6), "أ": (0xFEF7, 0xFEF8),
    "إ": (0xFEF9, 0xFEFA), "ا": (0xFEFB, 0xFEFC),
}

TASHKEEL = set("ًٌٍَُِّْٓ"
               "ٕٔـ")

ARABIC_RE = re.compile(r"[؀-ۿﹰ-﻿]")


def _is_arabic(ch):
    return bool(ARABIC_RE.match(ch))


def reshape(text):
    """يستبدل كل حرف بشكله الصحيح حسب موضعه، ويدمج لام-ألف."""
    # نزع التشكيل: الخطوط العادية ترسمه في غير موضعه
    text = "".join(c for c in text if c not in TASHKEEL)

    chars = list(text)
    out = []
    i = 0
    while i < len(chars):
        ch = chars[i]

        # لام متبوعة بألف = حرف واحد
        if ch == "ل" and i + 1 < len(chars) and chars[i + 1] in LAM_ALEF:
            prev = chars[i - 1] if i > 0 else ""
            joined_before = prev in CONNECTS_FORWARD
            iso, fin = LAM_ALEF[chars[i + 1]]
            out.append(chr(fin if joined_before else iso))
            i += 2
            continue

        if ch not in FORMS:
            out.append(ch)
            i += 1
            continue

        prev = chars[i - 1] if i > 0 else ""
        nxt = chars[i + 1] if i + 1 < len(chars) else ""

        joined_before = prev in CONNECTS_FORWARD
        joined_after = nxt in FORMS and ch in CONNECTS_FORWARD

        if joined_before and joined_after:
            form = MED
        elif joined_before:
            form = FIN
        elif joined_after:
            form = INI
        else:
            form = ISO

        out.append(FORMS[ch][form])
        i += 1

    return "".join(out)


def _mirror(s):
    pairs = {"(": ")", ")": "(", "[": "]", "]": "[",
             "{": "}", "}": "{", "<": ">", ">": "<"}
    return "".join(pairs.get(c, c) for c in s)


def display(text):
    """يعيد النص جاهزًا للرسم: مُشكَّلًا ومعكوس الترتيب للعرض من اليمين.

    الأرقام والكلمات اللاتينية تبقى بترتيبها الصحيح داخل الجملة العربية.
    """
    shaped = reshape(text)

    # تقسيم إلى مقاطع ثلاثة الأنواع: عربي، لاتيني/أرقام، ومسافات.
    # المسافة مقطع مستقل عمدًا — لو ألحقناها بالمقطع الذي قبلها لانتقلت
    # إلى طرف السطر عند العكس، فتلتصق الأرقام بالكلمة العربية التالية.
    segments = []
    for ch in shaped:
        kind = "s" if ch == " " else ("a" if _is_arabic(ch) else "l")
        if segments and segments[-1][0] == kind:
            segments[-1][1] += ch
        else:
            segments.append([kind, ch])

    # ترتيب المقاطع من اليمين، والعربي منها يُعكس داخليًا
    parts = []
    for kind, seg in reversed(segments):
        if kind == "a":
            parts.append(seg[::-1])
        elif kind == "l":
            parts.append(_mirror(seg))
        else:
            parts.append(seg)
    return "".join(parts)


def wrap(text, font, max_width, draw, max_lines=3):
    """يقسم النص إلى أسطر تناسب عرضًا معيّنًا. يعيد أسطرًا جاهزة للرسم."""
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        if draw.textlength(display(trial), font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines and len(" ".join(lines).split()) < len(words):
        lines[-1] = lines[-1] + "…"
    return [display(l) for l in lines]
