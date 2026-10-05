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
import urllib.error
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
MAX_AGE_DAYS = 2                   # ملفات الأيام التي تُفحص أصلًا
# الأخبار الجديدة فقط (قرار المستخدم 29/9: «القديمة مش مهم»). نافذة متحركة
# لا تاريخ ثابت: الحصة المجانية اليومية محدودة، فتذهب كلها للجديد. 12 ساعة
# تغطي ما كُتب بعد نفاد الحصة مساءً، فيُرسم عند تجدّدها (00:00 UTC).
MAX_AGE_HOURS = 12
SIZE = (1024, 576)                 # 16:9 مثل كروت الموقع

# بلد كل نسخة: يعطي المشهد مكانه وألوان فريقه بدل ملعب لا هوية له.
EDITION_COUNTRY = {"eg": "Egypt", "sa": "Saudi Arabia", "world": ""}

STYLE = ("photorealistic sports-magazine / news-agency photograph, dramatic cinematic "
         "lighting, high contrast, rich saturated colors, dynamic diagonal composition, "
         "strong emotion, shallow depth of field, crisp detail, "
         "plain jerseys without numbers or names, "
         "no text, no letters, no numbers, no logos, no crests, no watermark")

# الصورة القديمة كانت "كرة على عشب" لكل خبر رياضي: صحيحة ولا تشد أحدًا. المطلوب
# لحظة الذروة في الخبر نفسه (فوز، هدف، جمهور)، بألوان الفريق الحقيقية، ومع ذلك
# بلا وجه حقيقي معروف: لاعبون مجهولون من الخلف أو في حركة. القاعدة ثابتة.
SCENE_SYSTEM = """You write the image prompt for the photo at the top of a news article.
The photo must stop a reader scrolling their feed: the most dramatic, emotional moment of
THIS specific story, not a generic symbol. 45-70 words, English only, one paragraph.

How to build it:
- Find the peak moment in the story and show it happening: the winning celebration, the
  crowd erupting, the market screen turning red, the storm hitting the city.
- Be specific: the country, the city, the venue, the time of day, the team colours.
- Put people and emotion in the frame whenever the story has them. Never just an object
  lying still (a ball on grass, a gavel on a desk) unless the story is about that object.
- Choose a striking angle: low angle, close action, silhouettes against floodlights,
  confetti or flares, golden-hour or night light.

Sports:
- Name the team's real kit colours: Egypt national team red shirts, white shorts, black
  socks; Saudi national team white or green; Al Ahly red; Zamalek white with red chest
  stripes; Al Hilal blue; Al Nassr yellow; Al Ittihad yellow and black; Pyramids FC navy.
- Win or goal: players in that kit celebrating together, jumping, arms raised, seen from
  behind or in motion blur, in a packed stadium of fans in the same colours waving the
  national flag, flares and floodlights. Loss: players on their knees, heads down, empty
  seats. Transfer or signing: a jersey in the club colours in a stadium tunnel.

Economy, politics, tech, entertainment: think like a magazine-cover art director. Build
one bold, surprising visual idea from real objects in a real place, e.g. a gold bar
glowing under a spotlight on a Cairo street at night, a smartphone towering like a
skyscraper over Riyadh, an oil tanker sailing across a trading-floor screen. Make the
reader curious in one glance.

Hard rules (never break):
- Never a recognisable face of a real person. Players, officials and celebrities appear
  anonymous: from behind, silhouetted, in motion blur, or too far to identify. No portraits.
- No readable text, numbers, scoreboards, jersey numbers, logos, crests or brand marks.
  National flags are allowed (they have no writing).
- Death, violence, crime, disaster: calm and symbolic (candles, rain on a window, rescue
  lights at a distance). Never blood, bodies, weapons or injured people.
Return only the prompt."""


def _client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


def scene_prompt(client, headline, summary, category, country=""):
    if client is None:
        return headline
    r = client.messages.create(
        model=MODEL, max_tokens=250, system=SCENE_SYSTEM,
        messages=[{"role": "user", "content":
                   "Headline: {}\nSummary: {}\nCategory: {}\nSite edition country: {}".format(
                       headline, summary, category, country or "international")}])
    text = "".join(b.text for b in r.content if b.type == "text").strip()
    return text or headline


def generate(prompt):
    """يعيد بايتات صورة JPEG بمقاس SIZE، أو يرفع استثناء."""
    from PIL import Image
    if os.environ.get("AIART_FAKE"):                       # اختبار محلي بلا مزوّد
        img = Image.new("RGB", (1024, 1024), (30, 40, 90))
    else:
        acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        # 4 خطوات لا 8: FLUX-schnell مصمَّم لـ1-4 خطوات، والتكلفة بالخطوة، فالثماني
        # كانت تستهلك ضعف الحصة المجانية اليومية بلا فرق يُرى في الصورة.
        req = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/accounts/{}/ai/run/{}".format(acct, CF_MODEL),
            data=json.dumps({"prompt": (prompt + ", " + STYLE)[:2000], "steps": 4}).encode(),
            headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"],
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            # نص الرد فيه السبب الحقيقي (حصة، صلاحية، فلتر محتوى)؛ بدونه يظهر
            # "HTTP Error 429" وحده ولا يُعرف ماذا نصلح.
            body = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError("HTTP {}: {}".format(e.code, body))
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


def wants_art(art, title="", category=""):
    """الصورة الحقيقية الأول (قرار صاحب الموقع 2026-10-05): خبر عن شخص أو مكان له
    صورة حقيقية من ويكيبيديا يبقى بها (القارئ يرى الوجه الحقيقي، ولا نصنع شبه أحد)،
    وكذلك صورة حقيقية لموضوع الخبر نفسه (photos.close_stock). الباقي (صورة رياضة
    عامة، أو مدينة/صحف احتياطي، أو بلا صورة) يأخذ صورة مولّدة."""
    p = art.get("photo") or {}
    if p.get("url") and not p.get("stock") and not p.get("ai"):
        return False
    if p.get("stock") and not p.get("ai"):
        if "topic" not in p:          # صورة اتختارت قبل حفظ موضوعها: نحسبه
            p = photos.stock_photo(title, category, "", photos.photo_text(art)) or {}
        if photos.close_stock(p):
            return False
    # ملف الرسم ضاع (كان يُحفظ داخل site/ الذي يُمسح كل بناء) فيُعاد توليده
    return not p.get("ai") or not os.path.exists(
        os.path.join(ART_DIR, os.path.basename(p.get("url", ""))))


STATUS = os.path.join(ROOT, "data", "aiart_status.json")


def quota_error(msg):
    """رفض بسبب الحصة أو كثرة الطلبات: لا فائدة من المحاولة ثانية في التشغيلة نفسها."""
    m = msg.lower()
    return ("429" in m or "4006" in m or "allocation" in m or "neurons" in m
            or "rate limit" in m or "quota" in m)


def save_status(made, failed, errors, stopped):
    """خلاصة آخر تشغيلة في ملف يُحفظ مع data/: سجلات GitHub لا تُقرأ بلا تسجيل
    دخول، فتوقّف الرسم ست ساعات يوم 29/9 بلا أي أثر يوضح السبب."""
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({"at": datetime.datetime.now(datetime.timezone.utc).isoformat()[:19],
                   "made": made, "failed": failed, "stopped_on_quota": stopped,
                   "errors": errors[:5]}, f, ensure_ascii=False, indent=2)


def run(budget=150, cap=12):
    if not (os.environ.get("AIART_FAKE") or
            (os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))):
        print("لا مفاتيح Cloudflare — تخطي الرسوم (الموقع يبقى على صوره الحالية)")
        save_status(0, 0, ["no Cloudflare keys in environment"], False)
        return
    client = _client()
    store_p = os.path.join(ROOT, "data", "articles.json")
    with open(store_p, encoding="utf-8") as f:
        store = json.load(f)
    cutoff = (datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
    fresh_since = (datetime.datetime.now(datetime.timezone.utc) -
                   datetime.timedelta(hours=MAX_AGE_HOURS)).isoformat()
    start, made, failed, store_changed = time.time(), 0, 0, False
    errors, stopped = [], False
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
                if (not isinstance(art, dict) or not art.get("body")
                        or not wants_art(art, t["title"], t.get("category", ""))):
                    continue
                # written_at بصيغة ISO بتوقيت UTC، فالمقارنة النصية مقارنة زمنية
                if (art.get("written_at") or "") < fresh_since:
                    continue
                head = art.get("headline") or t["title"]
                photo = done.get(head)
                if photo is None:
                    if stopped or made >= cap or time.time() - start > budget:
                        continue
                    try:
                        prompt = scene_prompt(client, head, art.get("summary", ""),
                                              t.get("category", ""),
                                              EDITION_COUNTRY.get(gkey, ""))
                        photo = art_photo(head, generate(prompt))
                        made += 1
                        print("  ✓ {} ← {}".format(head[:50], prompt[:70]))
                    except Exception as e:
                        failed += 1
                        msg = type(e).__name__ + ": " + str(e)
                        errors.append(msg[:300])
                        print("  ✗ {}: {}".format(head[:50], msg[:200]))
                        if quota_error(msg):
                            stopped = True
                            print("  ⏸ الحصة/حد الطلبات — توقف الرسم لهذه التشغيلة")
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
    save_status(made, failed, errors, stopped)
    print("✓ رُسم {} مقالًا، وفشل {}".format(made, failed))


if __name__ == "__main__":
    b = float(sys.argv[sys.argv.index("--budget") + 1]) if "--budget" in sys.argv else 150
    c = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 12
    run(b, c)
