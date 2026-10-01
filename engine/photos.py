# -*- coding: utf-8 -*-
"""
صور مرخصة من ويكيبيديا وويكيميديا كومنز — البديل القانوني لصور الصحف.

صور الصحف حقوقها لناشريها وإن ذُكر مصدرها، وعلامتها المائية علامة حقوقهم.
لذلك كل صورة هنا برخصة حرة (CC، ملكية عامة، OGL)، وتحتها المصوّر والرخصة
ورابط الملف (شرط الرخصة؛ والحارس guard.py يرفض صورة كومنز بلا هذا السطر).

الصورة يجب أن تخص الخبر نفسه، وصورة لا علاقة لها بالخبر تضلل القارئ فلا
تُوضع أبدًا. المصادر بالترتيب، وكل مصدر يحتاط لما قبله:

  صاحب الخبر (عنوان الترند، ثم أول وسوم المقال):
    1. صورة صفحة ويكيبيديا بالاسم نفسه (عربي ثم إنجليزي، مع التحويلات).
    2. صورة الكيان في ويكي بيانات (P18) — الأصل الكامل حين تكون صورة
       الصفحة مقتطعة صغيرة.
    3. تصنيف الشخص أو الفريق في كومنز (P373): أحدث صورة عالية الدقة له.
    ويُشترط (بويكي بيانات) أن يكون الكيان من النوع الصحيح:
    - شخص باسمه الكامل («رونالدو» وحدها صفحة لاعب آخر)، ورد اسمه في
      العنوان إن جاء من الوسوم.
    - فريق أو بطولة بأسمائها.
    - مكان هو موضوع الخبر، لا مكان وقوعه («قرطاج» في خبر عن مهرجان).
    - عنوان ملتبس (صفحة توضيح، مثل «Luis Suárez») يوقف البحث بالاسم.
  4. صورة تعبيرية إن طابق الخبر موضوعها بكلماته (ذهب، بورصة، انتخابات،
     مستشفى...)، من مجموعة منتقاة محفوظة محليًا (data/stock_photos.json)،
     فتعمل ولو تعذّر الاتصال. يُكتب تحتها «صورة تعبيرية».
  5. لا موضوع مطابق: مدينة بلد الخبر إن عُرف من كلماته (القاهرة، الرياض)،
     وإلا صورة صحف عامة — فلكل مقال صورة، ويُكتب تحتها «صورة تعبيرية».

الجودة: نعرض نسخة بعرض 1280 (مقاس قياسي عند ويكيميديا، وفوق حد Google
Discover وهو 1200)، وأصل صورة صاحب الخبر 960 بكسل فأكثر.

  python engine/photos.py            # يملأ صور المقالات التي لم تُجرَّب بعد
  python engine/photos.py --recheck  # يعيد التجربة لكل المقالات
  python engine/photos.py --stock    # يحدّث بيانات الصور التعبيرية من كومنز
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://{lang}.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
UA = "AltrendatBot/1.0 (https://altrendat.com; info@altrendat.com)"
# OGL: رخصة الحكومة البريطانية المفتوحة (الاستخدام التجاري مسموح بشرط النسب)
FREE = re.compile(r"(cc[\s-]?by|cc0|public domain|^pd\b|gfdl|\bogl\b|no restrictions)", re.I)
NOT_FREE = re.compile(r"(\bnc\b|\bnd\b|non-?commercial|no-?deriv|fair use)", re.I)
TAGS = re.compile(r"<[^>]+>")
WIDTH = 1280                       # عرض العرض، ومقاس قياسي لمصغّرات ويكيميديا
MIN_NAMED = 960                    # أقل عرض لأصل صورة صاحب الخبر
MIN_SMALL = 600                    # الحد الثاني حين لا صورة أكبر للشخص أو الفريق
MAX_TAGS = 4                       # الوسوم الأولى هي أصحاب الخبر
RASTER = re.compile(r"\.(jpe?g|png|webp)$", re.I)
PHOTO_FILE = re.compile(r"\.jpe?g$", re.I)        # الصور الفوتوغرافية في التصنيفات
NOT_PHOTO = re.compile(r"(logo|signature|autograph|coat of arms|emblem|crest|flag|"
                       r"map\b|poster|screenshot|stamp|شعار|توقيع|علم)", re.I)
STOCK_PATH = os.path.join(ROOT, "data", "stock_photos.json")

# أنواع الكيانات في ويكي بيانات (P31)
HUMAN = "Q5"
TEAM_TYPES = {"Q476028", "Q6979593", "Q135408445", "Q103229495", "Q20639856",
              "Q12973014", "Q847017", "Q67145856", "Q17376093", "Q10651067"}
COMPETITION_TYPES = {"Q34542757", "Q500834", "Q34262807", "Q15991303", "Q34542827",
                     "Q135741070", "Q623109", "Q27020041", "Q51036091", "Q13406554",
                     "Q18608583", "Q1079023"}
# منتجات بأسمائها (طائرة، سيارة، هاتف): صورتها صورة الخبر إن كانت هي العنوان
OBJECT_TYPES = {"Q15056993", "Q15056995", "Q3231690", "Q19723451", "Q10929058"}
# فئات صورة المكان فيها ليست صورة الخبر (المباراة ليست صورة المدينة)
NO_PLACE = {"رياضة", "فن ومشاهير", "ديني", "طقس", "أبراج وفلك", "تعليم", "شخصية"}
# عنوان مباراة أو بطولة («تركيا ضد إيطاليا»، «gulf cup»): صورة البلد أو المدينة
# ليست صورة الخبر
MATCH = re.compile(r"(\sضد\s|\svs\.?\s|\sv\s|×|مباراة|كأس|كاس|دوري|بطولة|تصفيات|"
                   r"\scup\s|\sleague\s|championship|qualif)", re.I)
# بلد الخبر من كلماته، لا من النسخة التي رصدته: ترند السعودية قد يكون خبرًا عن
# مصر (مصريون كثيرون هناك يبحثون عن أخبار بلدهم)، وخبر ملك الأردن ليس محليًا
# سعوديًا. يحدد صورة البلد التعبيرية، ويوجّه إشعار التطبيق (site.py).
_AR_WORD = r"(?<![\w])[وبلفك]?(?:{})(?![\w])"
EG_MARKERS = re.compile(_AR_WORD.format("|".join((
    "مصر", "مصري", "مصرية", "المصري", "المصرية", "المصريين", "المصريون", "القاهرة",
    "الجيزة", "الإسكندرية", "الجنيه", "الجنيه المصري", "العاصمة الإدارية", "السيسي",
    "مدبولي", "egypt", "egyptian", "cairo"))), re.I)
SA_MARKERS = re.compile(_AR_WORD.format("|".join((
    "السعودية", "السعودي", "السعوديين", "سعودي", "الرياض", "جدة", "مكة", "المدينة المنورة",
    "الدمام", "الريال السعودي", "أبشر", "نيوم", "saudi", "riyadh", "jeddah"))), re.I)


def story_country(*texts):
    """«eg» أو «sa» إن كان الخبر عن بلد واحد منهما، وإلا «» (يهم كل القراء)."""
    t = " ".join(x or "" for x in texts)
    eg, sa = bool(EG_MARKERS.search(t)), bool(SA_MARKERS.search(t))
    if eg != sa:
        return "eg" if eg else "sa"
    return ""


# صور وكالات الأنباء عليها شعارها (مرخصة، لكنها تبدو صورة صحيفة)
AGENCY = re.compile(r"(news agency|وكالة|mehrnews|tasnimnews|farsnews|isna\.ir|irna\.ir|"
                    r"xinhua|anadolu|aa\.com\.tr|\bmehr\b|\btasnim\b)", re.I)
EXTMETA = "Artist|Credit|LicenseShortName|LicenseUrl"
SPORT_TOPICS = {"football", "tennis", "basketball", "cricket"}
# فئات يُعرف أصحابها باسم واحد (المغنون والممثلون)
MONONYM_OK = {"فن ومشاهير"}

# ── الصور التعبيرية ──────────────────────────────────────────────────
# ملفات حرة من كومنز أعرض من 1600 بكسل، لكل موضوع كلماته في TOPIC_WORDS.
# «موضوع@بلد» يسبق الموضوع العام لنسخته؛ وموضوع بلا صورة عامة لا يُستخدم
# إلا في نسخته. غيّر القائمة ثم شغّل: python engine/photos.py --stock
STOCK = {
    "tennis": ["Tennis ball on tennis court 20170619.jpg"],
    "basketball": ["Basketball Hoop (45655562422).jpg"],
    "cricket": ["Cricket match and Marina Bay Sands Hotel in Singapore.jpg"],
    "football": ["Adidas soccer ball on a grass pitch (Unsplash).jpg",
                 "The Peninsula Stadium at night - Salford City - Aug 24.jpg"],
    "football@eg": ["Adidas soccer ball on a grass pitch (Unsplash).jpg",
                    "Cairo International Stadium 2019.jpg"],
    "football@sa": ["Adidas soccer ball on a grass pitch (Unsplash).jpg",
                    "Entire King Saud University Stadium.jpg"],
    "un": ["United Nations General Assembly Hall (3).jpg",
           "United Nations General Assembly 2024.jpg"],
    "court": ["Courtroom One Gavel - Flickr - Joe Gratz.jpg"],
    "parliament@eg": ["The Egyptian Parliament building.jpg"],
    "parliament@world": ["Capitol at Dusk 2.jpg"],
    "elections": ["Ballot dropped into ballot box 2024 Swedish EU election at Stångenässkolan, Brastad.jpg",
                  "Ballot with ballot box in Sonoma, California - November 2022 - Sarah Stierch 02.jpg"],
    "oil": ["Oil platform P-51 (Brazil).jpg", "LostHillsPumpjacksSunset.JPG"],
    "gold": ["Gold bullion bars.jpg"],
    "crypto": ["Bitcoin BTC golden coin with the symbol.jpg"],
    "stocks": ["Frankfurt Stock Exchange (Ank Kumar) 03.jpg"],
    "money": ["1 United States dollar banknotes (348734).jpg"],
    "inflation": ["SPAR kolonial mat varehandel hyller (Supermarket interior GROCERY store aisle "
                  "shelves) Frokostblandinger gryn müsli Axa frukt energi 4-korn blåbær (cereals "
                  "muesli) etc Tjøme NORWAY 2023-08-31 IMG 1095.jpg"],
    "housing": ["Residential Street in Otford - geograph.org.uk - 6913848.jpg"],
    "housing@eg": ["Central business district, New Administrative Capital.jpg"],
    "housing@sa": ["Residential building on Olaya street (12753702893).jpg"],
    "capital@eg": ["Central business district, New Administrative Capital.jpg"],
    "trade": ["Container ship NYK Themis at the Port of Los Angeles.jpg"],
    "aviation": ["Airliner wing and clouds over South Pacific.jpg"],
    "space": ["2016 Falcon 9 at Vandenberg Air Force Base.jpg"],
    "ai": ["Datacenter Server Racks (22370909788).jpg"],
    "phone": ["Black smartphone in hand (Unsplash).jpg"],
    "games": ["Hands holding video game controller (50811892858).jpg"],
    "health": ["Corridor on the second level - NÄL hospital 1.jpg",
               "2023 Stetoskop.jpg"],
    "exams": ["Richard Huish College Exam Hall.jpg"],
    "ramadan": ["Ramadan lanterns.jpg", "Fanous Ramadan.jpg"],
    "hajj": ["Masjid al-Haram 2022.jpg"],
    "tourism@eg": ["All Gizah Pyramids.jpg"],
    "cinema": ["Kino Atlas Interier J.jpg"],
    "music": ["Beach-Please-2022-crowd-stage-lights-night-performance.jpg"],
    "weather": ["Close-up of the rain drops on a car window. Car in a blurry background.jpg",
                "Lightning in Dallas 2015.jpg",
                "Cloud cumulonimbus at baltic sea(1).jpg"],
    "prayer": ["Masjid al-Haram 2022.jpg",
               "The Courtyard of Al-Azhar Mosque, Cairo, Egypt.jpg"],
    "prayer@eg": ["The Courtyard of Al-Azhar Mosque, Cairo, Egypt.jpg"],
    "prayer@sa": ["Masjid al-Haram 2022.jpg"],
    "sky": ["Beneath the Milky Way.jpg"],
    "school": ["Students in a classroom.jpg"],
    "nationalday@sa": ["Royal Saudi Air Force jets doing a fly past next to the Jeddah Corniche "
                       "on the 90th Saudi National Day.jpg", "Riyadh Skyline.jpg"],
    # آخر الاحتياط: مدينة بلد الخبر، وإلا صحف (خبر بلا موضوع ولا بلد معروف)
    "city@eg": ["Cairo skyline, Panoramic view, Egypt.jpg", "Cairo and Nile Skyline.jpg"],
    "city@sa": ["Riyadh Skyline.jpg",
                "Riyadh Skyline showing the King Abdullah Financial District (KAFD) and the "
                "famous Kingdom Tower .jpg"],
    "news": ["Vecteezy stack-of-newspaper 1961329.jpg"],
}
# كلمات كل موضوع، تُطابَق كلمةً كاملة في العنوان والعنوان الصحفي والوسوم.
# الترتيب مهم (الأخص أولًا)، والكلمات الملتبسة مستبعدة عمدًا: «ذهب» فعل،
# «أسهم» فعل، «الريال» نادٍ، «رمضان» اسم، «هاتفي» اتصال، «تطبيق» القانون.
TOPIC_WORDS = [
    ("tennis", ["تنس", "التنس", "tennis", "wimbledon"]),
    ("basketball", ["كرة السلة", "لكرة السلة", "nba", "basketball"]),
    ("cricket", ["كريكيت", "الكريكيت", "cricket", "wicket", "wickets", "innings", "t20",
                 "الرمي أولًا", "الرمي أولا", "الضرب أولًا", "الضرب أولا"]),
    ("football", ["كرة القدم", "كرة قدم", "لكرة القدم", "soccer", "fifa", "فيفا", "الفيفا",
                  "كأس العالم", "دوري أبطال", "concacaf", "uefa", "nations league",
                  "world cup", "premier league", "mls", "كأس الخليج", "خليجي", "gulf cup",
                  "أمم أفريقيا", "أمم إفريقيا"]),
    ("un", ["الأمم المتحدة", "مجلس الأمن", "الجمعية العامة", "united nations",
            "security council", "general assembly"]),
    ("court", ["محكمة", "المحكمة", "النيابة", "النيابة العامة", "احتيال", "court", "convicted",
               "sentenced", "indicted", "lawsuit", "judge", "verdict", "fraud"]),
    ("parliament", ["مجلس النواب", "مجلس الشيوخ", "البرلمان", "مجلس الشورى",
                    "congress", "senate", "house of representatives", "capitol"]),
    ("elections", ["انتخابات", "الانتخابات", "الاقتراع", "التصويت", "election",
                   "elections", "ballot", "voters", "approval rating", "polls"]),
    ("oil", ["نفط", "النفط", "أوبك", "برنت", "oil price", "oil prices", "crude", "opec", "brent"]),
    ("gold", ["الذهب", "سعر الذهب", "أسعار الذهب", "سبائك", "gold price", "gold prices", "bullion"]),
    ("crypto", ["بيتكوين", "البيتكوين", "العملات المشفرة", "العملات الرقمية", "bitcoin",
                "crypto", "cryptocurrency", "ethereum"]),
    ("stocks", ["البورصة", "بورصة", "الأسهم", "سوق الأسهم", "stock", "stocks", "nasdaq",
                "dow", "s&p", "shares", "etf", "wall street"]),
    ("money", ["الدولار", "سعر الدولار", "الجنيه", "الجنيه المصري", "الريال السعودي",
               "سعر الصرف", "العملة", "البنك المركزي", "أسعار الفائدة", "سعر الفائدة",
               "dollar", "currency", "exchange rate", "central bank", "federal reserve",
               "interest rate", "interest rates", "fed", "بنك", "البنك", "البنوك", "التأمين",
               "bank", "banks", "insurance"]),
    ("inflation", ["التضخم", "السلع الغذائية", "inflation", "consumer prices", "grocery prices"]),
    ("capital", ["العاصمة الإدارية", "العاصمة الإدارية الجديدة", "العاصمة الجديدة"]),
    ("housing", ["عقارات", "العقارات", "التمويل العقاري", "الإسكان", "الإيجار", "الإيجارات",
                 "شقق", "mortgage", "mortgages", "housing", "real estate", "home prices"]),
    ("trade", ["ميناء", "الموانئ", "الجمارك", "جمارك", "رسوم جمركية", "tariff", "tariffs",
               "shipping", "exports", "imports"]),
    ("aviation", ["طيران", "الطيران", "مطار", "المطار", "airline", "airlines", "flight",
                  "flights", "airport", "boeing", "airbus"]),
    ("space", ["الفضاء", "ناسا", "nasa", "spacex", "rocket"]),
    ("ai", ["الذكاء الاصطناعي", "ai", "artificial intelligence", "nvidia", "openai",
            "chatgpt", "anthropic", "chips", "semiconductor", "semiconductors", "data center"]),
    ("phone", ["آيفون", "ايفون", "هواتف", "الهواتف", "الهواتف الذكية", "المحفظة الرقمية",
               "الخدمات الإلكترونية", "iphone", "smartphone", "smartphones", "samsung",
               "whatsapp", "واتساب"]),
    ("games", ["بلايستيشن", "ألعاب الفيديو", "playstation", "ps5", "xbox", "nintendo",
               "video game", "video games", "gaming"]),
    ("health", ["مستشفى", "المستشفى", "المستشفيات", "وزارة الصحة", "الأطباء", "أدوية",
                "لقاح", "hospital", "hospitals", "healthcare", "health care", "medicare",
                "medicaid", "fda", "vaccine"]),
    ("nationalday", ["اليوم الوطني", "national day"]),
    ("school", ["المدارس", "مدرسة", "المدرسة", "الطلاب", "طلاب", "التعليم", "التربية والتعليم",
                "school", "schools", "students", "teachers"]),
    ("exams", ["امتحانات", "الامتحانات", "الثانوية العامة", "exams", "exam"]),
    ("ramadan", ["شهر رمضان", "رمضان المبارك", "الإفطار", "السحور", "ramadan"]),
    ("hajj", ["الحج", "العمرة", "الحجاج", "المعتمرين", "المسجد الحرام", "hajj", "umrah"]),
    ("tourism", ["السياحة", "السياح", "الأهرامات", "tourism", "tourists", "pyramids"]),
    ("cinema", ["فيلم", "الفيلم", "السينما", "شباك التذاكر", "movie", "film", "box office"]),
    ("music", ["حفل غنائي", "حفلة غنائية", "ألبوم", "concert", "album"]),
    ("weather", ["طقس", "الطقس", "الأرصاد", "أمطار", "الأمطار", "درجات الحرارة",
                 "weather", "hurricane", "tornado"]),
    ("prayer", ["أذان", "اذان", "مواقيت الصلاة", "صلاة", "الصلاة", "prayer"]),
    ("sky", ["خسوف", "كسوف", "eclipse", "meteor"]),
]
# فئات صورتها التعبيرية صادقة لكل أخبارها، ولو خلت من كلمات الموضوع
CATEGORY_TOPIC = {"طقس": "weather", "ديني": "prayer", "أبراج وفلك": "sky",
                  "رياضة": "football"}      # أغلب أخبار الرياضة هنا كرة قدم


# ── الاتصال ──────────────────────────────────────────────────────────
def _get_json(lang, params):
    if lang == "commons":
        base = COMMONS_API
    elif lang == "wikidata":
        base = WIKIDATA_API
    else:
        base = API.format(lang=lang)
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _clean(value):
    text = html.unescape(TAGS.sub(" ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


_claims_cache = {}


def _claims(qid, prop):
    """قيم خاصية من ويكي بيانات: P31 (النوع)، P625 (الإحداثيات)، P18 (الصورة)،
    P373 (تصنيف كومنز)."""
    if not qid:
        return []
    key = (qid, prop)
    if key not in _claims_cache:
        data = _get_json("wikidata", {"action": "wbgetclaims", "entity": qid,
                                      "property": prop, "format": "json"})
        out = []
        for c in (data.get("claims") or {}).get(prop, []):
            v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            out.append(v.get("id") if isinstance(v, dict) and "id" in v else v)
        _claims_cache[key] = out
    return _claims_cache[key]


def entity_kind(qid):
    """«human» أو «team» أو «competition» أو «place» أو None (مفهوم عام،
    برنامج تلفزيوني، مؤسسة...)."""
    kinds = set(_claims(qid, "P31"))
    if HUMAN in kinds:
        return "human"
    if kinds & TEAM_TYPES:
        return "team"
    if kinds & COMPETITION_TYPES:
        return "competition"
    if kinds & OBJECT_TYPES:
        return "object"
    if _claims(qid, "P625"):
        return "place"
    return None


# ── مطابقة النصوص ────────────────────────────────────────────────────
_DIACRITICS = re.compile(r"[ً-ْـ]")
GENERIC_WORDS = {"منتخب", "نادي", "فريق", "لكره", "كره", "القدم", "الوطني", "fc", "cf",
                 "sc", "club", "national", "team", "football", "soccer", "cup", "league"}


def _norm(text):
    """نص للمطابقة: حروف صغيرة، بلا تشكيل، والألف والتاء والياء موحّدة."""
    s = _DIACRITICS.sub("", (text or "").lower())
    s = re.sub("[إأآ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"[^\w&+]+", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


def mentioned(name, text, kind):
    """هل ورد الكيان في عنوان الخبر أو مقدمته؟ الشخص باسمه أو بلقبه (الاسم
    الأخير)، والفريق بأي كلمة مميزة من اسمه، والمكان باسمه كاملًا."""
    n, t = _norm(name), _norm(text)
    if n.strip() and n in t:
        return True
    words = [w for w in n.split() if len(w) >= 3 and w not in GENERIC_WORDS]
    if not words:
        return False
    if kind == "human":
        return " " + words[-1] + " " in t
    if kind in ("team", "competition"):
        return any(" " + w + " " in t for w in words)
    return False


# ── ملفات الصور ──────────────────────────────────────────────────────
def _photo_from_info(info, name, min_width):
    """صورة من بيانات ملف في كومنز، أو None إن صغرت أو لم تكن رخصتها حرة."""
    if (info.get("width") or 0) < min_width or not info.get("thumburl"):
        return None
    em = info.get("extmetadata") or {}
    lic = _clean((em.get("LicenseShortName") or {}).get("value", ""))
    if not lic or not FREE.search(lic) or NOT_FREE.search(lic):
        return None
    raw_credit = (em.get("Artist") or {}).get("value", "") + " " + (em.get("Credit") or {}).get("value", "")
    if AGENCY.search(raw_credit):
        return None                    # صورة وكالة أنباء: عليها شعارها
    artist = _clean((em.get("Artist") or {}).get("value", ""))
    if not artist or artist.lower().startswith(("see ", "unknown")):
        artist = "مصور غير مذكور"
    return {
        "url": info["thumburl"].split("?", 1)[0],
        "width": info.get("thumbwidth"), "height": info.get("thumbheight"),
        "artist": artist[:80],
        "license": lic,
        "license_url": (em.get("LicenseUrl") or {}).get("value", ""),
        "file_page": info.get("descriptionurl") or
        "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(name),
    }


def _file_info(lang, name, min_width=WIDTH):
    """بيانات ملف بالاسم: الرخصة والمصوّر ومصغّر بعرض WIDTH، أو None."""
    if not RASTER.search(name or ""):
        return None                    # الشعارات والأعلام والخرائط (svg) ليست صورًا
    meta = _get_json(lang, {
        "action": "query", "format": "json", "formatversion": "2",
        "titles": "File:" + name, "prop": "imageinfo",
        "iiprop": "extmetadata|url|size", "iiurlwidth": str(WIDTH),
        "iiextmetadatafilter": EXTMETA,
    })
    info = ((meta.get("query", {}).get("pages") or [{}])[0].get("imageinfo") or [{}])[0]
    return _photo_from_info(info, name, min_width)


def _category_photo(category):
    """أحدث صورة عالية الدقة في تصنيف كومنز لشخص أو فريق، والأفقية أولًا."""
    data = _get_json("commons", {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "categorymembers", "gcmtitle": "Category:" + category,
        "gcmtype": "file", "gcmlimit": "50", "gcmsort": "timestamp", "gcmdir": "desc",
        "prop": "imageinfo", "iiprop": "extmetadata|url|size|timestamp",
        "iiurlwidth": str(WIDTH),
        "iiextmetadatafilter": EXTMETA,
    })
    best = []
    for pg in data.get("query", {}).get("pages", []):
        name = pg.get("title", "").split(":", 1)[-1]
        if NOT_PHOTO.search(name):
            continue
        info = (pg.get("imageinfo") or [{}])[0]
        # png: صور لاعبي الـNFL وغيرهم تُرفع png؛ نقبلها كبيرة (1600+) وبعد jpg
        is_jpg = bool(PHOTO_FILE.search(name))
        if not is_jpg and not (RASTER.search(name) and (info.get("width") or 0) >= 1600):
            continue
        photo = _photo_from_info(info, name, WIDTH)
        if photo:
            landscape = (info.get("width") or 0) >= (info.get("height") or 1)
            best.append((is_jpg, landscape, info.get("timestamp", ""), photo))
    best.sort(key=lambda b: b[:3], reverse=True)
    return best[0][3] if best else None


# ── صاحب الخبر ───────────────────────────────────────────────────────
_pages = {}


def _page(name, lang):
    """صفحة ويكيبيديا بهذا الاسم تمامًا (مع التحويلات): dict أو «dis» أو None."""
    key = (name, lang)
    if key not in _pages:
        data = _get_json(lang, {
            "action": "query", "format": "json", "formatversion": "2",
            "titles": name, "redirects": "1",
            "prop": "pageimages|pageprops", "piprop": "name", "pilicense": "free",
        })
        page = (data.get("query", {}).get("pages") or [{}])[0]
        props = page.get("pageprops") or {}
        if page.get("missing") or page.get("invalid") or not props.get("wikibase_item"):
            _pages[key] = None
        elif "disambiguation" in props:
            _pages[key] = "dis"
        else:
            _pages[key] = {"title": page.get("title", name), "qid": props["wikibase_item"],
                           "image": page.get("pageimage") or ""}
    return _pages[key]


def _entity_photo(lang, page, kind):
    """صورة الكيان: صورة صفحته، ثم صورته في ويكي بيانات، ثم تصنيفه في كومنز."""
    photo = _file_info(lang, page["image"], MIN_NAMED)
    for alt in ([] if photo else _claims(page["qid"], "P18")[:2]):
        photo = _file_info("commons", alt, MIN_NAMED)
        if photo:
            break
    if not photo and kind in ("human", "team"):
        for cat in _claims(page["qid"], "P373")[:1]:
            photo = _category_photo(cat)
    if not photo and kind in ("human", "team"):
        # لا شيء بعرض 960: صورة أصغر (600+) للشخص نفسه أحسن من صورة لا تخصه
        photo = _file_info(lang, page["image"], MIN_SMALL)
        for alt in ([] if photo else _claims(page["qid"], "P18")[:2]):
            photo = _file_info("commons", alt, MIN_SMALL)
            if photo:
                break
    if photo:
        photo.update({"wiki_title": page["title"], "wiki_lang": lang})
    return photo


def _accept(kind, name, category, from_tag, text, sporty=False):
    """هل صورة هذا الكيان صورة الخبر؟ sporty: خبر مباراة أو رياضة."""
    if kind is None:
        return False
    if kind == "object":
        return not from_tag            # المنتج صورة الخبر إن كان هو العنوان فقط
    if kind == "human":
        if len(name.split()) < 2 and category not in MONONYM_OK:
            return False               # «رونالدو» وحدها قد تكون لاعبًا آخر
        return not from_tag or mentioned(name, text, kind)
    if kind in ("team", "competition"):
        return not from_tag or mentioned(name, text, kind)
    # مكان: موضوع الخبر، لا مكان وقوعه
    if category in NO_PLACE or sporty:
        return False
    return not from_tag or mentioned(name, text, kind)


def _variants(title):
    """العنوان كما هو، وبأحرف كبيرة للإنجليزي («jos buttler» ← «Jos Buttler»)."""
    title = title.strip()
    out = [title]
    if re.search(r"[a-z]", title) and title == title.lower():
        out.append(title.title())
    return out


# ── مصادر إضافية لصور الأشخاص (كلها من أسرة ويكيميديا، فتبقى رخصتها حرة) ──────
# ما لا تجده الصفحة العربية/الإنجليزية: شخص بلا صفحة بالاسم نفسه، أو صفحته بلا
# صورة وله غيرها في كومنز. الترتيب: بحث ويكي بيانات بالاسم ثم تصنيف كومنز بالاسم
# الإنجليزي ثم بحث ملفات كومنز. كلها تشترط الاسم الكامل (كلمتين فأكثر).
def _wd_humans(name, lang):
    """كيانات ويكي بيانات من نوع إنسان تطابق الاسم تمامًا (التسمية أو اسم مستعار)."""
    data = _get_json("wikidata", {"action": "wbsearchentities", "search": name,
                                  "language": lang, "uselang": lang, "type": "item",
                                  "limit": "6", "format": "json"})
    want, out = _norm(name), []
    for r in data.get("search", []):
        if _norm(r.get("label", "")) != want and _norm((r.get("match") or {}).get("text", "")) != want:
            continue
        if entity_kind(r["id"]) == "human":
            out.append(r["id"])
    return out


def _en_label(qid):
    data = _get_json("wikidata", {"action": "wbgetentities", "ids": qid, "props": "labels",
                                  "languages": "en", "format": "json"})
    return ((data.get("entities", {}).get(qid, {}).get("labels") or {}).get("en") or {}).get("value", "")


def _commons_search(name):
    """أحدث صورة حرة عالية الدقة في كومنز يذكر اسم ملفها الاسم كاملًا."""
    data = _get_json("commons", {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrsearch": '"' + name + '" filetype:bitmap',
        "gsrnamespace": "6", "gsrlimit": "30",
        "prop": "imageinfo", "iiprop": "extmetadata|url|size|timestamp",
        "iiurlwidth": str(WIDTH), "iiextmetadatafilter": EXTMETA,
    })
    want, best = _norm(name), []
    for pg in data.get("query", {}).get("pages", []):
        fname = pg.get("title", "").split(":", 1)[-1]
        if want.strip() not in _norm(re.sub(r"\.\w+$", "", fname)):
            continue
        if not PHOTO_FILE.search(fname) or NOT_PHOTO.search(fname):
            continue
        info = (pg.get("imageinfo") or [{}])[0]
        photo = _photo_from_info(info, fname, MIN_NAMED)
        if photo:
            landscape = (info.get("width") or 0) >= (info.get("height") or 1)
            best.append((landscape, info.get("timestamp", ""), photo))
    best.sort(key=lambda b: (b[0], b[1]), reverse=True)
    return best[0][2] if best else None


def _more_person_photo(name):
    """صورة شخص باسمه من المصادر الإضافية، أو None. لا يُعتمد إلا شخص واحد في
    ويكي بيانات يطابق الاسم تمامًا: الاسمان المتشابهان («Patrick Garcia» جندي
    أمريكي ومغنٍّ فلبيني) يعنيان أننا لا نعرف أيهما، فلا صورة أفضل من صورة غلط."""
    for lang in ("ar", "en"):
        humans = _wd_humans(name, lang)
        if len(humans) != 1:
            continue
        qid = humans[0]
        found = lambda ph: (ph.update({"wiki_title": name, "wiki_lang": lang}) or ph)
        for alt in _claims(qid, "P18")[:2]:
            photo = _file_info("commons", alt, MIN_NAMED)
            if photo:
                return found(photo)
        for cat in _claims(qid, "P373")[:1]:
            photo = _category_photo(cat)
            if photo:
                return found(photo)
        label = _en_label(qid)                 # كيان موثّق بلا صورة مربوطة: ابحث باسمه في كومنز
        if label and len(label.split()) >= 2:
            photo = _commons_search(label)
            if photo:
                return found(photo)
    return None


def find_photo(title, category, langs=("ar", "en"), tags=(), text=""):
    """صورة صاحب الخبر أو None. text: العنوان الصحفي؛ الشخص أو المكان المأخوذ
    من الوسوم يجب أن يرد فيه أو في عنوان الترند، فيكون موضوع الخبر لا ذكرًا
    عابرًا فيه (لاعب معتزل في خبر مباراة)."""
    text = title + " " + (text or "")
    # العنوان الصحفي أيضًا: ترند «honduras» خبره عن دوري الأمم (Nations League)
    sporty = (category == "رياضة" or bool(MATCH.search(" " + text + " ")) or
              topic_of(text + " " + " ".join(tags or []), category) in SPORT_TOPICS)
    names = [(v, False) for v in _variants(title)]
    names += [(t.strip(), True) for t in list(tags or [])[:MAX_TAGS]
              if t and t.strip() and t.strip() != title.strip()]
    for name, from_tag in names:
        for lang in langs:
            try:
                page = _page(name, lang)
                if page == "dis" and not from_tag:
                    return None        # عنوان ملتبس: لا تخمين بصورة شخص آخر
                if not isinstance(page, dict):
                    continue
                kind = entity_kind(page["qid"])
                if not _accept(kind, name, category, from_tag, text, sporty):
                    break              # الصفحة موجودة لكنها ليست صورة الخبر
                photo = _entity_photo(lang, page, kind)
                if photo:
                    return photo
            except Exception:
                continue
    # لا الصفحة ولا ويكي بيانات أعطت صورة: المصادر الإضافية، للأشخاص فقط
    for name, from_tag in names:
        if len(name.split()) < 2 and category not in MONONYM_OK:
            continue
        if from_tag and not mentioned(name, text, "human"):
            continue
        if sporty and not from_tag and len(name.split()) < 2:
            continue
        try:
            photo = _more_person_photo(name)
        except Exception:
            photo = None
        if photo:
            return photo
    return None


# ── الصور التعبيرية ──────────────────────────────────────────────────
_stock = None


def load_stock():
    global _stock
    if _stock is None:
        try:
            with open(STOCK_PATH, encoding="utf-8") as f:
                _stock = json.load(f)
        except Exception:
            _stock = {}
    return _stock


def topic_of(text, category):
    """موضوع الخبر من كلماته، أو من فئته إن كانت صورتها صادقة لكل أخبارها."""
    t = _norm(text)
    for topic, keys in TOPIC_WORDS:
        for k in keys:
            if _norm(k) in t:
                return topic
    return CATEGORY_TOPIC.get(category)


def stock_photo(title, category, country, text=""):
    """صورة تعبيرية تطابق موضوع الخبر، ثابتة لكل عنوان — أو None."""
    # كلمات الترند نفسه أولًا («qqq stock» بورصة، ولو ذكر خبره الانتخابات)
    topic = topic_of(title, None) or topic_of(title + " " + (text or ""), category)
    # صورة بلد الخبر لا بلد النسخة: خبر العاصمة الإدارية في ترند السعودية مصري
    # والملعب المحلي لمباراة محلية فقط: «النرويج ضد الدنمارك» في ترند السعودية
    # ليست في ملعب سعودي
    country = story_country(title, text) or ("" if topic in SPORT_TOPICS else country)
    pool = load_stock()
    choices = (topic and (pool.get(topic + "@" + country) or pool.get(topic))) or []
    if not choices:
        # لا موضوع مطابق: مدينة بلد الخبر إن عُرف من كلماته، وإلا صحف
        where = story_country(title, text)
        choices = pool.get("city@" + where) or pool.get("news") or []
    if not choices:
        return None
    seed = sum(ord(c) for c in title)          # ثابت بين التشغيلات، بخلاف hash()
    photo = dict(choices[seed % len(choices)])
    photo["stock"] = True
    return photo


def photo_text(art):
    """كلمات موضوع الصورة التعبيرية: العنوان الصحفي والوسوم."""
    art = art or {}
    return " ".join([art.get("headline", "")] + list(art.get("tags") or []))


def photo_for(title, category, country, langs=("ar", "en"), art=None):
    """صورة تخص الخبر، أو None (فيعرض الموقع كارته). art: المقال المكتوب."""
    art = art or {}
    return (find_photo(title, category, langs, art.get("tags"), art.get("headline", "")) or
            stock_photo(title, category, country, photo_text(art)))


def refresh_stock():
    """يقرأ بيانات صور STOCK من كومنز ويحفظها في data/stock_photos.json."""
    out = {}
    for key, names in STOCK.items():
        out[key] = []
        for name in names:
            try:
                photo = _file_info("commons", name)
            except Exception as e:
                print("  ✗ " + name + ": " + str(e))
                photo = None
            if photo:
                out[key].append(photo)
            else:
                print("  ✗ لا تصلح: " + name)
            time.sleep(0.2)
    with open(STOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("✓ " + str(sum(len(v) for v in out.values())) + " صورة تعبيرية في " +
          str(len(out)) + " موضوعًا")


# رقم قواعد الاختيار الحالية. مقال صورته بقواعد أقدم (أو بلا رقم) يُعاد
# اختيار صورته تلقائيًا في التشغيلة الدورية. ارفعه عند تغيير القواعد.
PHOTO_VERSION = 7                 # 7: مصادر إضافية للأشخاص (ويكي بيانات بالاسم، png كبيرة، 600px كحد ثانٍ)


def mark(art, photo):
    """يضع الصورة في المقال مع رقم القواعد التي اختارتها."""
    art["photo"] = photo
    art["photo_v"] = PHOTO_VERSION


def _snapshots():
    """ملفات البيانات التي فيها مقالات: ملف اليوم، ثم الأرشيف الأحدث أولًا."""
    days = os.path.join(ROOT, "data", "days")
    out = []
    live = os.path.join(ROOT, "data", "trends.json")
    if os.path.exists(live):
        out.append((live, None, None))
    names = [n for n in os.listdir(days) if n.endswith(".json")]
    for name in sorted(names, key=lambda n: n.split("-", 1)[-1], reverse=True):
        key, day = name[:-5].split("-", 1)
        out.append((os.path.join(days, name), key, day))
    return out


def backfill(recheck=False, budget=None, only_mark=False):
    """يختار صور المقالات التي لم تُختر صورتها بالقواعد الحالية، في ملف اليوم
    والأرشيف ومخزن المقالات، الأحدث أولًا.
    recheck: يعيد الاختيار لكل المقالات.
    budget: أقصى ثوانٍ للتشغيلة (التشغيلة الدورية محدودة الوقت)، والباقي
            يكمل في التشغيلات التالية.
    only_mark: يضع رقم القواعد الحالية على الصور الموجودة بلا بحث (بعد إعادة
               اختيار كاملة جرت بالقواعد نفسها)."""
    store_path = os.path.join(ROOT, "data", "articles.json")
    with open(store_path, encoding="utf-8") as f:
        store = json.load(f)
    start = time.time()
    named = stock = tried = 0
    out_of_time = False
    for path, key, day in _snapshots():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if key is None:               # trends.json: {بلد: {..., trends}}
            groups = [(k, v.get("day") or v.get("generated_at", "")[:10], v)
                      for k, v in data.items() if isinstance(v, dict)]
        else:
            groups = [(key, day, data)]
        changed = False
        for gkey, gday, snap in groups:
            langs = ("en",) if gkey == "world" else ("ar", "en")
            for t in snap.get("trends", []):
                art = t.get("article")
                if not isinstance(art, dict) or not art.get("body"):
                    continue
                if art.get("photo_v") == PHOTO_VERSION and not recheck:
                    continue
                if (art.get("photo") or {}).get("ai"):     # رسم aiart.py لا يُستبدل
                    continue
                if budget and time.time() - start > budget:
                    out_of_time = True
                    break
                if only_mark:
                    mark(art, art.get("photo"))
                else:
                    mark(art, photo_for(t["title"], t.get("category", ""), gkey, langs, art))
                    tried += 1
                    p = art["photo"]
                    if p and p.get("stock"):
                        stock += 1
                    elif p:
                        named += 1
                    print("  {} {} ← {}".format(gkey, t["title"], (p or {}).get("wiki_title") or
                                                 ("تعبيرية" if p else "كارت الموقع")))
                k = gkey + "|" + gday + "|" + t["title"]
                if k in store and isinstance(store[k], dict) and store[k].get("body"):
                    mark(store[k], art["photo"])
                changed = True
            if out_of_time:
                break
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        if out_of_time:
            break
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    if only_mark:
        print("✓ وُضع رقم القواعد " + str(PHOTO_VERSION) + " على صور المقالات")
    else:
        print("✓ اختيرت صور " + str(tried) + " مقالًا: " + str(named) + " بصورة صاحب الخبر، " +
              str(stock) + " بصورة تعبيرية مطابقة، والباقي بكارت الموقع" +
              (" — ويكمل الباقي في التشغيلة التالية" if out_of_time else ""))


if __name__ == "__main__":
    if "--stock" in sys.argv:
        refresh_stock()
    else:
        budget = None
        if "--budget" in sys.argv:
            budget = float(sys.argv[sys.argv.index("--budget") + 1])
        backfill(recheck="--recheck" in sys.argv, budget=budget,
                 only_mark="--mark" in sys.argv)
