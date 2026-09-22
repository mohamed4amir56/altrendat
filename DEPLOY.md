# النشر — خطوة بخطوة

الموقع صفحات ثابتة، فينشر على أي استضافة مجانية بلا خادم ولا بناء.

## 1. ارفع المستودع إلى GitHub

اجعله **عامًا** — الكرون كل 20 دقيقة يتجاوز الدقائق المجانية في
المستودعات الخاصة. لا أسرار في الكود؛ المفتاح في Secrets.

```
gh repo create altrendat --public --source=. --push
```

## 2. أضف المفتاح إلى المستودع

Settings ← Secrets and variables ← Actions ← New repository secret

    ANTHROPIC_API_KEY = sk-ant-...

## 3. Cloudflare Pages

dash.cloudflare.com ← Workers & Pages ← Create ← Pages ←
Connect to Git ← اختر المستودع.

| الحقل | القيمة |
|---|---|
| Framework preset | None |
| Build command | *(اتركه فارغًا)* |
| Build output directory | `site` |

الموقع يصير على `https://<اسم-المشروع>.pages.dev` خلال دقيقة،
**قبل حجز أي نطاق**.

## 4. بعد حجز النطاق

في Cloudflare Pages ← Custom domains ← Set up a domain.

ثم في GitHub: Settings ← Secrets and variables ← Actions ←
Variables ← New variable:

    SITE_BASE = https://altrendat.com

الكرون يقرأها ويبني عليها تلقائيًا. بدونها يبني على عنوان
pages.dev المجاني.

## 5. Search Console

search.google.com/search-console ← أضف الموقع ← أرسل
`https://<نطاقك>/sitemap.xml`

## 6. AdSense — لاحقًا

**لا تتقدّم قبل 4 إلى 8 أسابيع** من المحتوى والزيارات الحقيقية.
رفض واحد يجعل القبول لاحقًا أصعب. الصفحات الثابتة المطلوبة
(من نحن، الخصوصية، اتصل بنا) جاهزة في التذييل.
