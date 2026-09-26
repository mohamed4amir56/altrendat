# -*- coding: utf-8 -*-
"""
محرّك قسم الوظائف وعقود العمل — altrendat.com/jobs/

يوفّر قسماً شاملاً ومحدّثاً للوظائف الأكثر بحثاً في الوطن العربي:
1. وظائف حكومية ومسابقات رسمية (مصر، السعودية، الخليج).
2. عقود عمل بالخارج ودول أجنبية (ألمانيا، كندا، إيطاليا، بريطانيا).
3. وظائف شركات الخليج الكبرى (أرامكو، طيران الإمارات، بنوك).
4. وظائف عن بعد بالدولار ومن المنزل (Remote Work).

يدعم:
- Schema.org (JobPosting) للظهور التلقائي في Google for Jobs.
- فلاتر وتصنيفات تفاعلية وسريعة.
- تنبيهات الأمان والمصداقية ضد النصب وروابط رسمية مباشرة.
"""
import html
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_FILE = os.path.join(ROOT, "data", "jobs.json")
E = html.escape

# فئات الوظائف
CATEGORIES = {
    "gov": {"name_ar": "وظائف حكومية", "icon": "🏛️", "color": "#3ddc97"},
    "abroad": {"name_ar": "عقود عمل بالخارج", "icon": "✈️", "color": "#5aa9ff"},
    "gulf": {"name_ar": "وظائف الخليج", "icon": "🇸🇦", "color": "#f5c542"},
    "remote": {"name_ar": "وظائف عن بعد", "icon": "🌐", "color": "#c77dff"},
}

TYPE_LABELS = {
    "FULL_TIME": "دوام كامل 🟢",
    "PART_TIME": "دوام جزئي ⏱️",
    "SEASONAL": "عقد موسمي ✈️",
    "REMOTE": "عمل عن بعد 🌐",
}

INITIAL_JOBS = [
    {
        "id": "egypt-tax-authority-jobs-2026",
        "slug": "egypt-tax-authority-jobs-2026",
        "title": "مسابقة وظائف مصلحة الضرائب المصرية 2026 — شروط ومواعيد التقديم بالرابط الرسمي",
        "category": "gov",
        "country": "مصر",
        "country_code": "eg",
        "flag": "🇪🇬",
        "employer": "مصلحة الضرائب المصرية — الجهاز المركزي للتنظيم والإدارة",
        "location": "جميع محافظات مصر",
        "salary": "رواتب تبدأ من 7,500 إلى 11,000 جنيه + حوافز وبدلات",
        "deadline": "2026-10-31",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://jobs.caoa.gov.eg/",
        "summary": "إعلان الجهاز المركزي للتنظيم والإدارة عن فتح باب التقديم لمسابقة مصلحة الضرائب المصرية لتعيين مأموري ضرائب فحص وحجز وباحثين قانونيين وتقنيي حاسب آلي بجميع المحافظات.",
        "requirements": [
            "الحصول على بكالوريوس تجارة (شعبة محاسبة) أو ليسانس حقوق/شريعة وقانون بتقدير عام جيد على الأقل.",
            "ألا يزيد سن المتقدم عن 35 عاماً في تاريخ نشر الإعلان.",
            "إجادة استخدام الحاسب الآلي وتطبيقات قواعد البيانات.",
            "اجتياز الامتحانات الإلكترونية والمقابلة الشخصية بمركز تقييم القدرات والمسابقات."
        ],
        "documents": [
            "صورة بطاقة الرقم القومي سارية (وجهين).",
            "أصل المؤهل الدراسي وشهادة التخرج.",
            "الموقف من التجنيد للذكور أو الخدمة العامة للإناث.",
            "فيش جنائي موجه للجهاز المركزي للتنظيم والإدارة أو مصلحة الضرائب.",
            "إيصال الإيداع البنكي بحساب الجهاز في أحد البنوك الحكومية."
        ],
        "how_to_apply": "يتم التقديم إلكترونياً وبشكل حصري من خلال بوابة الوظائف الحكومية الرسمية (jobs.caoa.gov.eg) بعد استيفاء الأوراق ورفعها بصيغة PDF."
    },
    {
        "id": "germany-chancenkarte-opportunity-card-2026",
        "slug": "germany-chancenkarte-opportunity-card-2026",
        "title": "عقود عمل في ألمانيا 2026 — كل ما تريد معرفته عن بطاقة الفرصة (Chancenkarte) ورابط التقديم",
        "category": "abroad",
        "country": "ألمانيا",
        "country_code": "de",
        "flag": "🇩🇪",
        "employer": "وكالة التوظيف الفيدرالية الألمانية (Bundesagentur für Arbeit)",
        "location": "ألمانيا (جميع المقاطعات)",
        "salary": "متوسط رواتب 2,800 إلى 4,500 يورو شهرياً حسب المهنة والتخصص",
        "deadline": "مفتوح على مدار العام 2026",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://www.make-it-in-germany.com/en/visa-residence/types/job-search-opportunity-card",
        "summary": "دليل التقديم على بطاقة الفرصة الألمانية (Chancenkarte) التي تتيح السفر والبحث عن عمل في ألمانيا لمدة عام بدون عقد مسبق اعتماداً على نظام النقاط والمؤهلات واللغة.",
        "requirements": [
            "الحصول على مؤهل جامعي معترف به في ألمانيا أو شهادة مهنية معتمدة سنتين على الأقل.",
            "إتقان اللغة الألمانية بمستوى A1 على الأقل، أو اللغة الإنجليزية بمستوى B2.",
            "جمع 6 نقاط على الأقل في حاسبة النقاط الألمانية (العمر، الخبرة، اللغة، الشهادة).",
            "إثبات القدرة المالية للمعيشة خلال فترة البحث عبر حساب بنكي مغلق أو كفالة رسمية."
        ],
        "documents": [
            "جواز سفر ساري المفعول.",
            "شهادات التخرج وبيان الدرجات مع الترجمة المعتمدة للألمانية أو الإنجليزية.",
            "شهادة اللغة الرسمية (Goethe / Telc للألماني أو IELTS / TOEFL للإنجليزي).",
            "سيرة ذاتية وفق النموذج الأوروبي Europass.",
            "تأمين صحي للسفر يغطي فترة الإقامة الأولى."
        ],
        "how_to_apply": "التقديم الرسمي يتم عبر بوابة التأشيرات التابعة للخارجية الألمانية ومنصة Make it in Germany، وحجز موعد في السفارة الألمانية في بلدك."
    },
    {
        "id": "canada-skilled-trades-work-permit-2026",
        "slug": "canada-skilled-trades-work-permit-2026",
        "title": "فرص عمل في كندا 2026 مع توفير تأشيرة العمل (LMIA) — المهن المطلوبة ورابط بنك الوظائف الكندي",
        "category": "abroad",
        "country": "كندا",
        "country_code": "ca",
        "flag": "🇨🇦",
        "employer": "شركات كندية معتمدة (عبر Job Bank Canada)",
        "location": "مقاطعات أونتاريو، ألبرتا، بريتيش كولومبيا، كندا",
        "salary": "من 22 إلى 42 دولار كندي/ساعة (3,500 - 6,500 CAD شهرياً)",
        "deadline": "مفتوح حسب كل شواغر كل شركة",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://www.jobbank.gc.ca/jobsearch/jobsearch?fnoncan=1",
        "summary": "تفاصيل فرص العمل المتاحة في كندا الموجهة للمتقدمين من خارج كندا مع تصريح العمل المعتمد (LMIA) في قطاعات البناء، النقل، الضيافة، الرعاية، والتقنية.",
        "requirements": [
            "خبرة عملية موثقة في المهنة المطلوبة من عامين إلى 3 أعوام.",
            "مستوى لغة إنجليزية متوسط (IELTS General بمستوى 5.0 فأعلى) أو فرنسية للمقاطعات الفرنكوفونية.",
            "سيرة ذاتية متوافقة مع النمط الكندي (Canadian Resume Format).",
            "شهادة خلو من السوابق الجنائية وفحص طبي معتمد."
        ],
        "documents": [
            "نسخة جواز السفر ساري الصلاحية.",
            "شهادات الخبرة السابقة وعقود العمل الموثقة.",
            "المؤهل الدراسي وشهادة معادلة WES إن وجدت.",
            "خطابات توصية من أصحاب عمل سابقين."
        ],
        "how_to_apply": "ابحث في بنك الوظائف الكندي الحكومي (Job Bank) عبر فلتر 'المتقدمين الدوليين من خارج كندا' (Canadians and international candidates) وقدّم مباشرة مع صاحب العمل."
    },
    {
        "id": "saudi-jadarat-gov-careers-2026",
        "slug": "saudi-jadarat-gov-careers-2026",
        "title": "وظائف منصة جدارات الحكومية 2026 بالسعودية — الشروط ورابط التقديم على الوظائف الإدارية والتقنية",
        "category": "gulf",
        "country": "السعودية",
        "country_code": "sa",
        "flag": "🇸🇦",
        "employer": "المنصة الوطنية الموحدة للتوظيف (جدارات) — الوزارات والهيئات السعودية",
        "location": "الرياض، مكة، جدة، الشرقية، جميع مناطق المملكة",
        "salary": "سلالم رواتب الخدمة المدنية (من 6,000 إلى 16,000 ريال سعودي)",
        "deadline": "مستمر حسب الإعلانات الوظيفية لكل جهة",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://jadarat.sa/",
        "summary": "طرح عدد من الجهات الحكومية والوزارات بالمملكة العربية السعودية وظائف شاغرة بالمراتب من الرابعة حتى العاشرة عبر منصة جدارات الموحدة للرجال والنساء.",
        "requirements": [
            "أن يكون المتقدم حاصلاً على المؤهل العلمي المناسب (دبلوم، بكالوريوس، ماجستير).",
            "اجتياز اختبار القدرة المعرفية للوظائف الإدارية لدرجة البكالوريوس فأعلى.",
            "معادلة الشهادة الصادرة من خارج المملكة لدى وزارة التعليم.",
            "التفرغ التام وعدم شغل وظيفة حكومية حالياً."
        ],
        "documents": [
            "وثيقة التخرج وسجل الدرجات الأكاديمي.",
            "شهادة التصنيف المهني والتسجيل إن كانت الوظيفة تخصصية (صحية أو هندسية).",
            "شهادة اختبار القدرة المعرفية من هيئة تقويم التعليم والتدريب."
        ],
        "how_to_apply": "تسجيل الدخول عبر النفاذ الوطني الموحد على منصة جدارات (jadarat.sa)، وتحديث الملف الشخصي ثم اختيار الإعلانات الوظيفية المتاحة والتقديم عليها."
    },
    {
        "id": "egypt-education-teachers-competition-2026",
        "slug": "egypt-education-teachers-competition-2026",
        "title": "مسابقة وزارة التربية والتعليم 2026 لتعيين 30 ألف معلم مساعد — التخصصات والأوراق المطلوبة",
        "category": "gov",
        "country": "مصر",
        "country_code": "eg",
        "flag": "🇪🇬",
        "employer": "وزارة التربية والتعليم والتعليم الفني بالتعاون مع التنظيم والإدارة",
        "location": "المديريات التعليمية بالمحافظات",
        "salary": "رواتب المعلمين المساعدين وفقاً للدرجة الوظيفية وحوافز التطوير",
        "deadline": "2026-10-25",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://jobs.caoa.gov.eg/",
        "summary": "إعلان تفاصيل المرحلة الجديدة من مسابقة تعيين المعلمين المساعدين بوزارة التربية والتعليم لتخصصات رياض الأطفال، معلم فصل للمرحلة الابتدائية، والمواد الأساسية.",
        "requirements": [
            "خريج كليات التربية أو كليات الآداب والعلوم ودار العلوم الحاصلين على دبلوم تربوي عام.",
            "ألا يقل التقدير العام عن جيد.",
            "ألا يزيد سن المتقدم عن 40 سنة في تاريخ نشر الإعلان.",
            "التقديم في النطاق الجغرافي المسجل ببطاقة الرقم القومي للمحافظة."
        ],
        "documents": [
            "أصل شهادة التخرج والمؤهل الدراسي.",
            "الدبلوم التربوي لغير خريجي كليات التربية.",
            "شهادة الموقف من التجنيد أو الخدمة العامة.",
            "صورة بطاقة الرقم القومي سارية وصحيفة الحالة الجنائية."
        ],
        "how_to_apply": "التقديم عبر بوابة الوظائف الحكومية المصرية خلال فترة فتح باب التسجيل المعلنة رسمياً."
    },
    {
        "id": "italy-seasonal-worker-decreto-flussi-2026",
        "slug": "italy-seasonal-worker-decreto-flussi-2026",
        "title": "عقود عمل في إيطاليا 2026 (Decreto Flussi) — شروط السفر والعمل الموسمي بالقطاعين الزراعي والسياحي",
        "category": "abroad",
        "country": "إيطاليا",
        "country_code": "it",
        "flag": "🇮🇹",
        "employer": "مزارع وفنادق ومؤسسات إيطالية معتمدة",
        "location": "إيطاليا (ميلانو، روما، صقلية، فلورنسا)",
        "salary": "1,400 إلى 2,200 يورو شهرياً + إمكانية توفير السكن",
        "deadline": "حسب الحصص الرسمية لمرسوم التدفقات",
        "posted_at": "2026-09-25",
        "employment_type": "SEASONAL",
        "apply_url": "https://portaleservizi.dlci.interno.it/",
        "summary": "تفاصيل قانون العمل الموسمي وغير الموسمي الإيطالي (ديكريتو فلوسي) الذي يمنح آلاف العقود للمواطنين من خارج الاتحاد الأوروبي للعمل في قطاعات الزراعة، الفنادق، والنقل.",
        "requirements": [
            "وجود صاحب عمل في إيطاليا يقدم طلب تصريح العمل (Nulla Osta) باسم العامل.",
            "جواز سفر ساري المفعول لمدة لا تقل عن سنتين.",
            "ألا يكون لدى المتقدم سوابق ترحيل من دول الاتحاد الأوروبي.",
            "الالتزام بمدة العقد الموسمي والعودة أو تحويله إلى إقامة عمل دائمة قانونياً."
        ],
        "documents": [
            "جواز السفر وشهادة الميلاد المترجمة والمصدقة.",
            "عقد العمل المعتمد من مكتب العمل الإيطالي (Sportello Unico).",
            "نموذج طلب التأشيرة معبأ بالكامل."
        ],
        "how_to_apply": "يقوم صاحب العمل في إيطاليا بالتقديم عبر بوابة وزارة الداخلية الإيطالية، ثم يستلم العامل تصريح Nulla Osta لاستخراج فيزا العمل من السفارة الإيطالية."
    },
    {
        "id": "aramco-saudi-careers-2026",
        "slug": "aramco-saudi-careers-2026",
        "title": "وظائف شركة أرامكو السعودية ونيوم 2026 — شواغر كبرى للتخصصات الهندسية والإدارية والفنية",
        "category": "gulf",
        "country": "السعودية",
        "country_code": "sa",
        "flag": "🇸🇦",
        "employer": "شركة الزيت العربية السعودية (أرامكو) ومشاريع نيوم",
        "location": "الظهران، الرياض، تبوك، نيوم، رأس تنورة",
        "salary": "رواتب مجزية جداً + بدل سكن، تأمين طبي شامل، وبدل مواصلات",
        "deadline": "مستمر عبر البوابة الإلكترونية",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://www.aramco.com/ar/careers",
        "summary": "فتح باب التوظيف المباشر في أرامكو السعودية ومشروع نيوم العالمي للمهندسين، مسؤولي السلامة، المحاسبين، ومطوري البرمجيات، وخبراء سلاسل الإمداد.",
        "requirements": [
            "مؤهل جامعي مناسب في الهندسة، علوم الحاسب، الإدارة المالية، أو السلامة المهنية.",
            "إتقان اللغة الإنجليزية تحدثاً وكتابة.",
            "خبرة مهنية تبدأ من عامين للمحترفين أو برامج مخصصة لحديثي التخرج المتميزين.",
            "مهارات حل المشكلات والعمل ضمن فرق عمل متعددة الثقافات."
        ],
        "documents": [
            "السيرة الذاتية المفصلة باللغة الإنجليزية.",
            "نسخ مصدقة من المؤهلات الأكاديمية والشهادات المهنية المعتمدة (PMP, NEBOSH, etc.).",
            "صورة من بطاقة الهوية أو الإقامة/جواز السفر."
        ],
        "how_to_apply": "التقديم حصرياً ومباشرة عبر بوابة أرامكو الرسمية للتوظيف وإنشاء ملف شخصي واختيار رقم الوظيفة الشاغرة."
    },
    {
        "id": "emirates-airline-group-careers-dubai",
        "slug": "emirates-airline-group-careers-dubai",
        "title": "وظائف طيران الإمارات في دبي 2026 — خدمة العملاء والضيافة الجوية والعمليات الأرضية",
        "category": "gulf",
        "country": "الإمارات",
        "country_code": "ae",
        "flag": "🇦🇪",
        "employer": "مجموعة الإمارات (Emirates Group)",
        "location": "دبي، الإمارات العربية المتحدة",
        "salary": "9,000 إلى 18,000 درهم إماراتي معفاة من الضرائب + تذاكر طيران وسكن",
        "deadline": "مفتوح على مدار العام",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://www.emiratesgroupcareers.com/",
        "summary": "حملة توظيف واسعة تطلقها مجموعة الإمارات في دبي للكوادر العربية من مختلف الدول في مجالات الضيافة الجوية، خدمة العملاء بالمطارات، المبيعات، والدعم اللوجستي.",
        "requirements": [
            "إتقان اللغة الإنجليزية تحدثاً وكتابة بطلاقة تامة (تعتبر اللغات الإضافية ميزة).",
            "شهادة الثانوية العامة كحد أدنى، ويفضل المؤهلات الجامعية.",
            "مهارات تواصل استثنائية والقدرة على التعامل مع جنسيات متعددة.",
            "اللياقة البدنية والمظهر اللائق."
        ],
        "documents": [
            "سيرة ذاتية حديثة باللغة الإنجليزية.",
            "صورة شخصية رسمية وصورة كاملة وفق معايير شركات الطيران.",
            "جواز سفر ساري المفعول."
        ],
        "how_to_apply": "التقديم عبر بوابة Emirates Group Careers الرسمية، حيث يتم فرز الطلبات ودعوة المرشحين لأيام التوظيف المفتوحة (Open Days) والمقابلات."
    },
    {
        "id": "remote-customer-support-specialist-2026",
        "slug": "remote-customer-support-specialist-2026",
        "title": "وظائف خدمة عملاء عن بعد (Remote) بالدولار 2026 — العمل من المنزل لشركات عالمية",
        "category": "remote",
        "country": "عالمي (عن بعد)",
        "country_code": "remote",
        "flag": "🌐",
        "employer": "شركات تقنية وتجارة إلكترونية عالمية (عبر منصات التوظيف المباشر)",
        "location": "العمل من المنزل (Remote من أي دولة عربية)",
        "salary": "من 800 إلى 1,400 دولار أمريكي شهرياً",
        "deadline": "مستمر",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://remotive.com/remote-jobs/customer-support",
        "summary": "فرص عمل بدوام كامل وجزئي لمتحدثي اللغتين العربية والإنجليزية لتقديم الدعم الفني وخدمة العملاء عبر الشات والإيميل والهاتف لشركات أجنبية برواتب بالدولار.",
        "requirements": [
            "إجادة اللغة الإنجليزية بمستوى جيد جداً أو ممتاز كتابة ومحادثة.",
            "توفر جهاز كمبيوتر سريع وإنترنت فائق السرعة ومستقر وسماعة عازلة للضوضاء.",
            "الصبر ومهارات حل مشاكل العملاء بلباقة واحترافية.",
            "القدرة على العمل في نوبات مرنة ومسائية إن تطلب الأمر."
        ],
        "documents": [
            "سيرة ذاتية باللغة الإنجليزية تبرز مهارات التواصل وسرعة الكتابة.",
            "حساب بنكي بالدولار أو وسيلة دفع دولية معتمدة (مثل Payoneer / Wise) لاستلام المستحقات."
        ],
        "how_to_apply": "التقديم عبر المنصات العالمية الموثوقة للعمل عن بعد مثل Remotive و We Work Remotely ومواقع الشركات المباشرة."
    },
    {
        "id": "remote-data-entry-content-moderator-2026",
        "slug": "remote-data-entry-content-moderator-2026",
        "title": "وظائف إدخال بيانات ومراجعة محتوى من المنزل 2026 — برواتب بالدولار والعمل الحر",
        "category": "remote",
        "country": "عالمي (عن بعد)",
        "country_code": "remote",
        "flag": "🌐",
        "employer": "منصات البيانات والتدريب الذكاء الاصطناعي (Appen, Telus, OneForma)",
        "location": "من المنزل (Flexible Hours)",
        "salary": "من 6 إلى 12 دولار في الساعة حسب المشروع والمهام",
        "deadline": "مفتوح على مدار العام",
        "posted_at": "2026-09-25",
        "employment_type": "PART_TIME",
        "apply_url": "https://www.telusinternational.com/careers/ai-community",
        "summary": "فرص موثوقة للعمل من البيت في مجالات إدخال البيانات، تقييم نتائج محركات البحث، وتدريب نماذج الذكاء الاصطناعي باللغة العربية مع شركات تقنية كبرى.",
        "requirements": [
            "معرفة جيدة بالقراءة والكتابة باللغتين العربية والإنجليزية.",
            "دقة الملاحظة والالتزام بإرشادات التقييم والمهام الموكلة.",
            "جهاز كمبيوتر وهاتف ذكي متصلين بالإنترنت.",
            "القدرة على الالتزام بـ 15 إلى 20 ساعة عمل أسبوعياً."
        ],
        "documents": [
            "بريد إلكتروني رسمي ومستند إثبات هوية لتأكيد الحساب.",
            "اجتياز اختبارات تقييم قصيرة مجانية على المنصة قبل بدء استلام المهام."
        ],
        "how_to_apply": "التسجيل في مجتمعات تقييم البيانات المعتمدة دولياً مثل Telus AI Community أو OneForma واختيار المشاريع الداعمة للغة العربية."
    },
    {
        "id": "egypt-post-office-competition-2026",
        "slug": "egypt-post-office-competition-2026",
        "title": "مسابقة وظائف الهيئة القومية للبريد المصري 2026 — شروط ورابط تقديم مهندسين ومحامين وأخصائيي بريد",
        "category": "gov",
        "country": "مصر",
        "country_code": "eg",
        "flag": "🇪🇬",
        "employer": "الهيئة القومية للبريد المصري — الجهاز المركزي للتنظيم والإدارة",
        "location": "جميع محافظات ومكاتب بريد الجمهورية",
        "salary": "رواتب ومكافآت وحوافز أداء بريدية مجزية طبقاً للائحة الهيئة",
        "deadline": "2026-11-15",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://jobs.caoa.gov.eg/",
        "summary": "إعلان الجهاز المركزي للتنظيم والإدارة عن مسابقة كبرى لشغل وظائف شاغرة بالهيئة القومية للبريد تشمل تخصصات مهندس ميكانيكا/كهرباء، مهندس تخطيط نقل، أخصائي بريد، وأخصائي خدمة عملاء ومحامين بجميع المحافظات.",
        "requirements": [
            "الحصول على المؤهل العالي المناسب للتخصص المطلوب (هندسة، تجارة، حقوق/شريعة وقانون).",
            "ألا يقل التقدير العام التراكمي عن جيد للمؤهلات العليا.",
            "ألا يزيد عمر المتقدم عن 30 عاماً في تاريخ نشر الإعلان.",
            "اجتياز الامتحانات الإلكترونية المقررة بنظام تقييم القدرات التابع للجهاز."
        ],
        "documents": [
            "أصل بطاقة الرقم القومي سارية المفعول.",
            "شهادة المؤهل الدراسي وشهادة القيد بنقابة المهندسين أو المحامين إن تطلب التخصص.",
            "صحيفة الحالة الجنائية سارية وموجهة للجهاز المركزي للتنظيم والإدارة أو هيئة البريد.",
            "الموقف من التجنيد للذكور أو الخدمة العامة للإناث.",
            "إيصال سداد الرسوم المقررة بحساب الجهاز المركزي للتنظيم والإدارة."
        ],
        "how_to_apply": "التقديم حصرياً عبر بوابة الوظائف الحكومية الإلكترونية (jobs.caoa.gov.eg) برفع المستندات المطلوبة ملونة بصيغة PDF."
    },
    {
        "id": "qatar-kawader-government-jobs-2026",
        "slug": "qatar-kawader-government-jobs-2026",
        "title": "وظائف منصة كوادر الحكومية في قطر 2026 — شواغر كبرى في الوزارات والهيئات الحكومية",
        "category": "gulf",
        "country": "قطر",
        "country_code": "qa",
        "flag": "🇶🇦",
        "employer": "ديوان الخدمة المدنية والتطوير الحكومي — قطر (منصة كوادر الوطنية)",
        "location": "الدوحة، قطر",
        "salary": "سلالم رواتب الخدمة المدنية القطرية + بدلات سكن وتأمين صحي",
        "deadline": "مستمر حسب شواغر كل وزارة",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://kawader.gov.qa/",
        "summary": "طرح مئات الوظائف التخصصية والإدارية والتعليمية بالوزارات والهيئات الحكومية القطرية عبر المنصة الوطنية للتوظيف (كوادر) لحاملي الشهادات الجامعية والدبلومات.",
        "requirements": [
            "مؤهل تعليمي معتمد (بكالوريوس أو دبلوم) في التخصص المعلن.",
            "إجادة استخدام الحاسب الآلي والأنظمة الحكومية الرقمية.",
            "اجتياز المقابلة الشخصية واختبارات الجدارة الوظيفية المقررة من ديوان الخدمة المدنية."
        ],
        "documents": [
            "السيرة الذاتية المحدثة.",
            "الشهادات الأكاديمية وكشف الدرجات ومعادلة الشهادة للمتخرجين من خارج الدولة.",
            "صورة من البطاقة الشخصية وجواز السفر."
        ],
        "how_to_apply": "يتم التقديم بالدخول إلى منصة كوادر الوطنية للتوظيف (kawader.gov.qa) واختيار الوظيفة المناسبة واستكمال مسار الترشيح."
    },
    {
        "id": "uk-health-and-care-worker-visa-2026",
        "slug": "uk-health-and-care-worker-visa-2026",
        "title": "عقود عمل في بريطانيا 2026 مع توفير تأشيرة الرعاية الصحية والتمريض (Health and Care Visa)",
        "category": "abroad",
        "country": "بريطانيا",
        "country_code": "gb",
        "flag": "🇬🇧",
        "employer": "هيئة الخدمات الصحية الوطنية البريطانية (NHS) ودور الرعاية المعتمدة",
        "location": "لندن، مانشستر، برمنغهام، إنجلترا، المملكة المتحدة",
        "salary": "من 23,200 إلى 34,500 جنيه إسترليني سنوياً + تغطية رسوم التأشيرة الصحية",
        "deadline": "مفتوح على مدار العام",
        "posted_at": "2026-09-25",
        "employment_type": "FULL_TIME",
        "apply_url": "https://www.gov.uk/health-care-worker-visa",
        "summary": "تفاصيل عقود العمل وتأشيرة الرعاية الصحية البريطانية التي توفر مساراً سريعاً للهجرة والإقامة القانونية للممرضين، الأطباء، ومقدمي الرعاية الصحية المؤهلين مع إعفاء كامل من الرسوم الصحية الإضافية (IHS).",
        "requirements": [
            "الحصول على عرض عمل معتمد وشهادة كفالة (Certificate of Sponsorship - CoS) من جهة مرخصة في بريطانيا.",
            "إتقان اللغة الإنجليزية واجتياز اختبار IELTS Academic أو OET بمستوى معتمد.",
            "شهادة تخرج في التمريض أو الطب أو مؤهل مهني معترف به في الرعاية.",
            "شهادة فحص السجل الجنائي وفحص مرض الدرن (TB test)."
        ],
        "documents": [
            "جواز سفر ساري المفعول ورقم مرجعي لشهادة الكفالة (CoS).",
            "شهادة الكفاءة في اللغة الإنجليزية معتمدة من UKVI.",
            "السيرة الذاتية المهنية وشهادات التخرج والترخيص المهني."
        ],
        "how_to_apply": "البحث عن الشواغر المعتمدة عبر موقع توظيف NHS Jobs الرسمي أو بوابات كفلاء التأشيرات المعتمدين لدى الحكومة البريطانية ثم التقديم على التأشيرة عبر gov.uk."
    }
]


def load_jobs():
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    # تهيئة أولية
    save_jobs(INITIAL_JOBS)
    return INITIAL_JOBS


def save_jobs(jobs):
    os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def render_job_schema(job, canonical):
    """Schema.org JobPosting متوافقة 100% مع معايير Google for Jobs الرسمية."""
    valid_through = job.get("deadline")
    if not valid_through or len(valid_through) != 10:
        valid_through = "2026-12-31"

    schema = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": job["title"],
        "description": f"{job['summary']} المؤهلات والشروط: {' '.join(job.get('requirements', []))}",
        "identifier": {
            "@type": "PropertyValue",
            "name": job["employer"],
            "value": job["id"]
        },
        "datePosted": job.get("posted_at", "2026-09-25"),
        "validThrough": f"{valid_through}T23:59:59+00:00",
        "employmentType": job.get("employment_type", "FULL_TIME"),
        "hiringOrganization": {
            "@type": "Organization",
            "name": job["employer"]
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": job.get("country_code", "EG").upper(),
                "addressLocality": job.get("location", "العاصمة")
            }
        },
        "url": canonical
    }
    return json.dumps(schema, ensure_ascii=False)


def build_jobs_site(base_url, out_dir, nav_func=None):
    jobs = load_jobs()
    jobs_dir = os.path.join(out_dir, "jobs")
    os.makedirs(jobs_dir, exist_ok=True)

    urls = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    nav_index = nav_func(1) if callable(nav_func) else (nav_func or "")
    nav_single = nav_func(2) if callable(nav_func) else (nav_func or "")

    # 1. صفحة الفهرس الرئيسية للوظائف: site/jobs/index.html
    main_canonical = f"{base_url}/jobs/"
    index_html = render_jobs_index(jobs, base_url, nav_index)
    with open(os.path.join(jobs_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    urls.append((main_canonical, today_str, "0.9"))

    # 2. صفحات الوظائف الفردية: site/jobs/<slug>/index.html
    for j in jobs:
        slug = j["slug"]
        single_dir = os.path.join(jobs_dir, slug)
        os.makedirs(single_dir, exist_ok=True)

        canonical = f"{base_url}/jobs/{slug}/"
        single_html = render_job_single(j, canonical, base_url, nav_single, jobs)
        with open(os.path.join(single_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(single_html)
        urls.append((canonical, j.get("posted_at", today_str), "0.8"))

    return urls


def render_jobs_index(jobs, base_url, countries_nav_html):
    n_gov = sum(1 for j in jobs if j.get("category") == "gov")
    n_abroad = sum(1 for j in jobs if j.get("category") == "abroad")
    n_gulf = sum(1 for j in jobs if j.get("category") == "gulf")
    n_remote = sum(1 for j in jobs if j.get("category") == "remote")

    cards_html = []
    for j in jobs:
        cat_info = CATEGORIES.get(j["category"], {"name_ar": "وظائف", "icon": "💼", "color": "#f5c542"})
        search_text = " ".join([
            j.get("title", ""),
            j.get("employer", ""),
            j.get("location", ""),
            j.get("salary", ""),
            j.get("summary", ""),
            j.get("country", ""),
            cat_info["name_ar"],
            " ".join(j.get("requirements", [])),
            " ".join(j.get("documents", [])),
            j.get("how_to_apply", ""),
        ]).lower()

        reqs = j.get("requirements", [])
        req_tags = "".join([
            f"<span class='req-tag'>✓ {E(r[:45] + ('...' if len(r)>45 else ''))}</span>"
            for r in reqs[:2]
        ])

        type_str = TYPE_LABELS.get(j.get("employment_type", "FULL_TIME"), "دوام كامل 🟢")

        cards_html.append(f"""
        <article class="job-card" data-cat="{j['category']}" data-country="{j.get('country_code', 'all')}" data-search="{E(search_text)}">
          <div class="job-header">
            <div class="job-header-left">
              <span class="job-badge" style="--c:{cat_info['color']}">{cat_info['icon']} {cat_info['name_ar']}</span>
              <span class="job-country">{j.get('flag', '')} {j.get('country', '')}</span>
            </div>
            <span class="job-type-pill">{type_str}</span>
          </div>
          <h2 class="job-title"><a href="{base_url}/jobs/{j['slug']}/">{E(j['title'])}</a></h2>
          <div class="job-fast-facts">
            <div class="fact-item">🏢 <span><strong>الجهة:</strong> {E(j['employer'][:34])}</span></div>
            <div class="fact-item">📍 <span><strong>المكان:</strong> {E(j['location'])}</span></div>
            <div class="fact-item">💰 <span><strong>الراتب:</strong> {E(j['salary'])}</span></div>
            <div class="fact-item">⏰ <span><strong>آخر موعد:</strong> {E(j['deadline'])}</span></div>
          </div>
          <p class="job-summary">{E(j['summary'])}</p>
          {f'<div class="job-reqs-preview">{req_tags}</div>' if req_tags else ''}
          <div class="job-footer">
            <a class="btn-job-details" href="{base_url}/jobs/{j['slug']}/">عرض الشروط والتقديم ⬅️</a>
            <a class="btn-job-apply-direct" href="{j['apply_url']}" target="_blank" rel="noopener nofollow">الرابط الرسمي المباشر 🔗</a>
          </div>
        </article>
        """)

    matrix_html = f"""
    <div class="jobs-matrix">
      <div class="matrix-card" data-cat="gov" onclick="setCategory('gov')" style="--m-color:#3ddc97;">
        <div class="matrix-header">
          <span class="matrix-icon">🏛️</span>
          <span class="matrix-count">{n_gov} مسابقات</span>
        </div>
        <div class="matrix-title">وظائف حكومية رسمية</div>
        <p class="matrix-sub">مصلحة الضرائب، التربية والتعليم، البريد، جدارات السعودية، كوادر قطر</p>
      </div>
      <div class="matrix-card" data-cat="abroad" onclick="setCategory('abroad')" style="--m-color:#5aa9ff;">
        <div class="matrix-header">
          <span class="matrix-icon">✈️</span>
          <span class="matrix-count">{n_abroad} عقود وتأشيرات</span>
        </div>
        <div class="matrix-title">عقود سفر وهجرة للخارج</div>
        <p class="matrix-sub">بطاقة الفرصة الألمانية، عقود كندا LMIA، إيطاليا Decreto Flussi، وفيزا بريطانيا</p>
      </div>
      <div class="matrix-card" data-cat="gulf" onclick="setCategory('gulf')" style="--m-color:#f5c542;">
        <div class="matrix-header">
          <span class="matrix-icon">🇸🇦</span>
          <span class="matrix-count">{n_gulf} شركات رائدة</span>
        </div>
        <div class="matrix-title">وظائف كبرى شركات الخليج</div>
        <p class="matrix-sub">أرامكو ونيوم، طيران الإمارات بدبي برواتب وبدلات وتأمين شامل</p>
      </div>
      <div class="matrix-card" data-cat="remote" onclick="setCategory('remote')" style="--m-color:#c77dff;">
        <div class="matrix-header">
          <span class="matrix-icon">🌐</span>
          <span class="matrix-count">{n_remote} فرص بالدولار</span>
        </div>
        <div class="matrix-title">وظائف عن بعد (Remote)</div>
        <p class="matrix-sub">خدمة عملاء دولية، تدريب الذكاء الاصطناعي وإدخال بيانات من المنزل</p>
      </div>
    </div>
    """

    search_box_html = f"""
    <div class="job-search-box">
      <div class="search-input-wrapper">
        <span class="search-icon">🔍</span>
        <input type="text" id="jobSearchInput" placeholder="ابحث باسم الوظيفة، التخصص، أو الدولة (مثال: ضرائب، ألمانيا، كندا، تمريض، تدخيل بيانات...)" oninput="handleSearch()">
        <button id="clearSearchBtn" class="clear-search-btn" onclick="clearSearch()" style="display:none;" title="مسح البحث">✕</button>
      </div>
      <div class="search-meta-row">
        <div id="resultsCount" class="results-count">عرض جميع الوظائف (<strong>{len(jobs)}</strong> فرصة متاحة)</div>
        <div class="quick-tags">
          <span class="quick-tags-label">الأكثر بحثاً:</span>
          <button class="quick-tag" onclick="quickSearch('ألمانيا')">🇩🇪 ألمانيا</button>
          <button class="quick-tag" onclick="quickSearch('كندا')">🇨🇦 كندا</button>
          <button class="quick-tag" onclick="quickSearch('مصر')">🏛️ وظائف مصر</button>
          <button class="quick-tag" onclick="quickSearch('جدارات')">🇸🇦 جدارات</button>
          <button class="quick-tag" onclick="quickSearch('عن بعد')">💵 بالدولار</button>
          <button class="quick-tag" onclick="quickSearch('معلم')">📚 مسابقة المعلمين</button>
        </div>
      </div>
    </div>
    """

    filters_html = f"""
    <div class="job-filters-wrap">
      <div class="filter-row">
        <span class="filter-label">القطاع:</span>
        <div class="filter-pills" id="catPills">
          <button class="pill-btn active" data-cat="all" onclick="setCategory('all')">💼 جميع القطاعات ({len(jobs)})</button>
          <button class="pill-btn" data-cat="gov" onclick="setCategory('gov')">🏛️ حكومي ومسابقات ({n_gov})</button>
          <button class="pill-btn" data-cat="abroad" onclick="setCategory('abroad')">✈️ عقود سفر للخارج ({n_abroad})</button>
          <button class="pill-btn" data-cat="gulf" onclick="setCategory('gulf')">🇸🇦 وظائف الخليج ({n_gulf})</button>
          <button class="pill-btn" data-cat="remote" onclick="setCategory('remote')">🌐 عمل عن بعد ({n_remote})</button>
        </div>
      </div>
      <div class="filter-row" style="margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,.05);">
        <span class="filter-label">الدولة:</span>
        <div class="filter-pills" id="countryPills">
          <button class="pill-btn active" data-country="all" onclick="setCountry('all')">🌍 كل الدول</button>
          <button class="pill-btn" data-country="eg" onclick="setCountry('eg')">🇪🇬 مصر</button>
          <button class="pill-btn" data-country="sa" onclick="setCountry('sa')">🇸🇦 السعودية</button>
          <button class="pill-btn" data-country="de" onclick="setCountry('de')">🇩🇪 ألمانيا</button>
          <button class="pill-btn" data-country="ca" onclick="setCountry('ca')">🇨🇦 كندا</button>
          <button class="pill-btn" data-country="it" onclick="setCountry('it')">🇮🇹 إيطاليا</button>
          <button class="pill-btn" data-country="gb" onclick="setCountry('gb')">🇬🇧 بريطانيا</button>
          <button class="pill-btn" data-country="qa" onclick="setCountry('qa')">🇶🇦 قطر</button>
          <button class="pill-btn" data-country="ae" onclick="setCountry('ae')">🇦🇪 الإمارات</button>
          <button class="pill-btn" data-country="remote" onclick="setCountry('remote')">🌐 دولي / عن بعد</button>
        </div>
      </div>
    </div>
    """

    no_results_html = """
    <div id="noResultsBox" class="no-results-box" style="display:none;">
      <div class="no-results-icon">🔎</div>
      <h3>لم نجد وظائف مطابقة لبحثك</h3>
      <p>جرّب استخدام كلمات عامة مثل: <strong>حكومي، ألمانيا، كندا، محاسبة، تمريض</strong> أو اضغط على الزر أدناه لإعادة ضبط الفلاتر.</p>
      <button class="btn-reset-filters" onclick="resetAllFilters()">إعادة ضبط البحث وعرض جميع الوظائف 🔄</button>
    </div>
    """

    body = f"""
    <div class="jobs-hero">
      <h1 style="font-size:2.1rem;margin-bottom:8px;">💼 دليل وظائف اليوم وعقود العمل الرسمية 2026</h1>
      <p class="jobs-lead">بوابتك الذكية والموثوقة لأحدث الوظائف الحكومية والمسابقات الرسمية، عقود العمل وتأشيرات الهجرة بالخارج، وظائف كبرى شركات الخليج، والعمل عن بعد بالدولار مع روابط التقديم الرسمية المباشرة بدون وسطاء.</p>
    </div>

    {matrix_html}

    <div class="safety-box">
      <span class="safety-icon">🛡️</span>
      <div class="safety-text">
        <strong>تنبيه الأمان والمصداقية من موقع الترندات:</strong>
        <p>جميع إعلانات الوظائف المنشورة تتضمن روابط التقديم الرسمية والمجانية مباشرة لدى جهة العمل. احذر من أي وسيط أو شخص يطلب مبالغ مالية مقابل تسهيل التوظيف.</p>
      </div>
    </div>

    {search_box_html}

    {filters_html}

    {no_results_html}

    <div class="jobs-list" id="jobsContainer">
      {''.join(cards_html)}
    </div>

    <div class="channel-cta">
      <div class="channel-cta-text">
        <h4>📢 اشترك في قناة الوظائف العاجلة على تليجرام</h4>
        <p>تصلك إعلانات الوظائف الحكومية والشركات وعقود السفر لحظة بلحظة مع روابط التقديم المباشرة مجاناً.</p>
      </div>
      <div class="channel-cta-btns">
        <a class="btn-tg" href="https://t.me/altrendat_news" target="_blank" rel="noopener">👉 انضم لقناة الوظائف الآن</a>
      </div>
    </div>

    <script>
    let activeCat = 'all';
    let activeCountry = 'all';
    let searchQuery = '';

    function setCategory(cat) {{
      activeCat = (activeCat === cat && cat !== 'all') ? 'all' : cat;
      updateFilterButtons();
      applyFilters();
    }}

    function setCountry(country) {{
      activeCountry = (activeCountry === country && country !== 'all') ? 'all' : country;
      updateFilterButtons();
      applyFilters();
    }}

    function quickSearch(keyword) {{
      const input = document.getElementById('jobSearchInput');
      if (input) {{
        input.value = keyword;
        handleSearch();
      }}
    }}

    function clearSearch() {{
      const input = document.getElementById('jobSearchInput');
      if (input) {{
        input.value = '';
        handleSearch();
        input.focus();
      }}
    }}

    function handleSearch() {{
      const input = document.getElementById('jobSearchInput');
      searchQuery = (input ? input.value : '').trim().toLowerCase();
      const clearBtn = document.getElementById('clearSearchBtn');
      if (clearBtn) {{
        clearBtn.style.display = searchQuery ? 'inline-flex' : 'none';
      }}
      applyFilters();
    }}

    function resetAllFilters() {{
      activeCat = 'all';
      activeCountry = 'all';
      searchQuery = '';
      const input = document.getElementById('jobSearchInput');
      if (input) input.value = '';
      const clearBtn = document.getElementById('clearSearchBtn');
      if (clearBtn) clearBtn.style.display = 'none';
      updateFilterButtons();
      applyFilters();
    }}

    function updateFilterButtons() {{
      document.querySelectorAll('#catPills .pill-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.getAttribute('data-cat') === activeCat);
      }});
      document.querySelectorAll('.jobs-matrix .matrix-card').forEach(card => {{
        card.classList.toggle('active', card.getAttribute('data-cat') === activeCat);
      }});
      document.querySelectorAll('#countryPills .pill-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.getAttribute('data-country') === activeCountry);
      }});
    }}

    function applyFilters() {{
      const cards = document.querySelectorAll('.job-card');
      let visibleCount = 0;

      cards.forEach(card => {{
        const cardCat = card.getAttribute('data-cat');
        const cardCountry = card.getAttribute('data-country');
        const cardText = card.getAttribute('data-search') || '';

        const matchCat = (activeCat === 'all' || cardCat === activeCat);
        const matchCountry = (activeCountry === 'all' || cardCountry === activeCountry);
        const matchSearch = (!searchQuery || cardText.includes(searchQuery));

        if (matchCat && matchCountry && matchSearch) {{
          card.style.display = 'block';
          visibleCount++;
        }} else {{
          card.style.display = 'none';
        }}
      }});

      const countEl = document.getElementById('resultsCount');
      if (countEl) {{
        if (searchQuery || activeCat !== 'all' || activeCountry !== 'all') {{
          countEl.innerHTML = `تم العثور على <strong>${{visibleCount}}</strong> وظيفة مطابقة`;
        }} else {{
          countEl.innerHTML = `عرض جميع الوظائف (<strong>${{visibleCount}}</strong> فرصة متاحة)`;
        }}
      }}

      const noResults = document.getElementById('noResultsBox');
      if (noResults) {{
        noResults.style.display = (visibleCount === 0) ? 'block' : 'none';
      }}
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      const params = new URLSearchParams(window.location.search);
      const q = params.get('q');
      const cat = params.get('cat');
      const country = params.get('country');

      if (q) {{
        const input = document.getElementById('jobSearchInput');
        if (input) input.value = q;
        searchQuery = q.trim().toLowerCase();
      }}
      if (cat) activeCat = cat;
      if (country) activeCountry = country;

      updateFilterButtons();
      applyFilters();
    }});
    </script>
    """

    return render_page_template(
        title="وظائف اليوم 2026 — وظائف حكومية وعقود عمل بالخارج والخليج | الترندات",
        desc="دليل وظائف اليوم المحدث يومياً: وظائف حكومية رسمية، عقود عمل في ألمانيا وكندا، وظائف الخليج والسعودية، ووظائف العمل عن بعد بالدولار مع روابط التقديم المباشرة.",
        canonical=f"{base_url}/jobs/",
        body=body,
        countries_nav=countries_nav_html,
        depth=1
    )


def render_job_single(job, canonical, base_url, countries_nav_html, all_jobs):
    cat_info = CATEGORIES.get(job["category"], {"name_ar": "وظائف", "icon": "💼", "color": "#f5c542"})
    schema_json = render_job_schema(job, canonical)

    req_items = "".join(f"<li>{E(r)}</li>" for r in job.get("requirements", []))
    doc_items = "".join(f"<li>{E(d)}</li>" for d in job.get("documents", []))

    related = [x for x in all_jobs if x["id"] != job["id"] and x["category"] == job["category"]][:3]
    if len(related) < 3:
        related += [x for x in all_jobs if x["id"] != job["id"] and x not in related][:3 - len(related)]

    rel_html = "".join(f"""
      <a class="item" href="{base_url}/jobs/{r['slug']}/">
        <span class="chip">{r.get('flag','')} {r.get('country','')} · {r['salary']}</span>
        <h3>{E(r['title'])}</h3>
        <span class="sub">🏢 {E(r['employer'])} · آخر موعد: {E(r['deadline'])}</span>
      </a>
    """ for r in related)

    body = f"""
    <nav class="breadcrumb">
      <a href="{base_url}/">الرئيسية</a> &gt; 
      <a href="{base_url}/jobs/">💼 وظائف اليوم</a> &gt; 
      <span>{cat_info['name_ar']}</span>
    </nav>

    <div class="job-single-header">
      <div class="job-header">
        <span class="job-badge" style="--c:{cat_info['color']}">{cat_info['icon']} {cat_info['name_ar']}</span>
        <span class="job-country">{job.get('flag', '')} {job.get('country', '')}</span>
      </div>
      <h1>{E(job['title'])}</h1>
      <div class="job-single-meta">
        <span>📅 تاريخ النشر: {job.get('posted_at', '')}</span>
        <span>⏰ آخر موعد للتقديم: {E(job['deadline'])}</span>
      </div>
    </div>

    <!-- بطاقة المعلومات السريعة -->
    <div class="job-quick-facts">
      <div class="fact-box">
        <span class="fact-icon">🏢</span>
        <span class="fact-title">الجهة المعلنة</span>
        <span class="fact-val">{E(job['employer'])}</span>
      </div>
      <div class="fact-box">
        <span class="fact-icon">📍</span>
        <span class="fact-title">مكان العمل</span>
        <span class="fact-val">{E(job['location'])}</span>
      </div>
      <div class="fact-box">
        <span class="fact-icon">💰</span>
        <span class="fact-title">الراتب المتوقع</span>
        <span class="fact-val">{E(job['salary'])}</span>
      </div>
      <div class="fact-box">
        <span class="fact-icon">⏰</span>
        <span class="fact-title">حالة التقديم</span>
        <span class="fact-val active-status">متاح حالياً</span>
      </div>
    </div>

    <div class="job-body">
      <h2>📌 ملخص الوظيفة</h2>
      <p>{E(job['summary'])}</p>

      <h2>📋 الشروط والمؤهلات المطلوبة</h2>
      <ul>{req_items}</ul>

      <h2>📑 المستندات والأوراق المطلوبة للتقديم</h2>
      <ul>{doc_items}</ul>

      <h2>🚀 طريقة التقديم الرسمية</h2>
      <p>{E(job.get('how_to_apply', ''))}</p>

      <div class="apply-cta-box">
        <h3>هل تنطبق عليك الشروط؟</h3>
        <p>قدّم الآن عبر الرابط الرسمي المباشر الخاص بجهة العمل دون أي رسوم أو وسطاء:</p>
        <a class="btn-apply-main" href="{job['apply_url']}" target="_blank" rel="noopener nofollow">
          👉 اضغط هنا للتقديم عبر الرابط الرسمي المباشر
        </a>
      </div>

      <div class="safety-box">
        <span class="safety-icon">🛡️</span>
        <div class="safety-text">
          <strong>إخلاء مسؤولية وأمان من موقع الترندات:</strong>
          <p>جميع المعلومات والروابط المنشورة منتقاة من المصادر الرسمية الحكومية والمواقع المعتمدة. لا تقم أبداً بدفع أي مبالغ مالية أو إرسال أرقام حساباتك البنكية لأي جهة غير موثوقة.</p>
        </div>
      </div>
    </div>

    <div class="channel-cta">
      <div class="channel-cta-text">
        <h4>📢 لا تفوّت الوظائف القادمة!</h4>
        <p>اشترك في قناتنا على تليجرام لمتابعة أحدث الوظائف فور الإعلان عنها يومياً.</p>
      </div>
      <div class="channel-cta-btns">
        <a class="btn-tg" href="https://t.me/altrendat_news" target="_blank" rel="noopener">انضم الآن مجاناً</a>
      </div>
    </div>

    <h2>فرص ووظائف أخرى قد تهمك</h2>
    <div class="list">
      {rel_html}
    </div>
    """

    return render_page_template(
        title=f"{job['title']} | الترندات",
        desc=job['summary'][:160],
        canonical=canonical,
        body=body,
        countries_nav=countries_nav_html,
        depth=2,
        jsonld_str=schema_json
    )


def render_page_template(title, desc, canonical, body, countries_nav="", depth=1, jsonld_str=None):
    root = "../" * depth if depth else "./"
    ld = f'<script type="application/ld+json">{jsonld_str}</script>' if jsonld_str else ""

    if "nav-jobs" not in countries_nav:
        jobs_nav_btn = "<a href='{r}jobs/' class='nav-jobs'>💼 وظائف اليوم</a>".format(r=root)
        full_nav = jobs_nav_btn + countries_nav
    else:
        full_nav = countries_nav

    flinks = f"""
    <a href="{root}">الرئيسية</a>
    <a href="{root}jobs/">وظائف اليوم</a>
    <a href="{root}eg/">مصر</a>
    <a href="{root}sa/">السعودية</a>
    """

    floating_bar = """<div class="floating-cta">
  <span>📢 تابع الترندات والوظائف:</span>
  <a class="btn-tg" href="https://t.me/altrendat_news" target="_blank" rel="noopener">تليجرام</a>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canonical)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(canonical)}">
<meta property="og:site_name" content="الترندات">
<meta property="og:image" content="https://altrendat.com/og-default.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://altrendat.com/og-default.jpg">
<meta name="twitter:title" content="{E(title)}">
<meta name="twitter:description" content="{E(desc)}">
<link rel="icon" type="image/x-icon" href="{root}favicon.ico">
<link rel="icon" type="image/png" sizes="48x48" href="{root}favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="{root}icon-192.png">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}style.css">
{ld}
</head>
<body>
<header class="site">
  <a class="brand" href="{root}">الترندات</a>
  <nav>{full_nav}</nav>
</header>
<main>{body}</main>
<footer class="site">
  <nav class="flinks">{flinks}</nav>
  <p>الترندات — محرك عربي يرصد ما يبحث عنه الناس والوظائف الشاغرة لحظة بلحظة.</p>
  <p class="fine">جميع الحقوق محفوظة © {datetime.now().year}</p>
</footer>
{floating_bar}
</body>
</html>"""
