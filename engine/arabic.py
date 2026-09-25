# -*- coding: utf-8 -*-
"""
تشكيل النص العربي للرسم على الصور بدقة متناهية.
يستخدم arabic-reshaper و python-bidi لضمان اتصال الحروف واتجاهها السليم من اليمين لليسار.
"""
import re

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def is_arabic(text):
    return bool(ARABIC_RE.search(text)) if text else False


def display(text):
    """إعادة تشكيل النص العربي وعكس اتجاهه بما يناسب محركات الرسم."""
    if not text:
        return ""
    if not is_arabic(text):
        return text
    if HAS_BIDI:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    return text


def wrap(text, font, max_width, draw, max_lines=3):
    """تقسيم النص العربي أو الإنجليزي إلى أسطر تناسب العرض المطلوب مع تشكيلها للعرض."""
    if not text:
        return []
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        disp_trial = display(trial)
        if draw.textlength(disp_trial, font=font) <= max_width:
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
