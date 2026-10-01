# -*- coding: utf-8 -*-
"""
أداة صور الجواز والتأشيرة — صفحات دائمة فيها أداة تعمل داخل المتصفح.

الزائر يرفع صورة من هاتفه، فتُقصّ بمقاس المستند الرسمي وتُبيَّض خلفيتها
وتخرج معها ورقة 10×15 جاهزة للطباعة. كل المعالجة على جهاز الزائر
(engine/idphoto.js)، فلا خادم ولا تكلفة ولا صور تُرفع.

  /passport-photo/                  الأداة + كل المقاسات
  /passport-photo/<slug>/           صفحة لكل مستند بشروطه ومصدره الرسمي

كل رقم في DOCS مأخوذ من الجهة الرسمية المذكورة في source، وتاريخ التحقق
في VERIFIED. لا تُضف مستندًا بلا مصدر رسمي يُفتح رابطه؛ ما ليس له شرط
منشور (مثل حجم الرأس في صورة 4×6) يُكتب صراحةً أنه اختيارنا.
"""
import hashlib
import html
import json
import os

E = html.escape
HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "passport-photo"
VERIFIED = "2026-10-02"
VERIFIED_AR = "2 أكتوبر 2026"

WHITE = [["أبيض", "#ffffff"]]

# head = نسبة ارتفاع الرأس (الذقن → قمة الرأس) من ارتفاع الصورة التي نقصّ عليها.
# top  = الهامش فوق قمة الرأس نسبةً لارتفاع الصورة. eye = ارتفاع العينين عن الحافة السفلى.
DOCS = [
    {
        "slug": "4x6", "w": 40, "h": 60, "label": "4×6 سم",
        "head": 0.55, "top": 0.10, "bgs": WHITE, "bg_default": True,
        "name": "صورة 4×6 بخلفية بيضاء", "flag": "🪪",
        "title": "عمل صورة 4×6 بخلفية بيضاء أونلاين مجانًا — جاهزة للطباعة",
        "desc": "حوّل صورة من هاتفك إلى صورة شخصية 4×6 سم بخلفية بيضاء في دقيقة: قصّ تلقائي على الوجه، "
                "وورقة 10×15 فيها 4 نسخ جاهزة للطباعة. مجانًا، والصورة لا تُرفع إلى أي خادم.",
        "lead": "ارفع صورة من هاتفك، فتُقصّ تلقائيًا بمقاس 4×6 سم وتُبيَّض خلفيتها، ومعها ورقة 10×15 فيها 4 نسخ للطباعة. مجانًا، والصورة تُعالَج على جهازك ولا تُرفع إلى أي خادم.",
        "facts": [("المقاس", "4 سم عرضًا × 6 سم ارتفاعًا"), ("الخلفية", "بيضاء"),
                  ("النسخ في ورقة 10×15", "4 صور")],
        "about": [
            ("أين تُطلب صورة 4×6؟",
             "مقاس 4×6 سم بخلفية بيضاء هو الأكثر طلبًا في المعاملات الرسمية في مصر والسعودية: جواز السفر المصري، "
             "والهوية الوطنية السعودية، وكثير من استمارات التقديم للجامعات والوظائف. لكل جهة شروط إضافية "
             "(الزي، عدد الصور)، فراجع ما تطلبه الجهة التي تقدّم لها."),
            ("حجم الرأس في الصورة",
             "لا يوجد شرط رسمي منشور يحدّد حجم الرأس في صورة 4×6. الأداة تضع الرأس بارتفاع 3.3 سم تقريبًا "
             "مع ظهور أعلى الكتفين، وهو التكوين المعتاد في الاستوديوهات. يمكنك تكبير الصورة أو تصغيرها من أدوات الضبط."),
        ],
    },
    {
        "slug": "egypt-passport", "w": 40, "h": 60, "label": "4×6 سم",
        "head": 0.55, "top": 0.10, "bgs": WHITE, "bg_default": True,
        "name": "صورة جواز السفر المصري", "flag": "🇪🇬",
        "title": "صورة جواز السفر المصري: المقاس 4×6 والخلفية والشروط + أداة مجانية",
        "desc": "صورة جواز السفر المصري مقاسها 4×6 سم بخلفية بيضاء، والمطلوب 4 صور حديثة. جهّزها من هاتفك مجانًا: "
                "قصّ تلقائي وخلفية بيضاء وورقة طباعة فيها 4 نسخ.",
        "lead": "جواز السفر المصري يحتاج 4 صور شخصية حديثة مقاس 4×6 سم بخلفية بيضاء. جهّزها هنا من صورة بهاتفك: ورقة الطباعة 10×15 تخرج فيها الأربع صور المطلوبة.",
        "facts": [("المقاس", "4×6 سم"), ("الخلفية", "بيضاء"), ("عدد الصور", "4 صور حديثة"),
                  ("النسخ في ورقة 10×15", "4 صور — العدد المطلوب بالضبط")],
        "source": ("وزارة الخارجية المصرية — استخراج أو تجديد جواز السفر",
                   "https://www.mfa.gov.eg/ar/ConsularServicesAndTransactions/Details/73"),
        "quote": "عدد (4) صور شخصية حديثة خلفية بيضاء مقاس 4×6",
        "about": [
            ("ما الذي تطلبه الجهة الرسمية بالضبط؟",
             "نص وزارة الخارجية المصرية في مستندات استخراج الجواز وتجديده: «عدد (4) صور شخصية حديثة خلفية بيضاء مقاس 4×6». "
             "الشرط نفسه يتكرر في الاستخراج لأول مرة والتجديد وبدل الفاقد والتالف."),
            ("حجم الرأس والملابس",
             "النص الرسمي لا يحدّد حجم الرأس ولا لون الملابس. الأداة تضع الرأس بارتفاع 3.3 سم تقريبًا مع ظهور أعلى الكتفين. "
             "تجنّب الملابس البيضاء حتى لا تذوب في الخلفية، وإن طلب مكتب الجوازات شيئًا مختلفًا فكلامه هو المرجع."),
        ],
    },
    {
        "slug": "saudi-id", "w": 40, "h": 60, "label": "4×6 سم",
        "head": 0.55, "top": 0.10, "bgs": WHITE, "bg_default": True, "unaltered": True,
        "name": "صورة الهوية الوطنية السعودية (أبشر)", "flag": "🇸🇦",
        "title": "صورة الهوية الوطنية وأبشر: مقاس 4×6 بخلفية بيضاء والشروط الرسمية + أداة مجانية",
        "desc": "صورة الهوية الوطنية السعودية مقاسها 4×6 بخلفية بيضاء، حديثة وملونة وبالزي السعودي وبدون نظارات. "
                "اقرأ الشروط كما أعلنتها أبشر والأحوال المدنية، وجهّز الصورة بالمقاس مجانًا.",
        "lead": "صورة الهوية الوطنية السعودية: ملونة وحديثة مقاس 4×6 بخلفية بيضاء، بالزي السعودي وبدون نظارات. قصّها هنا بالمقاس الصحيح من صورة بهاتفك.",
        "facts": [("المقاس", "4×6 سم"), ("الخلفية", "بيضاء"), ("الصورة", "ملونة وحديثة (خلال 6 أشهر)"),
                  ("الزي", "الزي السعودي"), ("النظارات", "بدون نظارات"),
                  ("التعديل", "بدون مؤثرات أو تحسين")],
        "source": ("المنصة الوطنية الموحدة my.gov.sa — إصدار هوية وطنية (الأحوال المدنية)",
                   "https://my.gov.sa/ar/services/152957"),
        "about": [
            ("ضوابط أبشر الستة لصورة الهوية",
             "أعلنت منصة أبشر في مايو 2023 (كما نقلت مجلة سيدتي) ستة ضوابط للصورة عند تجديد الهوية إلكترونيًا: أن تكون ملونة بخلفية بيضاء، "
             "وحديثة التُقطت خلال 6 أشهر، وملامح الوجه واضحة بلا تعابير وبلا مساحيق تجميل، وخالية من الطيّات والبقع والثقوب، "
             "والوجه ينظر مباشرة إلى الكاميرا، وبلا عيون حمراء من انعكاس الفلاش."),
            ("انتبه: «بدون مؤثرات أو تحسين»",
             "شروط الأحوال المدنية تنص على أن الصورة مطابقة للواقع وبدون مؤثرات أو تحسين. الأداة لا تغيّر ملامح الوجه، "
             "لكن تبييض الخلفية تعديل رقمي. الأضمن أن تصوّر أمام حائط أبيض فعلًا ثم تستخدم الأداة للقص والمقاس فقط، "
             "وتترك تبييض الخلفية حلًّا احتياطيًا."),
        ],
    },
    {
        "slug": "schengen-visa", "w": 35, "h": 45, "label": "35×45 مم",
        "head": 0.756, "head_min": 32 / 45, "head_max": 36 / 45, "top": 0.085,
        "bgs": [["رمادي فاتح", "#e4e4e4"], ["أزرق فاتح", "#dbe6f3"], ["أبيض", "#ffffff"]], "bg_default": True,
        "name": "صورة تأشيرة شنغن", "flag": "🇪🇺",
        "title": "صورة تأشيرة شنغن 35×45: المقاس وحجم الرأس والخلفية + أداة مجانية",
        "desc": "صورة فيزا شنغن مقاسها 35×45 مم، وارتفاع الرأس من الذقن إلى قمة الرأس 32–36 مم، والخلفية فاتحة موحّدة "
                "(فرنسا ترفض الأبيض). قصّ صورتك بالمقاس وتحقق من حجم الرأس مجانًا.",
        "lead": "صورة تأشيرة شنغن: 35×45 مم، والرأس من الذقن إلى قمته بين 32 و36 مم، وخلفية فاتحة موحّدة. الأداة تقصّ صورتك على هذه القياسات وتخبرك هل حجم الرأس مطابق.",
        "facts": [("المقاس", "35 مم عرضًا × 45 مم ارتفاعًا"),
                  ("ارتفاع الرأس", "32–36 مم من أسفل الذقن إلى قمة الرأس (دون احتساب الشعر)"),
                  ("الخلفية", "موحّدة فاتحة: رمادي فاتح أو أزرق فاتح. فرنسا لا تقبل الأبيض"),
                  ("النسخ في ورقة 10×15", "6 صور")],
        "source": ("السفارة الألمانية بالقاهرة — قالب فحص صور الجواز البيومترية",
                   "https://kairo.diplo.de/resource/blob/1496494/2198ba562da42ec69f29352054951703/passschablone-data.pdf"),
        "source2": ("فرنسا — قرار 5 فبراير 2009 بشأن صور الهوية (Légifrance)",
                    "https://www.legifrance.gouv.fr/loda/id/JORFTEXT000020246797/"),
        "about": [
            ("لماذا الخلفية رمادية لا بيضاء؟",
             "دول شنغن تتبع معيار منظمة الطيران المدني (ICAO) الذي يطلب خلفية فاتحة موحّدة، لكن التفاصيل تختلف: "
             "القرار الفرنسي ينص على أن الخلفية «موحّدة بلون فاتح (أزرق فاتح، رمادي فاتح). الأبيض ممنوع»، "
             "والقالب الألماني يطلب خلفية فاتحة موحّدة بتباين واضح مع الوجه والشعر. الرمادي الفاتح مقبول عند الجميع، "
             "لذلك جعلناه الاختيار الأول، ويمكنك تغييره إن طلبت قنصليتك لونًا آخر."),
            ("كيف يُقاس الرأس؟",
             "من أسفل الذقن إلى قمة الجمجمة، لا إلى أعلى الشعر — النص الفرنسي يقول «دون احتساب الشعر». "
             "الأداة تقدّر قمة الرأس من مواضع العينين والذقن، وتعرض لك الخطين على الصورة لتتأكد بنفسك."),
            ("هل تختلف الشروط بين دول شنغن؟",
             "المقاس وحجم الرأس واحد في كل الدول. الاختلاف في لون الخلفية وبعض التفاصيل، وكثير من مراكز التأشيرات "
             "تلتقط الصورة البيومترية عندها يوم الموعد. راجع قائمة المستندات في موقع القنصلية أو مركز التأشيرات الذي ستقدّم فيه."),
        ],
    },
    {
        "slug": "us-visa", "w": 51, "h": 51, "px": [600, 600], "label": "5×5 سم (600×600 بكسل)",
        "head": 0.60, "head_min": 0.50, "head_max": 0.69, "eye": 0.62, "eye_min": 0.56, "eye_max": 0.69,
        "bgs": WHITE, "bg_default": False, "unaltered": True, "max_kb": 240,
        "name": "صورة التأشيرة الأمريكية", "flag": "🇺🇸",
        "title": "صورة التأشيرة الأمريكية 5×5 سم (600×600 بكسل): الشروط الرسمية + أداة مجانية",
        "desc": "صورة الفيزا الأمريكية مربعة 5×5 سم (2×2 بوصة)، ورقميًّا 600×600 بكسل بحد أقصى 240 كيلوبايت، والرأس 50–69% "
                "من ارتفاع الصورة. قصّ صورتك على هذه القياسات وتحقق منها مجانًا.",
        "lead": "صورة التأشيرة الأمريكية مربعة 5×5 سم (2×2 بوصة)، والنسخة الرقمية 600×600 بكسل بصيغة JPEG لا تزيد على 240 كيلوبايت، والرأس بين 50% و69% من ارتفاع الصورة. الأداة تقصّ على هذه القياسات وتُخرج الملف بالحجم المطلوب.",
        "facts": [("المقاس المطبوع", "51×51 مم (2×2 بوصة)"),
                  ("المقاس الرقمي", "مربعة، من 600×600 إلى 1200×1200 بكسل"),
                  ("الملف", "JPEG لا يزيد على 240 كيلوبايت"),
                  ("ارتفاع الرأس", "50%–69% من ارتفاع الصورة (25–35 مم)"),
                  ("ارتفاع العينين", "56%–69% من الحافة السفلى"),
                  ("الخلفية", "بيضاء أو مائلة للبياض"),
                  ("الحداثة", "خلال آخر 6 أشهر"),
                  ("التعديل", "ممنوع تعديل الصورة ببرامج أو فلاتر أو ذكاء اصطناعي")],
        "source": ("وزارة الخارجية الأمريكية — Photo Requirements",
                   "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos.html"),
        "about": [
            ("مهم: لا تبيّض الخلفية لهذه الصورة",
             "وزارة الخارجية الأمريكية ترفض الصور المعدّلة رقميًّا: لا فلاتر ولا برامج تعديل ولا ذكاء اصطناعي، وتبييض الخلفية "
             "تعديل رقمي. لذلك خيار «تبييض الخلفية» مُطفأ هنا: صوّر أمام حائط أبيض بإضاءة منتظمة، واستخدم الأداة للقص والمقاس "
             "وحجم الملف فقط. إن فعّلت التبييض فعلى مسؤوليتك."),
            ("الهجرة العشوائية (اللوتري)",
             "برنامج تأشيرات التنوع يستخدم المواصفات نفسها: صورة مربعة 600×600 بكسل بصيغة JPEG لا تزيد على 240 كيلوبايت. "
             "مواعيد التسجيل وشروطه تعلنها وزارة الخارجية الأمريكية وحدها على dvprogram.state.gov، والتسجيل هناك بلا وسطاء."),
            ("النظارات وغطاء الرأس",
             "النظارات غير مسموح بها في صور التأشيرات الأمريكية. غطاء الرأس مسموح لسبب ديني بشرط ظهور الوجه كاملًا "
             "من أسفل الذقن إلى أعلى الجبهة ودون ظلال على الوجه."),
        ],
    },
]
BY_SLUG = {d["slug"]: d for d in DOCS}

CSS = """
<style>
.idp{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:18px 0}
.idp [hidden]{display:none!important}
.idp-pick{margin-bottom:14px}
.idp-pick label{display:block;color:var(--mut);font-size:.82rem;margin-bottom:4px}
.idp select{width:100%;background:var(--bg2);color:var(--txt);border:1px solid var(--line);
  border-radius:10px;padding:9px 11px;font:inherit}
.idp-drop{border:2px dashed var(--line);border-radius:14px;padding:22px 14px;text-align:center;transition:.2s}
.idp-drop.over{border-color:var(--gold);background:rgba(245,197,66,.06)}
.idp-drop.done .idp-hint{display:none}
.idp-hint{font-weight:700;margin-bottom:6px}
.idp-btn{display:inline-block;background:var(--gold);color:#1a1300;font:inherit;font-weight:800;border:0;
  border-radius:12px;padding:10px 20px;margin:5px;cursor:pointer;text-decoration:none}
.idp-btn.alt{background:transparent;color:var(--txt);border:1px solid var(--line)}
.idp-btn:hover{filter:brightness(1.08)}
.idp-btn.alt:hover{border-color:var(--gold);color:var(--gold)}
.idp-priv{color:var(--mut);font-size:.8rem;margin-top:8px}
.idp-status{margin-top:12px;font-size:.9rem;color:var(--acc);text-align:center}
.idp-status b{display:block;height:5px;background:var(--bg2);border-radius:9px;margin-top:6px;overflow:hidden}
.idp-status i{display:block;height:100%;width:0;background:var(--acc);transition:width .2s}
.idp-error{margin-top:12px;background:rgba(255,107,107,.1);border:1px solid rgba(255,107,107,.35);
  border-radius:10px;padding:10px 13px;color:#ff9b9b;font-size:.9rem}
.idp-work{display:grid;grid-template-columns:minmax(0,290px) minmax(0,1fr);gap:18px;margin-top:16px;align-items:start}
.idp-canvas{width:100%;max-width:290px;height:auto;display:block;margin:0 auto;background:#fff;
  border-radius:4px;box-shadow:0 0 0 1px var(--line),0 6px 22px rgba(0,0,0,.45);cursor:grab}
.idp-size{text-align:center;color:var(--mut);font-size:.8rem;margin-top:8px}
.idp-verdict{font-weight:800;border-radius:10px;padding:8px 12px;margin-bottom:10px;font-size:.9rem}
.idp-verdict.ok{background:rgba(62,207,142,.12);color:#3ecf8e}
.idp-verdict.bad{background:rgba(255,107,107,.12);color:#ff8585}
.idp-checks{list-style:none;padding:0;margin:0 0 12px;font-size:.86rem}
.idp-checks li{padding:2px 0}
.idp-checks .ok{color:#3ecf8e}.idp-checks .warn{color:var(--gold)}.idp-checks .bad{color:#ff8585}
.idp-ctl{border-top:1px solid var(--line);padding-top:10px;margin-top:6px;font-size:.86rem}
.idp-ctl label{display:flex;align-items:center;gap:8px;margin:7px 0}
.idp-ctl input[type=range]{flex:1;accent-color:var(--gold)}
.idp-ctl input[type=checkbox]{accent-color:var(--gold);width:17px;height:17px}
.idp-ctl select{width:auto;padding:5px 9px}
.idp-move{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:7px 0}
.idp-move button{background:var(--bg2);color:var(--txt);border:1px solid var(--line);border-radius:9px;
  min-width:38px;height:34px;font:inherit;cursor:pointer}
.idp-move button:hover{border-color:var(--gold)}
.idp-note{background:rgba(245,197,66,.08);border:1px solid rgba(245,197,66,.3);border-radius:10px;
  padding:8px 11px;font-size:.82rem;color:var(--gold);margin:8px 0}
.idp-dl{margin-top:12px}
.idp-dl .idp-btn{margin:4px 0 4px 6px}
.idp-docs{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:16px 0}
.idp-docs a{display:block;text-decoration:none;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:13px 15px;transition:.2s}
.idp-docs a:hover{border-color:var(--gold)}
.idp-docs b{display:block;font-size:1rem}
.idp-docs span{color:var(--mut);font-size:.82rem}
.idp-page h2{margin:26px 0 8px;font-size:1.2rem}
.idp-page p{margin-bottom:10px}
.idp-page ol,.idp-page ul.idp-list{margin:0 0 14px;padding-inline-start:22px}
.idp-page li{margin-bottom:6px;color:#dfe6f0}
.idp-page .src a{color:var(--acc)}
@media(max-width:640px){.idp-work{grid-template-columns:1fr}}
</style>"""

SHOOT = [
    "اطلب من شخص آخر أن يصوّرك من مسافة متر ونصف تقريبًا والهاتف في مستوى عينيك. صورة السيلفي القريبة تشوّه نِسَب الوجه.",
    "قف أمام حائط فاتح موحّد، وابتعد عنه نصف متر حتى لا يظهر ظلّك عليه.",
    "واجه نافذة أو مصدر ضوء منتظم، بلا ظلال على الوجه وبلا فلاش مباشر.",
    "انظر إلى العدسة مباشرة والرأس مستقيم، بتعبير محايد وفم مغلق وعينين مفتوحتين.",
    "اترك مساحة حول الرأس والكتفين في الصورة الأصلية؛ الأداة هي التي تقصّ.",
]

REJECT = [
    "ظل على الوجه أو على الخلفية.",
    "رأس مائل أو وجه غير مواجه للكاميرا.",
    "حجم الرأس أكبر أو أصغر من المطلوب.",
    "نظارات فيها انعكاس، أو شعر يغطي العينين.",
    "صورة قديمة لا تطابق الشكل الحالي، أو صورة مأخوذة من صورة مطبوعة.",
    "صورة معدّلة بفلاتر التجميل أو مولّدة بالذكاء الاصطناعي.",
]


def js_version():
    with open(os.path.join(HERE, "idphoto.js"), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:10]


def client_spec(d):
    keys = ("slug", "w", "h", "px", "label", "head", "head_min", "head_max", "top",
            "eye", "eye_min", "eye_max", "bgs", "bg_default", "unaltered", "max_kb")
    return {k: d[k] for k in keys if k in d}


def tool_html(current, js_src, hub=False):
    data = {"current": current, "docs": {d["slug"]: client_spec(d) for d in DOCS}}
    pick = ""
    if hub:
        options = "".join("<option value='{}'{}>{} — {}</option>".format(
            d["slug"], " selected" if d["slug"] == current else "", E(d["name"]), E(d["label"])) for d in DOCS)
        pick = ("<div class='idp-pick'><label for='idp-doc'>نوع الصورة</label>"
                "<select id='idp-doc'>{}</select></div>").format(options)
    # JSON داخل <script>: نمنع إغلاق الوسم من داخل البيانات
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f"""
    <section class="idp" id="idp" aria-label="أداة قص صور الجواز والتأشيرة">
      {pick}
      <div class="idp-drop" id="idp-drop">
        <p class="idp-hint">اختر صورة واضحة للوجه والكتفين — تخرج بمقاس <span data-idp-size></span></p>
        <label class="idp-btn"><input type="file" id="idp-file" accept="image/*" hidden>اختر صورة من جهازك</label>
        <label class="idp-btn alt"><input type="file" id="idp-cam" accept="image/*" capture="environment" hidden>التقط بالكاميرا</label>
        <p class="idp-priv">🔒 صورتك تُعالَج داخل متصفحك ولا تُرفع إلى أي خادم.</p>
      </div>
      <div class="idp-status" id="idp-status" hidden><span></span><b><i></i></b></div>
      <div class="idp-error" id="idp-error" role="alert" hidden></div>
      <div class="idp-work" id="idp-work" hidden>
        <div>
          <canvas class="idp-canvas" id="idp-canvas" width="400" height="600"></canvas>
          <p class="idp-size">المقاس: <span data-idp-size></span></p>
        </div>
        <div>
          <div class="idp-verdict" id="idp-verdict"></div>
          <ul class="idp-checks" id="idp-checks"></ul>
          <div class="idp-ctl">
            <label><input type="checkbox" id="idp-bg"> تبييض الخلفية</label>
            <label id="idp-bgcolor-row" hidden>لون الخلفية <select id="idp-bgcolor"></select></label>
            <div class="idp-note" id="idp-bgnote" hidden>الجهة الرسمية لهذا المستند ترفض الصور المعدّلة رقميًّا. الأضمن أن تصوّر أمام حائط أبيض وتترك هذا الخيار مُطفأ.</div>
            <label>تكبير <input type="range" id="idp-zoom" min="0.75" max="1.35" step="0.005" value="1"></label>
            <label>تدوير <input type="range" id="idp-rot" min="-8" max="8" step="0.25" value="0"></label>
            <div class="idp-move">تحريك
              <button type="button" data-idp-move="0,-1" aria-label="أعلى">▲</button>
              <button type="button" data-idp-move="0,1" aria-label="أسفل">▼</button>
              <button type="button" data-idp-move="1,0" aria-label="يمين">▶</button>
              <button type="button" data-idp-move="-1,0" aria-label="يسار">◀</button>
              <button type="button" id="idp-reset">إعادة الضبط</button>
            </div>
            <label><input type="checkbox" id="idp-guides" checked> إظهار خطوط القياس (لا تظهر في الصورة المحمّلة)</label>
          </div>
          <div class="idp-dl">
            <button type="button" class="idp-btn" id="idp-dl-sheet">تحميل ورقة الطباعة 10×15</button>
            <button type="button" class="idp-btn alt" id="idp-dl-photo">تحميل الصورة</button>
            <button type="button" class="idp-btn alt" id="idp-again">صورة أخرى</button>
          </div>
        </div>
      </div>
      <script type="application/json" id="idp-data">{blob}</script>
      <script type="module" src="{js_src}"></script>
    </section>"""


def common_sections():
    shoot = "".join("<li>{}</li>".format(E(s)) for s in SHOOT)
    reject = "".join("<li>{}</li>".format(E(s)) for s in REJECT)
    return f"""
    <h2>كيف تلتقط صورة تُقبل من أول مرة؟</h2>
    <ol>{shoot}</ol>
    <h2>كيف تطبعها؟</h2>
    <p>حمّل «ورقة الطباعة 10×15» واطبعها في أي معمل تصوير على ورق صور مقاس 10×15 سم (4×6 بوصة) <strong>بالحجم الفعلي دون تكبير أو قص</strong>، ثم قصّ الصور على الخطوط الرمادية. طباعة ورقة 10×15 أرخص كثيرًا من جلسة تصوير، وتخرج منها عدة نسخ.</p>
    <h2>أسباب رفض الصور الشائعة</h2>
    <ul class="idp-list">{reject}</ul>
    <h2>ماذا تفعل الأداة وما الذي لا تفعله؟</h2>
    <p>تحدّد الوجه، وتعدل ميل الرأس، وتقصّ الصورة بالمقاس، وتستبدل الخلفية إن طلبت. <strong>لا تعدّل ملامح الوجه</strong> ولا تجمّلها ولا تعيد رسمها: الوجه في الصورة الناتجة هو وجهك كما في الصورة الأصلية، بتغيير المقاس والتدوير فقط. كل ذلك يجري داخل متصفحك، فصورتك لا تغادر جهازك.</p>
    <p class="src">الأداة تساعدك على مطابقة المقاس والتكوين، والقرار النهائي في قبول الصورة للجهة التي تقدّم لها. فصل الخلفية يعمل بنموذج MODNet ومكتبة MediaPipe (رخصة Apache-2.0).</p>"""


def docs_grid(root, skip=None):
    cards = "".join(
        "<a href='{r}{s}/{slug}/'><b>{flag} {name}</b><span>{label}</span></a>".format(
            r=root, s=SLUG, slug=d["slug"], flag=d["flag"], name=E(d["name"]), label=E(d["label"]))
        for d in DOCS if d["slug"] != skip)
    return "<nav class='idp-docs'>" + cards + "</nav>"


def breadcrumb_ld(base, canonical, name, title, hub_only=False):
    items = [{"@type": "ListItem", "position": 1, "name": "الرئيسية", "item": base + "/"},
             {"@type": "ListItem", "position": 2, "name": "صور الجواز والتأشيرة", "item": "{}/{}/".format(base, SLUG)}]
    if not hub_only:
        items.append({"@type": "ListItem", "position": 3, "name": name, "item": canonical})
    return {"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": canonical,
            "inLanguage": "ar", "dateModified": VERIFIED,
            "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": items}}


def build_doc(d, base, nav, page_func, ver):
    canonical = "{}/{}/{}/".format(base, SLUG, d["slug"])
    facts = "".join("<tr><td>{}</td><td>{}</td></tr>".format(E(k), E(v)) for k, v in d["facts"])
    about = "".join("<h2>{}</h2><p>{}</p>".format(E(h), E(t)) for h, t in d["about"])
    src = ""
    if d.get("source"):
        links = ["<a href='{}' rel='noopener' target='_blank'>{}</a>".format(E(u), E(n))
                 for n, u in (d["source"], d.get("source2")) if n] if d.get("source2") else \
                ["<a href='{}' rel='noopener' target='_blank'>{}</a>".format(E(d["source"][1]), E(d["source"][0]))]
        src = "<p class='src'>المصدر الرسمي: {}. تحقّقنا من الشروط في {}.</p>".format(" · ".join(links), VERIFIED_AR)
    body = f"""{CSS}
    <div class="idp-page">
    <nav class="breadcrumb"><a href="../../">الرئيسية</a> › <a href="../">صور الجواز والتأشيرة</a> › <span>{E(d['name'])}</span></nav>
    <h1>{d['flag']} {E(d['name'])}</h1>
    <p class="lead">{E(d['lead'])}</p>
    {tool_html(d['slug'], '../idphoto.js?v=' + ver)}
    <h2>الشروط المطلوبة</h2>
    <table><thead><tr><th>البند</th><th>المطلوب</th></tr></thead><tbody>{facts}</tbody></table>
    {src}
    {about}
    {common_sections()}
    <h2>مقاسات أخرى</h2>
    {docs_grid('../../', skip=d['slug'])}
    </div>"""
    page_func("{}/{}/index.html".format(SLUG, d["slug"]), d["title"], d["desc"], body, canonical,
              nav=nav, depth=2, jsonld=breadcrumb_ld(base, canonical, d["name"], d["title"]))
    return (canonical, VERIFIED + "T00:00:00+00:00", "0.8")


def build_hub(base, nav, page_func, ver):
    canonical = "{}/{}/".format(base, SLUG)
    title = "صورة جواز السفر والتأشيرة أونلاين مجانًا — قصّ بالمقاس الرسمي وخلفية بيضاء"
    desc = ("جهّز صورة الجواز أو التأشيرة من هاتفك مجانًا: قصّ تلقائي بالمقاس الرسمي (4×6، شنغن 35×45، "
            "الأمريكية 5×5)، خلفية بيضاء، وورقة 10×15 جاهزة للطباعة. الصورة لا تُرفع إلى أي خادم.")
    rows = "".join(
        "<tr><td><a href='{slug}/' style='color:var(--acc)'>{flag} {name}</a></td><td>{label}</td><td>{bg}</td></tr>".format(
            slug=d["slug"], flag=d["flag"], name=E(d["name"]), label=E(d["label"]),
            bg=E("، ".join(n for n, _ in d["bgs"]))) for d in DOCS)
    body = f"""{CSS}
    <div class="idp-page">
    <nav class="breadcrumb"><a href="../">الرئيسية</a> › <span>صور الجواز والتأشيرة</span></nav>
    <h1>📸 صورة الجواز والتأشيرة من هاتفك — بالمقاس الرسمي</h1>
    <p class="lead">اختر نوع الصورة وارفع صورة من هاتفك: تُقصّ تلقائيًا بالمقاس الرسمي، وتُبيَّض خلفيتها، وتخرج معها ورقة 10×15 جاهزة للطباعة. مجانًا وبلا تسجيل، وصورتك لا تُرفع إلى أي خادم.</p>
    {tool_html(DOCS[0]['slug'], './idphoto.js?v=' + ver, hub=True)}
    <h2>المقاسات المتاحة</h2>
    <table><thead><tr><th>المستند</th><th>المقاس</th><th>الخلفية</th></tr></thead><tbody>{rows}</tbody></table>
    <p class="src">لكل مستند صفحة فيها شروطه كاملة ورابط الجهة الرسمية التي أخذناها منها. آخر تحقق: {VERIFIED_AR}.</p>
    {docs_grid('./')}
    {common_sections()}
    </div>"""
    page_func(SLUG + "/index.html", title, desc, body, canonical, nav=nav, depth=1,
              jsonld=breadcrumb_ld(base, canonical, "", title, hub_only=True))
    return (canonical, VERIFIED + "T00:00:00+00:00", "0.8")


# -- ربط مقالات الترند بالأداة --------------------------------------------

RELATED_WORDS = ("جواز السفر", "جوازات", "تأشيرة", "التأشيرة", "فيزا", "شنغن", "الهجرة العشوائية", "اللوتري")


def related_box(title, root):
    if any(w in title for w in RELATED_WORDS):
        return ("<aside class='eg-note' style='margin:18px 0'>📸 <a href='{}{}/' style='color:var(--gold)'>"
                "جهّز صورة الجواز أو التأشيرة بالمقاس الرسمي من هاتفك مجانًا</a></aside>").format(root, SLUG)
    return ""


def build_idphoto_site(base, out, nav_func, page_func):
    """يبني صفحة الأداة وصفحة لكل مستند وينسخ السكربت، ويعيد الروابط لخريطة الموقع."""
    ver = js_version()
    urls = [build_hub(base, nav_func(1), page_func, ver)]
    for d in DOCS:
        urls.append(build_doc(d, base, nav_func(2), page_func, ver))
    with open(os.path.join(HERE, "idphoto.js"), "rb") as f:
        js = f.read()
    with open(os.path.join(out, SLUG, "idphoto.js"), "wb") as f:
        f.write(js)
    return urls
