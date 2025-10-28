# 📚 سیستم مستندسازی قوانین - دادرس

ساختار یکپارچه و استاندارد برای ذخیره و مدیریت قوانین و مقررات به صورت JSON.

## 📂 ساختار فولدرها

```
laws_structured/
├── index.json                      # فهرست کلی تمام قوانین
├── README.md                       # این فایل
├── civil_law/                      # قانون مدنی
│   ├── metadata.json              # اطلاعات کلی قانون مدنی
│   ├── properties/                # بخش اموال و مالکیت
│   │   └── articles_001-010.json # مواد 1 تا 10
│   └── transactions/              # بخش معاملات و عقود
│       └── articles_183-184.json # مواد 183 تا 184
└── commercial_law/                # قانون تجارت (آماده توسعه)
    └── metadata.json
```

## 📋 ساختار فایل‌ها

### 1. index.json (فهرست اصلی)

فایل اصلی که شامل اطلاعات کلی تمام قوانین، دسته‌بندی‌ها و آمار است.

```json
{
  "version": "1.0.0",
  "total_laws": 1,
  "laws": [...],
  "categories": [...],
  "statistics": {...}
}
```

### 2. metadata.json (اطلاعات هر قانون)

اطلاعات جامع درباره یک قانون خاص:

```json
{
  "code": "civil_law",
  "title": "قانون مدنی",
  "date_approved": "1307/05/08",
  "sections": [...],
  "tags": [...]
}
```

### 3. articles_XXX-YYY.json (مواد قانونی)

هر فایل شامل 10-20 ماده قانونی با ساختار کامل:

```json
[
  {
    "article_number": 183,
    "title": "تعریف عقد",
    "text": "متن کامل ماده...",
    "explanation": "توضیح ساده و کاربردی",
    "examples": ["مثال 1", "مثال 2"],
    "key_points": ["نکته 1", "نکته 2"],
    "tags": ["تگ1", "تگ2"],
    "related_articles": [184, 185],
    "category": "معاملات",
    "subcategory": "عقود"
  }
]
```

## 🔍 فیلدهای استاندارد هر ماده

| فیلد | نوع | توضیح | الزامی |
|------|-----|--------|--------|
| `article_number` | عدد | شماره ماده | ✅ |
| `title` | متن | عنوان کوتاه | ✅ |
| `text` | متن | متن کامل قانون | ✅ |
| `explanation` | متن | توضیح ساده | ✅ |
| `examples` | آرایه | مثال‌های کاربردی | ⭕ |
| `key_points` | آرایه | نکات کلیدی | ⭕ |
| `tags` | آرایه | برچسب‌ها | ✅ |
| `related_articles` | آرایه اعداد | مواد مرتبط | ⭕ |
| `references` | آرایه | منابع | ⭕ |
| `category` | متن | دسته اصلی | ✅ |
| `subcategory` | متن | زیردسته | ⭕ |
| `status` | متن | وضعیت (active/deprecated) | ✅ |
| `last_modified` | تاریخ | آخرین تغییر | ⭕ |

## 🚀 نحوه استفاده

### 1. خواندن فهرست کلی

```python
import json

with open('data/laws_structured/index.json', 'r', encoding='utf-8') as f:
    index = json.load(f)
    
print(f"تعداد قوانین: {index['total_laws']}")
for law in index['laws']:
    print(f"- {law['title']}")
```

### 2. خواندن یک قانون خاص

```python
with open('data/laws_structured/civil_law/metadata.json', 'r', encoding='utf-8') as f:
    civil_law = json.load(f)
    
print(f"عنوان: {civil_law['title']}")
print(f"تاریخ تصویب: {civil_law['date_approved']}")
```

### 3. جستجوی مواد

```python
import glob

# خواندن تمام مواد بخش معاملات
articles = []
for file_path in glob.glob('data/laws_structured/civil_law/transactions/*.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        articles.extend(json.load(f))

# جستجو براساس تگ
def search_by_tag(articles, tag):
    return [a for a in articles if tag in a.get('tags', [])]

results = search_by_tag(articles, 'عقد')
print(f"یافت شد: {len(results)} ماده")
```

### 4. RAG و LLM Integration

```python
def prepare_context_for_llm(article):
    """آماده‌سازی متن برای مدل زبانی"""
    context = f"""
    ماده {article['article_number']}: {article['title']}
    
    متن قانون:
    {article['text']}
    
    توضیح:
    {article['explanation']}
    
    مثال‌ها:
    {chr(10).join('- ' + ex for ex in article['examples'])}
    
    نکات کلیدی:
    {chr(10).join('• ' + kp for kp in article['key_points'])}
    """
    return context.strip()
```

## 📊 آمار فعلی

- **تعداد قوانین**: 1 (قانون مدنی)
- **تعداد بخش‌ها**: 2 (اموال، معاملات)
- **تعداد مواد**: 4 (نمونه)
- **دسته‌بندی‌ها**: 4 (مدنی، تجاری، کیفری، خانواده)

## 🔄 توسعه آینده

- [ ] اضافه کردن تمام مواد قانون مدنی (1335 ماده)
- [ ] افزودن قانون تجارت
- [ ] افزودن قانون مجازات اسلامی
- [ ] ایجاد API برای جستجو
- [ ] ایجاد سیستم Embedding برای RAG
- [ ] اضافه کردن رأی‌های وحدت رویه

## 📝 نحوه افزودن مواد جدید

1. فایل JSON جدید در پوشه مناسب بسازید
2. ساختار استاندارد را رعایت کنید
3. فایل `index.json` را به‌روزرسانی کنید
4. فایل `metadata.json` قانون را به‌روزرسانی کنید

## 🤝 مشارکت

برای اضافه کردن قوانین جدید یا اصلاح موارد موجود:

1. ساختار JSON را رعایت کنید
2. تمام فیلدهای الزامی را پر کنید
3. مثال‌ها و توضیحات واضح بنویسید
4. تگ‌های مناسب اضافه کنید

## 📞 پشتیبانی

برای سوالات و پیشنهادات با تیم دادرس تماس بگیرید.

---

**نسخه**: 1.0.0  
**آخرین به‌روزرسانی**: 1404/08/06  
**وضعیت**: فعال ✅

