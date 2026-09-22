# -*- coding: utf-8 -*-
"""
توليد كارت 1200×675 لكل ترند.

لماذا نولّد صورنا بدل استخدام صور المصادر:
1. Google Discover يشترط عرضًا لا يقل عن 1200 بكسل. صور Google مصغّرات،
   وصور الأخبار التي فحصناها كانت 768 بكسل — أصغر من الحد.
2. نسخ صور الناشرين خطر على حقوق النشر. الكارت الذي نصنعه ملكنا.
3. الكارت يحمل اسم الموقع، فينشر العلامة مع كل مشاركة على واتساب.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arabic  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1200, 675
PAD = 72

FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"

BG_TOP = (14, 18, 28)
BG_BOT = (26, 20, 38)
GOLD = (245, 197, 66)
WHITE = (240, 244, 250)
MUTED = (150, 162, 182)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _gradient(w, h, top, bottom):
    """خلفية متدرجة — تُرسم سطرًا سطرًا."""
    img = Image.new("RGB", (w, h), top)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line([(0, y), (w, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * t)
                          for i in range(3)))
    return img


def _add(a, b):
    """جمع صورتين بلا numpy."""
    from PIL import ImageChops
    return ImageChops.add(a, b)


def make_card(trend, country_name, out_path, site="الترندات"):
    accent = _hex(trend.get("color", "#f5c542"))

    img = _gradient(W, H, BG_TOP, BG_BOT)
    img = _add(img, _radial(accent, (W - 190, 150), 330))
    d = ImageDraw.Draw(img)

    # شريط علوي بلون الفئة
    d.rectangle([0, 0, W, 8], fill=accent)

    f_title = ImageFont.truetype(FONT_BOLD, 76)
    f_cat = ImageFont.truetype(FONT_BOLD, 30)
    f_meta = ImageFont.truetype(FONT_REG, 28)
    f_site = ImageFont.truetype(FONT_BOLD, 34)

    # شارة الفئة (أعلى اليمين)
    cat = trend.get("category", "عام")
    cat_disp = arabic.display(cat)
    cw = d.textlength(cat_disp, font=f_cat)
    bx1, by1 = W - PAD, 62
    bx0, by0 = bx1 - cw - 44, by1 + 56
    d.rounded_rectangle([bx0, by1, bx1, by0], radius=28,
                        fill=tuple(int(c * 0.28) for c in accent))
    d.text((bx1 - 22, by1 + 28), cat_disp, font=f_cat,
           fill=accent, anchor="rm")

    # العنوان — يلتف حتى ثلاثة أسطر
    lines = arabic.wrap(trend["title"], f_title, W - PAD * 2, d, max_lines=3)
    y = 232
    for line in lines:
        d.text((W - PAD, y), line, font=f_title, fill=WHITE, anchor="ra")
        y += 92

    # خط فاصل
    d.line([(PAD, H - 168), (W - PAD, H - 168)], fill=(48, 56, 74), width=2)

    # حجم البحث (أسفل اليمين)
    traffic = "{} عملية بحث اليوم".format(trend.get("traffic", ""))
    d.text((W - PAD, H - 128), arabic.display(traffic),
           font=f_meta, fill=MUTED, anchor="ra")

    # البلد
    d.text((W - PAD, H - 86), arabic.display(country_name),
           font=f_meta, fill=MUTED, anchor="ra")

    # اسم الموقع (أسفل اليسار)
    d.text((PAD, H - 100), arabic.display(site),
           font=f_site, fill=GOLD, anchor="la")
    d.ellipse([PAD - 2, H - 48, PAD + 12, H - 34], fill=accent)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def _radial(color, center, radius):
    """هالة دائرية على خلفية سوداء، تُجمع مع الصورة."""
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    steps = 30
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = ((steps - i) / steps) ** 2.2 * 0.22
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  fill=tuple(int(c * a) for c in color))
    return layer


def main():
    with open(os.path.join(ROOT, "data", "trends.json"), encoding="utf-8") as f:
        data = json.load(f)

    made = 0
    for key, d in data.items():
        for i, t in enumerate(d["trends"], 1):
            name = "{}-{:02d}.png".format(key, i)
            path = os.path.join(ROOT, "output", "cards", name)
            make_card(t, d["country_name"], path)
            t["card"] = "cards/" + name
            made += 1
            print("  ✓ " + name + "  ←  " + t["title"])

    with open(os.path.join(ROOT, "data", "trends.json"), "w",
              encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n✓ " + str(made) + " كارت بمقاس 1200×675 في output/cards/")


if __name__ == "__main__":
    main()
