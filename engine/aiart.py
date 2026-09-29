# -*- coding: utf-8 -*-
"""
صور واقعية مولّدة بالذكاء الاصطناعي لأخبار الموقع.

لكل مقال صورة مخصوصة لموضوعه بأسلوب واحد، ويُكتب تحتها «صورة مولّدة بالذكاء
الاصطناعي» فلا يظنها القارئ لقطة حقيقية من الحدث.

القواعد (سياسة الموقع، لا تُخفَّف):
  - لا شبه أشخاص حقيقيين (لا بورتريه لسياسي أو لاعب) ولا نصوص ولا شعارات ولا
    دماء: المشهد مكان وأدوات وأشخاص عامون غير معروفين. الأخبار المأساوية
    بتعبير رمزي هادئ (شموع، مطر، أضواء إنقاذ).
  - صور ويكيبيديا القديمة تبقى احتياطًا لو فشل التوليد ولا تُحذف.

المزوّد: Cloudflare Workers AI (FLUX-1-schnell). المفاتيح من متغيرات البيئة
(GitHub Secrets)، وبدونها تخرج الخطوة بلا خطأ فيبقى الموقع على صوره الحالية:
  CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN (صلاحية Workers AI)
كتابة وصف المشهد بالإنجليزية تستخدم ANTHROPIC_API_KEY (Haiku، تكلفتها ضئيلة).

  python engine/aiart.py --budget 150 --max 12     # الأحدث أولًا
"""
import base64
import datetime
import hashlib
import io
import json
import os
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import photos  # noqa: E402

ROOT = photos.ROOT
ART_DIR = os.path.join(ROOT, "output", "art")   # يُنسخ إلى site/art عند البناء
BASE = os.environ.get("SITE_BASE") or "https://altrendat.com"
MODEL = "claude-haiku-4-5-20251001"
CF_MODEL = "@cf/black-forest-labs/flux-1-schnell"
MAX_AGE_DAYS = 3                   # لا نرسم الأرشيف القديم
SIZE = (1024, 576)                 # 16:9 مثل كروت الموقع

STYLE = ("photorealistic editorial photograph, natural but dramatic lighting, rich vivid "
         "colors, sharp focus, shallow depth of field, cinematic wide composition, "
         "subject centered, high detail, professional news photography look, "
         "no text, no letters, no logos, no watermark")

SCENE_SYSTEM = """You write one-paragraph image prompts for a news site's illustrations.
Given a news headline and summary, describe ONE clear, eye-catching visual scene that
symbolises the story (objects, setting, action, mood), 40-60 words, English only.
Rules:
- The image is photorealistic. Never depict a real, named person's likeness. If the story
  is about a person, show the setting and objects (a podium with microphones, a stadium,
  a courtroom, a stage) or generic unidentifiable people seen from behind or at a
  distance, never a recognisable portrait of that person.
- No text, numbers, flags with writing, logos, brand marks or newspaper headlines.
- Tragedy, violence, death or disaster: symbolic and calm (candles, empty chairs,
  rain, rescue lights). Never blood, bodies or weapons in use.
- Sports: stadium, ball, crowd energy, generic players seen from behind.
Return only the scene description."""


def _client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


def scene_prompt(client, headline, summary, category):
    if client is None:
        return headline
    r = client.messages.create(
        model=MODEL, max_tokens=200, system=SCENE_SYSTEM,
        messages=[{"role": "user", "content":
                   "Headline: {}\nSummary: {}\nCategory: {}".format(headline, summary, category)}])
    text = "".join(b.text for b in r.content if b.type == "text").strip()
    return text or headline


def generate(prompt):
    """يعيد بايتات صورة JPEG بمقاس SIZE، أو يرفع استثناء."""
    from PIL import Image
    if os.environ.get("AIART_FAKE"):                       # اختبار محلي بلا مزوّد
        img = Image.new("RGB", (1024, 1024), (30, 40, 90))
    else:
        acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        req = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/accounts/{}/ai/run/{}".format(acct, CF_MODEL),
            data=json.dumps({"prompt": (prompt + ", " + STYLE)[:2000], "steps": 8}).encode(),
            headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"],
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        if not data.get("success"):
            raise RuntimeError(str(data.get("errors"))[:200])
        img = Image.open(io.BytesIO(base64.b64decode(data["result"]["image"]))).convert("RGB")
    w, h = img.size                                        # قص 16:9 من الوسط
    ch = int(w * SIZE[1] / SIZE[0])
    top = max(0, (h - ch) // 2)
    img = img.crop((0, top, w, top + ch)).resize(SIZE)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=82, optimize=True)
    return out.getvalue()


def art_photo(headline, data):
    key = hashlib.sha1(headline.encode("utf-8")).hexdigest()[:14]
    os.makedirs(ART_DIR, exist_ok=True)
    with open(os.path.join(ART_DIR, key + ".jpg"), "wb") as f:
        f.write(data)
    return {"url": "{}/art/{}.jpg".format(BASE.rstrip("/"), key), "ai": True,
            "width": SIZE[0], "height": SIZE[1]}


def wants_art(art):
    """كل المقالات تأخذ رسمًا (قرار المستخدم)؛ صورة ويكيبيديا تبقى احتياطًا لو فشل التوليد."""
    p = art.get("photo") or {}
    # ملف الرسم ضاع (كان يُحفظ داخل site/ الذي يُمسح كل بناء) فيُعاد توليده
    return not p.get("ai") or not os.path.exists(
        os.path.join(ART_DIR, os.path.basename(p.get("url", ""))))


def run(budget=150, cap=12):
    if not (os.environ.get("AIART_FAKE") or
            (os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))):
        print("لا مفاتيح Cloudflare — تخطي الرسوم (الموقع يبقى على صوره الحالية)")
        return
    client = _client()
    store_p = os.path.join(ROOT, "data", "articles.json")
    with open(store_p, encoding="utf-8") as f:
        store = json.load(f)
    cutoff = (datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
    start, made, failed, store_changed = time.time(), 0, 0, False
    done = {}                                              # عنوان صحفي -> صورة (أُعيد استخدامه)
    for path, key, day in photos._snapshots():
        if day and day < cutoff:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        groups = ([(k, v.get("day") or v.get("generated_at", "")[:10], v)
                   for k, v in data.items() if isinstance(v, dict)] if key is None
                  else [(key, day, data)])
        changed = False
        for gkey, gday, snap in groups:
            if gday and gday < cutoff:
                continue
            for t in snap.get("trends", []):
                art = t.get("article")
                if not isinstance(art, dict) or not art.get("body") or not wants_art(art):
                    continue
                head = art.get("headline") or t["title"]
                photo = done.get(head)
                if photo is None:
                    if made >= cap or time.time() - start > budget:
                        continue
                    try:
                        prompt = scene_prompt(client, head, art.get("summary", ""),
                                              t.get("category", ""))
                        photo = art_photo(head, generate(prompt))
                        made += 1
                        print("  ✓ {} ← {}".format(head[:50], prompt[:70]))
                    except Exception as e:
                        failed += 1
                        print("  ✗ {}: {}".format(head[:50], str(e)[:120]))
                        continue
                    done[head] = photo
                photos.mark(art, photo)
                k = gkey + "|" + gday + "|" + t["title"]
                if isinstance(store.get(k), dict) and store[k].get("body"):
                    photos.mark(store[k], photo)
                    store_changed = True
                changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    if store_changed:
        with open(store_p, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    print("✓ رُسم {} مقالًا، وفشل {}".format(made, failed))


if __name__ == "__main__":
    b = float(sys.argv[sys.argv.index("--budget") + 1]) if "--budget" in sys.argv else 150
    c = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 12
    run(b, c)
