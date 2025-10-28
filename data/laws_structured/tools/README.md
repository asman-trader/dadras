# 🛠️ ابزارهای مدیریت قوانین

مجموعه ابزارهای قدرتمند برای پارس، تبدیل و مدیریت قوانین

---

## 📦 فایل‌ها

| فایل | توضیح |
|------|-------|
| `law_parser.py` | پارسر هوشمند TXT به JSON |
| `batch_processor.py` | پردازش دسته‌ای چند فایل |
| `law_cli.py` | ابزار خط فرمان (CLI) |
| `DATA_COLLECTION_GUIDE.md` | راهنمای جمع‌آوری منابع |
| `README.md` | این فایل |

---

## 🚀 شروع سریع

### نصب Requirements

```bash
pip install -r requirements.txt
```

اگر فایل requirements وجود ندارد:

```bash
pip install requests beautifulsoup4 pdfplumber
```

### استفاده سریع

```bash
# پارس یک فایل
python law_cli.py parse input.txt civil_law معاملات output/

# پردازش خودکار تمام فایل‌ها
python law_cli.py batch --auto

# جستجو
python law_cli.py search "عقد"

# لیست قوانین
python law_cli.py list

# آمار
python law_cli.py stats
```

---

## 📖 راهنمای استفاده

### 1️⃣ law_parser.py - پارسر اصلی

#### استفاده برنامه‌نویسی:

```python
from law_parser import LawParser

parser = LawParser()

# پارس یک فایل
articles = parser.parse_file(
    file_path='data/laws/قانون-مدنی.txt',
    law_code='civil_law',
    category='مدنی'
)

print(f"تعداد مواد: {len(articles)}")

# ذخیره نتیجه
parser.save_to_json('output.json', articles)

# پارس و ذخیره با chunk
parser.parse_and_save(
    input_file='input.txt',
    output_dir='output/',
    law_code='civil_law',
    category='معاملات',
    chunk_size=20
)
```

#### قابلیت‌ها:

- ✅ تشخیص خودکار شماره مواد
- ✅ استخراج عنوان، متن، توضیح
- ✅ پردازش مثال‌ها و نکات کلیدی
- ✅ استخراج و نرمال‌سازی تگ‌ها
- ✅ تولید تگ خودکار براساس محتوا
- ✅ پشتیبانی از encoding های مختلف
- ✅ تقسیم به chunk های قابل مدیریت

---

### 2️⃣ batch_processor.py - پردازش دسته‌ای

#### استفاده CLI:

```bash
# کشف و پردازش خودکار
python batch_processor.py --auto

# استفاده از فایل تنظیمات
python batch_processor.py --config config.json

# ایجاد قالب تنظیمات
python batch_processor.py --template
```

#### استفاده برنامه‌نویسی:

```python
from batch_processor import BatchProcessor

processor = BatchProcessor(
    base_input_dir='data/laws',
    base_output_dir='data/laws_structured'
)

# پردازش خودکار
processor.process_all()

# پردازش با config
processor.process_all('my_config.json')
```

#### فرمت فایل Config:

```json
[
  {
    "input": "data/laws/قانون-مدنی.txt",
    "law_code": "civil_law",
    "category": "مدنی",
    "output_section": "general",
    "chunk_size": 20
  }
]
```

---

### 3️⃣ law_cli.py - ابزار خط فرمان

#### دستورات اصلی:

##### Parse - پارس یک فایل

```bash
python law_cli.py parse <input> <law_code> <category> <output>

# مثال:
python law_cli.py parse ../../laws/moamlat.txt civil_law معاملات ../../laws_structured/civil_law/transactions
```

##### Batch - پردازش دسته‌ای

```bash
# کشف خودکار
python law_cli.py batch --auto

# با فایل config
python law_cli.py batch --config config.json
```

##### Search - جستجو

```bash
python law_cli.py search "عقد"
python law_cli.py search "مالکیت" --law civil_law --limit 5
```

##### List - لیست قوانین

```bash
python law_cli.py list
```

##### Stats - آمار

```bash
python law_cli.py stats
```

##### Validate - اعتبارسنجی

```bash
python law_cli.py validate
```

##### Export - صادرات

```bash
python law_cli.py export civil_law output.json
python law_cli.py export civil_law output.txt --format txt
```

##### Create - ایجاد قانون جدید

```bash
python law_cli.py create criminal_law "قانون مجازات اسلامی"
```

---

## 🔧 تنظیمات پیشرفته

### Custom Parser

```python
from law_parser import LawParser

class MyParser(LawParser):
    def _extract_article_number(self, line):
        # منطق سفارشی
        return super()._extract_article_number(line)

parser = MyParser()
```

### Parallel Processing

```python
from batch_processor import BatchProcessor
from concurrent.futures import ThreadPoolExecutor

processor = BatchProcessor()

# تنظیم تعداد workers
with ThreadPoolExecutor(max_workers=8) as executor:
    # پردازش
    pass
```

---

## 📊 مثال‌های کاربردی

### مثال 1: پارس سریع

```python
from law_parser import LawParser

parser = LawParser()
articles = parser.parse_file('law.txt', 'my_law', 'general')

for article in articles:
    print(f"ماده {article['article_number']}: {article['title']}")
```

### مثال 2: پردازش چند فایل

```python
from batch_processor import BatchProcessor

config = [
    {
        "input": "law1.txt",
        "law_code": "law1",
        "category": "cat1",
        "output_section": "sec1"
    },
    {
        "input": "law2.txt",
        "law_code": "law2",
        "category": "cat2",
        "output_section": "sec2"
    }
]

processor = BatchProcessor()
processor.process_all(config)
```

### مثال 3: جستجو و فیلتر

```python
from law_cli import LawCLI

cli = LawCLI()
cli.search("عقد", law_code="civil_law", limit=10)
```

---

## 🐛 عیب‌یابی

### مشکل: پارسر مواد را تشخیص نمی‌دهد

**علت**: فرمت شماره‌گذاری نامعتبر

**راه‌حل**:
```python
# اضافه کردن الگوی جدید به patterns
parser.patterns['article_number'].append(r'شماره[\s\u200c]*(\d+)')
```

### مشکل: خطای Encoding

**علت**: فایل با encoding نادرست

**راه‌حل**:
```bash
# تبدیل encoding
iconv -f WINDOWS-1256 -t UTF-8 input.txt > output.txt
```

### مشکل: JSON نامعتبر

**علت**: کاراکترهای خاص در متن

**راه‌حل**:
```python
# اضافه کردن escape در _clean_text
text = text.replace('"', '\\"')
```

---

## 🧪 تست

### اجرای تست‌ها

```bash
python -m pytest tests/
```

### تست دستی

```bash
# تست پارسر
python law_parser.py

# تست batch processor
python batch_processor.py --template

# تست CLI
python law_cli.py --help
```

---

## 📈 بهینه‌سازی

### نکات بهبود سرعت:

1. **استفاده از پردازش موازی**
```python
processor = BatchProcessor()
processor.process_all()  # از ThreadPool استفاده می‌کند
```

2. **کاهش اندازه chunk**
```python
parser.parse_and_save(..., chunk_size=10)  # برای فایل‌های بزرگ
```

3. **Cache کردن نتایج**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def parse_cached(file_path):
    return parser.parse_file(file_path)
```

---

## 🤝 مشارکت

### اضافه کردن الگوی جدید:

```python
# در law_parser.py
self.patterns['new_pattern'] = [
    r'الگوی1',
    r'الگوی2'
]
```

### افزودن دستور CLI جدید:

```python
# در law_cli.py
def my_new_command(self, args):
    # کد شما
    pass

# در main():
subparsers.add_parser('mycommand', help='توضیح')
```

---

## 📚 منابع

- [راهنمای جمع‌آوری داده](DATA_COLLECTION_GUIDE.md)
- [مستندات اصلی](../README.md)
- [راهنمای API](../API_GUIDE.md)

---

## ❓ سوالات متداول

**س: چطور فایل‌های PDF را پارس کنم؟**

ج: ابتدا به TXT تبدیل کنید:
```bash
pdftotext -enc UTF-8 law.pdf law.txt
python law_cli.py parse law.txt ...
```

**س: آیا پارسر از زبان عربی پشتیبانی می‌کند؟**

ج: بله، پارسر از UTF-8 پشتیبانی می‌کند.

**س: چطور تگ‌های سفارشی اضافه کنم؟**

ج: در فایل TXT:
```
برچسب‌ها: #تگ1 #تگ2 #تگ3
```

**س: آیا می‌توان فرمت خروجی را تغییر داد؟**

ج: بله، با تغییر متد `save_to_json` یا استفاده از دستور `export`.

---

**نسخه**: 1.0.0  
**نگهدارنده**: تیم دادرس  
**مجوز**: Proprietary

